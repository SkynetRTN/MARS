"""M5 input-reuse characterization at a4d429a; wrong results are explicit.

The defect probes pin observed stateful behavior, not acceptance criteria for
a future repair. Controls use fresh inputs and actual SEP/Numba measurements.
"""
import copy

import numpy as np
import pytest
import sep
from astropy.io import fits

from algorithms.catalogs.schemas import CatalogSource
from algorithms.fieldcal.field_cal import perform_field_calibration
from algorithms.fieldcal.schemas import PhotometricCalibrationSettings
from algorithms.photometry.photometry import run_photometry
from algorithms.photometry.schemas import PhotometrySettings, SourceExtractionData, SourceExtractionSettings
from algorithms.photometry.source_extraction import run_source_extraction
from algorithms.skylib_lite.extraction.main import extract_sources
from algorithms.skylib_lite.photometry import aperture_photometry
from algorithms.wcs.config import SolverSettings
from algorithms.wcs.wcs import solve_wcs


def _saturated_field():
    yy, xx = np.indices((128, 128))
    image = 100 + np.random.default_rng(7).normal(0, 1, xx.shape)
    for center, amplitude in ((40, 1000), (80, 10000)):
        image += amplitude*np.exp(-((xx-center)**2 + (yy-center)**2)/18)
    return image


def test_wcs28_failed_solve_mutates_shared_saturation_settings(tmp_path):
    image = _saturated_field()
    header = fits.Header({"EXPTIME": 1})
    before_header = header.copy()
    settings = SourceExtractionSettings(
        sat_level=8000, threshold=5, min_pixels=9, centroid=False,
        bk_size=32, discard_saturated=1,
    )
    original = settings.model_copy(deep=True)
    before, _, _ = run_source_extraction(image, header, settings)
    assert len(before) == 1
    result = solve_wcs(
        header, image, tmp_path, extraction_settings=settings,
        solver_settings=SolverSettings(),
    )
    assert result.wcs is None
    assert result.metadata.n_field == 2
    assert header == before_header  # A miss itself does not rewrite the header.
    # Known wrong: astrometry's local saturation override escapes to the caller.
    assert settings.discard_saturated == 0
    assert original.discard_saturated == 1
    after, _, _ = run_source_extraction(image, header, settings)
    control, _, _ = run_source_extraction(image, header, original)
    assert np.count_nonzero(image >= 8000) == 13
    assert len(after) == 2
    # With discard disabled the wrapper no longer builds a saturation mask,
    # so the newly admitted saturated source also reports zero sat_pixels.
    assert [s.sat_pixels for s in after] == [0, 0]
    assert len(control) == 1 and control[0].sat_pixels == 0


@pytest.mark.parametrize("first_failure", ["nonpositive", "empty_annulus"])
def test_reusing_measurement_table_keeps_failure_flags_after_valid_measurement(first_failure):
    image = np.zeros((41, 41))
    image[20, 20] = 300
    source = np.array([(21., 21.)], dtype=[("x", float), ("y", float)])
    if first_failure == "nonpositive":
        failed = aperture_photometry(
            np.zeros_like(image), source, background=np.zeros_like(image),
            background_rms=np.ones_like(image), a=2, apcorr_tol=0,
        )
        expected_failure = sep.APER_NONPOSITIVE
    else:
        failed = aperture_photometry(
            image, source, a=2, a_in=30, a_out=35, apcorr_tol=0,
        )
        expected_failure = sep.APER_ALLMASKED | sep.APER_TRUNC
    assert failed["flag"][0] & expected_failure == expected_failure
    assert not np.isfinite(failed["mag"][0])
    kwargs = dict(background=np.zeros_like(image), background_rms=np.ones_like(image), a=2, apcorr_tol=0)
    recovered = aperture_photometry(image, failed, **kwargs)
    fresh = aperture_photometry(image, source.copy(), **kwargs)
    # Independent planted impulse: current counts/magnitudes are valid, while
    # the reused table alone still carries a rejecting flag from the old call.
    assert recovered["flux"][0] == fresh["flux"][0] == pytest.approx(300.)
    assert recovered["mag"][0] == fresh["mag"][0] == pytest.approx(-2.5*np.log10(300))
    assert fresh["flag"][0] == 0
    assert recovered["flag"][0] & expected_failure == expected_failure


def _adaptive_field():
    yy, xx = np.indices((128, 128))
    image = 100 + np.random.default_rng(10).normal(0, 1, xx.shape)
    image += 1000*np.exp(-.5*(((xx-35)/2)**2 + ((yy-40)/1.2)**2))
    image += 600*np.exp(-.5*(((xx-90)/3)**2 + ((yy-85)/1.4)**2))
    sources, background, rms = extract_sources(
        image, downsample=1, threshold=5, bkg_kw={"size": 32},
        fwhm=0, centroid=False, max_ellipticity=3,
    )
    assert len(sources) == 2
    return image, sources, background, rms


@pytest.mark.parametrize("reuse", ["input", "output"])
def test_adaptive_weight_feedback_changes_apertures_when_table_is_reused(reuse):
    image, sources, background, rms = _adaptive_field()
    original = sources.copy()
    kwargs = dict(background=background, background_rms=rms, k=2,
                  fix_aper=True, fix_ell=True, fix_rot=True, apcorr_tol=0)
    first = aperture_photometry(image, sources, **kwargs)
    snapshot = first.copy()
    second = aperture_photometry(image, sources if reuse == "input" else first, **kwargs)
    control = aperture_photometry(image, original.copy(), **kwargs)
    np.testing.assert_array_equal(control, snapshot)
    # Isophotal weights favored the wider star. The first measurement replaces
    # them with aperture flux, which now favors the narrower star on reuse.
    assert original["flux"][1] > original["flux"][0]
    assert snapshot["flux"][0] > snapshot["flux"][1]
    np.testing.assert_allclose(snapshot["aper_a"], 5.87879944, atol=1e-7)
    np.testing.assert_allclose(second["aper_a"], 3.94784188, atol=1e-7)
    np.testing.assert_allclose(second["mag"]-snapshot["mag"], [.13690663, .28314708], atol=1e-7)


def test_public_photometry_rebuilds_tables_and_is_repeatable_without_input_mutation():
    image, table, background, rms = _adaptive_field()
    original_image, original_background, original_rms = image.copy(), background.copy(), rms.copy()
    sources = [SourceExtractionData(
        x=row["x"], y=row["y"], fwhm_x=row["a"]*2.3548200450309493,
        fwhm_y=row["b"]*2.3548200450309493, theta=np.rad2deg(row["theta"]), flux=row["flux"],
    ) for row in table]
    before_sources = [s.model_dump() for s in sources]
    settings = PhotometrySettings(mode="auto", a=2, fix_aper=True, apcorr_tol=0)
    before_settings = settings.model_dump()
    header = fits.Header({"EXPTIME": 1})
    before_header = header.copy()
    first = run_photometry(image, header, sources, settings, background=background, background_rms=rms)
    second = run_photometry(image, header, sources, settings, background=background, background_rms=rms)
    assert [s.model_dump() for s in first] == [s.model_dump() for s in second]
    assert [s.model_dump() for s in sources] == before_sources
    assert settings.model_dump() == before_settings and header == before_header
    np.testing.assert_array_equal(image, original_image)
    np.testing.assert_array_equal(background, original_background)
    np.testing.assert_array_equal(rms, original_rms)


@pytest.mark.parametrize("as_mapping", [False, True])
def test_phot17_catalog_inputs_are_copied_and_only_calibration_header_is_output(as_mapping):
    sources = [CatalogSource(
        x=10+10*i, y=20, catalog_name="APASS", mag=12+i, mag_error=.02,
        ref_mag=15+i+[-.05, 0, .05][i], ref_mag_error=.03,
    ) for i in range(3)]
    if as_mapping:
        sources = [s.model_dump() for s in sources]
    before = copy.deepcopy(sources)
    header = fits.Header({"FILTER": "V", "EXPTIME": 1, "OBSERVER": "test"})
    settings = PhotometricCalibrationSettings(variable_check_tol=0)
    before_settings = settings.model_dump()
    kwargs = dict(catalog_sources=sources, field_cal_settings=settings, use_provided_photometry=True)
    first_zp, first = perform_field_calibration(header, np.zeros((40, 40)), **kwargs)
    after_first = header.copy()
    second_zp, second = perform_field_calibration(header, np.zeros((40, 40)), **kwargs)
    assert sources == before
    assert settings.model_dump() == before_settings
    assert first_zp == second_zp == pytest.approx(3.)
    assert [s.model_dump() for s in first.phot_results] == [s.model_dump() for s in second.phot_results]
    assert [s.id for s in first.phot_results] == ["fieldcal_source_1", "fieldcal_source_2", "fieldcal_source_3"]
    assert header == after_first and header["OBSERVER"] == "test"
    assert set(header)-{"FILTER", "EXPTIME", "OBSERVER"} == {"PHOT_M0", "PHOT_M0E", "PHOT_CAL"}
    # Header mutation is a documented output, and a later failed measurement
    # preserves it transactionally rather than claiming a new calibration.
    with pytest.raises(RuntimeError, match="No catalog sources could be photometered"):
        perform_field_calibration(
            header, np.zeros((40, 40)), catalog_sources=sources,
            field_cal_settings=settings,
            photometry_settings=PhotometrySettings(a=2, a_in_px=4, a_out_px=6),
        )
    assert header == after_first and sources == before
