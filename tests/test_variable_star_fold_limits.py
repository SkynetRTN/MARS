"""TS-02: direct variable-star folding has bounded subtraction work."""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pytest

from algorithms.variable_star import folding
from algorithms.variable_star.lightcurve import VariableDataRow


@pytest.mark.parametrize("expression", [
    "folding._float_mod(1., 0.)",
    "folding._float_mod(1., -1.)",
    "folding._float_mod(float('inf'), 1.)",
    "folding._float_mod(1., 1e-300)",
    "folding.fold_with_error(rows, 'source1', 12., period=1e-300)",
    "folding.fold_with_error(rows + [VariableDataRow(float('inf'), 14., 12., .1, .1, .1)], 'source1', 12., period=1.)",
])
def test_direct_stalled_fold_is_rejected_in_a_bounded_subprocess(expression):
    source = (
        "from algorithms.variable_star import folding\n"
        "from algorithms.variable_star.lightcurve import VariableDataRow\n"
        "rows = [VariableDataRow(0., 14., 12., .1, .1, .1), "
        "VariableDataRow(1., 15., 12., .1, .1, .1)]\n"
        "print('READY', flush=True)\n"
        "input()\n"
        "try:\n"
        f"    {expression}\n"
        "except ValueError:\n"
        "    print('BLOCKED', flush=True)\n"
        "else:\n"
        "    raise AssertionError('unsafe input was accepted')\n"
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
        pytest.fail(f"fold did not terminate: {output!r} {errors!r}")
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()
    assert child.returncode == 0, errors
    assert output == "READY\nBLOCKED\n"


def test_exact_multiple_and_negative_value_keep_strict_subtraction_semantics():
    assert folding._float_mod(1., .5) == .5  # not Python modulo's zero
    assert folding._float_mod(-1., .5) == -1.


def test_default_and_zero_period_semantics_are_preserved():
    rows = [VariableDataRow(0., 14., 12., .1, .1, .1),
            VariableDataRow(1., 15., 12., .1, .1, .1)]
    assert folding.fold_with_error(rows, "source1", 12.) == folding.fold_with_error(
        rows, "source1", 12., period=1.
    )
    assert folding.fold_with_error(rows, "source1", 12., period=0.) == ([], [])


@pytest.mark.parametrize("settings", [
    {"period": math.nan}, {"period": math.inf}, {"phase": math.nan},
    {"phase": math.inf}, {"period": 1e308, "phase": 1e308},
    {"period": 1e308, "phase": 1.},
])
def test_non_finite_fold_settings_raise_validation_errors(settings):
    rows = [VariableDataRow(0., 14., 12., .1, .1, .1)]
    with pytest.raises(ValueError):
        folding.fold_with_error(rows, "source1", 12., **settings)


def test_aggregate_work_is_checked_before_modulo(monkeypatch):
    rows = [VariableDataRow(0., 14., 12., .1, .1, .1),
            VariableDataRow(1., 15., 12., .1, .1, .1)]
    monkeypatch.setattr(folding, "MAX_FOLD_OPERATIONS", 1)

    def expensive(*args, **kwargs):
        pytest.fail("oversized work reached subtraction")

    monkeypatch.setattr(folding, "_float_mod", expensive)
    with pytest.raises(ValueError, match="work limit"):
        folding.fold_with_error(rows, "source1", 12., period=.5)


def test_sample_budget_is_checked_before_differential_allocation(monkeypatch):
    monkeypatch.setattr(folding, "MAX_FOLD_SAMPLES", 1)

    def allocated(*args, **kwargs):
        pytest.fail("oversized fold reached differential allocation")

    monkeypatch.setattr(folding, "differential_data", allocated)
    rows = [VariableDataRow(0., 14., 12., .1, .1, .1)] * 2
    with pytest.raises(ValueError, match="sample limit"):
        folding.fold_with_error(rows, "source1", 12., period=.5)


def test_derived_baseline_overflow_is_rejected():
    with pytest.raises(ValueError, match="baseline"):
        folding.validate_fold_work(1., [-1e308, 1e308])


def test_public_fold_translates_shared_budget_failure(artifact_dir, monkeypatch):
    from tools import variable_star

    lightcurve = variable_star.load_variable_star_lightcurve(
        variable_star.resolve_variable_star_fixture("two_source_parity").path
    )
    assert lightcurve.errors == []
    monkeypatch.setattr(folding, "MAX_FOLD_OPERATIONS", 1)
    result = variable_star.fold_variable_star_lightcurve(
        lightcurve.artifact.path, variable_star="source1",
        reference_star_magnitude=12., period=.4,
    )
    assert [e.code for e in result.errors] == ["invalid_input"]
    assert result.artifact is None
