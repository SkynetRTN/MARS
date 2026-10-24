"""Retained numerical behavior must carry its limitations to the caller."""

import numpy as np
import pytest
from astropy.io import fits


def test_nonpositive_flux_placeholder_is_reported_without_changing_legacy_values():
    from algorithms.diagnostics import collect_numerical_notices
    from algorithms.photometry.photometry import run_photometry
    from algorithms.photometry.schemas import PhotometrySettings, SourceExtractionData

    image = np.zeros((15, 15))
    with collect_numerical_notices() as notices:
        rows = run_photometry(image, fits.Header({"EXPTIME": 1}),
            [SourceExtractionData(x=8, y=8)], PhotometrySettings(a=2, apcorr_tol=0),
            background=image.copy(), background_rms=np.ones_like(image))
    assert len(rows) == 1
    assert rows[0].flux == 0 and rows[0].mag == 0
    assert "nonpositive_aperture_flux" in {notice.code for notice in notices}


def test_empty_annulus_is_reported_even_when_the_legacy_flux_is_finite():
    from algorithms.diagnostics import collect_numerical_notices
    from algorithms.photometry.photometry import run_photometry
    from algorithms.photometry.schemas import PhotometrySettings, SourceExtractionData

    with collect_numerical_notices() as notices:
        rows = run_photometry(np.full((20, 20), 10.), fits.Header({"EXPTIME": 1}),
            [SourceExtractionData(x=10, y=10)],
            PhotometrySettings(a=2, a_in_px=30, a_out_px=35, apcorr_tol=0))
    assert len(rows) == 1 and rows[0].flux > 0
    assert "empty_background_annulus" in {notice.code for notice in notices}


@pytest.mark.parametrize("provided_shape", [False, True])
def test_isophotal_origin_warning_follows_the_actual_adaptive_branch(provided_shape):
    from algorithms.diagnostics import collect_numerical_notices
    from algorithms.photometry.photometry import run_photometry
    from algorithms.photometry.schemas import PhotometrySettings, SourceExtractionData

    y, x = np.indices((41, 41))
    image = 1000 * np.exp(-((x-20)**2 + (y-20)**2)/8)
    source = SourceExtractionData(x=21, y=21, fwhm_x=4 if provided_shape else None,
        fwhm_y=4 if provided_shape else None, theta=0, flux=10000 if provided_shape else None)
    with collect_numerical_notices() as notices:
        rows = run_photometry(image, fits.Header({"EXPTIME": 1}), [source],
            PhotometrySettings(mode="auto", a=2.5, centroid_radius=3, apcorr_tol=0),
            background=np.zeros_like(image), background_rms=np.ones_like(image))
    assert rows
    assert ("isophotal_origin_approximation" in {notice.code for notice in notices}) != provided_shape


@pytest.mark.parametrize("downsample", [1, 2])
def test_downsampled_saturation_counting_is_disclosed_only_on_that_path(downsample, frame_image):
    from algorithms.diagnostics import collect_numerical_notices
    from algorithms.photometry.source_extraction import run_source_extraction
    from algorithms.photometry.schemas import SourceExtractionSettings

    data, header = frame_image("ngc5128_b")
    with collect_numerical_notices() as notices:
        rows, _, _ = run_source_extraction(data.copy(), header, SourceExtractionSettings(downsample=downsample))
    assert rows
    assert ("saturation_count_unreliable" in {notice.code for notice in notices}) == (downsample > 1)


def test_calibration_reports_near_flat_snr_extrapolation_and_its_actual_snr_cut(frame_path):
    from tools.photometry import calibrate_zeropoint

    result = calibrate_zeropoint(frame_path("ngc5128_b"), catalog_fixture="selected_rows",
                                 compare_to="ngc5128_b_002")
    assert result.errors == []
    assert {"limiting_magnitude_unvalidated", "magnitude_error_snr_cut"} <= {w.code for w in result.warnings}


def test_direct_limiting_magnitude_is_disclosed_on_nearly_flat_snr_inputs():
    from tools.calibration import solve_zeropoint_from_measurements

    rows = [{"mag": float(i), "ref_mag": i + 20 + (0.01 if i % 2 else -0.01), "mag_error": .03}
            for i in range(10, 16)]
    result = solve_zeropoint_from_measurements(rows, [])
    assert result.errors == []
    assert result.limmag5 is not None and abs(result.limmag5) > 100
    assert "limiting_magnitude_unvalidated" in {w.code for w in result.warnings}
    assert "magnitude_error_snr_cut" not in {w.code for w in result.warnings}


def test_landolt_u_error_limit_is_not_attached_to_unaffected_bands():
    from tools.catalogs import resolve_reference_band

    assert "retained_catalog_uncertainty" in {w.code for w in resolve_reference_band("Landolt", "U").warnings}
    assert "retained_catalog_uncertainty" not in {w.code for w in resolve_reference_band("Landolt", "V").warnings}


def test_angular_matching_discloses_its_retained_ra_seam_limit():
    from algorithms.diagnostics import collect_numerical_notices
    from algorithms.catalogs.schemas import CatalogSource
    from algorithms.fieldcal.field_cal import _match_detected_sources
    from algorithms.fieldcal.schemas import SourceExtractionData

    with collect_numerical_notices() as notices:
        with pytest.raises(RuntimeError, match="Could not match"):
            _match_detected_sources(
                [CatalogSource(id="c", ra_hours=.00001, dec_degs=0)],
                [SourceExtractionData(id="d", ra_hours=23.99999, dec_degs=0, x=5, y=5)],
                wcs=None, header=fits.Header(), data=np.zeros((10, 10)), source_match_tol=5)
    assert "ra_seam_matching_approximation" in {notice.code for notice in notices}


def test_instrumental_public_photometry_reports_aperture_correction_crowding(frame_path, tmp_path):
    from tools.photometry import run_photometry_on_target

    result = run_photometry_on_target(frame_path("ngc5128_b"), use_field_cal=False, output_dir=tmp_path)
    assert result.errors == []
    assert result.status == "ok"
    assert "aperture_correction_crowding" in {warning.code for warning in result.warnings}


def test_hr_detection_reports_its_real_aperture_warning(frame_path, tmp_path, monkeypatch):
    from tools import artifacts
    from tools.hr_diagram import extract_photometry_from_fits

    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path)
    result = extract_photometry_from_fits(str(frame_path("ngc5128_b")))
    assert result.errors == [] and result.count > 0
    assert "aperture_correction_crowding" in {warning.code for warning in result.warnings}


def test_a_degenerate_fit_keeps_numerical_notices_on_its_error_result():
    from tools.calibration import solve_zeropoint_from_measurements

    result = solve_zeropoint_from_measurements([{"mag": 14., "ref_mag": 16., "mag_error": .03}], [])
    assert "no_solution" in {error.code for error in result.errors}
    assert "limiting_magnitude_unvalidated" in {warning.code for warning in result.warnings}


def test_solver_failure_keeps_source_extraction_notices(frame_path, tmp_path, monkeypatch):
    from algorithms.diagnostics import note_numerical_issue
    from tools import wcs

    def configured(settings):
        settings.ANET_INDEX_PATH = str(tmp_path)
        return ["astrometry.net"], []

    def failing_solver(*args, **kwargs):
        note_numerical_issue("saturation_count_unreliable", "Downsampled saturation counts are unreliable.")
        raise RuntimeError("test native failure")

    monkeypatch.setattr(wcs, "_configured_backend_warnings", configured)
    monkeypatch.setattr(wcs, "_solve_wcs", failing_solver)
    result = wcs.solve_astrometry(frame_path("ngc5128_b"), force=True)
    assert "solver_failed" in {error.code for error in result.errors}
    assert "saturation_count_unreliable" in {warning.code for warning in result.warnings}


def test_direct_band_resolution_discloses_the_retained_landolt_u_uncertainty():
    from tools.calibration import solve_zeropoint_from_measurements

    result = solve_zeropoint_from_measurements(
        [{"id": str(i), "mag": 12.+i, "mag_error": .03, "filter": "U"} for i in range(3)],
        [{"id": str(i), "catalog_name": "Landolt", "mags": {
            "U": {"value": 14.+i+(0.01 if i % 2 else -.01), "error": .03}}} for i in range(3)])
    assert result.errors == []
    assert "retained_catalog_uncertainty" in {warning.code for warning in result.warnings}


@pytest.mark.parametrize("phase", ["compute", "plot"])
def test_public_photometry_keeps_prior_notices_when_a_later_phase_raises(phase, frame_path, tmp_path, monkeypatch):
    from algorithms.diagnostics import note_numerical_issue
    from tools import photometry
    from tools.mcp.surface import call_tool, result_is_error

    if phase == "compute":
        def fail(*args, **kwargs):
            note_numerical_issue("saturation_count_unreliable", "Retained saturation counting limit.")
            raise ValueError("test photometry failure")
        monkeypatch.setattr(photometry, "compute_photometry", fail)
        expected = "saturation_count_unreliable"
    else:
        def fail(*args, **kwargs):
            raise ValueError("test plot failure")
        monkeypatch.setattr(photometry, "plot_photometry", fail)
        expected = "aperture_correction_crowding"
    reply = call_tool("run_photometry_on_target", {
        "target": str(frame_path("ngc5128_b")), "use_field_cal": False, "output_dir": tmp_path})
    assert "tool_exception" in {error["code"] for error in reply["errors"]}
    assert expected in {warning["code"] for warning in reply["warnings"]}
    assert result_is_error(reply)


def test_hr_pipeline_keeps_detection_warnings_when_the_catalog_fails(frame_path, monkeypatch):
    from tools import hr_diagram

    def fail(*args, **kwargs):
        raise RuntimeError("test catalog outage")

    monkeypatch.setattr(hr_diagram, "_fetch_gaia_and_match", fail)
    result = hr_diagram.run_full_hr_pipeline(str(frame_path("ngc5128_b")), "test cluster")
    assert result.status == "error"
    assert "aperture_correction_crowding" in {warning.code for warning in result.warnings}


def test_supplied_reference_magnitudes_do_not_invent_a_landolt_transform():
    from tools.calibration import solve_zeropoint_from_measurements

    result = solve_zeropoint_from_measurements(
        [{"id": str(i), "mag": 12.+i, "mag_error": .03, "filter": "U",
          "ref_mag": 14.+i+(0.01 if i % 2 else -.01)} for i in range(3)],
        [{"id": str(i), "catalog_name": "Landolt", "mags": {
            "U": {"value": 14.+i, "error": .03}}} for i in range(3)])
    assert result.errors == []
    assert "retained_catalog_uncertainty" not in {warning.code for warning in result.warnings}
