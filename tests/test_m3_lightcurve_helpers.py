"""M3 direct light-curve helpers (``docs/working/master-continuation-plan.md``).

Supported helper calls need defined results for: missing errors in variable
folds (TS-04), all-null dates (TS-31), constant weighted spectra (TS-17),
empty or non-finite peak selection (TS-16), and singleton or tied legacy
histograms (TS-18, TS-28). The registered tools already guarded several of
these; the helpers themselves did not.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from algorithms.hrdiagram_py import legacy
from algorithms.pulsar.periodogram import find_global_max
from algorithms.variable_star.folding import fold_with_error
from algorithms.variable_star.lightcurve import VariableDataRow as Row
from algorithms.variable_star.lightcurve import jd_range, with_error_mse
from algorithms.variable_star.periodogram import lomb_scargle_with_error, variable_periodogram
from tools.pulsar import _top_peaks


def _rows(missing: set[int] = frozenset()) -> list[Row]:
    rows = with_error_mse([
        Row(1.0 + 0.3 * index, 10.0 + 0.1 * index, 11.0, 0.1, 0.1, None) for index in range(5)
    ])
    return [Row(r.jd, r.source1, r.source2, r.error1, r.error2, None if i in missing else r.error_mse)
            for i, r in enumerate(rows)]


# --- TS-04: missing errors no longer misalign or abort variable folds ---------


@pytest.mark.parametrize("missing", [{0}, {2}, {4}, {1, 3}])
def test_a_fold_with_missing_errors_keeps_every_point_with_its_own_bounds(missing):
    complete_data, complete_errors = fold_with_error(_rows(), "source1", 12.0, period=0.5, display_periods=1)
    data, errors = fold_with_error(_rows(missing), "source1", 12.0, period=0.5, display_periods=1)

    assert data == complete_data
    assert len(errors) == len(data)
    by_phase = dict(((x, magnitude), (low, high))
                    for (x, magnitude), (_, low, high) in zip(complete_data, complete_errors))
    absent = {round(1.0 + 0.3 * index, 9) for index in missing}
    for (x, magnitude), (error_x, low, high), row_jd in zip(data, errors, _jds(data, missing)):
        assert error_x == x
        if row_jd in absent:
            assert (low, high) == (None, None)
        else:
            assert (low, high) == by_phase[(x, magnitude)]
            assert low < magnitude < high


def _jds(data, missing):
    # Recover each folded point's source JD from its magnitude (unique here).
    jd_by_magnitude = {round(10.0 + 0.1 * index + 1.0, 9): round(1.0 + 0.3 * index, 9) for index in range(5)}
    return [jd_by_magnitude[round(magnitude, 9)] for _, magnitude in data]


def test_error_bars_follow_their_own_row_when_jds_tie():
    # Upstream sorted values and bounds separately; with equal JDs a
    # larger-error row could sort ahead and take the other row's bounds.
    rows = [
        Row(1.0, 10.0, 11.0, 0.1, 0.1, 0.5),   # magnitude 11.0, bounds from 10.5
        Row(1.0, 9.9, 11.0, 0.1, 0.1, 0.01),   # magnitude 10.9, bounds from 10.89
        Row(2.0, 10.1, 11.0, 0.1, 0.1, 0.05),
    ]
    data, errors = fold_with_error(rows, "source1", 12.0, period=0.7, display_periods=1)
    for (_, magnitude), (_, low, high) in zip(data, errors):
        assert low < magnitude < high


def test_display_periods_two_duplicates_bounds_with_their_points():
    data, errors = fold_with_error(_rows({2}), "source1", 12.0, period=0.5, display_periods=2)
    assert len(data) == len(errors) == 10
    assert [x for x, _ in data] == [x for x, _, _ in errors]
    assert sum(low is None for _, low, _ in errors) == 2


@pytest.mark.parametrize("rows", [[], [Row(None, 10.0, 11.0, 0.1, 0.1, 0.07)],
                                  [Row(1.0, 10.0, None, 0.1, None, None)]])
def test_a_fold_with_nothing_to_fold_is_empty(rows):
    assert fold_with_error(rows, "source1", 12.0, period=0.5) == ([], [])


# --- TS-31: all-null dates ----------------------------------------------------


@pytest.mark.parametrize("rows", [[], [Row(None, 1.0, 1.0, 0.1, 0.1, 0.07)] * 3])
def test_jd_range_without_any_date_is_no_baseline(rows):
    assert jd_range(rows) == 0.0


def test_a_default_period_fold_without_dates_is_empty():
    assert fold_with_error([Row(None, 10.0, 11.0, 0.1, 0.1, 0.07)], "source1", 12.0) == ([], [])


def test_jd_range_is_unchanged_for_dated_rows():
    assert jd_range([Row(1.0, None, None, None, None, None), Row(None, 1, 1, 1, 1, 1),
                     Row(3.123456, None, None, None, None, None)]) == 2.1235


# --- TS-17: constant weighted spectra -----------------------------------------


@pytest.mark.parametrize("values", [[5.0] * 4, [11.0] * 4])
def test_a_constant_weighted_series_is_rejected_not_nan(values):
    with pytest.raises(ValueError, match="constant"):
        lomb_scargle_with_error([1.0, 2.0, 3.0, 4.0], values, [0.1, 0.2, 0.1, 0.3], 0.5, 2.0, 5)


def test_a_constant_differential_light_curve_is_rejected_by_the_periodogram():
    # This one produced inf rather than NaN: the weighted mean's rounding left
    # tiny nonzero residues over an exactly zero variance.
    rows = [Row(float(index), 10.0, 11.0, 0.1, 0.1, 0.07) for index in range(5)]
    with pytest.raises(ValueError, match="constant"):
        variable_periodogram(rows, "source1", 12.0, 0.5, 2.0)


def test_an_ordinary_weighted_spectrum_is_unchanged():
    samples = lomb_scargle_with_error(
        [0.0, 1.0, 2.0, 3.0], [1.0, 2.0, 1.0, 0.0], [0.1, 0.2, 0.1, 0.3], 0.1, 1.0, 4
    )
    assert samples[0] == pytest.approx((0.10000000000000002, 0.0024349304797532984))
    assert all(math.isfinite(power) for _, power in samples)


# --- TS-16: peak selection ----------------------------------------------------


def test_global_max_of_nothing_is_none():
    assert find_global_max(np.array([]), np.array([])) == (None, None)


@pytest.mark.parametrize("power, expected", [
    ([np.nan, 0.5, 0.9], (3.0, 0.9)),       # a NaN first no longer poisons the result
    ([0.2, np.inf, 0.9], (3.0, 0.9)),       # nor an infinity in the middle
    ([0.9, np.nan, 0.9], (1.0, 0.9)),       # ties still keep the earliest
])
def test_global_max_ignores_non_finite_power(power, expected):
    assert find_global_max(np.array([1.0, 2.0, 3.0]), np.array(power)) == expected


def test_global_max_of_only_non_finite_power_is_none():
    assert find_global_max(np.array([1.0, 2.0]), np.array([np.nan, np.inf])) == (None, None)


def test_global_max_rejects_mismatched_arrays():
    with pytest.raises(ValueError, match="same length"):
        find_global_max(np.array([1.0, 2.0]), np.array([]))


def test_top_peaks_skip_non_finite_power():
    peaks = _top_peaks(np.array([1.0, 2.0, 3.0]), np.array([0.2, np.nan, 0.9]), 3, 0.02)
    assert peaks == [{"x": 3.0, "power": 0.9}, {"x": 1.0, "power": 0.2}]


def test_top_peaks_of_nothing_are_empty():
    assert _top_peaks(np.array([]), np.array([]), 5, 0.02) == []
    assert _top_peaks(np.array([1.0]), np.array([np.nan]), 5, 0.02) == []


# --- TS-18 / TS-28: legacy histograms -----------------------------------------


@pytest.mark.parametrize("data", [[2.0], [1.0, 1.0, 1.0]])
def test_default_bin_of_a_single_value_is_one_bin(data):
    assert legacy.get_default_bin(data) == 1


def test_default_bin_with_tied_quartiles_falls_back_to_sturges():
    # Freedman-Diaconis divides by the IQR, which is zero here; Sturges'
    # ceil(log2 n) + 1 needs none.
    data = [1.0] * 6 + [5.0]
    assert legacy.get_default_bin(data) == math.ceil(math.log2(len(data))) + 1


def test_default_bin_is_unchanged_for_ordinary_data():
    assert legacy.get_default_bin([0.1 * i for i in range(50)]) == 4
    assert legacy.get_default_bin([]) == 10


def test_histogram_extremes_of_one_value_are_that_value():
    assert legacy.get_histogram_extremes([3.0], [3.0]) == {"min": 3.0, "max": 3.0}


def test_histogram_extremes_of_no_data_are_the_empty_sentinel():
    assert legacy.get_histogram_extremes([], [3.0]) == {"min": -999, "max": 999}


@pytest.mark.parametrize("n", [2, 3, 10, 100, 161, 1000])
def test_histogram_extremes_are_unchanged_from_two_points_up(n):
    data = list(range(n))
    expected = {"min": data[math.ceil(n * (0.5 - 0.9876 / 2))],
                "max": data[math.floor(n * (0.5 + 0.9876 / 2))]}
    assert legacy.get_histogram_extremes(data, [1]) == expected


# --- the registered fold tool -------------------------------------------------


def test_the_fold_tool_masks_bounds_for_a_row_without_a_combined_error(artifact_dir):
    from astropy.table import Table

    from tools.variable_star import (
        fold_variable_star_lightcurve,
        load_variable_star_lightcurve,
        resolve_variable_star_fixture,
    )

    lightcurve = load_variable_star_lightcurve(resolve_variable_star_fixture("two_source_parity").path)
    table = Table.read(lightcurve.artifact.path, format="ascii.ecsv")
    table["error_mse"] = Table.MaskedColumn(table["error_mse"], mask=[False, True, False, False])
    table.write(lightcurve.artifact.path, format="ascii.ecsv", overwrite=True)

    folded = fold_variable_star_lightcurve(
        lightcurve.artifact.path, variable_star="source1", reference_star_magnitude=12.0, period=0.4,
    )
    assert folded.errors == []  # was invalid_input: "list index out of range"
    assert folded.rows_folded == 8
    assert [warning.code for warning in folded.warnings] == ["unbounded_points_folded"]
    assert "2 folded points" in folded.warnings[0].message

    stage3 = Table.read(folded.artifact.path, format="ascii.ecsv")
    masked = list(stage3["error_low"].mask)
    assert masked == list(stage3["error_high"].mask)
    assert sum(masked) == 2
    for magnitude, low, high, is_masked in zip(stage3["magnitude"], stage3["error_low"],
                                               stage3["error_high"], masked):
        if not is_masked:
            assert low < magnitude < high
