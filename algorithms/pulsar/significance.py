"""First-party finite-grid Gaussian-noise false-alarm bounds (M2).

The port normalizes by the observed population variance: its power is N/2
times standard LS power. Fitting a floating mean can only increase that
power. Under iid Gaussian errors its single-frequency tail is therefore
bounded by Beta(1, (N-3)/2). A union bound over the actual evaluated grid
requires no independence assumption between trial frequencies.

This is conditional on that noise model and a grid chosen independently of
the flux values. It neither calibrates correlated/filtered radio noise nor
covers subsequent retuning. See docs/analysis/pulsar-candidates-confidence.md.
"""

from __future__ import annotations

import math
import sys

from . import limits

METHOD = "gaussian_bonferroni"
PROBABILITIES = (0.1, 0.01, 0.001)
ASSUMPTIONS = (
    "Independent Gaussian errors with equal variance around a constant mean.",
    "A finite trial grid fixed independently of the flux values; one search only.",
    "Conditional noise-model bound, not the probability of a pulsar or correct period.",
    "Correlated noise, baseline filtering, RFI and repeated retuning are not calibrated.",
)


def _counts(samples: int, trials: int) -> None:
    limits.integer(samples, "samples", limits.MAX_SAMPLES)
    limits.integer(trials, "trials", limits.MAX_STEPS + 2)
    if samples <= 3:
        raise ValueError("a false-alarm bound needs at least four samples")


def upper_bound(power: float, samples: int, trials: int) -> float:
    """Upper bound for the largest tested power under the stated Gaussian null.

    A positive floating-point floor avoids reporting zero for tail probabilities
    below representable precision; the floor remains conservative.
    """
    _counts(samples, trials)
    limits.finite(power, "power")
    normalized = 2.0 * power / samples
    if normalized < 0 or normalized > 1 + 1e-12:
        raise ValueError("power lies outside the sample-variance normalization")
    if normalized >= 1:
        return sys.float_info.min
    log_bound = math.log(trials) + (samples - 3) / 2 * math.log1p(-normalized)
    return math.exp(max(math.log(sys.float_info.min), min(0.0, log_bound)))


def threshold(alpha: float, samples: int, trials: int) -> float:
    """Power sufficient for a finite-grid Gaussian false-alarm bound <= alpha."""
    _counts(samples, trials)
    limits.finite(alpha, "false alarm probability", positive=True)
    if alpha >= 1:
        raise ValueError("false alarm probability must be below one")
    return -samples / 2 * math.expm1(2 * (math.log(alpha) - math.log(trials)) / (samples - 3))
