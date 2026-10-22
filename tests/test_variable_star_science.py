"""M2: independent checks of weighted powers and differential uncertainties."""

import numpy as np
import pytest
from astropy.table import Table
from astropy.timeseries import LombScargle
from scipy.linalg import lstsq

from algorithms.variable_star import lightcurve, periodogram
from algorithms.variable_star.folding import fold_with_error
from tools import variable_star


def test_exact_sinusoid_has_unit_power_independent_of_sample_duplication():
    times = np.arange(8) / 8
    values = np.cos(2 * np.pi * times)
    for copies in (1, 2):
        samples = periodogram.lomb_scargle_with_error(
            np.tile(times, copies), np.tile(values, copies),
            np.full(8 * copies, 0.1), 1., 1.001, 1,
        )
        assert samples[0][1] == pytest.approx(1., abs=1e-13)


@pytest.mark.parametrize("pattern", ["regular", "gapped", "irregular"])
def test_heteroscedastic_powers_match_independent_floating_mean_reference(pattern):
    rng = np.random.default_rng(27042)
    times = np.arange(32) * 0.13
    if pattern == "gapped":
        times[16:] += 4
    elif pattern == "irregular":
        times = np.sort(rng.uniform(0, 12, 32))
    errors = rng.uniform(0.03, 0.5, len(times))
    values = 14 + np.sin(2 * np.pi * times / 0.71) + rng.normal(size=32) * errors
    samples = np.array(periodogram.lomb_scargle_with_error(times, values, errors, .3, 2., 60))
    expected = LombScargle(times, values, errors, fit_mean=True, normalization="standard").power(
        1 / samples[:, 0], method="slow",
    )
    np.testing.assert_allclose(samples[:, 1], expected, rtol=2e-10, atol=2e-12)
    assert np.all((samples[:, 1] >= 0) & (samples[:, 1] <= 1))


def test_weighted_power_is_invariant_to_units_offsets_and_row_order():
    times = np.array([0., .17, .4, .63, 1.1, 1.4])
    values = np.array([.2, 1.1, -.4, .3, -.7, .9])
    errors = np.array([.1, .4, .2, .1, .6, .3])
    expected = LombScargle(times, values, errors).power(1., method="slow")
    for scale, offset, epoch in [(1., 0., 0.), (100., 10., 59000.)]:
        samples = periodogram.lomb_scargle_with_error(
            (times + epoch)[::-1], (values * scale + offset)[::-1],
            (errors * scale)[::-1], 1., 1.001, 1,
        )
        assert samples[0][1] == pytest.approx(expected, rel=1e-10)


@pytest.mark.parametrize("period, expected", [(1., 0.), (.1, 0.), (.25, 1.)])
def test_rank_deficient_trials_do_not_fit_roundoff_columns(period, expected):
    times = np.arange(8) / 8 if period == .25 else np.arange(8.)
    values = np.cos(2 * np.pi * times / period) if period == .25 else np.arange(8.)
    result = periodogram.lomb_scargle_with_error(times, values, [.1] * 8, period, period + .001, 1)
    assert result[0][1] == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("errors, expected", [
    ((.3, .4), .5), ((3e200, 4e200), 5e200), ((3e-200, 4e-200), 5e-200),
])
def test_differential_uncertainty_is_quadrature_without_halving(errors, expected):
    assert lightcurve.error_mse(*errors) == pytest.approx(expected, rel=1e-15, abs=0)


@pytest.mark.parametrize("target", ["source1", "source2"])
def test_folded_error_bars_keep_the_full_differential_standard_uncertainty(target):
    rows = lightcurve.with_error_mse([
        lightcurve.VariableDataRow(1., 14., 12., .3, .4, None),
        lightcurve.VariableDataRow(1.2, 14.2, 12., .3, .4, None),
    ])
    data, errors = fold_with_error(rows, target, 12., period=.7)
    for (_, value), (_, low, high) in zip(data, errors, strict=True):
        assert value - low == pytest.approx(.5)
        assert high - value == pytest.approx(.5)


def _csv(tmp_path):
    path = tmp_path / "sources.csv"
    lines = ["id,mjd,mag,mag_error"]
    for index, value in enumerate([14., 14.2, 13.7, 14.1, 14.3, 13.8]):
        lines.extend([
            f"target,{59000 + index * .13},{value},0.3",
            f"comparison,{59000 + index * .13},12,0.4",
        ])
    path.write_text("\n".join(lines) + "\n")
    return path


def test_public_stages_expose_correct_powers_uncertainties_and_units(tmp_path, artifact_dir):
    loaded = variable_star.load_variable_star_lightcurve(_csv(tmp_path))
    assert loaded.errors == []
    table = Table.read(loaded.artifact.path, format="ascii.ecsv")
    np.testing.assert_allclose(table["error_mse"], .5)
    assert str(table["error_mse"].unit) == "mag"
    assert table.meta["uncertainty_method"] == "independent_quadrature"

    result = variable_star.compute_variable_star_periodogram(
        loaded.artifact.path, variable_star="source1", reference_star_magnitude=12.,
    )
    assert result.errors == []
    payload = result.model_dump(mode="json")
    assert payload.get("power_normalization") == "standard"
    assert payload.get("fit_mean") is True
    assert payload.get("period_unit") == "d"
    spectrum = Table.read(result.artifact.path, format="ascii.ecsv")
    assert str(spectrum["period"].unit) == "d"
    assert spectrum.meta["power_normalization"] == "standard"
    times = table["mjd"].value - table["mjd"][0]
    errors = table["error_mse"].value
    values = table["source1"].value
    centered = values - np.average(values, weights=1 / errors**2)
    expected = []
    # Independent full intercept/cos/sin QR fit. Astropy's analytic slow
    # formula loses precision near the grid point aliased with the cadence.
    for period in spectrum["period"]:
        angle = 2 * np.pi * times / period
        design = np.column_stack((np.ones(len(times)), np.cos(angle), np.sin(angle))) / errors[:, None]
        coefficients, *_ = lstsq(design, centered / errors, lapack_driver="gelsy")
        residual = centered / errors - design @ coefficients
        expected.append(1 - np.dot(residual, residual) / np.dot(centered / errors, centered / errors))
    np.testing.assert_allclose(spectrum["power"], expected, atol=2e-9)


def test_old_cached_uncertainties_are_rederived_when_publicly_folding(tmp_path, artifact_dir):
    loaded = variable_star.load_variable_star_lightcurve(_csv(tmp_path))
    table = Table.read(loaded.artifact.path, format="ascii.ecsv")
    table.meta.clear()
    table["error_mse"] = np.full(len(table), .25)  # Old artifacts used half quadrature.
    table.write(loaded.artifact.path, format="ascii.ecsv", overwrite=True)
    result = variable_star.fold_variable_star_lightcurve(
        loaded.artifact.path, variable_star="source1", reference_star_magnitude=12., period=.7,
    )
    assert result.errors == []
    folded = Table.read(result.artifact.path, format="ascii.ecsv")
    np.testing.assert_allclose(folded["error_high"] - folded["error_low"], 1.)
    assert folded.meta["uncertainty_method"] == "independent_quadrature"
    assert str(folded["error_low"].unit) == "mag"


def test_legacy_combined_error_without_components_is_not_silently_trusted(tmp_path, artifact_dir):
    loaded = variable_star.load_variable_star_lightcurve(_csv(tmp_path))
    table = Table.read(loaded.artifact.path, format="ascii.ecsv")
    table.meta.clear()
    table["error1"] = [None] * len(table)
    table.write(loaded.artifact.path, format="ascii.ecsv", overwrite=True)
    result = variable_star.compute_variable_star_periodogram(
        loaded.artifact.path, variable_star="source1", reference_star_magnitude=12.,
    )
    assert [error.code for error in result.errors] == ["invalid_input"]
    assert result.artifact is None


@pytest.mark.parametrize("value", [14., 1e308])
def test_exact_constants_have_no_resolved_variation_despite_weighted_mean_rounding(value):
    samples = periodogram.lomb_scargle_with_error(range(5), [value] * 5, [.3] * 5, .1, 1., 10)
    assert all(np.isnan(power) for _, power in samples)


def test_public_constant_with_roundoff_prone_errors_is_rejected(tmp_path, artifact_dir):
    path = tmp_path / "constant.csv"
    lines = ["id,mjd,mag,mag_error"]
    for index in range(5):
        lines.extend([f"target,{index},14,0.18", f"reference,{index},12,0.24"])
    path.write_text("\n".join(lines) + "\n")
    loaded = variable_star.load_variable_star_lightcurve(path)
    assert loaded.errors == []
    result = variable_star.compute_variable_star_periodogram(
        loaded.artifact.path, variable_star="source1", reference_star_magnitude=12.,
    )
    assert [error.code for error in result.errors] == ["invalid_input"]
    assert result.artifact is None


def test_public_combined_uncertainty_overflow_has_no_success_artifact(tmp_path, artifact_dir):
    path = tmp_path / "overflow.csv"
    path.write_text("id,mjd,mag,mag_error\ntarget,1,14,1.7e308\nreference,1,12,1.7e308\n")
    result = variable_star.load_variable_star_lightcurve(path)
    assert [error.code for error in result.errors] == ["invalid_input"]
    assert result.artifact is None


def test_public_fold_rejects_unrepresentable_full_error_bounds(artifact_dir):
    path = artifact_dir / "large-errors.ecsv"
    Table({
        "mjd": [1., 1.2], "source1": [1e308, 1e308], "source2": [0., 0.],
        "error1": [6e307, 6e307], "error2": [8e307, 8e307],
        "error_mse": [5e307, 5e307],
    }).write(path, format="ascii.ecsv")
    result = variable_star.fold_variable_star_lightcurve(
        path, variable_star="source1", reference_star_magnitude=0., period=.7,
    )
    assert [error.code for error in result.errors] == ["invalid_input"]
    assert result.artifact is None
