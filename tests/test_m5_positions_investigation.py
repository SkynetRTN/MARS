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


@pytest.mark.parametrize("downsample", [1, 2, 3])
@pytest.mark.parametrize("discard", [0, 1])
def test_downsampling_preserves_detector_saturation_counts(saturated_pair, discard, downsample):
    image, saturation = saturated_pair
    with collect_numerical_notices() as notices:
        sources = _extract(image, saturation, downsample, discard)
    assert not notices
    if discard == 0:
        assert sources["saturated"].tolist() == [0, 13]
    else:
        assert len(sources) == 1
        assert sources[0]["x"] == pytest.approx(41-(downsample-1)/2, abs=.01)
        assert sources[0]["saturated"] == 0


@pytest.mark.parametrize("downsample, expected_x", [(1, 41), (2, 40.5), (3, 40)])
def test_python_api_discards_only_the_saturated_star(saturated_pair, downsample, expected_x):
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
    assert not notices


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


def test_isophotal_remeasurement_uses_zero_based_centers_for_final_flux():
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
        measured = aperture_photometry(image, _source_table(32, 32),
            background=np.zeros_like(image), background_rms=np.ones_like(image),
            k=2.5, radius=5, apcorr_tol=0)[0]
    assert measured["aper_a"] == pytest.approx(2.5*correct[0], abs=1e-11)
    assert measured["aper_b"] == pytest.approx(2.5*correct[1], abs=1e-11)
    assert not notices
    provided = aperture_photometry(image, _source_table(32, 32, correct[:4]),
        background=np.zeros_like(image), background_rms=np.ones_like(image),
        k=2.5, radius=5, apcorr_tol=0)[0]
    # Independent SEP exact circle sum for the symmetric covariance oracle.
    correct_radius = 2.5*np.sqrt(np.trace(correct[4])/2)
    sep_flux = sep.sum_circle(image, np.array([31.]), np.array([31.]), correct_radius, subpix=0)[0][0]
    # Allow the existing kernels' ~2.6e-9 relative numerical difference.
    assert measured["flux"] == pytest.approx(sep_flux, rel=1e-8)
    assert measured["flux"] == pytest.approx(46344.90836229487, abs=1e-7)
    assert measured["flux"] == pytest.approx(provided["flux"], abs=1e-7)
    assert measured["mag"] == pytest.approx(provided["mag"], abs=1e-11)


@pytest.mark.parametrize("sign", [-1, 1])
def test_equal_diagonal_moments_preserve_covariance_orientation(sign):
    image = np.zeros((21, 21))
    for coordinate, value in ((8, 1), (9, 4), (10, 6), (11, 4), (12, 1)):
        image[coordinate, coordinate] = value
    image[9, 11] = image[11, 9] = 1
    if sign < 0:
        image = image[:, ::-1].copy()
    reference = _weighted_moments(image, 10, 10, 5)
    np.testing.assert_allclose(reference[4], [[1, sign*7/9], [sign*7/9, 1]], atol=1e-15)
    assert np.rad2deg(reference[2]) == pytest.approx(sign*45)
    a, b, theta, flux = isophotal_analysis(image, np.array([10.]), np.array([10.]), 5.)
    np.testing.assert_allclose([a[0], b[0]], reference[:2], atol=1e-13)
    assert flux[0] == 18
    # Eigenvectors have an arbitrary sign, so compare orientation modulo pi.
    delta = (theta[0]-reference[2] + np.pi/2) % np.pi - np.pi/2
    assert delta == pytest.approx(0, abs=1e-13)


def _wcs(x_scale=2, y_scale=2):
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [64, 64]
    wcs.wcs.crval = [180, 0]
    wcs.wcs.cdelt = [-x_scale/3600, y_scale/3600]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    return wcs


def _match(catalog, detection, wcs=None, tolerance=1, angular_tolerance=None):
    return _match_detected_sources([catalog], [detection], wcs=wcs,
        header=fits.Header(), data=np.zeros((128, 128)), source_match_tol=tolerance,
        source_match_tol_arcsec=angular_tolerance)


def _spherical_distance_arcsec(ra1_hours, dec1, ra2_hours, dec2):
    longitude1, longitude2 = np.deg2rad(np.array([ra1_hours, ra2_hours])*15)
    latitude1, latitude2 = np.deg2rad([dec1, dec2])
    h = np.sin((latitude2-latitude1)/2)**2
    h += np.cos(latitude1)*np.cos(latitude2)*np.sin((longitude2-longitude1)/2)**2
    return np.rad2deg(2*np.arcsin(np.sqrt(h)))*3600


@pytest.mark.parametrize("center", [0, 12])
def test_angular_matching_handles_ra_seam(center):
    catalog = CatalogSource(id="c", ra_hours=(center+.00001) % 24, dec_degs=0)
    detection = SourceExtractionData(id="d", x=64, y=64,
        ra_hours=(center-.00001) % 24, dec_degs=0)
    assert _spherical_distance_arcsec(catalog.ra_hours, 0, detection.ra_hours, 0) == pytest.approx(1.08, abs=1e-8)
    with collect_numerical_notices() as notices:
        assert _match(catalog, detection, angular_tolerance=2)[0].id == "c"
    assert not notices


def test_variable_star_filter_handles_same_ra_seam_pair():
    source = CatalogSource(id="c", ra_hours=.00001, dec_degs=0)
    variable = CatalogSource(id="v", ra_hours=23.99999, dec_degs=0)
    assert _filter_variable_stars([source], variable_sources=[variable],
        wcs=_wcs(), header=fits.Header(), variable_check_tol=2) == []


def test_sky_only_matching_requires_an_explicit_angular_tolerance():
    catalog = CatalogSource(id="c", ra_hours=12+1.5/(3600*15), dec_degs=0)
    detection = SourceExtractionData(id="d", x=64, y=64, ra_hours=12, dec_degs=0)
    assert _match(catalog, detection, _wcs(), tolerance=1)[0].id == "c"
    with pytest.raises(ValueError, match="source_match_tol_arcsec"):
        _match(catalog, detection, tolerance=1)
    with pytest.raises(RuntimeError, match="Could not match any"):
        _match(catalog, detection, tolerance=99, angular_tolerance=1)
    assert _match(catalog, detection, tolerance=.01, angular_tolerance=2)[0].id == "c"


@pytest.mark.parametrize("axis, distance_px", [(0, .9), (1, 1.4)])
@pytest.mark.parametrize("rotation", [0, 37])
def test_wcs_matching_uses_detector_distance_for_sky_and_pixel_detections(axis, distance_px, rotation):
    wcs = _wcs(2, 1)
    angle = np.deg2rad(rotation)
    wcs.wcs.pc = [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    position = [64., 64.]
    position[axis] += distance_px
    ra, dec = wcs.all_pix2world(*position, 1)
    catalog = CatalogSource(id="c", ra_hours=float(ra/15), dec_degs=float(dec))
    sky = SourceExtractionData(id="d", x=64, y=64, ra_hours=12, dec_degs=0)
    pixel = SourceExtractionData(id="d", x=64, y=64)
    for detection in (sky, pixel):
        with collect_numerical_notices() as notices:
            if distance_px < 1:
                assert _match(catalog, detection, wcs)[0].id == "c"
            else:
                with pytest.raises(RuntimeError, match="Could not match any"):
                    _match(catalog, detection, wcs)
        assert not notices


@pytest.mark.parametrize("dec", [-89.999, 89.999])
def test_angular_matching_uses_spherical_distance_near_poles(dec):
    catalog = CatalogSource(id="c", ra_hours=0, dec_degs=dec)
    detection = SourceExtractionData(id="d", ra_hours=6, dec_degs=dec)
    # A 90-degree longitude offset this close to either pole is 5.091 arcsec.
    assert _spherical_distance_arcsec(0, dec, 6, dec) == pytest.approx(5.091168824, abs=1e-8)
    assert _match(catalog, detection, angular_tolerance=5.1)[0].id == "c"
    with pytest.raises(RuntimeError, match="Could not match any"):
        _match(catalog, detection, angular_tolerance=5)


@pytest.mark.parametrize("x,y", [(20, 10), (10, 20)])
def test_last_fits_pixel_is_measured(x, y):
    image = np.full((20, 20), 10.)
    source = SourceExtractionData(x=x, y=y)
    assert get_source_xy(source, None, None) == (x, y)
    # The actual origin-1 aperture kernel accepts this fully contained circle.
    direct = aperture_photometry(image, _source_table(x, y),
        background=np.zeros_like(image), background_rms=np.ones_like(image),
        a=.4, apcorr_tol=0)[0]
    assert direct["flag"] == 0
    assert direct["flux"] == pytest.approx(10*np.pi*.4**2, abs=1e-12)
    rows = run_photometry(image, fits.Header({"EXPTIME": 1}), [source],
        PhotometrySettings(a=.4, apcorr_tol=0),
        background=np.zeros_like(image), background_rms=np.ones_like(image))
    assert len(rows) == 1
    assert (rows[0].x, rows[0].y) == (x, y)
    assert rows[0].flux == pytest.approx(10*np.pi*.4**2, abs=1e-12)


@pytest.mark.parametrize("x,y", [(0, 10), (10, 0)])
def test_zero_fits_coordinate_is_rejected(x, y):
    image = np.full((20, 20), 10.)
    with pytest.raises(ValueError, match="Missing WCS and no source XYs given"):
        run_photometry(image, fits.Header({"EXPTIME": 1}),
            [SourceExtractionData(x=x, y=y)], PhotometrySettings(a=.4, apcorr_tol=0),
            background=np.zeros_like(image), background_rms=np.ones_like(image))


@pytest.mark.parametrize("value", [0, -1])
def test_nonpositive_measured_flux_is_not_returned(value):
    image = np.full((20, 20), float(value))
    rows = run_photometry(image, fits.Header({"EXPTIME": 1}),
        [SourceExtractionData(x=10, y=10)], PhotometrySettings(a=.4, apcorr_tol=0),
        background=np.zeros_like(image), background_rms=np.ones_like(image))
    assert rows == []


def test_last_fits_pixel_preserves_explicit_gain_and_tiny_circle():
    image = np.full((20, 20), 10.)
    rows = run_photometry(image, fits.Header({"EXPTIME": 1, "GAIN": 5}),
        [SourceExtractionData(x=20, y=20)], PhotometrySettings(a=.4, gain=2, apcorr_tol=0),
        background=np.zeros_like(image), background_rms=np.ones_like(image))
    assert len(rows) == 1
    assert rows[0].flux == pytest.approx(20*np.pi*.4**2, abs=1e-12)
    assert rows[0].mag_error > 0
