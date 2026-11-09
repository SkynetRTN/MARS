"""M5 flux validity, annular sky and growth-correction correctness regressions."""

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from algorithms.catalogs.schemas import CatalogSource, Mag
from algorithms.diagnostics import collect_numerical_notices
from algorithms.fieldcal.schemas import PhotometryData
from algorithms.fieldcal.solution import _calc_solution_with_mask
from algorithms.photometry.photometry import run_photometry
from algorithms.photometry.schemas import PhotometrySettings, SourceExtractionData
from algorithms.skylib_lite.photometry import aperture_photometry
from algorithms.skylib_lite.photometry.aperture_numba import _sum_circann, sum_circann


@pytest.mark.parametrize('sky', [0., 1.])
def test_phot01_nonpositive_flux_has_no_magnitude_or_public_detection(sky):
    image = np.zeros((15, 15))
    sources = np.array([(8., 8.)], dtype=[('x', float), ('y', float)])
    background = np.full_like(image, sky)
    with collect_numerical_notices() as notices:
        raw = aperture_photometry(image, sources, background, np.ones_like(image),
                                  a=2, apcorr_tol=0)
        rows = run_photometry(image, fits.Header({'EXPTIME': 1}),
            [SourceExtractionData(x=8, y=8)],
            PhotometrySettings(a=2, apcorr_tol=0, zero_point_mag=20),
            background=background, background_rms=np.ones_like(image))
    assert raw['flux'][0] == pytest.approx(-sky * np.pi * 4)
    assert raw['flag'][0] & 0x80
    assert np.isnan(raw['mag'][0]) and np.isnan(raw['mag_err'][0])
    assert rows == []
    assert 'nonpositive_aperture_flux' in {n.code for n in notices}


def test_phot01_public_calibration_refuses_an_image_containing_only_zeros(tmp_path):
    from tools.photometry import calibrate_zeropoint

    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [30., 30.]
    wcs.wcs.crval = [100., 20.]
    wcs.wcs.cdelt = [-1 / 3600, 1 / 3600]
    wcs.wcs.ctype = ['RA---TAN', 'DEC--TAN']
    header = wcs.to_header()
    header['EXPTIME'] = 1.
    header['FILTER'] = 'V'
    path = tmp_path / 'zero_photons.fits'
    fits.writeto(path, np.zeros((60, 60)), header)
    catalog = []
    for i, (x, ref) in enumerate([(15., 12.95), (30., 13.), (45., 13.05)]):
        ra, dec = wcs.all_pix2world(x, 20., 1)
        catalog.append(CatalogSource(id=str(i), x=x, y=20.,
            ra_hours=float(ra) / 15, dec_degs=float(dec), catalog_name='APASS',
            mags={'V': Mag(value=ref, error=0.)}))
    # Supplying catalog_sources selects the genuine offline pixel-measurement
    # path; no provided-photometry shortcut or extraction mock is used.
    result = calibrate_zeropoint(path, catalog_sources=catalog)
    assert result.errors
    assert result.zero_point is None
    warnings = {w.code: w.message for w in result.warnings}
    assert 'nonpositive_aperture_flux' in warnings


@pytest.mark.parametrize('add_positive_errors', [False, True])
def test_solver_preserves_explicit_magnitude_only_unweighted_contract(add_positive_errors):
    rows = [PhotometryData(flux=0, mag=0, mag_error=0, ref_mag=ref, ref_mag_error=0)
            for ref in [12.95, 13., 13.05]]
    if add_positive_errors:
        rows.extend([
            PhotometryData(flux=100, mag=-5, mag_error=.02, ref_mag=8., ref_mag_error=.01),
            PhotometryData(flux=50, mag=-4, mag_error=.03, ref_mag=9.01, ref_mag_error=.01),
        ])
    summary, keep = _calc_solution_with_mask(rows)
    assert np.isfinite(summary[0]) and np.isfinite(summary[1]) and summary[1] > 0
    if add_positive_errors:
        assert keep.tolist() == [False, False, False, True, True]
    else:
        assert keep.tolist() == [True, True, True]
        assert summary[0] == pytest.approx(13.)
        assert summary[1] == pytest.approx(.0288675134594817)


@pytest.mark.parametrize('masked', [False, True])
def test_phot02_empty_annulus_invalidates_measurement_and_preserves_flags(masked):
    image = np.full((20, 20), 10.)
    image[9, 9] += 300.
    inner, outer = (6., 8.) if masked else (30., 35.)
    yy, xx = np.indices(image.shape)
    mask = np.hypot(xx - 9, yy - 9) >= 5 if masked else None
    data = np.ma.array(image, mask=mask) if masked else image
    table = np.array([(10., 10.)], dtype=[('x', float), ('y', float)])
    # The driver uses the public annulus default (ignore_mask=False), while
    # sum_circle's sky subtraction internally requests ignore_mask=True.
    annulus = sum_circann(image, 9., 9., inner, outer, mask=mask)
    internal = _sum_circann(9., 9., np.array([inner, outer]), image, mask, 0,
                           np.zeros((1, 1)), None, 0, 0, ignore_mask=True)
    with collect_numerical_notices() as notices:
        raw = aperture_photometry(data, table, a=2, a_in=inner, a_out=outer, apcorr_tol=0)
        rows = run_photometry(data, fits.Header({'EXPTIME': 1}),
            [SourceExtractionData(x=10, y=10)],
            PhotometrySettings(a=2, a_in_px=inner, a_out_px=outer, apcorr_tol=0))
    assert internal[2] == 0
    expected_flag = 0x20 if masked else 0x10
    assert annulus[3][0] & expected_flag
    assert internal[3] & expected_flag
    assert raw['flag'][0] & internal[3]
    assert raw['flag'][0] & 0x40
    assert np.isnan(raw['flux'][0])
    assert rows == []
    notice_codes = {n.code for n in notices}
    assert raw['background_area'][0] == 0
    assert 'empty_background_annulus' in notice_codes


def test_phot12_growth_rejects_a_neighbor_and_uses_a_clean_reference(monkeypatch):
    import algorithms.skylib_lite.photometry.aperture as aperture

    yy, xx = np.indices((129, 129))
    sky = np.full((129, 129), 10.)
    primary = 1000 * np.exp(-((xx - 40)**2 + (yy - 50)**2) / 8)
    companion = 300 * np.exp(-((xx - 48.5)**2 + (yy - 50)**2) / (2 * 1.2**2))
    secondary = 100 * np.exp(-((xx - 95)**2 + (yy - 95)**2) / 8)
    sources = [SourceExtractionData(id='primary', x=41, y=51),
               SourceExtractionData(id='secondary', x=96, y=96)]
    original_sum_circle = aperture.sum_circle
    measurements = []
    growth_calls = []

    def traced_sum_circle(data, x, y, radius, *args, **kwargs):
        result = original_sum_circle(data, x, y, radius, *args, **kwargs)
        if np.isscalar(x) and kwargs.get('bkgann') is not None:
            growth_calls.append((float(radius), float(result[0][0])))
        return result

    for crowded in [False, True]:
        image = sky + primary + secondary + (companion if crowded else 0)
        baseline = run_photometry(image, fits.Header({'EXPTIME': 1}), sources,
            PhotometrySettings(a=3, a_in_px=20, a_out_px=25, apcorr_tol=0),
            background=sky, background_rms=np.ones_like(image))
        growth_calls.clear()
        with monkeypatch.context() as patch, collect_numerical_notices() as notices:
            patch.setattr(aperture, 'sum_circle', traced_sum_circle)
            corrected = run_photometry(image, fits.Header({'EXPTIME': 1}), sources,
                PhotometrySettings(a=3, a_in_px=20, a_out_px=25, apcorr_tol=1e-4),
                background=sky, background_rms=np.ones_like(image))
        assert ('aperture_correction_crowding' in {n.code for n in notices}) == crowded
        correction = corrected[1].mag - baseline[1].mag
        measurements.append((baseline, corrected, correction))
        if crowded:
            ratios = np.array([growth_calls[i][1] / growth_calls[i-1][1]
                               for i in range(1, len(growth_calls))])
            assert np.any(np.diff(ratios) > 1e-4)  # intended guard sees reacceleration
            assert growth_calls[-1][0] < 9
    isolated, crowded = measurements
    assert isolated[0][1].flux == crowded[0][1].flux
    assert isolated[1][1].flux == crowded[1][1].flux
    assert isolated[2] == pytest.approx(-.4412405521459153)
    assert crowded[2] == pytest.approx(isolated[2], abs=1e-10)
    assert crowded[1][1].mag == pytest.approx(isolated[1][1].mag, abs=1e-10)


def test_nonpositive_remeasurement_clears_preexisting_magnitudes():
    table = np.array([(8., 8., 42., .01)],
                     dtype=[('x', float), ('y', float), ('mag', float), ('mag_err', float)])
    image = np.zeros((15, 15))
    result = aperture_photometry(image, table, background=image.copy(),
                                background_rms=np.ones_like(image), a=2, apcorr_tol=0)
    assert np.isnan(result['mag'][0]) and np.isnan(result['mag_err'][0])


def test_growth_without_a_clean_reference_keeps_measured_aperture_scale():
    yy, xx = np.indices((129, 129))
    sky = np.full((129, 129), 10.)
    image = sky + 1000*np.exp(-((xx-40)**2 + (yy-50)**2)/8)
    image += 300*np.exp(-((xx-48.5)**2 + (yy-50)**2)/(2*1.2**2))
    source = [SourceExtractionData(x=41, y=51)]
    baseline = run_photometry(image, fits.Header({'EXPTIME': 1}), source,
        PhotometrySettings(a=3, a_in_px=20, a_out_px=25, apcorr_tol=0),
        background=sky, background_rms=np.ones_like(image))[0]
    with collect_numerical_notices() as notices:
        measured = run_photometry(image, fits.Header({'EXPTIME': 1}), source,
            PhotometrySettings(a=3, a_in_px=20, a_out_px=25, apcorr_tol=1e-4),
            background=sky, background_rms=np.ones_like(image))[0]
    assert measured.mag == baseline.mag
    assert {'aperture_correction_crowding', 'aperture_correction_unavailable'} <= {n.code for n in notices}
