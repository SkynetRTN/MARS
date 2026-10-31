"""Zero-point solution: weighted mean magnitude offset with Chauvenet rejection.

EXTRACTED FROM: skynet/packages/py/skynet-db/skynet_db/runners/utils.py
lines 468-603 (``_sigma_eq``, ``calc_solution``). M2 corrects the nonnegative
scatter boundary and small-sample rejection, and exposes an internal fit mask
for diagnostics while preserving the five-value public return.

``skynet_db/runners/utils.py`` is a 907-line grab-bag (S3 download helpers,
FITS product writers, VizieR cache pruning, header parsing, WCS box helpers,
DB session plumbing).  Only the zero-point solver lives here; the reference
magnitude resolver from the same file lives in ``ref_mag.py``.
"""
from __future__ import annotations

import logging

import numpy as np
from algorithms.diagnostics import note_numerical_issue
from numpy import transpose

# EXTRACTED: was `from skylib.util.stats import chauvenet` (installed skylib
# package) — now the shared vendored copy under algorithms.skylib_lite.
# ``chauvenet`` is the outlier-rejection kernel of this solver; it is
# numba-jitted and numba is a hard runtime dependency, not an optional
# accelerator.
from algorithms.skylib_lite.util.stats import chauvenet

from .schemas import PhotometryData

__all__ = ["calc_solution"]

logger = logging.getLogger(__name__)


# util.py (keep/ensure these exist)
def _sigma_eq(sigma2, sigmas2, b, m0):
    w = 1.0 / (sigmas2 + sigma2)
    return (((b - m0) ** 2 * w - 1) * w).sum()


def _fit_offset_and_scatter(b, sigmas2):
    """Profile the Gaussian likelihood over nonnegative additional variance.

    Compare zero with positive local minima found by score bracketing on a
    logarithmic variance grid. A nonpositive boundary score alone does not
    exclude a better interior minimum for heterogeneous measurement errors.
    """
    from scipy.optimize import brenth

    if not np.isfinite(sigmas2).all() or np.any(sigmas2 <= 0):
        raise ValueError("Weighted calibration needs positive finite total measurement variances")
    centered = b - b[0]

    def profile(variance):
        total = sigmas2 + variance
        weights = np.min(total) / total
        mean = float(np.sum(centered * weights) / np.sum(weights))
        residual = centered - mean
        likelihood = float(np.sum(np.log(total) + residual**2 / total))
        # A positive scaling of the likelihood score avoids squared weights.
        score = float(np.sum((residual**2 / total - 1) * weights))
        return mean, likelihood, score

    upper = float(np.ptp(centered)**2)
    if not np.isfinite(upper):
        raise ValueError("Calibration residual variance must remain finite")
    candidates = [0.0]
    if upper:
        lower = max(np.nextafter(0.0, 1.0), min(float(np.min(sigmas2)) * 1e-3, upper * 1e-6))
        grid = np.unique(np.r_[0.0, np.geomspace(lower, upper, 128),
                               sigmas2[sigmas2 < upper]])
        previous, previous_score = grid[0], profile(grid[0])[2]
        for variance in grid[1:]:
            score = profile(variance)[2]
            if previous_score > 0 and score <= 0:
                root = brenth(lambda value: profile(value)[2], previous, variance,
                              xtol=np.nextafter(0.0, 1.0), rtol=4 * np.finfo(float).eps)
                candidates.append(root)
            previous, previous_score = variance, score
        candidates.append(upper)
    variance = min(candidates, key=lambda value: profile(value)[1])
    mean = profile(variance)[0]
    return b[0] + mean, variance


def calc_solution(sources: list[PhotometryData]):
    return _calc_solution_with_mask(sources)[0]


def _fit_input_mask(sources: list[PhotometryData]) -> np.ndarray:
    """The rows the fit starts from, before any outlier rejection.

    Once any star carries an instrumental error, a star without a positive one
    is dropped here: it is never weighed, so it is not an outlier the fit
    rejected. Without instrumental errors every row enters. MARS: factored out
    of ``_calc_solution_with_mask`` so the diagnostic plot can tell the two
    apart; the rule is unchanged.
    """
    mag_errors = np.array(
        [getattr(source, "mag_error", None) or 0 for source in sources], dtype=float
    )
    return mag_errors > 0 if mag_errors.any() else np.ones(len(sources), dtype=bool)


def _calc_solution_with_mask(sources: list[PhotometryData]):
    """Return the legacy summary and the exact surviving input-row mask.

    Extra variance is nonnegative; measurement errors can explain all scatter.
    The zero-point error retains the empirical weighted-mean scatter estimator.
    It is not a propagated catalog-systematic error or a confidence interval.
    """
    from math import sqrt

    if not sources:
        return (np.nan, np.nan, np.nan, np.nan, 100.0), np.zeros(0, dtype=bool)

    mags, mag_errors, ref_mags, ref_mag_errors = transpose([
        (
            source.mag,
            getattr(source, "mag_error", None) or 0,
            source.ref_mag,
            getattr(source, "ref_mag_error", None) or 0,
        )
        for source in sources
    ])

    logger.debug("calc_solution: starting with %d sources", len(sources))
    indices = np.arange(len(sources))
    if mag_errors.any():
        good = _fit_input_mask(sources)
        indices = indices[good]
        mags = mags[good]
        mag_errors = mag_errors[good]
        ref_mags = ref_mags[good]
        ref_mag_errors = ref_mag_errors[good]
        snr = 1 / (10 ** (mag_errors / 2.5) - 1)
        logger.debug("calc_solution: kept %d sources after mag_error>0 filter", len(mags))
    else:
        snr = None

    b = ref_mags - mags
    if not len(b):
        return (np.nan, np.nan, np.nan, np.nan, 100.0), np.zeros(len(sources), dtype=bool)
    sigmas2 = mag_errors**2 + ref_mag_errors**2
    no_errors = not sigmas2.any()
    if no_errors:
        sigmas2 = 0
    sigma2 = 0
    weights = None

    iteration = 0
    while True:
        if no_errors:
            m0 = b[0] + (b - b[0]).mean()
            sigma2 = float(np.mean((b - m0) ** 2))
        else:
            m0, sigma2 = _fit_offset_and_scatter(b, sigmas2)
            weights = 1 / (sigmas2 + sigma2)
        if len(b) <= 2:
            break

        if no_errors:
            denom = len(b) - 1
            sigma_override = sqrt(((b - m0) ** 2).sum() / denom) if denom > 0 else float("inf")
            rejected = chauvenet(
                b, mean_override=m0, sigma_override=sigma_override, min_vals=2, max_iter=1
            )[0]
        else:
            # Each residual is measured against its own known error plus the
            # fitted extra scatter. An imprecise star is not a strong outlier
            # merely because it differs from a very precise star.
            standardized = (b - m0) / np.sqrt(sigmas2 + sigma2)
            rejected = chauvenet(
                standardized, mean_override=0.0, sigma_override=1.0, min_vals=2, max_iter=1
            )[0]
        iteration += 1
        logger.debug(
            "calc_solution: iteration=%d rejected=%d remaining=%d",
            iteration,
            int(rejected.sum()),
            int((~rejected).sum()),
        )
        if not rejected.any() or int((~rejected).sum()) < 2:
            break

        good = ~rejected
        indices = indices[good]
        mags = mags[good]
        if snr is not None:
            snr = snr[good]
        b = b[good]
        if weights is not None:
            weights = weights[good]
        if not no_errors:
            sigmas2 = sigmas2[good]

    n = len(b)
    if n > 1:
        if weights is None:
            m0_error = sqrt(((b - m0) ** 2).sum() / n / (n - 1))
        else:
            sum_weights = weights.sum()
            # Algebraically the original sandwich expression, evaluated on
            # residuals to avoid subtracting nearly equal large terms.
            m0_error = sqrt(n / (n - 1)) * np.linalg.norm((weights / sum_weights) * (b - m0))
    else:
        m0_error = np.nan

    limmag = np.nan
    if snr is not None:
        note_numerical_issue("limiting_magnitude_unvalidated",
            "The retained 5-sigma limiting-magnitude estimate uses an unvalidated log-SNR line "
            "extrapolation. Near-flat fits can yield implausible limits; this is not a measured "
            "detection-completeness limit.")
        calibrated_mags = mags + m0
        rank = 0
        if len(calibrated_mags) > 1 and np.any(calibrated_mags != calibrated_mags[0]):
            (limmag_a, limmag_b), _, rank, _, _ = np.polyfit(calibrated_mags, np.log10(snr), 1, full=True)
            if rank == 2 and limmag_a:
                limmag = (np.log10(5) - limmag_b) / limmag_a
        if rank < 2:
            note_numerical_issue("limiting_magnitude_unidentifiable",
                "The calibration stars do not span independently resolvable magnitudes for "
                "the log-SNR line. No limiting magnitude can be inferred from this sample.")

    if n:
        resid = b - m0
        logger.debug(
            "calc_solution: residual stats n=%d min=%s max=%s median=%s",
            n,
            float(np.min(resid)),
            float(np.max(resid)),
            float(np.median(resid)),
        )

    kept = np.zeros(len(sources), dtype=bool)
    kept[indices] = True
    summary = m0, m0_error, sqrt(sigma2), limmag, (1 - len(b) / len(sources)) * 100
    return summary, kept
