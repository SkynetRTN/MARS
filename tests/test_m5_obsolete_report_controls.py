"""PHOT-16's retired blank-CSV failures must stay explicit in public replay.

These verify maintained behavior, not a new calibration algorithm. Only the
failed operation is replaced; fixture loading, mapping and result construction
remain real. Returning a blank/success result from an exception branch, losing
captured warnings, or retaining a failed call's state would fail these controls.
"""

import json

import pytest
from astropy.io import fits

from algorithms.diagnostics import note_numerical_issue
from algorithms.fieldcal import field_cal
from tools import fieldcal_reference
from tools.registry import TOOL_FUNCTIONS


_FIELD = "ngc5128_b_002"


def _replay():
    return TOOL_FUNCTIONS["replay_field_calibration"](field=_FIELD)


def _assert_failure(result, code, message):
    assert result.solution is None and result.comparison is None
    assert result.matches == [] and result.num_matched == 0
    assert [(error.code, error.message) for error in result.errors] == [(code, message)]
    wire = json.loads(result.model_dump_json())
    assert wire["errors"] == [{"code": code, "message": message}]
    assert wire["solution"] is None


@pytest.mark.parametrize("failure", [
    PermissionError("frame cannot be read"), OSError("frame read failed"),
    ValueError("invalid frame header"),
])
def test_public_replay_frame_error_has_a_named_error_not_a_blank_cell(monkeypatch, failure):
    def failed_read(*args, **kwargs):
        raise failure

    monkeypatch.setattr(fits, "getheader", failed_read)
    _assert_failure(_replay(), "field_calibration_failed", str(failure))


def test_public_replay_without_wcs_has_a_named_error(monkeypatch):
    monkeypatch.setattr(fits, "getheader", lambda *args, **kwargs: fits.Header())
    _assert_failure(_replay(), "field_calibration_failed", "Missing WCS needed for calibration")


@pytest.mark.parametrize("failure,code", [
    (field_cal.DegenerateCalibrationError("no usable calibration stars", num_stars=0), "no_solution"),
    (RuntimeError("fit failed to converge"), "field_calibration_failed"),
    (ValueError("invalid calibration inputs"), "field_calibration_failed"),
])
def test_public_replay_solver_error_preserves_warnings_and_next_call_recovers(monkeypatch, failure, code):
    def failed_solve(*args, **kwargs):
        note_numerical_issue("limiting_magnitude_unvalidated", "diagnostic before solver failure")
        raise failure

    with monkeypatch.context() as scope:
        scope.setattr(field_cal, "perform_field_calibration", failed_solve)
        scope.setattr(fieldcal_reference, "replay_variable_sources", lambda *args, **kwargs: [])
        result = _replay()
        _assert_failure(result, code, str(failure))
        warnings = {warning.code: warning.message for warning in result.warnings}
        assert "variable_sources_not_recorded" in warnings
        assert warnings["limiting_magnitude_unvalidated"] == "diagnostic before solver failure"

    # The real next call redoes selection and fit; a preceding failure does not
    # poison a cache/global or copy its injected notice into the new result.
    recovered = _replay()
    assert recovered.errors == [] and recovered.solution.zero_point is not None
    assert recovered.num_matched == recovered.solution.source_count == 29
    assert "diagnostic before solver failure" not in {w.message for w in recovered.warnings}


@pytest.mark.parametrize("outcome", [None, (None, None)])
def test_public_replay_nonconvergence_has_a_named_error(monkeypatch, outcome):
    monkeypatch.setattr(field_cal, "perform_field_calibration", lambda *args, **kwargs: outcome)
    _assert_failure(_replay(), "no_solution", "field calibration did not converge")


def test_recorded_replay_does_not_run_pixel_photometry_or_centroiding(monkeypatch):
    def unexpected_pixel_measurement(*args, **kwargs):
        raise AssertionError("recorded magnitudes must not be remeasured")

    monkeypatch.setattr(field_cal, "run_photometry", unexpected_pixel_measurement)
    result = _replay()
    assert result.errors == [] and result.num_matched == 29
    assert result.comparison.delta_vs_skynet != 0
    assert result.selection_matches_recorded is False
