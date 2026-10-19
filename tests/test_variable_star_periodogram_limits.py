"""ALG-02: guard direct weighted-spectrum work without replacing its math."""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pytest

from algorithms.variable_star import periodogram


@pytest.mark.parametrize("arguments", [
    "1., math.nextafter(1., 2.), 1000",
    "math.nextafter(2., 0.), math.nextafter(2., 0.) + 1000 * math.ulp(math.nextafter(2., 0.)), 2000",
])
def test_nonprogressing_weighted_grid_is_rejected_in_a_bounded_child(arguments):
    source = (
        "import math\nfrom algorithms.variable_star import periodogram\n"
        "print('READY', flush=True)\ninput()\ntry:\n"
        "    periodogram.lomb_scargle_with_error([0.,1.,2.], [0.,1.,0.], "
        f"[.1,.1,.1], {arguments})\n"
        "except ValueError:\n    print('BLOCKED', flush=True)\n"
        "else:\n    raise AssertionError('unsafe grid accepted')\n"
    )
    child = subprocess.Popen(
        [sys.executable, "-u", "-c", source], text=True,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=Path(__file__).resolve().parents[1],
    )
    try:
        output, errors = child.communicate("\n", timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        output, errors = child.communicate()
        pytest.fail(f"grid did not terminate: {output!r} {errors!r}")
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()
    assert child.returncode == 0, errors
    assert output == "READY\nBLOCKED\n"


@pytest.mark.parametrize("start, stop, steps", [
    (math.nan, 1., 10), (.1, math.inf, 10),
    (.1, 1., 0), (.1, 1., -1), (.1, 1., 1.5), (.1, 1., True),
    (.1, 1., 1_000_000_000), (5e-324, 1e-323, 2000),
    (0., 1., 10), (-1., 1., 10), (1., 1., 10), (1., .1, 10),
])
def test_invalid_grid_is_rejected_before_weighted_preparation(monkeypatch, start, stop, steps):
    def expensive(*args, **kwargs):
        pytest.fail("invalid grid reached weighted preparation")

    monkeypatch.setattr(periodogram, "_error_mean", expensive)
    with pytest.raises(ValueError):
        periodogram.lomb_scargle_with_error([0., 1., 2.], [0., 1., 0.], [.1] * 3, start, stop, steps)


@pytest.mark.parametrize("errors", [
    [.1, .1], [.1, 0., .1], [.1, -.1, .1],
    [.1, math.nan, .1], [.1, math.inf, .1],
    [.1, 1e-300, .1], [.1, 1e300, .1],
    [1e-154, 1e-154, 1e-154],
])
def test_invalid_or_unrepresentable_weights_raise_validation_errors(errors):
    with pytest.raises(ValueError):
        periodogram.lomb_scargle_with_error([0., 1., 2.], [0., 1., 0.], errors, .1, 1., 10)


@pytest.mark.parametrize("times, values", [
    ([0., math.inf, 2.], [0., 1., 0.]),
    ([0., 1., 2.], [0., math.nan, 0.]),
    ([], []),
])
def test_invalid_weighted_vectors_raise_validation_errors(times, values):
    with pytest.raises(ValueError):
        periodogram.lomb_scargle_with_error(times, values, [.1] * len(times), .1, 1., 10)


def test_compound_work_limit_precedes_weighted_preparation(monkeypatch):
    monkeypatch.setattr(periodogram, "MAX_PERIODOGRAM_WORK", 1)

    def expensive(*args, **kwargs):
        pytest.fail("oversized spectrum reached weighted preparation")

    monkeypatch.setattr(periodogram, "_error_mean", expensive)
    with pytest.raises(ValueError, match="work"):
        periodogram.lomb_scargle_with_error([0., 1., 2.], [0., 1., 0.], [.1] * 3, .1, 1., 10)


def test_sample_limit_precedes_weighted_allocation(monkeypatch):
    monkeypatch.setattr(periodogram, "MAX_PERIODOGRAM_SAMPLES", 1)

    def expensive(*args, **kwargs):
        pytest.fail("oversized samples reached weighted preparation")

    monkeypatch.setattr(periodogram, "_error_mean", expensive)
    with pytest.raises(ValueError, match="sample"):
        periodogram.lomb_scargle_with_error([0., 1.], [0., 1.], [.1] * 2, .1, 1., 10)


@pytest.mark.parametrize("step, message", [(0., "advance"), (.01, "iteration count")])
def test_runtime_grid_guards_remain_when_preflight_is_bypassed(monkeypatch, step, message):
    monkeypatch.setattr(periodogram, "validate_periodogram_grid", lambda *args: step)
    with pytest.raises(ValueError, match=message):
        periodogram.lomb_scargle_with_error([0., 1., 2.], [0., 1., 0.], [.1] * 3, .1, 1., 4)


@pytest.mark.parametrize("times, values, start, stop", [
    ([0., 1e308, 2.], [0., 1., 0.], .1, 1.),
    ([0., 1., 2.], [0., 1e200, 0.], .1, 1.),
    ([0., 1., 2.], [1e308] * 3, .1, 1.),
    ([0., 1., 2.], [0., 1., 0.], 1e-308, 2e-308),
])
def test_unrepresentable_weighted_intermediates_raise_validation_errors(times, values, start, stop):
    with pytest.raises(ValueError):
        periodogram.lomb_scargle_with_error(times, values, [.1] * 3, start, stop, 10)
