"""Growth correction keeps annulus units and recognizes valid zero corrections."""
import numpy as np
import pytest

from algorithms.diagnostics import collect_numerical_notices
from algorithms.photometry.photometry import run_photometry
from algorithms.photometry.schemas import PhotometrySettings, SourceExtractionData
from algorithms.skylib_lite.photometry import aperture_photometry


@pytest.mark.parametrize("a,b,angle", [(3, 1.5, 0), (4, 2, 37), (3, 1.5, -45), (3, 3, 0)])
def test_growth_recovers_planted_gaussian_total_with_pixel_annulus(a, b, angle):
    yy, xx = np.indices((129, 129))
    theta = np.deg2rad(angle)
    dx, dy = xx-64.3, yy-64.3
    u, v = dx*np.cos(theta)+dy*np.sin(theta), -dx*np.sin(theta)+dy*np.cos(theta)
    sigma_x, sigma_y = 2., 2*b/a
    sky = np.full(xx.shape, 100.)
    image = sky + 1000*np.exp(-.5*((u/sigma_x)**2 + (v/sigma_y)**2))
    source = [SourceExtractionData(x=65.3, y=65.3)]
    settings = PhotometrySettings(a=a, b=b, theta=angle, a_in_px=8, a_out_px=12, apcorr_tol=0)
    baseline = run_photometry(image, {"EXPTIME": 1}, source, settings,
                              background=sky, background_rms=np.ones_like(sky))[0]
    with collect_numerical_notices() as notices:
        corrected = run_photometry(
            image, {"EXPTIME": 1}, source, settings.model_copy(update={"apcorr_tol": 1e-4}),
            background=sky, background_rms=np.ones_like(sky),
        )[0]
    assert not notices
    # Flux remains the measured aperture count; magnitude carries correction.
    assert corrected.flux == baseline.flux
    total_from_magnitude = 10**(-corrected.mag/2.5)
    assert total_from_magnitude == pytest.approx(2*np.pi*1000*sigma_x*sigma_y, rel=1e-3)
    assert corrected.mag < baseline.mag-.1


def test_converged_curve_needing_no_correction_is_available():
    yy, xx = np.indices((129, 129))
    sky = np.full(xx.shape, 100.)
    image = sky + 1000*np.exp(-((xx-64)**2 + (yy-64)**2)/.5)
    source = [SourceExtractionData(x=65, y=65)]
    settings = PhotometrySettings(a=5, a_in_px=8, a_out_px=12, apcorr_tol=0)
    baseline = run_photometry(image, {"EXPTIME": 1}, source, settings,
                              background=sky, background_rms=np.ones_like(sky))[0]
    with collect_numerical_notices() as notices:
        corrected = run_photometry(
            image, {"EXPTIME": 1}, source, settings.model_copy(update={"apcorr_tol": 1e-4}),
            background=sky, background_rms=np.ones_like(sky),
        )[0]
    assert corrected.mag == baseline.mag
    assert "aperture_correction_unavailable" not in {n.code for n in notices}


@pytest.mark.parametrize("b", [1.5, 3])
def test_truncated_growth_annulus_still_makes_correction_unavailable(b):
    yy, xx = np.indices((129, 129))
    sky = np.full(xx.shape, 100.)
    image = sky + 1000*np.exp(-.5*(((xx-8.3)/2)**2 + ((yy-64.3)/(2*b/3))**2))
    source = [SourceExtractionData(x=9.3, y=65.3)]
    settings = PhotometrySettings(a=3, b=b, a_in_px=8, a_out_px=12, apcorr_tol=0)
    baseline = run_photometry(image, {"EXPTIME": 1}, source, settings,
                              background=sky, background_rms=np.ones_like(sky))[0]
    with collect_numerical_notices() as notices:
        corrected = run_photometry(
            image, {"EXPTIME": 1}, source, settings.model_copy(update={"apcorr_tol": 1e-4}),
            background=sky, background_rms=np.ones_like(sky),
        )[0]
    assert corrected.mag == baseline.mag
    assert "aperture_correction_unavailable" in {n.code for n in notices}


@pytest.mark.parametrize("axis_ratio", [.5, 1.])
def test_adaptive_growth_corrects_each_distinct_aperture_size(axis_ratio):
    yy, xx = np.indices((161, 161))
    sky = np.full(xx.shape, 100.)
    image = sky.copy()
    for center, amplitude in [(40.3, 1000), (110.3, 100)]:
        image += amplitude*np.exp(-.5*(((xx-center)/2)**2 + ((yy-center)/(2*axis_ratio))**2))
    table = np.array([
        (41.3, 41.3, 1.5, 1.5*axis_ratio, 0., 1e4),
        (111.3, 111.3, 2., 2*axis_ratio, 0., 1e3),
    ], dtype=[(name, float) for name in ("x", "y", "a", "b", "theta", "flux")])
    with collect_numerical_notices() as notices:
        corrected = aperture_photometry(
            image, table, background=sky, background_rms=np.ones_like(sky),
            k=2, k_in=16/3, k_out=8, fix_aper=False, fix_ell=False, fix_rot=False,
        )
    assert not notices
    np.testing.assert_allclose(corrected["aper_a"], [3, 4])
    np.testing.assert_allclose(
        10**(-corrected["mag"]/2.5),
        2*np.pi*np.array([1000, 100])*2*(2*axis_ratio), rtol=1e-3,
    )
