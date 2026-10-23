"""Independent scientific reference for corrected M2 recorded-row solves.

Optimize mean and variance together, rather than profiling/bracketing the
production variance score. Tail probabilities come from SciPy, not the
vendored Chauvenet kernel. Historical Skynet fixtures remain unchanged.
"""

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm


def scientific_solution(sources):
    def value(source, name):
        return (source.get(name) if isinstance(source, dict) else getattr(source, name)) or 0

    rows = np.array([[value(s, name) for name in
                      ("mag", "mag_error", "ref_mag", "ref_mag_error")] for s in sources])
    keep = rows[:, 1] > 0 if rows[:, 1].any() else np.ones(len(rows), dtype=bool)
    while True:
        mag, err, ref, ref_err = rows[keep].T
        offset = ref - mag
        known = err**2 + ref_err**2
        if known.any():
            # Dimensionless parameters keep the independent 2D optimizer well
            # conditioned for both ~1 and ~20 magnitude zero points.
            origin = offset.mean()
            scale = max(float(offset.std()), float(np.sqrt(known).max()), 1e-6)
            y, v = (offset - origin) / scale, known / scale**2

            def objective(parameters):
                mean, extra = parameters
                total = v + extra
                return 0.5 * np.sum(np.log(total) + (y - mean)**2 / total)

            boundary_mean = np.average(y, weights=1 / v)
            candidates = [np.array([boundary_mean, 0.0])]
            for start in ([0, 1], [np.median(y), 0.1], [boundary_mean, 0.001]):
                fit = minimize(objective, start, method="Nelder-Mead",
                               bounds=[(None, None), (0, None)],
                               options={"xatol": 1e-11, "fatol": 1e-12, "maxiter": 3000})
                assert fit.success, fit.message
                candidates.append(fit.x)
            mean, extra = min(candidates, key=objective)
            zero_point = origin + mean * scale
            variance = extra * scale**2
            z = np.abs(offset - zero_point) / np.sqrt(known + variance)
        else:
            zero_point, variance = offset.mean(), offset.var()
            sigma = offset.std(ddof=1)
            z = np.abs(offset - zero_point) / sigma if sigma else np.zeros(len(offset))

        # Two-sided Gaussian tail < 1/(2*N), retaining at least two rows.
        rejected = z > norm.isf(0.25 / len(offset))
        if len(offset) <= 2 or not rejected.any() or (~rejected).sum() < 2:
            break
        keep[np.flatnonzero(keep)[rejected]] = False

    n = len(offset)
    residual = offset - zero_point
    if known.any():
        weights = 1 / (known + variance)
        error = np.sqrt(n / (n - 1) * np.sum(weights**2 * residual**2) / weights.sum()**2)
    else:
        error = offset.std(ddof=1) / np.sqrt(n)
    limiting = np.nan
    if err.any():
        log_snr = np.log10(1 / (10**(err / 2.5) - 1))
        slope, intercept = np.linalg.lstsq(np.c_[mag + zero_point, np.ones(n)], log_snr,
                                         rcond=None)[0]
        limiting = (np.log10(5) - intercept) / slope
    return (zero_point, error, np.sqrt(variance), limiting, 100 * (1 - n / len(rows))), keep
