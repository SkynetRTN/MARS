"""M5 investigation: characterize current failures, NOT desired acceptance behavior.

All images are synthetic and local. These tests intentionally pass while
PHOT-01/02/12 survive; a numerical repair should replace their bug-pinning
assertions with its acceptance contract. No production files are changed.
"""

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
def test_phot01_nonpositive_flux_remains_a_finite_magnitude(sky):
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
    assert raw['flag'][0] == 0
    assert raw['mag'][0] == raw['mag_err'][0] == 0
    assert len(rows) == 1
    assert rows[0].mag == 20 and rows[0].mag_error == 0
    assert 'nonpositive_aperture_flux' in {n.code for n in notices}


def test_phot01_public_calibration_succeeds_on_an_image_containing_only_zeros(tmp_path):
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
    assert result.errors == []
    assert result.zero_point == pytest.approx(13.)
    warnings = {w.code: w.message for w in result.warnings}
    assert 'nonpositive_aperture_flux' in warnings
    assert '3 of 3' in warnings['calibration_sufficiency_unverified']


@pytest.mark.parametrize('add_positive_errors', [False, True])
def test_phot01_zero_error_filter_depends_on_other_rows(add_positive_errors):
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
def test_phot02_empty_annulus_keeps_sky_flux_and_discards_annulus_flags(masked):
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
    assert annulus[3][0] == internal[3] == (0x20 if masked else 0x10)
    assert raw['flag'][0] == 0
    assert len(rows) == 1
    assert rows[0].flux == pytest.approx(300 + 10 * np.pi * 4)
    assert rows[0].mag + 2.5 * np.log10(300) == pytest.approx(-.37986341820956326)
    notice_codes = {n.code for n in notices}
    if masked:
        assert raw['background_area'][0] > 0  # misleading preflight area
        assert 'empty_background_annulus' not in notice_codes
    else:
        assert raw['background_area'][0] == 0
        assert 'empty_background_annulus' in notice_codes


def test_phot12_growth_absorbs_a_neighbor_and_shifts_a_distant_source(monkeypatch):
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
        assert 'aperture_correction_crowding' in {n.code for n in notices}
        correction = corrected[1].mag - baseline[1].mag
        measurements.append((baseline, corrected, correction))
        if crowded:
            ratios = np.array([growth_calls[i][1] / growth_calls[i-1][1]
                               for i in range(1, len(growth_calls))])
            assert np.any(np.diff(ratios) > 1e-4)  # intended guard sees reacceleration
            assert growth_calls[-1][0] > 11
    isolated, crowded = measurements
    assert isolated[0][1].flux == crowded[0][1].flux
    assert isolated[1][1].flux == crowded[1][1].flux
    assert isolated[2] == pytest.approx(-.4412405521459153)
    assert crowded[2] == pytest.approx(-.5526048150307812)
    assert crowded[1][1].mag - isolated[1][1].mag == pytest.approx(-.1113642628848659)
