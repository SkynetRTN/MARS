"""Regression checks for variance-normalized powers near their floating limit."""

from decimal import Decimal, FloatOperation, Inexact, ROUND_FLOOR, localcontext

import numpy as np
import pytest
from astropy.table import Table

from algorithms.pulsar import periodogram, significance
from tools import pulsar


@pytest.mark.parametrize("freq_mode", [False, True])
@pytest.mark.parametrize("value", [0.0, 0.1, -0.1, 1e300])
def test_public_constant_flux_cannot_publish_a_period_or_false_alarm_bound(
    tmp_path, artifact_dir, freq_mode, value,
):
    path = tmp_path / "constant.ecsv"
    Table({"time_s": np.arange(20) * 0.01, "source1": np.full(20, value)},
          meta={"flavour": "standard"}).write(path, format="ascii.ecsv")
    existing_files = set(artifact_dir.rglob("*"))

    result = pulsar.compute_pulsar_periodogram(
        path, start=1.0, stop=1.01, steps=1, freq_mode=freq_mode,
    )

    assert [error.code for error in result.errors] == ["invalid_input"]
    assert result.artifact is None
    assert result.peak_period_s is None
    assert result.peak_power is None
    assert result.false_alarm_probability_upper_bound is None
    assert result.false_alarm_thresholds == {}
    assert set(artifact_dir.rglob("*")) == existing_files


@pytest.mark.parametrize("freq_mode", [False, True])
@pytest.mark.parametrize("algorithm", [periodogram.lomb_scargle, periodogram.compute_periodogram],
                         ids=["powers", "driver"])
def test_direct_periodogram_rejects_fractional_constant_flux(algorithm, freq_mode):
    # np.var(full(20, 0.1)) is spuriously positive: exact equality of the
    # observations, rather than rounded mean/variance arithmetic, decides this.
    with pytest.raises(ValueError, match="constant"):
        algorithm(np.arange(20) * 0.01, np.full(20, 0.1),
                  start=1.0, stop=1.01, steps=1, freq_mode=freq_mode)


@pytest.mark.parametrize("freq_mode", [False, True])
def test_one_ulp_flux_variation_is_not_rejected_as_constant(tmp_path, artifact_dir, freq_mode):
    values = np.full(20, 0.1)
    values[::2] = np.nextafter(0.1, np.inf)
    path = tmp_path / "small-variation.ecsv"
    Table({"time_s": np.arange(20) * 0.01, "source1": values},
          meta={"flavour": "standard"}).write(path, format="ascii.ecsv")

    result = pulsar.compute_pulsar_periodogram(
        path, start=1.0, stop=1.01, steps=1, freq_mode=freq_mode,
    )

    assert result.errors == []
    assert result.artifact is not None
    assert result.peak_power is not None and np.isfinite(result.peak_power)


@pytest.mark.parametrize("freq_mode", [False, True])
@pytest.mark.parametrize("baseline", [0.1, -0.1, 1e-300, 1e300])
def test_one_ulp_variation_has_translation_invariant_power_and_tail(
    tmp_path, artifact_dir, freq_mode, baseline,
):
    times = np.arange(20) * 0.01
    values = np.full(20, baseline)
    values[10] = np.nextafter(baseline, np.inf)
    results = []
    for name, flux in [("absolute", values), ("offset", values - values[0])]:
        path = tmp_path / f"{name}.ecsv"
        Table({"time_s": times, "source1": flux}, meta={"flavour": "standard"}).write(
            path, format="ascii.ecsv",
        )
        result = pulsar.compute_pulsar_periodogram(
            path, start=1.0, stop=1.001, steps=1, freq_mode=freq_mode,
        )
        assert result.errors == []
        # Independently fitted QR on the unit impulse minus its mean at 1 Hz.
        assert result.peak_power == pytest.approx(0.006722674417646273, rel=2e-12)
        assert result.peak_residual_fraction == pytest.approx(0.999327732558236, rel=2e-14)
        assert result.false_alarm_probability_upper_bound == pytest.approx(0.9943001114808298, rel=2e-13)
        assert result.false_alarm_resolution_limited is False
        saved = Table.read(result.artifact.path, format="ascii.ecsv")
        assert saved.meta["false_alarm_probability_upper_bound"] == result.false_alarm_probability_upper_bound
        results.append(result)
    assert results[0].peak_power == pytest.approx(results[1].peak_power, rel=2e-14)


def _quadrature(exponent):
    times = np.arange(4) * 0.25
    delta = 2.0**-exponent
    return times, np.array([delta, 1 - delta, delta, -1 - delta])


def _reference_tail(exponent):
    # Ideal 1-Hz quadrature: SSE=4*d*d, TSS=2+4*d*d, Beta(1, 1/2).
    # Decimal prevents the reference from losing the same complement as power.
    with localcontext() as context:
        context.prec = 70
        delta = Decimal(2) ** -exponent
        residual_fraction = 2 * delta * delta / (1 + 2 * delta * delta)
        return float(residual_fraction.sqrt()), float(residual_fraction)


@pytest.mark.parametrize("freq_mode", [False, True])
def test_public_bound_uses_resolvable_residual_even_when_power_rounds_to_maximum(
    tmp_path, artifact_dir, freq_mode,
):
    times, values = _quadrature(27)
    path = tmp_path / "near-perfect.ecsv"
    Table({"time_s": times, "source1": values}, meta={"flavour": "standard"}).write(
        path, format="ascii.ecsv",
    )
    result = pulsar.compute_pulsar_periodogram(
        path, start=1.0, stop=1.001, steps=1, freq_mode=freq_mode,
    )
    assert result.errors == []
    expected, residual_fraction = _reference_tail(27)
    assert result.peak_power == pytest.approx(2.0)
    assert result.false_alarm_probability_upper_bound == pytest.approx(expected, rel=1e-7, abs=0)
    payload = result.model_dump(mode="json")
    assert payload.get("peak_residual_fraction") == pytest.approx(residual_fraction, rel=2e-7, abs=0)
    assert payload.get("false_alarm_resolution_limited") is False
    saved = Table.read(result.artifact.path, format="ascii.ecsv")
    assert saved.meta["false_alarm_probability_upper_bound"] == payload["false_alarm_probability_upper_bound"]
    assert saved.meta["peak_residual_fraction"] == payload["peak_residual_fraction"]
    assert saved.meta["false_alarm_statistic"] == "residual_fraction"


@pytest.mark.parametrize("exponent", [10, 20, 27, 35])
def test_residual_tail_tracks_noise_below_the_power_complement_resolution(exponent):
    times, values = _quadrature(exponent)
    result = periodogram.compute_periodogram(
        times, values, start=1.0, stop=1.001, steps=1, freq_mode=True,
    )
    expected, _ = _reference_tail(exponent)
    assert result.false_alarm_probability_upper_bound == pytest.approx(expected, rel=1e-5, abs=0)


def test_unresolved_fit_reports_null_and_warns_in_result_and_plot(tmp_path, artifact_dir):
    path = tmp_path / "exact.ecsv"
    Table({"time_s": np.arange(4) * 0.25, "source1": [0.0, 1.0, 0.0, -1.0]}).write(
        path, format="ascii.ecsv",
    )
    result = pulsar.compute_pulsar_periodogram(path, start=1.0, stop=1.001, steps=1)
    assert result.errors == []
    assert result.false_alarm_probability_upper_bound is None
    assert result.model_dump(mode="json").get("false_alarm_resolution_limited") is True
    assert "false_alarm_resolution_limited" in [warning.code for warning in result.warnings]
    saved = Table.read(result.artifact.path, format="ascii.ecsv")
    assert "false_alarm_probability_upper_bound" not in saved.meta
    assert saved.meta["false_alarm_resolution_limited"] is True
    plot = pulsar.plot_pulsar(result.artifact.path)
    assert plot.errors == []
    assert "false_alarm_resolution_limited" in [warning.code for warning in plot.warnings]


def test_scalar_maximum_power_does_not_invent_a_tail():
    assert significance.upper_bound(2.0, 4, 1) is None


@pytest.mark.parametrize("alpha", [0.1, 0.01])
@pytest.mark.parametrize("count_type", [int, np.int32, np.int64])
def test_representable_threshold_rounds_toward_sufficient_power(alpha, count_type):
    value = significance.threshold(alpha, count_type(4), count_type(200_002))
    assert value is not None
    # Evaluate the inverse with high precision, independent of upper_bound.
    with localcontext() as context:
        context.prec = 70
        residual_fraction = (Decimal(2) - Decimal(value)) / 2
        probability = 200_002 * residual_fraction.sqrt()
        assert probability <= Decimal(alpha)


def test_unrepresentable_threshold_is_unavailable():
    assert significance.threshold(0.001, 4, 200_002) is None


@pytest.mark.parametrize("host_setting", ["inexact_trap", "float_trap", "exponent_range"])
def test_public_thresholds_are_independent_of_host_decimal_context(
    tmp_path, artifact_dir, host_setting,
):
    path = tmp_path / "host-context.ecsv"
    Table({
        "time_s": np.arange(32) * 0.1,
        "source1": np.random.default_rng(12).normal(size=32),
    }).write(path, format="ascii.ecsv")

    with localcontext() as context:
        context.prec = 3
        context.rounding = ROUND_FLOOR
        if host_setting == "inexact_trap":
            context.traps[Inexact] = True
        elif host_setting == "float_trap":
            context.traps[FloatOperation] = True
        else:
            context.Emin = -1
            context.Emax = 0
            context.clamp = 1
        context.clear_flags()
        before = context.copy()
        result = pulsar.compute_pulsar_periodogram(
            path, start=1.0, stop=1.001, steps=1,
        )
        assert dict(context.flags) == dict(before.flags)
        assert dict(context.traps) == dict(before.traps)
        for name in ("prec", "rounding", "Emin", "Emax", "clamp"):
            assert getattr(context, name) == getattr(before, name)

    assert result.errors == []
    assert result.artifact is not None
    assert result.evaluated_trials == 1
    # Independent SciPy Beta(1, 14.5) inverse, scaled by N/2 = 16.
    assert result.false_alarm_thresholds == pytest.approx({
        "0.1": 2.3493143613235064,
        "0.01": 4.353673849626958,
        "0.001": 6.0637289297350145,
    }, rel=1e-13)


@pytest.mark.parametrize("has_residual_statistic", [False, True])
def test_old_gaussian_artifact_does_not_advertise_pre_fix_thresholds_as_current(
    tmp_path, artifact_dir, has_residual_statistic,
):
    path = tmp_path / "old-gaussian.ecsv"
    metadata = {
        "channel": "sum", "false_alarm_method": "gaussian_bonferroni",
        "false_alarm_probability_upper_bound": 2.2250738585072014e-308,
        "false_alarm_thresholds": {"0.1": 1.99, "0.01": 1.9999, "0.001": 2.0},
    }
    if has_residual_statistic:
        metadata["false_alarm_statistic"] = "residual_fraction"
    Table({"period_s": [0.9, 1.0, 1.1], "power": [1.0, 2.0, 1.0]}, meta=metadata).write(
        path, format="ascii.ecsv",
    )
    result = pulsar.plot_pulsar(path)
    assert result.errors == []
    assert "legacy_confidence_uncalibrated" in [warning.code for warning in result.warnings]
    assert not any("Gaussian noise FAP" in name for name in result.series)
    assert len([name for name in result.series if "uncalibrated" in name]) == 3


def test_omitted_threshold_warns_even_with_a_resolved_peak_bound(tmp_path, artifact_dir):
    path = tmp_path / "short-grid.ecsv"
    Table({
        "time_s": np.arange(4) * 0.25,
        "source1": [0.2, 0.7, -0.2, -0.6],
    }).write(path, format="ascii.ecsv")
    result = pulsar.compute_pulsar_periodogram(
        path, start=1.0, stop=1.001, steps=100_000, freq_mode=True,
    )
    assert result.errors == []
    assert result.false_alarm_probability_upper_bound is not None
    assert set(result.false_alarm_thresholds) == {"0.1", "0.01"}
    assert result.false_alarm_resolution_limited is True
    assert "false_alarm_resolution_limited" in [warning.code for warning in result.warnings]
    plotted = pulsar.plot_pulsar(result.artifact.path)
    assert plotted.errors == []
    assert len([name for name in plotted.series if "Gaussian noise FAP" in name]) == 2
    assert "false_alarm_resolution_limited" in [warning.code for warning in plotted.warnings]
