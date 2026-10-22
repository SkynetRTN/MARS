"""Preserved variable-star grid/fold behavior and intentional M2 error correction."""

import math

import pytest

from algorithms.variable_star.folding import fold_with_error, get_period_step
from algorithms.variable_star.lightcurve import (
    VariableDataRow,
    differential_data,
    differential_errors,
    jd_range,
    merge_sources_by_mjd,
    with_error_mse,
)
from algorithms.variable_star.periodogram import lomb_scargle_with_error


def test_merge_sources_by_mjd_keeps_first_seen_sources_and_unpaired_rows() -> None:
    """Catches a merge that drops unmatched observations or changes source order."""
    rows = [
        {"id": "comparison", "mjd": "2.0", "mag": "12.5", "mag_error": "0.03"},
        {"id": "variable", "mjd": "1.0", "mag": "14.0", "mag_error": "0.02"},
        {"id": "comparison", "mjd": "4.0", "mag": "12.0", "mag_error": "0.03"},
        {"id": "variable", "mjd": "3.0", "mag": "14.5", "mag_error": "0.02"},
    ]

    assert merge_sources_by_mjd(rows) == [
        VariableDataRow(1.0, None, 14.0, None, 0.02, None),
        VariableDataRow(2.0, 12.5, None, 0.03, None, None),
        VariableDataRow(3.0, None, 14.5, None, 0.02, None),
        VariableDataRow(4.0, 12.0, None, 0.03, None, None),
    ]


def test_differential_light_curve_and_errors_preserve_the_source1_sign() -> None:
    """Catches a reversed subtraction or halved differential standard errors."""
    rows = with_error_mse(
        [
            VariableDataRow(10.0, 15.0, 12.0, 0.2, 0.4, None),
            VariableDataRow(11.0, 16.0, 12.5, 0.2, 0.4, None),
            VariableDataRow(12.0, 17.0, None, 0.2, None, None),
        ]
    )

    assert differential_data(rows, "source1", 12.5) == [(10.0, 15.5), (11.0, 16.0)]
    expected_errors = [
        (10.0, 15.0527864045, 15.9472135955),
        (11.0, 15.5527864045, 16.4472135955),
    ]
    for actual, expected in zip(
        differential_errors(rows, "source1", 12.5), expected_errors, strict=True
    ):
        assert actual == pytest.approx(expected)
    assert jd_range(rows) == 2.0


def test_fold_with_error_duplicates_then_descending_sorts_two_period_display() -> None:
    """Catches a fold that reorders points before the upstream display expansion."""
    rows = with_error_mse(
        [
            VariableDataRow(10.0, 15.0, 12.0, 0.2, 0.4, None),
            VariableDataRow(11.0, 16.0, 12.5, 0.2, 0.4, None),
        ]
    )

    data, errors = fold_with_error(rows, "source1", 12.5, period=0.75, phase=0.2)

    expected_data = [(1.15, 16.0), (0.9, 15.5), (0.4, 16.0), (0.15, 15.5)]
    expected_fold_errors = [
        (1.15, 15.5527864045, 16.4472135955),
        (0.9, 15.0527864045, 15.9472135955),
        (0.4, 15.5527864045, 16.4472135955),
        (0.15, 15.0527864045, 15.9472135955),
    ]
    for actual, expected in zip(data, expected_data, strict=True):
        assert actual == pytest.approx(expected)
    for actual, expected in zip(errors, expected_fold_errors, strict=True):
        assert actual == pytest.approx(expected)
    assert get_period_step(0.75, 2.0) == 0.0028


def test_weighted_lomb_scargle_matches_the_extracted_typescript_grid() -> None:
    """Retains the extracted period grid; corrected powers have separate references."""
    samples = lomb_scargle_with_error(
        [0.0, 1.0, 2.0, 3.0], [1.0, 2.0, 1.0, 0.0], [0.1, 0.2, 0.1, 0.3], 0.1, 1.0, 4
    )

    assert [period for period, _ in samples] == pytest.approx([
        0.10000000000000002, 0.1778279410038923, 0.316227766016838, 0.5623413251903492,
    ])
    assert all(math.isfinite(power) and 0 <= power <= 1 for _, power in samples)


def test_weighted_lomb_scargle_keeps_typescript_nan_for_a_constant_series() -> None:
    """Catches Python division errors replacing TypeScript's IEEE NaN output."""
    samples = lomb_scargle_with_error([0.0, 1.0], [3.0, 3.0], [0.1, 0.1], 0.1, 0.2, 1)

    assert len(samples) == 1
    assert math.isnan(samples[0][1])


def test_fold_with_error_keeps_the_upstream_missing_error_alignment_failure() -> None:
    """Catches silently repairing the documented separate-filter misalignment."""
    rows = [
        VariableDataRow(1.0, 14.0, 12.0, 0.1, 0.1, None),
        VariableDataRow(2.0, 14.1, 12.0, 0.1, 0.1, 0.070710678),
    ]

    with pytest.raises(IndexError):
        fold_with_error(rows, "source1", 12.0, period=0.5)


def test_fold_with_error_keeps_the_upstream_empty_data_failure() -> None:
    """Pins the extracted service's unguarded first-row access on empty input."""
    with pytest.raises(IndexError):
        fold_with_error([], "source1", 12.0, period=0.5)


def test_differential_errors_returns_no_rows_when_no_variable_star_is_selected() -> None:
    """Catches the port treating the upstream NONE option as source2."""
    rows = with_error_mse([VariableDataRow(1.0, 14.0, 12.0, 0.1, 0.1, None)])

    assert differential_errors(rows, "none", 12.0) == []
