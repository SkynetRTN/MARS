"""Every result that can carry errors says whether the call failed.

The console marks a call, and the MCP surface flags it to the client, from
``status`` alone. Twenty result models carried ``errors`` but no ``status``, so
a tool that failed -- a crashed ``solve-field``, a periodogram given an
impossible grid -- was shown and reported as a success. They now derive it
(``tools.models.StatusFromErrors``): none is ``ok``, only "found nothing" codes
is ``not_found``, anything else is ``error``.
"""

from __future__ import annotations

import typing

import pytest
from pydantic import BaseModel

from tools.mcp.surface import normalize_result, result_is_error
from tools.registry import TOOL_FUNCTIONS


def _returned_models():
    for name, function in TOOL_FUNCTIONS.items():
        returned = typing.get_type_hints(function).get("return")
        for model in typing.get_args(returned) or (returned,):
            if isinstance(model, type) and issubclass(model, BaseModel):
                yield name, model


@pytest.mark.parametrize("tool, model", sorted(_returned_models(), key=lambda pair: (pair[0], pair[1].__name__)))
def test_a_result_that_can_carry_errors_carries_a_status(tool, model):
    if "errors" not in model.model_fields:
        pytest.skip(f"{model.__name__} reports no errors")
    assert "status" in model.model_fields or "status" in model.model_computed_fields, (
        f"{tool} returns {model.__name__}, whose errors no consumer would see as a failure"
    )


def _payload(tool, **arguments):
    return normalize_result(tool, TOOL_FUNCTIONS[tool](**arguments))


@pytest.mark.parametrize(
    "tool, arguments",
    [
        ("compute_pulsar_periodogram", {"path": "data/pulsar/Skynet_60898_psr_b0329_54_138326_88255.A.cal.txt", "steps": 10**9}),
        ("list_pulsar_scans", {"directory": "/nonexistent/pulsar"}),
        ("resolve_reference_band", {"catalog": "NOT_A_CATALOG", "image_filter": "V"}),
        ("solve_zeropoint_from_measurements", {"measurements": [], "catalog_sources": []}),
        ("list_variable_star_fixtures", {"directory": "/nonexistent/variable"}),
    ],
)
def test_a_failed_call_is_an_error_to_every_consumer(tool, arguments):
    payload = _payload(tool, **arguments)

    assert payload["errors"], "the call was meant to fail"
    assert payload["status"] == "error"
    assert result_is_error(payload)


@pytest.mark.parametrize(
    "tool, arguments",
    [
        ("resolve_optical_frame", {"name": "no such frame anywhere"}),
        ("resolve_variable_star_fixture", {"name": "no such fixture anywhere"}),
        ("load_zeropoint_reference", {"field": "no such field anywhere"}),
    ],
)
def test_a_lookup_that_found_nothing_is_not_found_not_an_error(tool, arguments):
    payload = _payload(tool, **arguments)

    assert [error["code"] for error in payload["errors"]] == ["not_found"]
    assert payload["status"] == "not_found"
    assert not result_is_error(payload)


def test_a_call_that_worked_is_ok():
    payload = _payload("list_pulsar_scans")

    assert payload["errors"] == []
    assert payload["status"] == "ok"
