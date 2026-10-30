"""First-party search defaults from observed spacing, with explicit limits."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import limits


@dataclass(frozen=True)
class Sampling:
    median_spacing_s: float | None
    uniform: bool

    @property
    def suggested_min_period_s(self) -> float | None:
        return None if self.median_spacing_s is None else 2 * self.median_spacing_s

    def metadata(self) -> dict[str, float | str | None]:
        shortest = self.suggested_min_period_s
        return {
            "sample_cadence_s": self.median_spacing_s,
            "suggested_min_period_s": shortest,
            "nyquist_period_s": shortest if self.uniform else None,
            "sampling_policy": (
                None if shortest is None else
                "uniform" if self.uniform else "median_spacing_heuristic"
            ),
        }


def summarize(times: np.ndarray) -> Sampling:
    """Sort distinct epochs; duplicates/gaps/jitter do not establish a Nyquist limit.

    Median positive spacing supplies a practical default for irregular data,
    without asserting a universal sampling cutoff. No five-decimal rounding.
    """
    times = limits.vector(times, "time_s")
    distinct = np.unique(times)
    if distinct.size < 2:
        return Sampling(None, False)
    with np.errstate(over="ignore", invalid="ignore"):
        gaps = np.diff(distinct)
        cadence = float(np.median(gaps))
        shortest = 2 * cadence
    limits.finite(shortest, "sampling-based minimum period", positive=True)
    uniform = distinct.size == times.size and bool(
        np.allclose(gaps, cadence, rtol=1e-7, atol=0.0)
    )
    return Sampling(cadence, uniform)
