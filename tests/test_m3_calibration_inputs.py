"""M3 malformed calibration inputs (``docs/working/master-continuation-plan.md``).

Mixed catalog row shapes and epochs, absent coordinates, missing FWHM in
adaptive apertures and degenerate zero-point header writes must neither escape
as exceptions nor advertise a usable calibration. Findings PHOT-04, PHOT-05,
PHOT-08 and PHOT-11 in ``docs/analysis/algorithm-remediation-plan.md``, plus
the integer row ids SkyMapper, SDSS, UCAC and PanSTARRS return live.

The frame is ``ngc5128_galaxy_b_001`` against the recorded APASS rows of the
``ngc5128_b_002`` solve; nothing here opens a socket.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from algorithms.fieldcal import field_cal
from algorithms.fieldcal.field_cal import DegenerateCalibrationError, perform_field_calibration
from algorithms.fieldcal.schemas import (
    CatalogSource,
    PhotometricCalibrationSettings,
    SourceExtractionData,
)
from algorithms.photometry.photometry import PhotometrySettings
from algorithms.photometry.schemas import SourceExtractionSettings
from algorithms.photometry.source_extraction import build_wcs_from_header
from tools.fieldcal_reference import replay_catalog_sources
from tools.optical import resolve_optical_frame
from tools.photometry import calibrate_zeropoint

FIELD = "ngc5128_b_002"

# The recorded rows carry float32 errors (and some tests integer ids) that the
# catalog serializer warns about on every model_dump; that noise is not under
# test here (see test_fieldcal_reference.py's float32_mag_errors).
pytestmark = pytest.mark.filterwarnings("ignore:Pydantic serializer warnings:UserWarning")


@pytest.fixture(scope="module")
def frame_path() -> Path:
    return Path(resolve_optical_frame("ngc5128_galaxy_b_001").path)


@pytest.fixture(scope="module")
def baseline(frame_path) -> float:
    result = calibrate_zeropoint(frame_path, catalog_sources=_rows(), compare_to=FIELD)
    assert result.errors == []
    return result.zero_point


def _rows(fixture: str = "full_response") -> list[CatalogSource]:
    return replay_catalog_sources(FIELD, fixture=fixture)


def _calibrate(frame_path, rows):
    return calibrate_zeropoint(frame_path, catalog_sources=rows, compare_to=FIELD)


def _direct(frame_path, rows, *, photometry_settings=None):
    with fits.open(frame_path) as hdul:
        header = hdul[0].header.copy()
        data = hdul[0].data.astype(float)
    outcome = perform_field_calibration(
        header,
        data,
        wcs=build_wcs_from_header(header),
        catalog_sources=rows,
        field_cal_settings=PhotometricCalibrationSettings(catalogs=["APASS"], variable_check_tol=0),
        photometry_settings=photometry_settings
        or PhotometrySettings(mode="aperture", a=5.0, a_in_px=8.0, a_out_px=12.0),
        extraction_settings=SourceExtractionSettings(),
    )
    return outcome, header


# --- mixed row shapes --------------------------------------------------------


@pytest.mark.parametrize("make_id", [np.int32, np.int64, np.uint64, int])
def test_integer_row_ids_from_live_providers_calibrate(frame_path, baseline, make_id):
    # VizieR/SkyServer rows reach the solve with the provider's integer id
    # type (SkyMapper int32, SDSS uint64, UCAC/PanSTARRS int64).
    rows = _rows()
    for index, row in enumerate(rows):
        row.id = make_id(1_000_000 + index)
    result = _calibrate(frame_path, rows)
    assert result.errors == []
    assert result.zero_point == pytest.approx(baseline, abs=1e-9)


def test_dict_and_model_rows_mix(frame_path, baseline):
    rows = _rows()
    mixed = [row.model_dump(exclude_unset=True) for row in rows[:60]] + rows[60:]
    result = _calibrate(frame_path, mixed)
    assert result.zero_point == pytest.approx(baseline, abs=1e-9)


# --- epochs (PHOT-04) ---------------------------------------------------------


def test_one_row_with_a_proper_motion_epoch_no_longer_aborts_the_solve(frame_path, baseline):
    rows = _rows()
    rows[0].pm_epoch = datetime(2000, 1, 1, 12)  # an epoch with no motion
    result = _calibrate(frame_path, rows)
    assert result.errors == []
    assert result.zero_point == pytest.approx(baseline, abs=1e-9)


def test_every_row_carrying_an_epoch_calibrates(frame_path, baseline):
    rows = _rows()
    for row in rows:
        row.pm_epoch, row.pm_sky, row.pm_pos_angle_sky = datetime(2016, 1, 1), 0.0, 0.0
    result = _calibrate(frame_path, rows)
    assert result.zero_point == pytest.approx(baseline, abs=1e-9)


def _detected(ra_hours, dec_degs):
    return SourceExtractionData(id="d1", x=10.0, y=10.0, ra_hours=ra_hours, dec_degs=dec_degs)


def _match(catalog_sources, detected, *, tol_arcsec=2.0):
    header = fits.Header({"DATE-OBS": "2026-01-01T00:00:00"})
    return field_cal._match_detected_sources(
        catalog_sources, detected, wcs=None, header=header,
        data=np.zeros((20, 20)), source_match_tol=tol_arcsec,
    )


def test_proper_motion_is_applied_to_the_frame_epoch():
    """A star 10" south at its 2016 epoch, moving 1"/yr north, is matched at
    the 2026 frame epoch; the same star without its motion is not."""
    ra_hours, dec = 12.0, 20.0
    epoch = datetime(2016, 1, 1)
    seconds = (datetime(2026, 1, 1) - epoch).total_seconds()
    moving = CatalogSource(
        id="c1", ra_hours=ra_hours, dec_degs=dec - 10 / 3600,
        pm_epoch=epoch, pm_sky=(10 / 3600) / seconds, pm_pos_angle_sky=0.0,
    )
    matched = _match([moving], [_detected(ra_hours, dec)])
    assert [source.id for source in matched] == ["c1"]

    still = moving.model_copy(update={"pm_sky": 0.0})
    with pytest.raises(RuntimeError, match="Could not match"):
        _match([still], [_detected(ra_hours, dec)])


# --- absent coordinates (PHOT-05) --------------------------------------------


def test_a_row_without_a_position_is_left_out_not_fatal(frame_path, baseline):
    rows = _rows()
    rows[0].ra_hours = rows[0].dec_degs = None
    rows[1].ra_hours = float("nan")
    result = _calibrate(frame_path, rows)
    assert result.errors == []
    assert math.isfinite(result.zero_point)


def test_rows_with_no_positions_at_all_fail_by_name(frame_path):
    rows = _rows()
    for row in rows:
        row.ra_hours = row.dec_degs = None
    result = _calibrate(frame_path, rows)
    (error,) = result.errors
    assert error.code == "field_calibration_failed"
    assert "position" in error.message
    assert result.zero_point is None


def test_matching_skips_positionless_rows_directly():
    ra_hours, dec = 12.0, 20.0
    rows = [
        CatalogSource(id="none"),
        CatalogSource(id="nan", ra_hours=float("nan"), dec_degs=dec),
        CatalogSource(id="good", ra_hours=ra_hours, dec_degs=dec),
    ]
    matched = _match(rows, [_detected(ra_hours, dec)])
    assert [source.id for source in matched] == ["good"]


# --- non-finite magnitudes ---------------------------------------------------


def test_non_finite_reference_magnitudes_are_dropped_before_the_solve(frame_path):
    rows = _rows("selected_rows")
    for row in rows[:3]:
        row.ref_mag = float("nan")
    rows[3].ref_mag = float("inf")
    result = _calibrate(frame_path, rows)
    assert result.errors == []
    assert math.isfinite(result.zero_point)


def test_a_non_finite_ref_mag_falls_back_to_the_rows_own_bands(frame_path):
    # NaN is treated as absent, so B is resolved from each row's catalog mags.
    rows = _rows("selected_rows")
    for row in rows:
        row.ref_mag = float("nan")
    result = _calibrate(frame_path, rows)
    assert result.errors == []
    assert math.isfinite(result.zero_point)


def test_only_non_finite_reference_magnitudes_fail_by_name(frame_path):
    rows = _rows("selected_rows")
    for row in rows:
        row.ref_mag = float("nan")
        row.mags = {"B": {"value": float("nan"), "error": 0.02}}
    result = _calibrate(frame_path, rows)
    assert [error.code for error in result.errors] == ["field_calibration_failed"]
    assert "catalog magnitudes" in result.errors[0].message


# --- degenerate solves and the header (PHOT-08) ------------------------------


def test_a_single_star_solve_is_not_reported_as_a_calibration(frame_path):
    result = _calibrate(frame_path, _rows("selected_rows")[:1])
    assert result.zero_point is None
    (error,) = result.errors
    assert error.code == "no_solution"
    assert "1 calibration star" in error.message


def test_a_degenerate_solve_writes_no_zero_point_keywords(frame_path):
    with pytest.raises(DegenerateCalibrationError, match="1 calibration star") as caught:
        _direct(frame_path, _rows("selected_rows")[:1])
    assert caught.value.num_stars == 1


def test_a_non_finite_zero_point_is_refused_before_the_header(frame_path, monkeypatch):
    monkeypatch.setattr(field_cal, "calc_solution",
                        lambda sources: (float("nan"), float("nan"), 0.0, float("nan"), 0.0))
    written = {}

    class Recording(fits.Header):
        def __setitem__(self, key, value):
            written[key] = value
            super().__setitem__(key, value)

    with fits.open(frame_path) as hdul:
        header = Recording(hdul[0].header)
        data = hdul[0].data.astype(float)
    with pytest.raises(DegenerateCalibrationError, match="non-finite zero point"):
        perform_field_calibration(
            header, data, wcs=build_wcs_from_header(header),
            catalog_sources=_rows("selected_rows"),
            field_cal_settings=PhotometricCalibrationSettings(variable_check_tol=0),
            photometry_settings=PhotometrySettings(mode="aperture", a=5.0, a_in_px=8.0, a_out_px=12.0),
            extraction_settings=SourceExtractionSettings(),
        )
    assert not {"PHOT_M0", "PHOT_M0E", "PHOT_CAL"} & set(written)


def test_a_usable_solve_still_writes_its_keywords(frame_path):
    (zero_point, result), header = _direct(frame_path, _rows("selected_rows"))
    assert header["PHOT_M0"] == pytest.approx(zero_point)
    assert header["PHOT_M0E"] == pytest.approx(result.zero_point_error_mag)
    assert header["PHOT_CAL"] == "APASS"


def test_the_tool_never_reports_a_non_finite_zero_point(frame_path, monkeypatch):
    # Defence in depth at the tool boundary, behind the algorithm's own guard.
    monkeypatch.setattr(
        field_cal, "perform_field_calibration",
        lambda *args, **kwargs: (float("nan"), None),
    )
    result = _calibrate(frame_path, _rows("selected_rows"))
    assert result.zero_point is None
    assert [error.code for error in result.errors] == ["no_solution"]


# --- adaptive apertures (PHOT-11) --------------------------------------------


def test_adaptive_apertures_get_the_detected_fwhm(frame_path):
    (zero_point, result), _header = _direct(
        frame_path, _rows("selected_rows"), photometry_settings=PhotometrySettings(mode="auto"),
    )
    assert math.isfinite(zero_point)
    assert result.zero_point_error_mag > 0
    assert len(result.phot_results) > 10


def test_adaptive_apertures_without_any_fwhm_fail_by_name(frame_path, monkeypatch):
    original = field_cal.run_source_extraction

    def no_fwhm(*args, **kwargs):
        sources, background, rms = original(*args, **kwargs)
        return [s.model_copy(update={"fwhm_x": None, "fwhm_y": None}) for s in sources], background, rms

    monkeypatch.setattr(field_cal, "run_source_extraction", no_fwhm)
    with pytest.raises(ValueError, match="Centroiding radius must be provided"):
        _direct(frame_path, _rows("selected_rows"), photometry_settings=PhotometrySettings(mode="auto"))
