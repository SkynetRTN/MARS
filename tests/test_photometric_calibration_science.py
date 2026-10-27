"""M2 calibration selection, scatter and small-sample rejection, offline."""

import warnings

import numpy as np
import pytest
from astropy.io import fits

from algorithms.catalogs.schemas import CatalogSource, Mag
from algorithms.fieldcal.field_cal import _match_detected_sources, perform_field_calibration
from algorithms.fieldcal.schemas import PhotometricCalibrationSettings, PhotometryData, SourceExtractionData
from algorithms.fieldcal.solution import calc_solution
from tools.photometry_pipeline import _replicate_zero_point_rejection


@pytest.mark.parametrize("step", [0., np.spacing(15.)])
def test_rank_deficient_snr_line_keeps_zero_point_but_withholds_limiting_magnitude(step):
    from tools.calibration import solve_zeropoint_from_measurements

    rows = [{"mag": 15. + i * step, "ref_mag": 15. + i * step + offset,
             "mag_error": .03, "ref_mag_error": .02}
            for i, offset in enumerate([1.23, 1.24, 1.26, 1.27])]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = solve_zeropoint_from_measurements(rows, [])
    assert result.errors == []
    assert result.zero_point == pytest.approx(1.25)
    assert result.zero_point_error_mag == pytest.approx(.00912870929175277)
    assert result.limmag5 is None
    assert "limiting_magnitude_unidentifiable" in {warning.code for warning in result.warnings}


def _measurements(offsets, errors=0.02, reference_error=0.01):
    errors = np.broadcast_to(errors, (len(offsets),))
    return [PhotometryData(id=str(i), mag=15 + i * 0.1, mag_error=float(error),
                           ref_mag=15 + i * 0.1 + float(offset), ref_mag_error=reference_error)
            for i, (offset, error) in enumerate(zip(offsets, errors))]


@pytest.mark.parametrize("count", range(5, 11))
@pytest.mark.parametrize("with_errors", [False, True])
def test_small_calibrations_reject_a_planted_outlier(count, with_errors):
    offsets = np.r_[20 + np.linspace(-0.001, 0.001, count - 1), 24.0]
    sources = _measurements(offsets, errors=0.02 if with_errors else 0,
                            reference_error=0.01 if with_errors else 0)
    zero_point, error, scatter, _, rejected = calc_solution(sources)
    assert zero_point == pytest.approx(20, abs=1e-10)
    assert rejected == pytest.approx(100 / count, abs=1e-10)
    assert error > 0 and scatter >= 0
    np.testing.assert_array_equal(_replicate_zero_point_rejection(sources),
                                  [True] * (count - 1) + [False])


def test_measurement_errors_can_explain_all_the_scatter():
    offsets = np.array([19.98, 19.99, 20.00, 20.01, 20.02, 20.015])
    result = calc_solution(_measurements(offsets, errors=0.05, reference_error=0.03))
    assert result[0] == pytest.approx(float(np.mean(offsets)), abs=1e-12)
    assert result[2] == 0.0
    assert result[4] == 0.0


@pytest.mark.parametrize("count", [3, 4])
def test_tiny_weighted_calibrations_can_reject_without_leaving_a_singleton(count):
    sources = _measurements([20 + i * 0.001 for i in range(count - 1)] + [24])
    assert calc_solution(sources)[4] == pytest.approx(100 / count)
    np.testing.assert_array_equal(_replicate_zero_point_rejection(sources),
                                  [True] * (count - 1) + [False])


def test_an_imprecise_star_is_not_rejected_for_its_raw_residual():
    offsets = np.r_[20 + np.linspace(-0.01, 0.01, 6), 23]
    errors = np.r_[np.full(6, 0.02), 3]
    result = calc_solution(_measurements(offsets, errors=errors, reference_error=0))
    assert result[0] == pytest.approx(np.average(offsets, weights=1 / errors**2), abs=1e-12)
    assert result[2] == 0
    assert result[4] == 0
    assert _replicate_zero_point_rejection(
        _measurements(offsets, errors=errors, reference_error=0)).all()


def test_zero_extra_scatter_keeps_the_measurement_error_weights():
    offsets = np.array([20.001, 19.999, 20.002, 20.0, 19.998, 20.001])
    errors = np.array([0.02, 0.03, 0.04, 0.05, 0.06, 0.08])
    # Independent fixed-slope WLS normal equation at the zero-variance boundary.
    weights = 1 / (errors**2 + 0.01**2)
    expected = float(np.sum(weights * offsets) / np.sum(weights))
    result = calc_solution(_measurements(offsets, errors=errors))
    assert result[0] == pytest.approx(expected, abs=1e-12)
    assert result[2] == 0.0


def test_equal_errors_have_the_analytic_positive_intrinsic_variance():
    sources = _measurements([19.9, 20.1] * 3)
    result = calc_solution(sources)
    # Population residual variance .01 minus measurement variance .0005.
    assert result[0] == pytest.approx(20.0, abs=1e-12)
    assert result[2] == pytest.approx(np.sqrt(0.0095), rel=1e-10)
    assert result[4] == 0


def test_a_zero_boundary_score_does_not_hide_a_better_positive_scatter_fit():
    from scipy.optimize import minimize

    offsets = np.array([20.0, 19.0, 19.5, 20.5, 21.0, 21.5])
    errors = np.array([1e-6, 0.1, 0.1, 0.1, 0.1, 0.1])

    def negative_log_likelihood(parameters):
        mean, variance = parameters
        total = errors**2 + variance
        return 0.5 * np.sum(np.log(total) + (offsets - mean)**2 / total)

    independent = minimize(negative_log_likelihood, [20.25, 0.7], method="Nelder-Mead",
                           bounds=[(None, None), (0, None)],
                           options={"xatol": 1e-10, "fatol": 1e-10})
    assert independent.success
    result = calc_solution(_measurements(offsets, errors=errors, reference_error=0))
    assert result[0] == pytest.approx(independent.x[0], abs=1e-7)
    assert result[2] == pytest.approx(np.sqrt(independent.x[1]), rel=1e-6)
    assert result[4] == 0


@pytest.mark.parametrize("max_stars", [0, 2])
def test_saturation_is_filtered_before_brightness_trimming_and_zero_mag_is_valid(max_stars):
    rows = [CatalogSource(id=str(i), catalog_name="APASS", x=2 + i, y=3,
                          mag=reference - 20 + jitter, mag_error=0.02,
                          mags={"V": Mag(value=reference, error=0.01)}, sat_pixels=saturated)
            for i, (reference, jitter, saturated) in enumerate([
                (0.0, -0.01, 0), (1.0, 0.01, 0), (-2.0, 1.0, 3), (2.0, 0.002, 0),
            ])]
    header = fits.Header({"FILTER": "V"})
    _, result = perform_field_calibration(
        header, np.zeros((10, 10)), catalog_sources=rows, use_provided_photometry=True,
        field_cal_settings=PhotometricCalibrationSettings(
            catalogs=["APASS"], variable_check_tol=0, min_snr=0, max_stars=max_stars),
    )
    expected_ids = ["0", "1"] if max_stars else ["0", "1", "3"]
    assert [source.id for source in result.phot_results] == expected_ids
    assert result.zero_point_corr == pytest.approx(20, abs=0.01)
    assert header["PHOT_M0"] == result.zero_point_corr


def test_catalog_zero_saturation_does_not_erase_a_saturated_detection():
    catalog = CatalogSource(id="star", catalog_name="APASS", ra_hours=10, dec_degs=-30,
                            mags={"V": Mag(value=12)}, sat_pixels=0)
    detection = SourceExtractionData(id="detected", x=5, y=5, ra_hours=10, dec_degs=-30,
                                     sat_pixels=7)
    (matched,) = _match_detected_sources(
        [catalog], [detection], wcs=None, header={}, data=np.zeros((10, 10)), source_match_tol=1,
    )
    assert matched.sat_pixels > 0
