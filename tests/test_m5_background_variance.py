"""Independent sky/source variance checks for corrected M5 aperture sums."""

import numpy as np
import pytest
from astropy.io import fits

from algorithms.photometry.photometry import run_photometry
from algorithms.diagnostics import collect_numerical_notices
from algorithms.photometry.schemas import PhotometrySettings, SourceExtractionData
from algorithms.skylib_lite.photometry.aperture import aperture_photometry
from algorithms.skylib_lite.photometry.aperture_numba import sum_circle


@pytest.mark.parametrize("minor", [1., 2.])
@pytest.mark.parametrize("gain", [1., 2.])
def test_supplied_rms_annular_error_includes_sky_mean_and_net_source_shot(minor, gain):
    area, annulus = np.pi*2*minor, np.pi*(8**2 - 6**2)*minor/2
    expected = gain*np.sqrt(300/gain + 16*area*(1 + area/annulus))
    for sky in [-50., 0., 50.]:
        image = np.full((41, 41), sky)
        image[20, 20] += 300
        row = run_photometry(image, fits.Header({"EXPTIME": 1}),
            [SourceExtractionData(x=21, y=21)],
            PhotometrySettings(a=2, b=minor, theta=37, a_in_px=6, a_out_px=8, gain=gain, apcorr_tol=0),
            background_rms=np.full_like(image, 4))[0]
        assert row.flux == pytest.approx(300*gain)
        assert row.flux_error == pytest.approx(expected, rel=1e-10)


def test_local_annulus_residual_noise_is_positive_and_offset_invariant():
    yy, xx = np.indices((41, 41))
    noise = np.random.default_rng(9).normal(0, 4, xx.shape)
    image = noise.copy()
    image[20, 20] += 300
    outputs = [sum_circle(image + sky, np.array([20.]), np.array([20.]), 2., bkgann=(6., 8.), gain=1)
               for sky in [-1000., 0., 1000.]]
    flux = [row[0][0] for row in outputs]
    error = [row[1][0] for row in outputs]
    assert all(row[3][0] == 0 for row in outputs)
    assert error[1] > np.sqrt(flux[1])  # both aperture sky and sky-mean noise
    np.testing.assert_allclose(flux, flux[1], rtol=1e-12)
    np.testing.assert_allclose(error, error[1], rtol=1e-12)


@pytest.mark.parametrize("reject", [False, True])
def test_masked_outlier_annulus_uses_absolute_detector_mask(reject):
    image = np.full((41, 41), 10.)
    image[20, 20] += 300
    # Extreme pixel in the offset annulus, safely masked at its actual index.
    image[20, 27] = 1e6
    mask = np.zeros(image.shape, bool)
    mask[20, 27] = True
    result = sum_circle(image, np.array([20.]), np.array([20.]), 2., err=4., mask=mask,
                        bkgann=(6., 8.), gain=1, reject_outliers=reject)
    assert result[0][0] == pytest.approx(300)
    assert np.isfinite(result[1][0]) and result[1][0] > np.sqrt(300)
    assert result[3][0] & 0x20


def test_background_rms_masks_are_applied_without_mutating_input_masks():
    image = np.full((41, 41), 10.)
    image[20, 20] += 300
    image[20, 21] = 1e6
    input_mask = np.zeros(image.shape, bool)
    rms_mask = input_mask.copy()
    rms_mask[20, 21] = True
    table = np.array([(21., 21.)], dtype=[("x", float), ("y", float)])
    result = aperture_photometry(np.ma.array(image, mask=input_mask), table,
        background=np.full_like(image, 10), background_rms=np.ma.array(np.full_like(image, 4), mask=rms_mask),
        a=2, apcorr_tol=0)
    assert np.isfinite(result["flux_err"][0])
    assert result["flux"][0] < 1000
    assert not input_mask.any()


def test_missing_rms_estimation_ignores_data_under_the_combined_mask():
    rng = np.random.default_rng(1)
    base = rng.normal(0, 1, (65, 65))
    base[32, 32] += 300
    mask = np.zeros(base.shape, bool)
    mask[:30] = True
    bad = base.copy()
    bad[mask] = rng.normal(0, 1000, mask.sum())
    rows = []
    for image in [base, bad]:
        table = np.array([(33., 33.)], dtype=[("x", float), ("y", float)])
        rows.append(aperture_photometry(np.ma.array(image, mask=mask), table,
            background=np.zeros_like(image), a=2, apcorr_tol=0)[0])
    assert rows[0]["flux"] == rows[1]["flux"]
    assert rows[0]["flux_err"] == pytest.approx(rows[1]["flux_err"], rel=1e-12)


def test_custom_annulus_geometry_controls_flux_and_its_reported_noise():
    image = np.full((41, 41), 10.)
    image[20, 20] += 300
    image[27, 20] += 100  # outside the requested 8 x 4 ellipse, inside an 8-pixel circle
    table = np.array([(21., 21.)], dtype=[("x", float), ("y", float)])
    row = aperture_photometry(image, table, background_rms=np.full_like(image, 4),
        a=2, a_in=6, a_out=8, b_out=4, apcorr_tol=0)[0]
    assert row["background_area"] == pytest.approx(14*np.pi)
    assert row["background"] == pytest.approx(10)
    assert row["flux"] == pytest.approx(300)
    expected_variance = 300 + 16*4*np.pi*(1 + (4*np.pi)/(14*np.pi))
    assert row["flux_err"] == pytest.approx(np.sqrt(expected_variance))


def test_invalid_rms_pixels_are_masked_locally_without_discarding_a_valid_frame():
    image = np.full((41, 41), 10.)
    image[20, 20] += 300
    rms = np.full_like(image, 4)
    rms[0, 0] = -1  # e.g. an overshoot in an interpolated RMS map, away from the source
    rms[0, 1] = np.nan
    with collect_numerical_notices() as notices:
        rows = run_photometry(image, fits.Header({'EXPTIME': 1}), [SourceExtractionData(x=21, y=21)],
            PhotometrySettings(a=2, a_in_px=6, a_out_px=8, apcorr_tol=0), background_rms=rms)
    assert len(rows) == 1 and rows[0].flux == pytest.approx(300)
    assert 'background_noise_masked' in {notice.code for notice in notices}
