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
from decimal import Decimal, localcontext

from . import limits

METHOD = "gaussian_bonferroni"
STATISTIC = "residual_fraction"
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


def residual_upper_bound(residual_fraction: float, samples: int, trials: int) -> float:
    """Evaluate the Beta tail from RSS/TSS without subtracting power from one.

    A positive floor is used only when a resolved residual's probability
    underflows, never as a substitute for an unresolved residual.
    """
    _counts(samples, trials)
    limits.finite(residual_fraction, "residual fraction", positive=True)
    if residual_fraction > 1:
        raise ValueError("residual fraction must not exceed one")
    log_bound = math.log(trials) + (samples - 3) / 2 * math.log(residual_fraction)
    return math.exp(max(math.log(sys.float_info.min), min(0.0, log_bound)))


def upper_bound(power: float, samples: int, trials: int) -> float | None:
    """Scalar-power reference; the normalization endpoint has no resolved tail.

    The driver uses a directly fitted residual instead. Subtract before
    dividing to avoid an additional cancellation in ``1 - 2*power/N``.
    """
    _counts(samples, trials)
    limits.finite(power, "power")
    normalized = 2.0 * power / samples
    if normalized < 0 or normalized > 1 + 1e-12:
        raise ValueError("power lies outside the sample-variance normalization")
    residual_fraction = (samples / 2 - power) / (samples / 2)
    if residual_fraction <= 0:
        return None
    return residual_upper_bound(residual_fraction, samples, trials)


def threshold(alpha: float, samples: int, trials: int) -> float | None:
    """Upward-rounded sufficient power, or null at an unrepresentable endpoint.

    Compute the inverse above binary64 precision before rounding toward larger
    powers. Rounding to the normalization cap does not yield a drawable level.
    """
    _counts(samples, trials)
    limits.finite(alpha, "false alarm probability", positive=True)
    if alpha >= 1:
        raise ValueError("false alarm probability must be below one")
    samples, trials = int(samples), int(trials)
    with localcontext() as context:
        context.prec = 80
        residual = (Decimal(float(alpha)) / trials) ** (Decimal(2) / (samples - 3))
        cutoff = Decimal(samples) / 2 * (1 - residual)
        value = float(cutoff)
        if Decimal(value) < cutoff:
            value = math.nextafter(value, math.inf)
    return value if value < samples / 2 else None
