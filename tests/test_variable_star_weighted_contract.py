"""TS-03: incomplete observations must not misalign weighted samples."""

from __future__ import annotations

import math

import pytest
from astropy.table import MaskedColumn, Table

from algorithms.variable_star.lightcurve import VariableDataRow
from algorithms.variable_star import periodogram
from algorithms.variable_star.periodogram import variable_periodogram
from tools import variable_star


def _paired_rows():
    return [VariableDataRow(float(i), value, 12., .1, .1, .070710678)
            for i, value in enumerate([14., 14.1, 13.9, 14.2])]


def _artifact(artifact_dir, rows, *, masked=False):
    path = artifact_dir / "weighted.ecsv"
    table = Table({
        name: [getattr(row, attr) for row in rows]
        for name, attr in [("mjd", "jd"), ("source1", "source1"), ("source2", "source2"),
                           ("error1", "error1"), ("error2", "error2"), ("error_mse", "error_mse")]
    })
    if masked:
        for name in table.colnames:
            values = list(table[name])
            table.replace_column(name, MaskedColumn(
                [0. if value is None else value for value in values],
                mask=[value is None for value in values], name=name,
            ))
    table.write(path, format="ascii.ecsv")
    return path


def test_direct_unpaired_rows_do_not_change_the_paired_weighted_spectrum():
    pairs = _paired_rows()
    unpaired = VariableDataRow(4., 14.5, None, .1, None, None)
    assert variable_periodogram(pairs + [unpaired], "source1", 12., .1, 1.) == variable_periodogram(
        pairs, "source1", 12., .1, 1.
    )


def test_missing_combined_error_is_an_explicit_direct_failure():
    rows = _paired_rows()
    rows[1] = VariableDataRow(1., 14.1, 12., .1, .1, None)
    with pytest.raises(ValueError, match="combined uncertainty"):
        variable_periodogram(rows, "source1", 12., .1, 1.)


@pytest.mark.parametrize("missing", ["source2", "jd"])
@pytest.mark.parametrize("masked", [False, True], ids=["object-null", "numeric-mask"])
def test_unpaired_artifact_rows_keep_their_missing_values(artifact_dir, missing, masked):
    pair = _paired_rows()[0]
    values = dict(vars(pair))
    values[missing] = None
    path = _artifact(artifact_dir, [pair, VariableDataRow(**values)], masked=masked)
    rows = variable_star._rows_from_artifact(variable_star._describe(path))
    assert getattr(rows[1], missing) is None


@pytest.mark.parametrize("masked", [False, True], ids=["object-null", "numeric-mask"])
def test_public_unpaired_handoff_preserves_spectrum_and_reports_omission(artifact_dir, masked):
    path = _artifact(
        artifact_dir, _paired_rows() + [VariableDataRow(4., 14.5, None, .1, None, None)], masked=masked,
    )
    result = variable_star.compute_variable_star_periodogram(
        path, variable_star="source1", reference_star_magnitude=12.
    )
    assert result.errors == []
    assert result.samples == 2001
    assert any(w.code == "unpaired_rows_skipped" and "1" in w.message for w in result.warnings)
    table = Table.read(result.artifact.path, format="ascii.ecsv")
    expected = variable_periodogram(_paired_rows(), "source1", 12., .1, 1.)
    assert list(table["period"]) == [x for x, _ in expected]
    assert list(table["power"]) == [y for _, y in expected]


@pytest.mark.parametrize("uncertainty", [None, 0., math.nan, math.inf])
def test_public_invalid_combined_errors_fail_without_an_artifact(artifact_dir, uncertainty):
    rows = _paired_rows()
    rows[1] = VariableDataRow(1., 14.1, 12., .1, .1, uncertainty)
    path = _artifact(artifact_dir, rows)
    result = variable_star.compute_variable_star_periodogram(
        path, variable_star="source1", reference_star_magnitude=12.
    )
    assert [e.code for e in result.errors] == ["invalid_input"]
    assert result.artifact is None


def test_public_constant_series_is_not_advertised_as_a_success(artifact_dir):
    rows = [VariableDataRow(float(i), 14., 12., .1, .1, .070710678) for i in range(3)]
    path = _artifact(artifact_dir, rows)
    result = variable_star.compute_variable_star_periodogram(
        path, variable_star="source1", reference_star_magnitude=12.
    )
    assert [e.code for e in result.errors] == ["invalid_input"]
    assert result.artifact is None


def test_public_all_unpaired_rows_are_a_structured_failure(artifact_dir):
    path = _artifact(artifact_dir, [VariableDataRow(0., 14., None, .1, None, None)])
    result = variable_star.compute_variable_star_periodogram(
        path, variable_star="source1", reference_star_magnitude=12.
    )
    assert [e.code for e in result.errors] == ["invalid_input"]
    assert result.artifact is None


def test_direct_driver_rejects_oversized_input_before_differential_allocation(monkeypatch):
    monkeypatch.setattr(periodogram, "MAX_PERIODOGRAM_SAMPLES", 1)

    def expensive(*args, **kwargs):
        pytest.fail("oversized input reached differential preparation")

    monkeypatch.setattr(periodogram, "differential_data", expensive)
    with pytest.raises(ValueError, match="sample"):
        variable_periodogram(_paired_rows(), "source1", 12., .1, 1.)


def test_public_work_limit_is_a_structured_failure(artifact_dir, monkeypatch):
    path = _artifact(artifact_dir, _paired_rows())
    monkeypatch.setattr(periodogram, "MAX_PERIODOGRAM_WORK", 1)
    result = variable_star.compute_variable_star_periodogram(
        path, variable_star="source1", reference_star_magnitude=12.
    )
    assert [e.code for e in result.errors] == ["invalid_input"]
    assert result.artifact is None


def test_ingested_partial_source_csv_reaches_weighted_stage(artifact_dir, tmp_path):
    path = tmp_path / "partial.csv"
    lines = ["id,mjd,mag,mag_error"]
    for row in _paired_rows():
        lines.extend([f"target,{row.jd},{row.source1},{row.error1}",
                      f"reference,{row.jd},{row.source2},{row.error2}"])
    lines.append("target,4,14.5,0.1")
    path.write_text("\n".join(lines) + "\n")
    lightcurve = variable_star.load_variable_star_lightcurve(path)
    assert lightcurve.errors == []
    assert lightcurve.rows_merged == 5
    result = variable_star.compute_variable_star_periodogram(
        lightcurve.artifact.path, variable_star="source1", reference_star_magnitude=12.
    )
    assert result.errors == []
    assert result.samples == 2001
    assert [w.code for w in result.warnings] == ["unpaired_rows_skipped"]


def test_masked_combined_error_is_missing_not_nan_and_cannot_shift_weights(artifact_dir):
    rows = _paired_rows()
    rows[1] = VariableDataRow(1., 14.1, 12., .1, .1, None)
    path = _artifact(artifact_dir, rows, masked=True)
    loaded = variable_star._rows_from_artifact(variable_star._describe(path))
    assert loaded[1].error_mse is None
    result = variable_star.compute_variable_star_periodogram(
        path, variable_star="source1", reference_star_magnitude=12.
    )
    assert [e.code for e in result.errors] == ["invalid_input"]
    assert "combined uncertainty" in result.errors[0].message
    assert result.artifact is None


def test_nonscalar_artifact_cells_are_a_structured_failure(artifact_dir):
    path = _artifact(artifact_dir, _paired_rows())
    table = Table.read(path, format="ascii.ecsv")
    table.replace_column("source1", [[14., 15.]] * 4)
    table.write(path, format="ascii.ecsv", overwrite=True)
    result = variable_star.compute_variable_star_periodogram(
        path, variable_star="source1", reference_star_magnitude=12.
    )
    assert [e.code for e in result.errors] == ["invalid_input"]
    assert result.artifact is None
