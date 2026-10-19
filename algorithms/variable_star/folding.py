"""Variable-star period folding with upstream row and display semantics.

# PORTED: git-history:algorithms/lightcurve/variable/variable-lightcurve.algorithms.ts
# PORTED: git-history:algorithms/lightcurve/variable/variable-period-folding.algorithms.ts
"""

from __future__ import annotations

import math
from typing import Sequence

from algorithms.variable_star.lightcurve import (
    VariableDataRow,
    differential_data,
    differential_errors,
    jd_range,
)


# First-party TS-02 acceptance bounds, not changes to the folding formula.
MAX_FOLD_SAMPLES = 2_000
MAX_FOLD_ITERATIONS = 100_000
MAX_FOLD_OPERATIONS = 10_000_000


def _finite(value: float, name: str, *, positive: bool = False) -> None:
    try:
        valid = math.isfinite(value) and (not positive or value > 0)
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        qualifier = "finite and positive" if positive else "finite"
        raise ValueError(f"{name} must be {qualifier}.")


def validate_fold_work(period: float, times: Sequence[float]) -> None:
    """Validate direct/tool folding work before repeated subtraction starts."""
    _finite(period, "period", positive=True)
    if not len(times):
        raise ValueError("light-curve artifact contains no rows.")
    if len(times) > MAX_FOLD_SAMPLES:
        raise ValueError(f"fold exceeds the {MAX_FOLD_SAMPLES}-sample limit.")
    for time in times:
        _finite(time, "fold time")
    baseline = max(times) - min(times)
    _finite(baseline, "observation baseline")
    cycles = baseline / period
    if not math.isfinite(cycles):
        raise ValueError("period is too small to fold representably over this observation.")
    if (cycles > MAX_FOLD_ITERATIONS
            or (math.ceil(cycles) + 1) * len(times) > MAX_FOLD_OPERATIONS):
        raise ValueError("period exceeds the fold work limit for this observation.")


def _float_mod(value: float, modulus: float) -> float:
    """Keep the TypeScript strict ``>`` loop for finite, bounded inputs."""
    _finite(value, "fold value")
    _finite(modulus, "modulus", positive=True)
    cycles = max(0., value) / modulus
    if not math.isfinite(cycles) or cycles > MAX_FOLD_ITERATIONS:
        raise ValueError("modulo exceeds the fold iteration limit.")
    iterations = 0
    while value > modulus:
        iterations += 1
        if iterations > MAX_FOLD_ITERATIONS:
            raise ValueError("modulo exceeds the fold iteration limit.")
        value -= modulus
    return value


def fold_with_error(
    rows: Sequence[VariableDataRow],
    variable_star: str,
    reference_star_magnitude: float,
    *,
    period: float = -1,
    phase: float = 0.0,
    display_periods: int = 2,
) -> tuple[list[tuple[float, float]], list[tuple[float, float, float]]]:
    """Fold differential data and error bars exactly as the variable service.

    The intentionally separate filters retain the original index-alignment
    fragility when a paired row has no combined error.
    """
    if variable_star == "none":
        return [], []
    if len(rows) > MAX_FOLD_SAMPLES:
        raise ValueError(f"fold exceeds the {MAX_FOLD_SAMPLES}-sample limit.")
    _finite(period, "period")  # negative means use the upstream JD baseline
    _finite(phase, "phase")
    data = sorted(differential_data(rows, variable_star, reference_star_magnitude))
    errors = sorted(differential_errors(rows, variable_star, reference_star_magnitude))
    chosen_period = jd_range(rows) if period < 0 else period
    folded_data: list[tuple[float, float]] = []
    folded_errors: list[tuple[float, float, float]] = []
    if chosen_period != 0:
        min_jd = data[0][0]
        validate_fold_work(chosen_period, [row[0] for row in data])
        _finite(phase * chosen_period, "phase shift")
        for index, (jd, magnitude) in enumerate(data):
            x = phase * chosen_period + _float_mod(jd - min_jd, chosen_period)
            _finite(x, "fold phase")
            if x > chosen_period:
                x -= chosen_period
            error = errors[index]
            folded_data.append((x, magnitude))
            folded_errors.append((x, error[1], error[2]))
            if display_periods == 2:
                _finite(x + chosen_period, "duplicated fold phase")
                folded_data.append((x + chosen_period, magnitude))
                folded_errors.append((x + chosen_period, error[1], error[2]))
    return (
        sorted(folded_data, key=lambda row: row[0], reverse=True),
        sorted(folded_errors, key=lambda row: row[0], reverse=True),
    )


def get_period_step(period_folding_period: float, observation_range: float) -> float:
    """Return the folding-slider step from the extracted form component."""
    value = period_folding_period**2 * 0.01 / observation_range
    return float(f"{value:.4f}") if value > 10e-6 else 10e-6
