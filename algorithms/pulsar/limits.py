"""First-party work guards around preserved pulsar arithmetic (M1).

These are acceptance limits, not a replacement numerical method or a server
deadline. Counts are checked before loops/interpolation/output allocation.
"""

from __future__ import annotations

import math
import operator

import numpy as np

MAX_SAMPLES = 100_000
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_BINS = 10_000
MAX_FOLD_ITERATIONS = 100_000
MAX_FOLD_WORK = 100_000_000
MAX_BACKGROUND_WORK = 20_000_000
MAX_STEPS = 200_000
MAX_PERIODOGRAM_WORK = 200_000_000
MAX_SAMPLE_RATE = 192_000
MAX_AUDIO_SECONDS = 600.0
MAX_AUDIO_FRAMES = 4_000_000
MAX_INTERPOLATED_POINTS = 4_000_000


def finite(value: float, name: str, *, positive: bool = False) -> None:
    try:
        valid = math.isfinite(value) and (not positive or value > 0)
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        qualifier = "finite and positive" if positive else "finite"
        raise ValueError(f"{name} must be {qualifier}, got {value!r}")


def integer(value: int, name: str, maximum: int) -> None:
    try:
        number = operator.index(value)
    except TypeError:
        number = 0
    if isinstance(value, (bool, np.bool_)) or not 0 < number <= maximum:
        raise ValueError(f"{name} must be an integer in [1, {maximum}], got {value!r}")


def vector(value, name: str, *, allow_nan: bool = False) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim != 1 or array.size > MAX_SAMPLES:
        raise ValueError(f"{name} must be a vector of at most {MAX_SAMPLES} samples")
    array = np.asarray(array, dtype=np.float64)
    invalid = np.isinf(array) if allow_nan else ~np.isfinite(array)
    if invalid.any():
        raise ValueError(f"{name} contains non-finite samples")
    return array


def fold_settings(bins: int, phase: float, cal: float, display_period: int = 1) -> None:
    integer(bins, "bins", MAX_BINS)
    integer(display_period, "display_period", 2)
    finite(phase, "phase")
    finite(cal, "cal")


def audio_settings(speed: float, cal: float, sample_rate: int, seconds: float) -> None:
    finite(speed, "speed", positive=True)
    finite(cal, "cal")
    integer(sample_rate, "sample_rate", MAX_SAMPLE_RATE)
    finite(seconds, "audio_seconds", positive=True)
    frames = seconds * sample_rate
    if seconds > MAX_AUDIO_SECONDS or not 1 <= frames <= MAX_AUDIO_FRAMES:
        raise ValueError(
            f"audio output must be at most {MAX_AUDIO_SECONDS:g} seconds and "
            f"contain 1..{MAX_AUDIO_FRAMES} frames"
        )
