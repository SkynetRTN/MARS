"""Every registered tool has an explicit effect/consent disposition (AUD-01)."""

import pytest

from tools.agent.policy import risk_tags
from tools.effects import CONSENT_ARTIFACT_WRITERS, NO_LOCAL_WRITE, PRIVATE_ARTIFACT_EXEMPTIONS
from tools.mcp.groups import annotations_for
from tools.registry import TOOL_FUNCTIONS, TOOL_SCHEMAS


def test_inventory_is_a_complete_disjoint_registry_partition():
    groups = [NO_LOCAL_WRITE, CONSENT_ARTIFACT_WRITERS, PRIVATE_ARTIFACT_EXEMPTIONS]
    assert set.union(*(set(group) for group in groups)) == set(TOOL_FUNCTIONS)
    assert sum(map(len, groups)) == len(TOOL_FUNCTIONS)


@pytest.mark.parametrize("schema", TOOL_SCHEMAS, ids=lambda schema: schema["name"])
def test_agent_and_mcp_use_the_same_effect_inventory(schema):
    name = schema["name"]
    assert annotations_for(schema)["read_only_hint"] == (name in NO_LOCAL_WRITE)
    assert ("writes" in risk_tags(name)) == (name in CONSENT_ARTIFACT_WRITERS)


@pytest.mark.parametrize("name", ["search_mast", "search_casda"])
def test_exempt_archive_tables_do_not_exempt_downloads(name):
    assert "writes" not in risk_tags(name, {"download": False})
    assert risk_tags(name, {"download": True}) == frozenset({"writes", "slow"})


def test_exempt_solver_logs_do_not_exempt_input_mutation():
    assert "writes" not in risk_tags("solve_astrometry", {"write_header": False})
    assert "writes" in risk_tags("solve_astrometry", {"write_header": True})
    assert "writes" in risk_tags("unreviewed_new_writer")
