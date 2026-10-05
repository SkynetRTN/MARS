"""PHOT-15: bounded custom magnitude expressions, without numerical drift."""

from __future__ import annotations

import ast
import math
import subprocess
import sys
from pathlib import Path

import pytest

from algorithms.fieldcal import ref_mag
from algorithms.fieldcal.field_cal import _collect_calibration_sources
from algorithms.fieldcal.schemas import CatalogSource, Mag, PhotometryData


@pytest.mark.parametrize("expression", [
    "2**1000000000", "9**9**9", "2**(2**20)", "2**17", "2**-17",
    "2**r", "2**(r-r)", "1" * 400, "+".join(["r"] * 200),
    "-" * 40 + "r", "(" * 40 + "r" + ")" * 40,
])
def test_unsafe_expressions_do_not_reach_the_python_evaluator(monkeypatch, expression):
    def forbidden(*args, **kwargs):
        pytest.fail("unsafe expression reached Python eval")

    monkeypatch.setattr(ref_mag, "eval", forbidden, raising=False)
    assert ref_mag._safe_eval_expr(expression, {"r": 14.4}) is None


def test_long_expression_is_rejected_before_parsing(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("oversized expression reached the AST parser")

    with monkeypatch.context() as scoped:
        scoped.setattr(ast, "parse", forbidden)
        result = ref_mag._safe_eval_expr("r+" * 2000 + "r", {"r": 14.4})
    assert result is None


@pytest.mark.parametrize("expression", [
    "r.__class__", "(r).__class__", "[r][0]", "r if r else 0",
    "sqrt(r,r)", "sqrt(r=1)", "abs(r)", "True + r",
])
def test_only_numeric_arithmetic_and_single_argument_math_calls_are_accepted(expression):
    assert ref_mag._safe_eval_expr(expression, {"r": 14.4}) is None


def test_band_regex_metacharacters_are_literal_not_pattern_syntax():
    assert ref_mag._safe_eval_expr("r+r", {"r.r": 10., "r": 2.}) == 4.
    assert ref_mag._safe_eval_expr("r.r+1", {"r.r": 10.}) == 11.


def test_malformed_regex_band_name_cannot_escape_the_failure_contract():
    assert ref_mag._safe_eval_expr("r+1", {"(": 5., "r": 2.}) == 3.


@pytest.mark.parametrize("bands", [
    {"r": math.nan}, {"r": math.inf}, {"r": object()},
    {"r": 2., **{f"b{i}": 1. for i in range(64)}},
    {"r" * 129: 2.},
    {"r.r": 2., "r_r": 3.},
])
def test_invalid_or_oversized_band_namespaces_fail_without_an_exception(bands):
    assert ref_mag._safe_eval_expr("1+1", bands) is None


@pytest.mark.parametrize("expression, expected", [
    ("r - 0.2936*(r-i) - 0.1439", 14.4 - .2936 * (14.4 - 14.25) - .1439),
    ("sqrt(r)+log10(i)", math.sqrt(14.4) + math.log10(14.25)),
    ("(r-i)**2", (14.4 - 14.25)**2),
    ("2**16", 65536.), ("2**-16", 2.**-16),
    ("7//2", 3.), ("2**1.5", 2.**1.5),
])
def test_accepted_expressions_keep_python_arithmetic(expression, expected):
    assert ref_mag._safe_eval_expr(expression, {"r": 14.4, "i": 14.25}) == expected


def test_unsafe_explicit_custom_transform_cannot_fall_back_to_an_unrelated_band():
    result = ref_mag.resolve_ref_mag_for_filter(
        image_filter="custom", catalog_name="APASS",
        cs_mags={"V": Mag(value=14., error=.1)},
        custom_filter_lookup={"APASS": {"custom": "2**1000000000"}},
    )
    assert result == (None, None)


def test_custom_transform_keeps_numeric_error_propagation():
    result = ref_mag.resolve_ref_mag_for_filter(
        image_filter="custom", catalog_name="APASS",
        cs_mags={"r": Mag(value=14.4, error=.02), "i": Mag(value=14.25, error=.03)},
        custom_filter_lookup={"APASS": {"custom": "r - 0.2936*(r-i) - 0.1439"}},
    )
    assert result[0] == 14.4 - .2936 * (14.4 - 14.25) - .1439
    assert result[1] == pytest.approx(math.hypot(.7064 * .02, .2936 * .03), rel=1e-5)


def test_calibration_collection_skips_an_unsafe_explicit_transform(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("custom calibration reached Python eval")

    monkeypatch.setattr(ref_mag, "eval", forbidden, raising=False)
    catalog = CatalogSource(id="s", catalog_name="APASS", mags={"V": Mag(value=14., error=.1)})
    measured = PhotometryData(id="s", filter="custom", mag=13., mag_error=.1)
    result = _collect_calibration_sources(
        [measured], [catalog], catalog_filter_lookup=None,
        custom_filter_lookup={"APASS": {"custom": "2**1000000000"}},
    )
    assert result == []
    assert measured.ref_mag is None


def test_alias_traversal_has_a_finite_hop_budget(monkeypatch):
    calls = []
    original = ref_mag._safe_eval_expr

    def record(expression, bands):
        calls.append(expression)
        return original(expression, bands)

    monkeypatch.setattr(ref_mag, "_safe_eval_expr", record)
    lookup = {f"alias{i}": f"alias{i+1}" for i in range(100)}
    assert ref_mag._resolve_filter_lookup_candidate(
        "alias0", {}, lookup, propagate_error=True,
    ) == (None, None)
    assert len(calls) == ref_mag.MAX_LOOKUP_HOPS


def test_band_count_is_bounded_before_flattening_or_error_propagation(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("oversized namespace reached expression processing")

    monkeypatch.setattr(ref_mag, "_safe_eval_expr", forbidden)
    mags = {f"band{i}": Mag(value=14., error=.1) for i in range(65)}
    assert ref_mag.resolve_ref_mag_for_filter(
        image_filter="custom", catalog_name="APASS", cs_mags=mags,
        custom_filter_lookup={"APASS": {"custom": "1+1"}},
    ) == (None, None)
    assert ref_mag._resolve_filter_lookup_candidate(
        "1+1", {name: (14., .1) for name in mags}, {}, propagate_error=True,
    ) == (None, None)


def test_integer_intermediates_cannot_compound_past_the_bit_budget():
    # Each literal fits, but multiplication would cross the 1,024-bit bound.
    literal = str(2**600)
    assert ref_mag._safe_eval_expr(f"{literal}*{literal}", {}) is None
    assert ref_mag._safe_eval_expr(f"({literal}*{literal})**16", {}) is None


@pytest.mark.parametrize("expression", ["1e308*1e308", "sqrt(-1)", "log10(0)", "2**-1e308"])
def test_nonrepresentable_or_invalid_numeric_operations_are_unresolved(expression):
    assert ref_mag._safe_eval_expr(expression, {}) is None


def test_all_declared_reference_registry_polynomials_keep_exact_arithmetic():
    bands = {"g": 15., "r": 14.6, "i": 14.4, "z": 14.2, "y": 14.,
             "B": 15.2, "V": 14.6, "uprime": 15.5, "gprime": 14.9,
             "rprime": 14.4, "iprime": 14.25}
    checked = 0
    for catalog in ref_mag.CATALOG_OPTIONS.values():
        for expression in catalog.filter_lookup.values():
            if not any(op in expression for op in "+-*/"):
                continue
            expected = eval(expression, {"__builtins__": {}}, bands)
            assert ref_mag._safe_eval_expr(expression, bands) == expected
            checked += 1
    assert checked > 0


def test_band_named_like_math_function_cannot_rebind_a_call():
    assert ref_mag._safe_eval_expr("sqrt(r)", {"sqrt": 1., "r": 4.}) is None
    assert ref_mag._safe_eval_expr("sqrt+1", {"sqrt": 4.}) == 5.


def test_large_power_requests_terminate_in_a_bounded_child():
    source = (
        "import sys\nfrom algorithms.fieldcal.ref_mag import _safe_eval_expr\n"
        "if sys.platform == 'linux':\n"
        "    import os, resource\n"
        "    with open('/proc/self/statm') as handle:\n"
        "        mapped = int(handle.read().split()[0]) * os.sysconf('SC_PAGE_SIZE')\n"
        "    resource.setrlimit(resource.RLIMIT_AS, (mapped + 64*1024*1024, mapped + 64*1024*1024))\n"
        "print('READY', flush=True)\ninput()\n"
        "for expression in ['9**9**9', '2**1000000000', '2**(2**20)']:\n"
        "    assert _safe_eval_expr(expression, {}) is None\n"
        "print('BLOCKED', flush=True)\n"
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
        pytest.fail(f"expression work did not terminate: {output!r} {errors!r}")
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()
    assert child.returncode == 0, errors
    assert output == "READY\nBLOCKED\n"
