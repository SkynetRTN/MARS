"""Offline characterization of retained M5 position/geometry defects.

These tests deliberately PIN CURRENT WRONG BEHAVIOR; they are investigation
artifacts, not acceptance tests for a fix. The independent expectations use
weighted covariance, spherical haversine distance, or elementary aperture area.
All photometry/extraction calls use the actual SEP/Numba kernels; no mocks.
"""
from __future__ import annotations

import numpy as np
import pytest
import sep
from astropy.io import fits
from astropy.wcs import WCS

from algorithms.catalogs.schemas import CatalogSource
from algorithms.diagnostics import collect_numerical_notices
from algorithms.fieldcal.field_cal import _filter_variable_stars, _match_detected_sources
from algorithms.photometry.photometry import run_photometry
from algorithms.photometry.schemas import PhotometrySettings, SourceExtractionData, SourceExtractionSettings
from algorithms.photometry.source_extraction import get_source_xy, run_source_extraction
from algorithms.skylib_lite.extraction.main import extract_sources
from algorithms.skylib_lite.photometry.aperture import aperture_photometry, isophotal_analysis


@pytest.fixture
def saturated_pair():
    yy, xx = np.indices((128, 128))
    image = 100 + np.random.default_rng(7).normal(0, 1, xx.shape)
    for center, amplitude in ((40, 1000), (80, 10000)):
        image += amplitude * np.exp(-((xx-center)**2 + (yy-center)**2)/18)
    saturation = image >= 8000
    assert saturation.sum() == 13
    return image, saturation


def _extract(image, saturation, downsample, discard):
    return extract_sources(
        image, downsample=downsample, threshold=5,
        bkg_kw=dict(size=32, filter_size=3), fwhm=0, min_pixels=9,
        min_fwhm=0, max_fwhm=0, max_ellipticity=0, clean=0,
        centroid=False, sat_img=saturation, discard_saturated=discard,
    )[0]


@pytest.mark.parametrize("discard", [0, 1])
def test_characterize_downsampling_assigns_saturation_to_wrong_star(saturated_pair, discard):
    image, saturation = saturated_pair
    correct = _extract(image, saturation, 1, discard)
    with collect_numerical_notices() as notices:
        wrong = _extract(image, saturation, 2, discard)
    assert [n.code for n in notices] == ["saturation_count_unreliable"]
    if discard == 0:
        assert correct["saturated"].tolist() == [0, 13]
        # BUG: the healthy first star inherits 24; the saturated star gets zero.
        assert wrong["saturated"].tolist() == [24, 0]
    else:
        assert len(correct) == len(wrong) == 1
        assert correct[0]["x"] == pytest.approx(41, abs=.01)
        # BUG: discard removes the healthy star and retains the saturated one.
        assert wrong[0]["x"] == pytest.approx(80.5, abs=.01)
        assert wrong[0]["saturated"] == 0


@pytest.mark.parametrize("downsample, expected_x", [(1, 41), (2, 80.5)])
def test_characterize_python_api_discard_keeps_wrong_star(saturated_pair, downsample, expected_x):
    image, _ = saturated_pair
    with collect_numerical_notices() as notices:
        rows, _, _ = run_source_extraction(
            image, fits.Header({"EXPTIME": 1}),
            SourceExtractionSettings(downsample=downsample, sat_level=8000,
                threshold=5, min_pixels=9, centroid=False, bk_size=32,
                discard_saturated=1),
        )
    assert len(rows) == 1 and rows[0].sat_pixels == 0
    assert rows[0].x == pytest.approx(expected_x, abs=.01)
    assert bool(notices) == (downsample > 1)


def _weighted_moments(image, x, y, radius):
    yy, xx = np.indices(image.shape)
    selected = (xx-x)**2 + (yy-y)**2 <= radius**2
    values = image[selected]
    coordinates = np.stack((xx[selected], yy[selected]))
    flux = values.sum()
    center = (coordinates * values).sum(axis=1)/flux
    offsets = coordinates - center[:, None]
    covariance = (offsets * values) @ offsets.T/flux
    values, vectors = np.linalg.eigh(covariance)
    angle = np.arctan2(vectors[1, -1], vectors[0, -1])
    angle = (angle + np.pi/2) % np.pi - np.pi/2
    return np.sqrt(values[-1]), np.sqrt(values[0]), angle, flux, covariance


def _source_table(x, y, shape=None):
    rows = np.zeros(1, dtype=[(f, float) for f in ("x", "y", "a", "b", "theta", "flux")])
    rows["x"], rows["y"] = x, y
    if shape is not None:
        rows["a"], rows["b"], rows["theta"], rows["flux"] = shape
    return rows


def test_characterize_isophotal_origin_and_final_aperture_flux():
    yy, xx = np.indices((65, 65))
    image = 1000*np.exp(-((xx-31)**2 + (yy-31)**2)/18)
    correct = _weighted_moments(image, 31, 31, 5)
    shifted = _weighted_moments(image, 32, 32, 5)
    for coordinate, reference in ((31., correct), (32., shifted)):
        actual = isophotal_analysis(image, np.array([coordinate]), np.array([coordinate]), 5.)
        # Independent covariance confirms the width arithmetic on each disk.
        np.testing.assert_allclose([a[0] for a in actual[:2]], reference[:2], atol=1e-11)
        assert actual[3][0] == pytest.approx(reference[3], rel=1e-13)
    assert shifted[3]/correct[3] == pytest.approx(.9509593883839033, rel=1e-10)
    with collect_numerical_notices() as notices:
        wrong = aperture_photometry(image, _source_table(32, 32),
            background=np.zeros_like(image), background_rms=np.ones_like(image),
            k=2.5, radius=5, apcorr_tol=0)[0]
    assert [n.code for n in notices] == ["isophotal_origin_approximation"]
    # BUG: FITS coordinates are passed directly to the zero-based analysis.
    assert wrong["aper_a"] == pytest.approx(2.5*shifted[0], abs=1e-11)
    assert wrong["aper_b"] == pytest.approx(2.5*shifted[1], abs=1e-11)
    assert np.rad2deg(wrong["aper_theta"]) == pytest.approx(-45, abs=1e-8)
    good = aperture_photometry(image, _source_table(32, 32, correct[:4]),
        background=np.zeros_like(image), background_rms=np.ones_like(image),
        k=2.5, radius=5, apcorr_tol=0)[0]
    # Independent SEP exact circle sum for the symmetric covariance oracle.
    correct_radius = 2.5*np.sqrt(np.trace(correct[4])/2)
    sep_flux = sep.sum_circle(image, np.array([31.]), np.array([31.]), correct_radius, subpix=0)[0][0]
    # Allow the existing kernels' ~2.6e-9 relative numerical difference.
    assert good["flux"] == pytest.approx(sep_flux, rel=1e-8)
    assert good["flux"] == pytest.approx(46344.90836229487, abs=1e-7)
    assert wrong["flux"] == pytest.approx(45807.94676338208, abs=1e-7)
    assert wrong["mag"] - good["mag"] == pytest.approx(.0126530045300714, abs=1e-11)


def test_characterize_equal_diagonal_moments_lose_orientation():
    image = np.zeros((21, 21))
    for coordinate, value in ((8, 1), (9, 4), (10, 6), (11, 4), (12, 1)):
        image[coordinate, coordinate] = value
    image[9, 11] = image[11, 9] = 1
    reference = _weighted_moments(image, 10, 10, 5)
    np.testing.assert_allclose(reference[4], [[1, 7/9], [7/9, 1]], atol=1e-15)
    assert np.rad2deg(reference[2]) == pytest.approx(45)
    a, b, theta, flux = isophotal_analysis(image, np.array([10.]), np.array([10.]), 5.)
    np.testing.assert_allclose([a[0], b[0]], reference[:2], atol=1e-13)
    assert flux[0] == 18
    assert theta[0] == 0  # BUG: x2==y2 is not sufficient to set theta to zero.


def _wcs(x_scale=2, y_scale=2):
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [64, 64]
    wcs.wcs.crval = [180, 0]
    wcs.wcs.cdelt = [-x_scale/3600, y_scale/3600]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    return wcs


def _match(catalog, detection, wcs=None, tolerance=1):
    return _match_detected_sources([catalog], [detection], wcs=wcs,
        header=fits.Header(), data=np.zeros((128, 128)), source_match_tol=tolerance)


def _spherical_distance_arcsec(ra1_hours, dec1, ra2_hours, dec2):
    longitude1, longitude2 = np.deg2rad(np.array([ra1_hours, ra2_hours])*15)
    latitude1, latitude2 = np.deg2rad([dec1, dec2])
    h = np.sin((latitude2-latitude1)/2)**2
    h += np.cos(latitude1)*np.cos(latitude2)*np.sin((longitude2-longitude1)/2)**2
    return np.rad2deg(2*np.arcsin(np.sqrt(h)))*3600


@pytest.mark.parametrize("center", [0, 12])
def test_characterize_angular_matching_ra_seam(center):
    catalog = CatalogSource(id="c", ra_hours=(center+.00001) % 24, dec_degs=0)
    detection = SourceExtractionData(id="d", x=64, y=64,
        ra_hours=(center-.00001) % 24, dec_degs=0)
    assert _spherical_distance_arcsec(catalog.ra_hours, 0, detection.ra_hours, 0) == pytest.approx(1.08, abs=1e-8)
    with collect_numerical_notices() as notices:
        if center == 0:
            with pytest.raises(RuntimeError, match="Could not match any"):
                _match(catalog, detection, tolerance=2)  # BUG: 1.08 < 2 arcsec.
        else:
            assert _match(catalog, detection, tolerance=2)[0].id == "c"
    assert [n.code for n in notices] == (["ra_seam_matching_approximation"] if center == 0 else [])


def test_variable_star_filter_handles_same_ra_seam_pair():
    source = CatalogSource(id="c", ra_hours=.00001, dec_degs=0)
    variable = CatalogSource(id="v", ra_hours=23.99999, dec_degs=0)
    assert _filter_variable_stars([source], variable_sources=[variable],
        wcs=_wcs(), header=fits.Header(), variable_check_tol=2) == []


def test_characterize_missing_wcs_changes_match_tolerance_units():
    catalog = CatalogSource(id="c", ra_hours=12+1.5/(3600*15), dec_degs=0)
    detection = SourceExtractionData(id="d", x=64, y=64, ra_hours=12, dec_degs=0)
    assert _match(catalog, detection, _wcs(), tolerance=1)[0].id == "c"
    # Numeric 1 means 1 arcsec here, despite source_match_tol's pixel contract.
    with pytest.raises(RuntimeError, match="Could not match any"):
        _match(catalog, detection, tolerance=1)


@pytest.mark.parametrize("axis, distance_px, angular_matches", [(0, .9, False), (1, 1.4, True)])
def test_characterize_anisotropic_tolerance_disagrees_between_matching_modes(axis, distance_px, angular_matches):
    wcs = _wcs(2, 1)
    position = [64., 64.]
    position[axis] += distance_px
    ra, dec = wcs.all_pix2world(*position, 1)
    catalog = CatalogSource(id="c", ra_hours=float(ra/15), dec_degs=float(dec))
    sky = SourceExtractionData(id="d", x=64, y=64, ra_hours=12, dec_degs=0)
    pixel = SourceExtractionData(id="d", x=64, y=64)
    # Independent scale contract: sky mode uses arithmetic mean 1.5 arcsec/px.
    separation = _spherical_distance_arcsec(12, 0, float(ra/15), float(dec))
    assert (separation < 1.5) == angular_matches
    for detection, expected in ((sky, angular_matches), (pixel, distance_px < 1)):
        with collect_numerical_notices() as notices:
            if expected:
                assert _match(catalog, detection, wcs)[0].id == "c"
            else:
                with pytest.raises(RuntimeError, match="Could not match any"):
                    _match(catalog, detection, wcs)
        assert not notices  # Current mismatch has no disclosure notice.


@pytest.mark.parametrize("x,y", [(20, 10), (10, 20)])
def test_characterize_last_fits_pixel_is_rejected(x, y):
    image = np.full((20, 20), 10.)
    source = SourceExtractionData(x=x, y=y)
    assert get_source_xy(source, None, None) == (x, y)
    # The actual origin-1 aperture kernel accepts this fully contained circle.
    direct = aperture_photometry(image, _source_table(x, y),
        background=np.zeros_like(image), background_rms=np.ones_like(image),
        a=.4, apcorr_tol=0)[0]
    assert direct["flag"] == 0
    assert direct["flux"] == pytest.approx(10*np.pi*.4**2, abs=1e-12)
    # BUG: origin-0 admission drops a valid final-row/final-column center.
    with pytest.raises(ValueError, match="Missing WCS and no source XYs given"):
        run_photometry(image, fits.Header({"EXPTIME": 1}), [source],
            PhotometrySettings(a=.4, apcorr_tol=0),
            background=np.zeros_like(image), background_rms=np.ones_like(image))


@pytest.mark.parametrize("x,y", [(0, 10), (10, 0)])
def test_characterize_zero_fits_coordinate_is_admitted(x, y):
    image = np.full((20, 20), 10.)
    with collect_numerical_notices() as notices, np.errstate(invalid="ignore", divide="ignore"):
        rows = run_photometry(image, fits.Header({"EXPTIME": 1}),
            [SourceExtractionData(x=x, y=y)], PhotometrySettings(a=.4, apcorr_tol=0),
            background=np.zeros_like(image), background_rms=np.ones_like(image))
    # BUG: a wholly off-frame circle survives admission as a finite placeholder.
    assert len(rows) == 1 and rows[0].flux == 0
    assert rows[0].mag == rows[0].mag_error == 0
    assert [n.code for n in notices] == ["nonpositive_aperture_flux"]
