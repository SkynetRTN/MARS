"""M5 CHARACTERIZATION, not acceptance of the retained uncertainty model.

These probes establish current failure mechanisms for the investigation in
docs/analysis/m5-measured-flux-source-position.md. Convert the defect assertions
to correctness regressions when changing the corresponding production paths.
The analytic weighted fit is a control that refutes an obsolete report.
"""

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


def test_phot13_inverse_magnitude_error_gate_rejects_flux_snr_above_ten():
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
    # KNOWN BUG PHOT-13: the advertised floor corresponds to flux SNR 10.365.
    assert [row.id for row in result.phot_results] == ["snr-10.4", "snr-10.5"]
    assert "magnitude_error_snr_cut" in {notice.code for notice in notices}


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


def test_optimal_radius_objective_uses_rms_as_variance():
    yy, xx = np.indices((41, 41))
    image = 5 * np.exp(-((xx - 20)**2 + (yy - 20)**2) / 18)
    rms = np.full_like(image, 4.)
    observed = calc_flux_err(np.array([3.]), image, 20., 20., 1.5, .3, rms, None, 1.)
    reference_flux, reference_error, _ = sep.sum_ellipse(
        image, [20.], [20.], 3., 2., .3, err=rms, gain=1., subpix=0,
    )
    expected = reference_error[0] / reference_flux[0]
    assert expected == pytest.approx(.2486048855, rel=1e-6)
    # KNOWN BUG: _sum_ellipse expects variance, while its caller supplies RMS.
    assert observed == pytest.approx(.1581641560, rel=1e-6)
    assert observed < .65 * expected


@pytest.mark.parametrize("use_maps", [False, True])
def test_uncertainty_changes_with_an_arbitrary_constant_sky_offset(use_maps):
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
    # KNOWN BUG: noise is added to the raw sky-inclusive sum before subtraction.
    # Even a supplied RMS map cannot remove this raw-offset dependence.
    if use_maps:
        expected = np.sqrt(300 + 16 * np.pi * 2**2)
        assert measured[1] == pytest.approx(expected)
        np.testing.assert_allclose(measured, [14.1796308072, 22.3844126532, 33.6062562709])
    else:
        np.testing.assert_allclose(measured, [0, np.sqrt(300), 31.9073396074])


@pytest.mark.slow
def test_ngc5128_six_zero_errors_come_from_missing_rms_and_negative_raw_sums(frame_path, monkeypatch):
    from tools.photometry import calibrate_zeropoint

    captured = {}
    original = field_cal.run_photometry

    def capture(data, header, sources, settings, **kwargs):
        rows = original(data, header, sources, settings, **kwargs)
        captured.update(data=data, rows=rows, kwargs=kwargs)
        return rows

    monkeypatch.setattr(field_cal, "run_photometry", capture)
    result = calibrate_zeropoint(
        frame_path("ngc5128_b"), catalog_fixture="selected_rows", compare_to="ngc5128_b_002",
    )
    assert result.errors == []
    assert len(captured["rows"]) == 35
    assert captured["kwargs"]["background"] is None
    assert captured["kwargs"]["background_rms"] is None
    zeros = [row for row in captured["rows"] if row.flux_error == 0]
    assert len(zeros) == 6
    assert all(row.flux > 0 and row.mag_error == 0 for row in zeros)
    x, y = np.array([[row.x - 1, row.y - 1] for row in zeros]).T
    raw_aperture, _, _, _ = sum_circle(captured["data"], x, y, 5.)
    raw_annulus, _, _, _ = sum_circann(captured["data"], x, y, 8., 12.)
    assert np.all(raw_aperture < 0)
    assert np.all(raw_annulus < 0)
