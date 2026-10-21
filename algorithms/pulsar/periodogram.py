"""Lomb-Scargle periodogram for pulsar light curves — stage 2 of the pipeline.

PORTED from MARS's retired TypeScript extraction:

* ``git-history:algorithms/periodogram/core/lomb-scargle.ts`` — ``lombScargle`` and the
  ``ArrMath`` helpers it computes through (astromancer
  ``shared/data/utils.ts``).
* ``git-history:algorithms/periodogram/core/peak-detection.ts`` — ``findLocalMax``,
  ``confidenceThreshold``, ``CONFIDENCE_LEVELS``.
* ``git-history:algorithms/periodogram/pulsar/pulsar-periodogram-range.ts`` —
  ``nyquistPeriodogramRange``.

The pulsar tool uses the **unweighted** ``lombScargle``; pulsar rows carry no
per-point error, which is why ``lombScargleWithError`` is not ported.

This is the stage that produces a period. Everything downstream — folding, and
the folded sonification — needs one, so nothing downstream can run until this
does. See ``docs/pulsar-tool-pipeline.md``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from . import limits, sampling, significance

__all__ = [
    "Periodogram",
    "CONFIDENCE_LEVELS",
    "DEFAULT_STEPS",
    "lomb_scargle",
    "find_global_max",
    "confidence_threshold",
    "nyquist_periodogram_range",
]

#: ``PulsarPeriodogram.points`` default — the periodogram grid step count.
DEFAULT_STEPS = 1000

#: Verbatim from ``peak-detection.ts``. ``color`` is a rendering concern and is
#: carried because it is part of the original literal.
CONFIDENCE_LEVELS: tuple[dict, ...] = (
    {"id": "conf-1-sigma", "name": "67.3% Confidence", "alpha": 1 - 0.673, "color": "red"},
    {"id": "conf-2-sigma", "name": "95.4% Confidence", "alpha": 1 - 0.954, "color": "orange"},
    {"id": "conf-3-sigma", "name": "99.73% Confidence", "alpha": 1 - 0.9973, "color": "green"},
)


@dataclass
class Periodogram:
    """A computed spectrum plus the peak the folding stage consumes."""

    x: np.ndarray
    """Period (seconds) in period mode, frequency (Hz) in frequency mode."""

    power: np.ndarray
    """Normalized Lomb-Scargle spectral power."""

    freq_mode: bool
    start: float
    stop: float
    steps: int

    peak_x: Optional[float] = None
    peak_power: Optional[float] = None

    confidence: dict[str, float] = field(default_factory=dict)
    """Legacy independent-trial thresholds; no longer populated by the driver."""

    false_alarm_method: str | None = None
    false_alarm_probability_upper_bound: float | None = None
    false_alarm_thresholds: dict[str, float] = field(default_factory=dict)
    evaluated_trials: int = 0
    sampling: sampling.Sampling | None = None

    @property
    def peak_period_s(self) -> Optional[float]:
        """The peak as a period in seconds, whichever mode was computed."""
        if self.peak_x is None or self.peak_x == 0:
            return None
        return 1.0 / self.peak_x if self.freq_mode else float(self.peak_x)

    @property
    def peak_frequency_hz(self) -> Optional[float]:
        if self.peak_x is None or self.peak_x == 0:
            return None
        return float(self.peak_x) if self.freq_mode else 1.0 / self.peak_x

    @property
    def peak_confidence_level(self) -> Optional[str]:
        """Highest confidence level the peak clears, or ``None``."""
        if self.peak_power is None:
            return None
        best = None
        for level in CONFIDENCE_LEVELS:
            if self.peak_power >= self.confidence.get(level["id"], math.inf):
                best = level["name"]
        return best


def lomb_scargle(
    ts: np.ndarray,
    ys: np.ndarray,
    start: float,
    stop: float,
    steps: int = DEFAULT_STEPS,
    freq_mode: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """``lombScargle(ts, ys, start, stop, steps, freqMode)``.

    Returns ``(x, power)``. In period mode ``x`` is period in seconds; in
    frequency mode it is frequency in Hz.

    Two upstream behaviours are reproduced rather than cleaned up, because they
    decide which trial periods are actually evaluated:

    * **Period mode evaluates a logarithmic grid driven by a linear loop.**
      The loop variable steps linearly from ``start`` to ``stop`` and is
      discarded; the evaluated point is
      ``exp(log(start) + (log(stop) - log(start)) * i / steps)``. So the loop
      only supplies the iteration count. Frequency mode overwrites both with
      the linear loop variable and really is linear.
    * **The endpoint is not forced.** Usually the last point is short of
      ``stop``; accumulated float error can supply an extra iteration with
      ``i == steps``. Report/count the actual coordinates, not just ``steps``.

    Power is N/2 times standard-normalized Lomb-Scargle power; upstream reaches
    it through ``ArrMath.dot(v)``, which is ``dot(v, v)``. Numerically degenerate
    trials use a stable projection as documented in the M2 acceptance record.
    """
    ts = limits.vector(ts, "time_s")
    ys = limits.vector(ys, "flux")
    if ts.size != ys.size:
        # Upstream calls alert() and returns []; a library cannot do that.
        raise ValueError(
            f"Dimension mismatch between time array and value array: "
            f"{ts.size} != {ys.size}"
        )
    if ts.size == 0:
        return np.empty(0), np.empty(0)
    if ts.size < 3 or np.unique(ts).size < 3:
        raise ValueError("need at least three samples at distinct times")
    limits.finite(start, "start", positive=True)
    limits.finite(stop, "stop", positive=True)
    limits.integer(steps, "steps", limits.MAX_STEPS)
    if ts.size * (steps + 2) > limits.MAX_PERIODOGRAM_WORK:
        raise ValueError("periodogram exceeds the sample-times-grid work budget")
    if start <= 0 or stop <= 0:
        raise ValueError(
            f"start and stop must be positive (the grid is logarithmic in "
            f"period mode), got start={start!r}, stop={stop!r}"
        )
    if stop <= start:
        raise ValueError(f"stop must exceed start, got {start!r} -> {stop!r}")
    if steps <= 0:
        raise ValueError(f"steps must be positive, got {steps!r}")

    step = (stop - start) / steps
    if not math.isfinite(step) or step <= 0 or start + step == start:
        raise ValueError("periodogram grid increment cannot make finite progress")

    h_residue = ys - ys.mean()
    # ArrMath.var is the population variance (divides by N).
    with np.errstate(over="ignore", invalid="ignore"):
        two_var_of_y = 2 * float(np.var(ys))
    limits.finite(two_var_of_y, "flux variance", positive=True)

    log_start = math.log(start)
    log_stop = math.log(stop)

    xs: list[float] = []
    powers: list[float] = []

    # Reproduce upstream's float accumulation: `for (xVal = start;
    # xVal < stop; xVal += step)`. Accumulating is not the same as
    # start + i * step, and it decides the final iteration count.
    x_val = start
    i = 0
    while x_val < stop:
        if i >= steps + 2:
            raise ValueError("periodogram grid exceeded its iteration budget")
        log_x_val = math.exp(log_start + (log_stop - log_start) * i / steps)
        frequency = log_x_val if freq_mode else 1.0 / log_x_val
        if freq_mode:
            frequency = x_val
            log_x_val = x_val

        limits.finite(1 / frequency, "trial period in seconds", positive=True)
        omega = 2.0 * math.pi * frequency
        limits.finite(omega, "angular frequency", positive=True)
        with np.errstate(over="ignore", invalid="ignore"):
            two_omega_t = 2 * omega * ts
        if not np.isfinite(two_omega_t).all():
            raise ValueError("time-frequency products must remain finite")
        tau = math.atan2(
            float(np.sum(np.sin(two_omega_t))),
            float(np.sum(np.cos(two_omega_t))),
        ) / (2.0 * omega)
        omega_t_minus_tau = omega * (ts - tau)

        cos_term = np.cos(omega_t_minus_tau)
        sin_term = np.sin(omega_t_minus_tau)

        try:
            cos_norm = float(np.dot(cos_term, cos_term))
            sin_norm = float(np.dot(sin_term, sin_term))
            cross = float(np.dot(cos_term, sin_term))
            if (
                min(cos_norm, sin_norm) <= np.finfo(float).eps * ts.size
                or abs(cross) > 1e-10 * math.sqrt(cos_norm * sin_norm)
            ):
                # At e.g. exact Nyquist, roundoff defeats tau's intended
                # orthogonality. The port's sum of two quotients then ceases
                # to be a projection and can exceed N/2. Fit the same raw
                # columns with an SVD rank test; never scale tiny roundoff
                # columns into artificial independent regressors.
                design = np.column_stack((cos_term, sin_term))
                basis, singular_values, _ = np.linalg.svd(design, full_matrices=False)
                cutoff = np.finfo(float).eps * max(design.shape) * singular_values[0]
                projection = basis[:, singular_values > cutoff].T @ h_residue
                power = float(np.dot(projection, projection)) / two_var_of_y
            else:
                power = (
                    float(np.dot(h_residue, cos_term)) ** 2.0 / cos_norm
                    + float(np.dot(h_residue, sin_term)) ** 2.0 / sin_norm
                ) / two_var_of_y
        except (ZeroDivisionError, OverflowError, np.linalg.LinAlgError) as exc:
            raise ValueError("singular periodogram trial") from exc
        limits.finite(power, "spectral power")

        xs.append(log_x_val)
        powers.append(power)

        x_val += step
        i += 1

    return np.asarray(xs, dtype=np.float64), np.asarray(powers, dtype=np.float64)


def find_global_max(x: np.ndarray, power: np.ndarray) -> tuple[Optional[float], Optional[float]]:
    """``findLocalMax(points)`` — despite the name, the **global** maximum.

    Upstream returns it as a single-element array and labels the resulting
    chart series "Global Maxima"; the name is original. Its x value is the
    peak period that the period-folding tab consumes, which makes this the
    handoff between stage 2 and stage 3.
    """
    if x.size == 0:
        return None, None
    # `points[i][1] > globalMax[1]` — strictly greater, so ties keep the
    # earliest, which in period mode is the shortest period.
    index = int(np.argmax(power))
    return float(x[index]), float(power[index])


def confidence_threshold(alpha: float, points: int) -> float:
    """Historical ``-Math.log(1 - (1 - alpha) ** (1 / points))``, verbatim.

    Spectral-power threshold a peak must clear to beat the false-alarm
    probability ``alpha`` over ``points`` independent exponential trials.
    Not used for current sample-variance-normalized public results.
    """
    return -math.log(1 - (1 - alpha) ** (1 / points))


def nyquist_periodogram_range(
    ts: np.ndarray, freq_mode: bool = False
) -> Optional[dict[str, float]]:
    """Historical ``nyquistPeriodogramRange(ts, method)`` search bounds.

    Returns ``None`` for fewer than two samples rather than emitting garbage,
    as upstream does. Keys are upstream's: ``startPeriod``, ``endPeriod``,
    ``periodFoldingPeriodMin``, ``periodFoldingPeriodMax``.

    ``avgDiff`` is twice the mean sample interval, rounded to 5 decimals.
    Upstream called it a Nyquist limit, which is not justified for irregular
    data. The public driver now uses ``sampling.summarize`` instead.
    """
    ts = limits.vector(ts, "time_s")
    if ts.size < 2:
        return None

    with np.errstate(over="ignore", invalid="ignore"):
        total_diff = float(np.sum(np.diff(ts)))
    scaled_interval = total_diff / (ts.size - 1) * 2 * 100000
    limits.finite(scaled_interval, "Nyquist interval", positive=True)
    avg_diff = round(scaled_interval) / 100000
    limits.finite(avg_diff, "Nyquist interval", positive=True)

    if freq_mode:
        start_period = 0.1
        end_period = round((1 / avg_diff) * 100000) / 100000
    else:
        start_period = avg_diff
        end_period = 3.0

    return {
        "startPeriod": start_period,
        "endPeriod": end_period,
        "periodFoldingPeriodMin": avg_diff,
        "periodFoldingPeriodMax": 3.0,
    }


def compute_periodogram(
    ts: np.ndarray,
    ys: np.ndarray,
    *,
    start: Optional[float] = None,
    stop: Optional[float] = None,
    steps: int = DEFAULT_STEPS,
    freq_mode: bool = False,
) -> Periodogram:
    """Run preserved powers with first-party search and significance semantics.

    Default period bounds are twice median positive spacing through 3 s;
    frequency mode uses the reciprocal band. Irregular spacing supplies a
    search heuristic, not a hard Nyquist limit. Significance is a conservative
    finite-grid bound under iid Gaussian noise, not a detection probability.
    """
    ts = limits.vector(ts, "time_s")
    if ts.size < 3:
        raise ValueError("need at least three samples to compute a periodogram")
    observed_sampling = sampling.summarize(ts)
    if start is None or stop is None:
        shortest = observed_sampling.suggested_min_period_s
        if shortest is None:
            raise ValueError("need at least two samples to choose search bounds")
        default_start = 1 / 3.0 if freq_mode else shortest
        default_stop = 1 / shortest if freq_mode else 3.0
        start = default_start if start is None else start
        stop = default_stop if stop is None else stop

    x, power = lomb_scargle(ts, ys, start, stop, steps, freq_mode)
    peak_x, peak_power = find_global_max(x, power)

    trials = len(x)
    thresholds = {}
    false_alarm = None
    method = None
    if ts.size > 3 and trials and peak_power is not None:
        false_alarm = significance.upper_bound(peak_power, ts.size, trials)
        thresholds = {
            str(alpha): significance.threshold(alpha, ts.size, trials)
            for alpha in significance.PROBABILITIES
        }
        method = significance.METHOD

    return Periodogram(
        x=x,
        power=power,
        freq_mode=freq_mode,
        start=float(start),
        stop=float(stop),
        steps=int(steps),
        peak_x=peak_x,
        peak_power=peak_power,
        false_alarm_method=method,
        false_alarm_probability_upper_bound=false_alarm,
        false_alarm_thresholds=thresholds,
        evaluated_trials=trials,
        sampling=observed_sampling,
    )
