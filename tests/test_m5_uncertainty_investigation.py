"""M5 uncertainty correctness against analytic and independent SEP references."""

import numpy as np
import pytest
import sep
from astropy.io import fits

from algorithms.diagnostics import collect_numerical_notices
from algorithms.fieldcal import field_cal
from algorithms.fieldcal.schemas import (
    CatalogSource,
    PhotometricCalibrationSettings,
    PhotometryData,
)
from algorithms.fieldcal.solution import _calc_solution_with_mask
from algorithms.photometry.photometry import run_photometry
from algorithms.photometry.schemas import PhotometrySettings, SourceExtractionData
from algorithms.skylib_lite.photometry.aperture import calc_flux_err
from algorithms.skylib_lite.photometry.aperture_numba import sum_circle, sum_circann


def test_phot13_snr_gate_accepts_flux_snr_above_ten():
    sources = [
        CatalogSource(
            id=f"snr-{snr}", catalog_name="APASS", x=10 + i * 5, y=10,
            mag=-5 - i * .2, mag_error=2.5 * np.log10(1 + 1 / snr),
            flux=1000, flux_error=1000 / snr,
            ref_mag=15 - i * .2 + i * .005, ref_mag_error=.02,
        )
        for i, snr in enumerate([10.1, 10.3, 10.4, 10.5])
    ]
    assert all(source.flux / source.flux_error > 10 for source in sources)
    with collect_numerical_notices() as notices:
        _, result = field_cal.perform_field_calibration(
            fits.Header({"FILTER": "V"}), np.zeros((50, 50)),
            catalog_sources=sources, detected_sources=[], use_provided_photometry=True,
            field_cal_settings=PhotometricCalibrationSettings(min_snr=10, variable_check_tol=0),
        )
    assert [row.id for row in result.phot_results] == ["snr-10.1", "snr-10.3", "snr-10.4", "snr-10.5"]
    assert "magnitude_error_snr_cut" not in {notice.code for notice in notices}


def test_current_fit_weights_follow_the_supplied_magnitude_variances():
    """The current M2 fitter does not derive zero-point weights from SNR."""
    sources = [
        PhotometryData(mag=-5, mag_error=.01, ref_mag=15, ref_mag_error=0),
        PhotometryData(mag=-4, mag_error=.02, ref_mag=16.01, ref_mag_error=0),
    ]
    solution, survivors = _calc_solution_with_mask(sources)
    # Analytic two-measurement Gaussian mean: a 4:1 precision ratio and zero
    # extra variance when the 0.01-mag separation is explained by errors.
    assert solution[0] == pytest.approx(20.002)
    assert solution[2] == 0
    assert survivors.tolist() == [True, True]


def test_optimal_radius_objective_squares_rms_like_independent_sep():
    yy, xx = np.indices((41, 41))
    image = 5 * np.exp(-((xx - 20)**2 + (yy - 20)**2) / 18)
    rms = np.full_like(image, 4.)
    observed = calc_flux_err(np.array([3.]), image, 20., 20., 1.5, .3, rms, None, 1.)
    reference_flux, reference_error, _ = sep.sum_ellipse(
        image, [20.], [20.], 3., 2., .3, err=rms, gain=1., subpix=0,
    )
    expected = reference_error[0] / reference_flux[0]
    assert expected == pytest.approx(.2486048855, rel=1e-6)
    assert observed == pytest.approx(expected, rel=1e-6)


@pytest.mark.parametrize("use_maps", [False, True])
def test_uncertainty_is_independent_of_a_constant_reduction_offset(use_maps):
    settings = PhotometrySettings(a=2, a_in_px=6, a_out_px=8, gain=1, apcorr_tol=0)
    measured = []
    for sky in [-50., 0., 50.]:
        image = np.full((41, 41), sky)
        image[20, 20] += 300
        kwargs = dict(background=np.full_like(image, sky), background_rms=np.full_like(image, 4)) if use_maps else {}
        row = run_photometry(
            image, fits.Header({"EXPTIME": 1}), [SourceExtractionData(x=21, y=21)], settings, **kwargs,
        )[0]
        assert row.flux == pytest.approx(300)
        measured.append(row.flux_error)
    if use_maps:
        expected = np.sqrt(300 + 16 * np.pi * 2**2)
    else:
        expected = np.sqrt(300)
    np.testing.assert_allclose(measured, expected)


@pytest.mark.slow
def test_ngc5128_negative_reduced_sums_retain_positive_uncertainties(frame_path, monkeypatch):
    from tools.photometry import calibrate_zeropoint

    captured = {}
    original = field_cal.run_photometry

    def capture(data, header, sources, settings, **kwargs):
        rows = original(data, header, sources, settings, **kwargs)
        captured.update(data=data, rows=rows, sources=sources, kwargs=kwargs)
        return rows

    monkeypatch.setattr(field_cal, "run_photometry", capture)
    result = calibrate_zeropoint(
        frame_path("ngc5128_b"), catalog_fixture="selected_rows", compare_to="ngc5128_b_002",
    )
    assert result.errors == []
    assert len(captured["sources"]) == 35
    # One edge source now carries the annulus-truncation flag and is excluded.
    assert len(captured["rows"]) == 34
    assert captured["kwargs"]["background"] is None
    assert captured["kwargs"]["background_rms"] is not None
    assert all(row.flux_error > 0 and row.mag_error > 0 for row in captured["rows"])
    x, y = np.array([[row.x - 1, row.y - 1] for row in captured["sources"]]).T
    raw_aperture, _, _, _ = sum_circle(captured["data"], x, y, 5.)
    raw_annulus, _, _, _ = sum_circann(captured["data"], x, y, 8., 12.)
    formerly_zero = (raw_aperture < 0) & (raw_annulus < 0)
    assert formerly_zero.sum() == 6
