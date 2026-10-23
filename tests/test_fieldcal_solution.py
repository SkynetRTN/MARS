"""M2 scientific fits over the unchanged recorded Skynet calibration rows.

The original summaries and accepted-row flags remain historical evidence.
The corrected solver is checked against an independent two-parameter fit;
analytic synthetic cases live in test_photometric_calibration_science.py.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from algorithms.fieldcal.schemas import PhotometryData
from algorithms.fieldcal.solution import _sigma_eq, calc_solution

from .conftest import ZP_CASES
from .fieldcal_oracle import scientific_solution


def _sources(rows: list[dict]) -> list[PhotometryData]:
    return [
        PhotometryData(
            mag=r["mag"],
            mag_error=r["mag_error"],
            ref_mag=r["ref_mag"],
            ref_mag_error=r["ref_mag_error"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Recorded-solve parity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", ZP_CASES)
def test_recorded_rows_match_an_independent_scientific_solve(zp_case, case):
    rows, _ = zp_case(case)
    expected, keep = scientific_solution(_sources(rows))
    actual = calc_solution(_sources(rows))
    np.testing.assert_allclose(actual[:4], expected[:4], rtol=0, atol=1e-7)
    assert actual[4] == pytest.approx(expected[4], abs=1e-12)
    from tools.photometry_pipeline import _replicate_zero_point_rejection
    np.testing.assert_array_equal(_replicate_zero_point_rejection(_sources(rows)), keep)


@pytest.mark.parametrize("case", ZP_CASES)
def test_survivor_count_and_historical_record_are_reported_separately(zp_case, case):
    rows, summary = zp_case(case)
    n_in = len(rows)
    assert n_in == summary["num_candidates"]

    *_, rej_percent = calc_solution(_sources(rows))
    n_kept = round(n_in * (1 - rej_percent / 100))

    _, keep = scientific_solution(_sources(rows))
    assert n_kept == int(keep.sum())
    assert sum(r["accepted"] for r in rows) == summary["num_fit_accepted_sources"]


def test_rej_percent_counts_pre_fit_drops_not_just_chauvenet():
    from tools.photometry_pipeline import _replicate_zero_point_rejection

    offsets = [30, 19.999, 20.001, 20.002, 19.998, 20, 20.001, 24]
    sources = [PhotometryData(mag=15 + i / 10, mag_error=0 if i == 0 else 0.02,
                              ref_mag=15 + i / 10 + offset, ref_mag_error=0.01)
               for i, offset in enumerate(offsets)]
    assert calc_solution(sources)[4] == 25.0
    np.testing.assert_array_equal(_replicate_zero_point_rejection(sources),
                                  [False, True, True, True, True, True, True, False])


@pytest.mark.parametrize("case", ("ngc5286_b_000", "ngc5286_b_001", "ngc5286_b_002"))
def test_rejected_count_matches_when_nothing_is_pre_dropped(zp_case, case):
    """Where no row is pre-dropped, rejections account for the whole shortfall."""
    rows, summary = zp_case(case)
    assert all(r["mag_error"] for r in rows), "fixture should have no zero mag_error rows"

    n_in = len(rows)
    *_, rej_percent = calc_solution(_sources(rows))
    n_kept = round(n_in * (1 - rej_percent / 100))

    assert n_in - n_kept == summary["num_fit_rejected_sources"]


def test_case_zero_points_are_genuinely_different(zp_case):
    """Guard against the fixtures silently collapsing onto one another.

    The three NGC 5286 frames are the same field and span ~1.8 mag of zero
    point; NGC 5128 sits near 21 because Afterglow's convention offsets it. If a
    refactor ever made calc_solution ignore its input, several of the assertions
    above would still pass on a constant — this one would not.
    """
    zps = {case: calc_solution(_sources(zp_case(case)[0]))[0] for case in ZP_CASES}
    assert len(set(round(z, 6) for z in zps.values())) == len(ZP_CASES)
    assert max(zps.values()) - min(zps.values()) > 15.0


# ---------------------------------------------------------------------------
# Solver contract
# ---------------------------------------------------------------------------

def test_empty_source_list_returns_nan_and_full_rejection():
    """The documented empty case: four NaNs and 100% rejected, never a raise."""
    zp, zp_err, slop, limmag, rej = calc_solution([])
    assert all(math.isnan(v) for v in (zp, zp_err, slop, limmag))
    assert rej == 100.0


def test_zero_mag_errors_take_the_unweighted_branch():
    """With no per-source errors the fit is a plain mean, and limmag5 is NaN.

    ``no_errors`` is a whole separate arm of the solver: the offset becomes an
    unweighted mean, sigma comes from the n-1 denominator, and ``snr`` is never
    formed so no limiting magnitude can be derived. Upstream returns NaN there
    rather than 0, and callers test for it.
    """
    offsets = [0.10, -0.05, 0.02, -0.07, 0.00, 0.03]
    sources = [
        PhotometryData(mag=15.0, mag_error=0, ref_mag=15.0 + d, ref_mag_error=0)
        for d in offsets
    ]
    zp, zp_err, slop, limmag, rej = calc_solution(sources)

    assert zp == pytest.approx(float(np.mean(offsets)), rel=1e-12)
    assert math.isnan(limmag)
    assert rej == 0.0
    assert zp_err > 0 and slop > 0


def test_sources_with_nonpositive_mag_error_are_dropped_when_any_error_is_set():
    """A zero mag_error is a *filter*, not a weight, once any source has one.

    ``calc_solution`` computes SNR as ``1/(10**(mag_error/2.5) - 1)``, which
    divides by zero for ``mag_error == 0``. Upstream's guard is to drop those
    rows entirely — but only when at least one row carries an error, because an
    all-zero column means "this run has no errors at all". Getting this backwards
    would either crash on real data or silently weight junk rows.
    """
    good = [
        PhotometryData(mag=15.0 + i * 0.1, mag_error=0.02, ref_mag=16.0 + i * 0.1,
                       ref_mag_error=0.01)
        for i in range(8)
    ]
    poisoned = good + [
        PhotometryData(mag=15.0, mag_error=0, ref_mag=25.0, ref_mag_error=0)
    ]

    zp_good, *_ = calc_solution(good)
    zp_poisoned, _, _, _, rej = calc_solution(poisoned)

    # The 10-mag outlier would drag an unfiltered mean by ~1 mag.
    assert zp_poisoned == pytest.approx(zp_good, abs=1e-12)
    # Dropped before the fit — but still counted against the input list, because
    # rej_percent's denominator is len(sources) as passed in.
    assert rej == pytest.approx(100 / 9, abs=1e-9)


@pytest.mark.slow
def test_zero_scatter_input_has_no_cancellation_crash(frame_image):
    """Stable empirical errors remain nonnegative at the zero-scatter boundary.

    This tests the numerical solver; M3 still refuses degenerate calibration
    results before writing header keywords.
    """
    from algorithms.photometry.photometry import run_photometry
    from algorithms.photometry.schemas import (
        PhotometrySettings, SourceExtractionSettings,
    )
    from algorithms.photometry.source_extraction import run_source_extraction

    data, header = frame_image("ngc3628")
    detected, _, _ = run_source_extraction(
        np.array(data), header, SourceExtractionSettings(), file_id=1
    )
    measured = run_photometry(
        np.array(data), header, detected, PhotometrySettings(a=5.0, apcorr_tol=0.0)
    )
    # min_snr = 10 is the field-calibration default, i.e. mag_error <= 0.1.
    usable = [m for m in measured if m.mag is not None and m.mag_error and 1 / m.mag_error >= 10]
    assert len(usable) > 20

    exact = [
        PhotometryData(mag=m.mag, mag_error=m.mag_error,
                       ref_mag=m.mag + 21.0, ref_mag_error=0.02)
        for m in usable
    ]
    zero_point, error, scatter, _, _ = calc_solution(exact)
    assert zero_point == pytest.approx(21, abs=1e-12)
    assert math.isfinite(error) and error >= 0
    assert scatter == 0

    # The same sources with a whisker of catalog noise solve cleanly.
    rng = np.random.default_rng(20260811)
    noisy = [
        PhotometryData(mag=s.mag, mag_error=s.mag_error,
                       ref_mag=s.ref_mag + float(rng.normal(0, 0.02)),
                       ref_mag_error=s.ref_mag_error)
        for s in exact
    ]
    zp, _, _, _, _ = calc_solution(noisy)
    assert zp == pytest.approx(21.0, abs=0.03)


def test_single_source_yields_nan_error():
    """n < 2 has no degrees of freedom left for an uncertainty."""
    zp, zp_err, _, _, rej = calc_solution(
        [PhotometryData(mag=15.0, mag_error=0.01, ref_mag=16.25, ref_mag_error=0.01)]
    )
    assert zp == pytest.approx(1.25)
    assert math.isnan(zp_err)
    assert rej == 0.0


def test_outlier_is_rejected_and_does_not_move_the_zero_point():
    """A 2-mag outlier is rejected, leaving the offset where the clean fit put it.

    The rejection loop reruns Chauvenet until nothing more is flagged, so the
    count is not necessarily one — an outlier inflates sigma on the first pass
    and a couple of legitimate tail sources can go with it. What must hold is
    that something is rejected and the surviving zero point tracks the clean fit
    to well under the injected 2 mag.
    """
    rng = np.random.default_rng(20260811)
    sources = [
        PhotometryData(
            mag=float(m), mag_error=0.01,
            ref_mag=float(m) + 1.5 + float(rng.normal(0, 0.01)), ref_mag_error=0.005,
        )
        for m in np.linspace(13.0, 17.0, 19)
    ]
    clean_zp, *_ = calc_solution(sources)

    sources.append(
        PhotometryData(mag=15.0, mag_error=0.01, ref_mag=18.5, ref_mag_error=0.005)
    )
    zp, _, _, _, rej = calc_solution(sources)

    assert rej >= 100 / 20
    assert zp == pytest.approx(clean_zp, abs=1e-2)


def test_sigma_eq_signs_for_equal_measurement_errors():
    """The historical score helper changes sign across this equal-error root."""
    b = np.array([1.20, 1.31, 1.25, 1.18, 1.29])
    sigmas2 = np.full(5, 0.0004)
    m0 = float(b.mean())
    root = float(((b - m0) ** 2).sum() / len(b))

    assert _sigma_eq(root * 0.2, sigmas2, b, m0) > 0
    assert _sigma_eq(root * 5.0, sigmas2, b, m0) < 0


def test_ref_mag_error_absent_is_not_treated_as_zero_weight(zp_case):
    """Blank ``ref_mag_error`` cells must stay ``None`` through the schema.

    Roughly a third of the APASS rows in the recorded fits have no reference
    magnitude error. ``calc_solution`` folds that into ``sigmas2`` via
    ``getattr(source, "ref_mag_error", None) or 0``, i.e. missing behaves as
    zero *in the variance sum* while still counting as a usable source. If the
    CSV loader coerced blanks to 0.0 the arithmetic would agree, but if anything
    ever coerced them to NaN the whole fit would go NaN — so assert the fixtures
    really do carry the missing values.
    """
    rows, _ = zp_case("ngc5286_b_000")
    assert any(r["ref_mag_error"] is None for r in rows)
    assert all(r["mag_error"] is not None for r in rows)

    zp, *_ = calc_solution(_sources(rows))
    assert math.isfinite(zp)
