"""Native correctness regressions for M5 input and measurement-table reuse.

Controls use fresh inputs and actual SEP/Numba measurements.
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


def test_wcs28_saturation_override_is_local_to_failed_solve(tmp_path):
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
    # Including saturated stars for this solve must not affect later extraction.
    assert settings.model_dump() == original.model_dump()
    assert original.discard_saturated == 1
    after, _, _ = run_source_extraction(image, header, settings)
    control, _, _ = run_source_extraction(image, header, original)
    assert np.count_nonzero(image >= 8000) == 13
    assert len(after) == 1 and after[0].sat_pixels == 0
    assert len(control) == 1 and control[0].sat_pixels == 0


def test_wcs28_extraction_failure_preserves_caller_settings(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise RuntimeError("extraction failed")

    monkeypatch.setattr("algorithms.wcs.wcs.run_source_extraction", fail)
    settings = SourceExtractionSettings(discard_saturated=1)
    original = settings.model_dump()
    with pytest.raises(RuntimeError, match="extraction failed"):
        solve_wcs(fits.Header(), np.zeros((8, 8)), tmp_path,
                  extraction_settings=settings, solver_settings=SolverSettings())
    assert settings.model_dump() == original


@pytest.mark.parametrize("flag_dtype", [np.int8, np.uint8, np.int16, np.uint16, np.int64, np.uint64])
@pytest.mark.parametrize("first_failure", ["nonpositive", "empty_annulus", "masked"])
def test_valid_remeasurement_clears_aperture_flags_and_keeps_other_flags(first_failure, flag_dtype):
    image = np.zeros((41, 41))
    image[20, 20] = 300
    flag_info = np.iinfo(flag_dtype)
    high_bit = 1 << (flag_info.bits - (2 if flag_info.min < 0 else 1))
    retained_flags = int(sep.OBJ_MERGED) | int(sep.OBJ_TRUNC)
    if flag_info.bits > 8:
        retained_flags |= 0x100 | high_bit
    source = np.array([(21., 21., retained_flags)],
                      dtype=[("x", float), ("y", float), ("flag", flag_dtype)])
    if first_failure == "nonpositive":
        failed = aperture_photometry(
            np.zeros_like(image), source, background=np.zeros_like(image),
            background_rms=np.ones_like(image), a=2, apcorr_tol=0,
        )
        expected_failure = sep.APER_NONPOSITIVE
    elif first_failure == "empty_annulus":
        failed = aperture_photometry(
            image, source, a=2, a_in=30, a_out=35, apcorr_tol=0,
        )
        expected_failure = sep.APER_ALLMASKED | sep.APER_TRUNC
    else:
        failed = aperture_photometry(
            np.ma.array(image, mask=np.ones_like(image, dtype=bool)), source,
            background=np.zeros_like(image), background_rms=np.ones_like(image),
            a=2, apcorr_tol=0,
        )
        expected_failure = sep.APER_ALLMASKED | sep.APER_HASMASKED
    assert int(failed["flag"][0]) & int(expected_failure) == expected_failure
    assert not np.isfinite(failed["mag"][0])
    before_failed = failed.tobytes()
    kwargs = dict(background=np.zeros_like(image), background_rms=np.ones_like(image), a=2, apcorr_tol=0)
    recovered = aperture_photometry(image, failed, **kwargs)
    fresh = aperture_photometry(image, source.copy(), **kwargs)
    # The independent planted impulse has a valid current measurement.
    assert recovered["flux"][0] == fresh["flux"][0] == pytest.approx(300.)
    assert recovered["mag"][0] == fresh["mag"][0] == pytest.approx(-2.5*np.log10(300))
    assert recovered["flag"][0] == fresh["flag"][0] == retained_flags
    assert recovered["flag"].dtype == np.dtype(flag_dtype)
    assert failed.tobytes() == before_failed


def test_remeasurement_recomputes_current_mask_flags():
    image = np.zeros((41, 41))
    image[20, 20] = 300
    source = np.array([(21., 21., sep.OBJ_MERGED | 0x100 | 0xF0)],
                      dtype=[("x", float), ("y", float), ("flag", np.uint16)])
    mask = np.zeros_like(image, dtype=bool)
    mask[20, 21] = True
    result = aperture_photometry(
        np.ma.array(image, mask=mask), source,
        background=np.zeros_like(image), background_rms=np.ones_like(image),
        a=2, apcorr_tol=0,
    )
    assert np.isfinite(result["mag"][0])
    assert result["flag"][0] == sep.OBJ_MERGED | 0x100 | sep.APER_HASMASKED


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
def test_adaptive_table_reuse_retains_original_isophotal_weights(reuse):
    image, sources, background, rms = _adaptive_field()
    original = sources.copy()
    kwargs = dict(background=background, background_rms=rms, k=2,
                  fix_aper=True, fix_ell=True, fix_rot=True, apcorr_tol=0)
    first = aperture_photometry(image, sources, **kwargs)
    snapshot = first.copy()
    second = aperture_photometry(image, sources if reuse == "input" else first, **kwargs)
    control = aperture_photometry(image, original.copy(), **kwargs)
    np.testing.assert_array_equal(control, snapshot)
    # Isophotal weights favor the wider star, but measured aperture flux favors
    # the narrower star. Reusing a measured table must retain the former.
    assert original["flux"][1] > original["flux"][0]
    assert snapshot["flux"][0] > snapshot["flux"][1]
    np.testing.assert_allclose(snapshot["aper_a"], 5.87879944, atol=1e-7)
    np.testing.assert_array_equal(second, snapshot)
    np.testing.assert_array_equal(first, snapshot)
    np.testing.assert_array_equal(sources, original)
    np.testing.assert_array_equal(first["iso_flux"], original["flux"])


def test_raw_isophotal_weights_are_preserved_instead_of_sep_cflux():
    image = np.zeros((65, 65))
    image[20, 20], image[44, 44] = 300, 200
    sources = np.array([
        (21., 21., 2., 2., 0., 100., 1e5),
        (45., 45., 3., 3., 0., 200., 1.),
    ], dtype=[(name, float) for name in ("x", "y", "a", "b", "theta", "flux", "cflux")])
    kwargs = dict(background=np.zeros_like(image), background_rms=np.ones_like(image),
                  k=2, fix_aper=True, apcorr_tol=0)
    first = aperture_photometry(image, sources, **kwargs)
    # Input isophotal weights favor radius 6; cflux and aperture flux both favor
    # radius 4, so either mistaken substitution breaks this independent oracle.
    np.testing.assert_array_equal(first["aper_a"], [6., 6.])
    second = aperture_photometry(image, first, **kwargs)
    np.testing.assert_array_equal(second["aper_a"], [6., 6.])
    np.testing.assert_array_equal(first["flux"], [300., 200.])
    np.testing.assert_array_equal(first["iso_flux"], [100., 200.])
    np.testing.assert_array_equal(second, first)


@pytest.mark.parametrize("have_isophotal_data", [False, True])
def test_fixed_to_adaptive_reuse_matches_a_fresh_input(have_isophotal_data):
    image, sources, background, rms = _adaptive_field()
    if not have_isophotal_data:
        sources = sources[["x", "y"]].copy()
    original = sources.copy()
    fixed = aperture_photometry(
        image, sources, background=background, background_rms=rms,
        a=3, apcorr_tol=0,
    )
    before_fixed = fixed.tobytes()
    kwargs = dict(background=background, background_rms=rms, k=2,
                  fix_aper=True, fix_ell=True, fix_rot=True, apcorr_tol=0)
    reused = aperture_photometry(image, fixed, **kwargs)
    fresh = aperture_photometry(image, original, **kwargs)
    np.testing.assert_array_equal(reused["aper_a"], fresh["aper_a"])
    np.testing.assert_array_equal(reused["flux"], fresh["flux"])
    np.testing.assert_array_equal(reused["mag"], fresh["mag"])
    np.testing.assert_array_equal(reused["iso_flux"], fresh["iso_flux"])
    assert fixed.tobytes() == before_fixed


@pytest.mark.parametrize("readonly", [False, True])
@pytest.mark.parametrize("mode", ["fixed", "adaptive"])
def test_low_level_measurement_does_not_mutate_input_table(mode, readonly):
    image, sources, background, rms = _adaptive_field()
    original = sources.copy()
    sources.flags.writeable = not readonly
    kwargs = dict(background=background, background_rms=rms, apcorr_tol=0)
    if mode == "fixed":
        kwargs["a"] = 3
    else:
        kwargs.update(k=2, fix_aper=True)
    result = aperture_photometry(image, sources, **kwargs)
    np.testing.assert_array_equal(sources, original)
    assert not np.shares_memory(result, sources)
    assert sources.flags.writeable is not readonly


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
    assert len(first) == len(second) == 2
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
