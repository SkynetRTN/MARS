"""Error-weighted variable-star Lomb--Scargle computation.

# PORTED: git-history:algorithms/periodogram/core/lomb-scargle.ts::lombScargleWithError
# PORTED: git-history:algorithms/periodogram/variable/variable-periodogram.compute.ts
"""

from __future__ import annotations

from math import exp, isfinite, log, pi
from numbers import Integral
from typing import Sequence

import numpy as np

from algorithms.variable_star.lightcurve import VariableDataRow, differential_data


# First-party acceptance bounds around the M2 weighted least-squares correction.
DEFAULT_STEPS = 2_000
MAX_PERIODOGRAM_SAMPLES = 2_000
MAX_PERIODOGRAM_STEPS = 200_000
MAX_PERIODOGRAM_WORK = 20_000_000


def _finite(value: float, name: str, *, positive: bool = False) -> None:
    try:
        valid = isfinite(value) and (not positive or value > 0)
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        qualifier = "finite and positive" if positive else "finite"
        raise ValueError(f"{name} must be {qualifier}.")


def _validate_work(samples: int, steps: int) -> None:
    if not isinstance(steps, Integral) or isinstance(steps, bool) or not 1 <= steps <= MAX_PERIODOGRAM_STEPS:
        raise ValueError(f"steps must be an integer between 1 and {MAX_PERIODOGRAM_STEPS}.")
    if not 1 <= samples <= MAX_PERIODOGRAM_SAMPLES:
        raise ValueError(f"periodogram requires 1 to {MAX_PERIODOGRAM_SAMPLES} samples.")
    if samples * (steps + 1) > MAX_PERIODOGRAM_WORK:
        raise ValueError(f"periodogram exceeds the {MAX_PERIODOGRAM_WORK} sample-grid work limit.")


def validate_periodogram_grid(start: float, stop: float, steps: int = DEFAULT_STEPS) -> float:
    """Validate the original accumulating grid, including float-drift endpoints."""
    _validate_work(1, steps)
    _finite(start, "start_period", positive=True)
    _finite(stop, "end_period", positive=True)
    if stop <= start:
        raise ValueError("end_period must exceed start_period.")
    step = (stop - start) / steps
    if not isfinite(step) or step <= 0:
        raise ValueError("period range must have a representable positive step.")
    if start + step <= start:
        raise ValueError("period range step must advance start_period.")
    value = start
    for _ in range(steps + 1):
        next_value = value + step
        if not isfinite(next_value) or next_value <= value:
            raise ValueError("period range step must advance every grid point finitely.")
        value = next_value
        if value >= stop:
            return step
    raise ValueError("period range exceeds the bounded grid iteration count.")


def _validate_weights(errors: Sequence[float]) -> np.ndarray:
    weights = []
    for error in errors:
        _finite(error, "uncertainty", positive=True)
        try:
            weight = 1 / error**2
        except (OverflowError, ZeroDivisionError) as exc:
            raise ValueError("uncertainty must yield a representable positive weight.") from exc
        _finite(weight, "uncertainty weight", positive=True)
        weights.append(weight)
    _finite(sum(weights), "total uncertainty weight", positive=True)
    return np.asarray(weights) / sum(weights)


def _error_mean(values: Sequence[float], errors: Sequence[float]) -> float:
    weights = [1 / error**2 for error in errors]
    return sum(value * weight for value, weight in zip(values, weights, strict=True)) / sum(weights)


def lomb_scargle_with_error(
    times: Sequence[float],
    values: Sequence[float],
    errors: Sequence[float],
    start: float,
    stop: float,
    steps: int = 1000,
) -> list[tuple[float, float]]:
    """Weighted floating-mean LS with standard dimensionless power in [0, 1].

    Finite, aligned inputs must fit the bounded sample/grid work budget.
    M2 corrects the weighted formula; the accumulating logarithmic-period grid
    is preserved. M3 rejects constant series and nonfinite trial powers with
    ValueError rather than returning undefined spectra.
    """
    if len(times) != len(values) or len(times) != len(errors):
        raise ValueError("Dimension mismatch between time, value and uncertainty arrays.")
    _validate_work(len(times), steps)
    step = validate_periodogram_grid(start, stop, steps)
    for time, value in zip(times, values, strict=True):
        _finite(time, "time")
        _finite(value, "value")
    weights = _validate_weights(errors)
    try:
        # Center relative to an observed value before averaging. This avoids
        # inventing variance in exact constants or losing a small signal to a
        # rounded large absolute weighted mean.
        offsets = [float(value) - float(values[0]) for value in values]
        for offset in offsets:
            _finite(offset, "value offset")
        # Standard power is a ratio: remove a common amplitude before means
        # and squared energies, avoiding both subnormal loss and overflow.
        amplitude = max(abs(offset) for offset in offsets)
        if amplitude:
            offsets = [offset / amplitude for offset in offsets]
        residue_mean = _error_mean(offsets, errors)
        _finite(residue_mean, "weighted mean")
        residues = [value - residue_mean for value in offsets]
        for residue in residues:
            _finite(residue, "residue")
        variance = sum(float(weight) * residue**2 for weight, residue in zip(weights, residues, strict=True))
        _finite(variance, "weighted variance")
        if variance == 0 and any(residue != 0 for residue in residues):
            raise ValueError("weighted variance is not representable.")
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("weighted normalization is not representable.") from exc
    if variance == 0:
        raise ValueError("A constant series has no variance; its periodogram is undefined.")
    root_weights = np.sqrt(weights)
    response = root_weights * residues
    with np.errstate(over="ignore", invalid="ignore"):
        relative_times = np.asarray(times, dtype=float) - times[0]
    if not np.isfinite(relative_times).all():
        raise ValueError("relative times must remain finite.")
    result: list[tuple[float, float]] = []
    x_value = start
    index = 0
    while x_value < stop:
        if index >= steps + 1:
            raise ValueError("period range exceeds the bounded grid iteration count.")
        period = exp(log(start) + (log(stop) - log(start)) * index / steps)
        _finite(period, "trial period", positive=True)
        omega = 2 * pi / period
        _finite(2 * omega, "trial angular frequency", positive=True)
        with np.errstate(over="ignore", invalid="ignore"):
            angles = omega * relative_times
        if not np.isfinite(angles).all():
            raise ValueError("trial frequency-time products must remain finite.")
        columns = np.column_stack((np.cos(angles), np.sin(angles)))
        # Weighted centering eliminates the fitted offset. Use the same weights
        # for response, model columns and reference variance.
        columns -= weights @ columns
        design = root_weights[:, None] * columns
        try:
            basis, singular_values, _ = np.linalg.svd(design, full_matrices=False)
            # The uncentered intercept has norm one. Include the phase-formation
            # error scale as well as the SVD backward-error scale, so collapsed
            # aliases are not fitted through phase-roundoff columns. This is an
            # estimated resolution policy, not a certified error enclosure.
            cutoff = np.finfo(float).eps * (max(len(times), 3) + float(np.max(np.abs(angles))))
            projection = basis[:, singular_values > cutoff].T @ response
            power = float(projection @ projection) / variance
        except (OverflowError, np.linalg.LinAlgError) as exc:
            raise ValueError("weighted trial power is not representable.") from exc
        if not isfinite(power):
            raise ValueError(f"weighted trial power at period {period!r} is not finite.")
        power = min(1., max(0., power))
        result.append((period, power))
        next_value = x_value + step
        if not isfinite(next_value) or next_value <= x_value:
            raise ValueError("period range step must advance every grid point finitely.")
        x_value = next_value
        index += 1
    return result


def variable_periodogram(
    rows: Sequence[VariableDataRow],
    variable_star: str,
    reference_star_magnitude: float,
    start: float,
    stop: float,
) -> list[tuple[float, float]]:
    """Compute the fixed grid from paired rows with aligned uncertainties."""
    _validate_work(len(rows), DEFAULT_STEPS)
    _finite(reference_star_magnitude, "reference_star_magnitude")
    paired = [
        row for row in rows
        if row.jd is not None and row.source1 is not None and row.source2 is not None
    ]
    if any(row.error_mse is None for row in paired):
        raise ValueError("Every paired observation requires a combined uncertainty (error_mse).")
    data = differential_data(paired, variable_star, reference_star_magnitude)
    errors = [row.error_mse for row in paired]
    return lomb_scargle_with_error(
        [row[0] for row in data], [row[1] for row in data], errors, start, stop, DEFAULT_STEPS
    )
