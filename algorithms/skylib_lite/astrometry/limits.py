"""First-party WCS-02 attempt limits; not a whole-solve wall-clock budget."""

from __future__ import annotations

import math

DEFAULT_SOLVER_TIMEOUT_S = 300.0
MAX_SOLVER_TIMEOUT_S = 900.0


def normalize_solver_timeout(value: object) -> float:
    """Omission/None selects a finite default; invalid budgets never disable it."""
    if value is None:
        return DEFAULT_SOLVER_TIMEOUT_S
    try:
        timeout = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Solver timeout must be 1–900 finite seconds.") from exc
    if isinstance(value, bool) or not math.isfinite(timeout) or not 1 <= timeout <= MAX_SOLVER_TIMEOUT_S:
        raise ValueError("Solver timeout must be 1–900 finite seconds.")
    return timeout
