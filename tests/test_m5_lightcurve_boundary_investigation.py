"""M5 period-grid and variable-fold evidence at 7375f82.

Characterization cases explicitly pin retained helper/endpoint behavior. They
are not acceptance tests for future fixes. Working controls run real public
artifacts and the current numerical drivers; no production functions mocked.
"""
import csv
import numpy as np
import pytest
from astropy.table import Table

from algorithms.pulsar import sampling
from algorithms.pulsar.periodogram import compute_periodogram, nyquist_periodogram_range
from algorithms.variable_star.folding import fold_with_error, get_period_step
from algorithms.variable_star.lightcurve import VariableDataRow
from tools.variable_star import (
    compute_variable_star_periodogram,
    fold_variable_star_lightcurve,
    load_variable_star_lightcurve,
)


@pytest.mark.parametrize("period,baseline,unrounded,actual", [
    (1., 1000., 1e-5, 1e-5),
    (.1, 5., 2e-5, 0.),
    (.2, 10., 4e-5, 0.),
    (1., 100., 1e-4, 1e-4),
])
def test_characterization_slider_rounding_can_erase_a_positive_period_step(period, baseline, unrounded, actual):
    assert period**2*.01/baseline == pytest.approx(unrounded, rel=1e-14)
    assert get_period_step(period, baseline) == actual
    if actual == 0:
        assert unrounded > 1e-5  # It passed the intended minimum-step branch.


def _public_lightcurve(tmp_path, times, magnitudes):
    path = tmp_path / "boundary.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "mjd", "mag", "mag_error"])
        for time, magnitude in zip(times, magnitudes, strict=True):
            writer.writerow(["target", 59000+time, magnitude, .03])
            writer.writerow(["reference", 59000+time, 12., .04])
    loaded = load_variable_star_lightcurve(path)
    assert not loaded.errors and loaded.artifact is not None
    return loaded


def test_public_periodogram_advances_despite_zero_legacy_slider_step(artifact_dir, tmp_path):
    times = np.array([0, .03, .07, .12, .2, .29, .43, .7, 1, 1.4, 2.1, 3.2, 4.1, 5])
    magnitudes = 14 + .2*np.sin(2*np.pi*times/.1)
    loaded = _public_lightcurve(tmp_path, times, magnitudes)
    assert get_period_step(.1, 5) == 0  # That helper is not the computation grid.
    result = compute_variable_star_periodogram(
        loaded.artifact.path, variable_star="source1", reference_star_magnitude=12,
        start_period=.09, end_period=.11,
    )
    assert not result.errors and result.artifact is not None
    spectrum = Table.read(result.artifact.path, format="ascii.ecsv")
    periods, power = np.asarray(spectrum["period"]), np.asarray(spectrum["power"])
    assert 2000 <= len(periods) <= 2001  # Retained accumulating-grid endpoint.
    assert np.isfinite(periods).all() and np.all(np.diff(periods) > 0)
    assert np.isfinite(power).all() and np.all((power >= 0) & (power <= 1))
    assert periods[0] == pytest.approx(.09)
    assert periods[-1] <= .11*(1+1e-12)
    assert periods[np.argmax(power)] == pytest.approx(.1, abs=1e-5)
    assert np.max(power) > .99
    assert spectrum["period"].unit == "d" and result.period_unit == "d"


def test_characterization_variable_exact_multiples_keep_the_right_endpoint():
    times = np.array([0., np.nextafter(1., 0.), 1., np.nextafter(1., 2.), 2.])
    rows = [VariableDataRow(time, 10+i, 8., .03, .04, .05) for i, time in enumerate(times)]
    data, bounds = fold_with_error(rows, "source1", 8., period=1, display_periods=1)
    by_magnitude = {magnitude: phase for phase, magnitude in data}
    expected_closed = [0., times[1], 1., times[3]-1, 1.]
    np.testing.assert_array_equal([by_magnitude[10+i] for i in range(5)], expected_closed)
    canonical = np.remainder(times, 1.)
    np.testing.assert_array_equal(canonical[[0, 2, 4]], 0.)
    # This retained closed-end representation is periodically equivalent; the
    # variable path does not bin away those rows or shift their error bounds.
    assert len(data) == len(bounds) == len(rows)
    for (phase, magnitude), (bound_phase, low, high) in zip(data, bounds, strict=True):
        assert phase == bound_phase
        assert low == pytest.approx(magnitude-.05)
        assert high == pytest.approx(magnitude+.05)


@pytest.mark.parametrize("display_periods", [1, 2])
def test_public_variable_boundary_rows_and_day_units_are_preserved(artifact_dir, tmp_path, display_periods):
    loaded = _public_lightcurve(tmp_path, [0, 1, 2], [14, 15, 16])
    result = fold_variable_star_lightcurve(
        loaded.artifact.path, variable_star="source1", reference_star_magnitude=12,
        period=1, display_periods=display_periods,
    )
    assert not result.errors and not result.warnings and result.artifact is not None
    folded = Table.read(result.artifact.path, format="ascii.ecsv")
    assert len(folded) == result.rows_folded == 3*display_periods
    assert folded["phase"].unit == "d" and result.period_unit == "d"
    expected = {14: [0.], 15: [1.], 16: [1.]}
    for magnitude, first_phases in expected.items():
        phases = sorted(folded["phase"][folded["magnitude"] == magnitude])
        assert phases == first_phases + ([first_phases[0]+1] if display_periods == 2 else [])
    np.testing.assert_allclose(folded["error_low"], folded["magnitude"]-.05)
    np.testing.assert_allclose(folded["error_high"], folded["magnitude"]+.05)


def test_current_sampling_defaults_keep_sub_five_microsecond_spacing():
    times = np.arange(16)*1e-6
    with pytest.raises(ValueError, match="Nyquist interval"):
        nyquist_periodogram_range(times)
    current = sampling.summarize(times)
    assert current.uniform
    assert current.suggested_min_period_s == pytest.approx(2e-6)
    spectrum = compute_periodogram(times, np.sin(2*np.pi*np.arange(16)/5), steps=16)
    # The maintained driver computes positive defaults without the old rounding.
    assert spectrum.start == pytest.approx(2e-6)
    assert spectrum.stop == 3
    assert len(spectrum.power) > 0 and np.isfinite(spectrum.power).all()


def test_current_period_grid_rejects_unrepresentable_progress_before_computation():
    from algorithms.variable_star.periodogram import validate_periodogram_grid

    with pytest.raises(ValueError, match="representable"):
        validate_periodogram_grid(5e-324, 1e-323)
    # Ordinary neighboring periods must advance; this differs from a zero
    # slider step whose only remaining callers are direct helper consumers.
    assert validate_periodogram_grid(.09, .11) > 0
