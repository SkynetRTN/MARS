"""Error-weighted variable-star Lomb--Scargle computation.

# PORTED: git-history:algorithms/periodogram/core/lomb-scargle.ts::lombScargleWithError
# PORTED: git-history:algorithms/periodogram/variable/variable-periodogram.compute.ts
"""

from __future__ import annotations

from math import atan2, cos, exp, inf, isfinite, log, nan, pi, sin
from numbers import Integral
from typing import Sequence

from algorithms.variable_star.lightcurve import VariableDataRow, differential_data


# First-party acceptance bounds; the extracted weighted formula stays unchanged.
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


def _validate_weights(errors: Sequence[float]) -> None:
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


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _variance(values: Sequence[float]) -> float:
    mean = _mean(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _error_mean(values: Sequence[float], errors: Sequence[float]) -> float:
    weights = [1 / error**2 for error in errors]
    return sum(value * weight for value, weight in zip(values, weights, strict=True)) / sum(weights)


def _error_dot(left: Sequence[float], errors: Sequence[float], right: Sequence[float]) -> float:
    weights = [1 / error**2 for error in errors]
    products = [a * b for a, b in zip(left, right, strict=True)]
    return sum(value * weight for value, weight in zip(products, weights, strict=True)) / sum(weights)


def _ieee_divide(numerator: float, denominator: float) -> float:
    """Match JavaScript number division where Python would raise on zero."""
    if denominator != 0:
        return numerator / denominator
    if numerator == 0:
        return nan
    return inf if numerator > 0 else -inf


def lomb_scargle_with_error(
    times: Sequence[float],
    values: Sequence[float],
    errors: Sequence[float],
    start: float,
    stop: float,
    steps: int = 1000,
) -> list[tuple[float, float]]:
    """Return the exact error-weighted, logarithmic-period spectrum.

    Finite, aligned inputs must fit the bounded sample/grid work budget.
    Accepted inputs retain TypeScript arithmetic, including constant-series NaN.
    """
    if len(times) != len(values) or len(times) != len(errors):
        raise ValueError("Dimension mismatch between time, value and uncertainty arrays.")
    _validate_work(len(times), steps)
    step = validate_periodogram_grid(start, stop, steps)
    for time, value in zip(times, values, strict=True):
        _finite(time, "time")
        _finite(value, "value")
    _validate_weights(errors)
    try:
        residue_mean = _error_mean(values, errors)
        _finite(residue_mean, "weighted mean")
        residues = [value - residue_mean for value in values]
        for residue in residues:
            _finite(residue, "residue")
        two_variance = 2 * _variance(values)
        _finite(two_variance, "twice the variance")
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("weighted normalization is not representable.") from exc
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
        two_omega_times = [2 * omega * value for value in times]
        for value in two_omega_times:
            _finite(value, "trial frequency-time product")
        tau = atan2(sum(sin(value) for value in two_omega_times), sum(cos(value) for value in two_omega_times)) / (2 * omega)
        shifted = [omega * (value - tau) for value in times]
        for value in shifted:
            _finite(value, "shifted trial time")
        cos_values = [cos(value) for value in shifted]
        sin_values = [sin(value) for value in shifted]
        try:
            power = _ieee_divide(
                _ieee_divide(
                    _error_dot(residues, errors, cos_values) ** 2,
                    sum(value * value for value in cos_values),
                )
                + _ieee_divide(
                    _error_dot(residues, errors, sin_values) ** 2,
                    sum(value * value for value in sin_values),
                ),
                two_variance,
            )
        except OverflowError as exc:
            raise ValueError("weighted trial power is not representable.") from exc
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
