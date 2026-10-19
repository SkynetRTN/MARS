"""Approval policy for the headless agent loop.

The engine receives an approver callable and has no UI dependency. This module
classifies the relatively costly, keyed, and artifact-writing tools so a caller
can decide which calls need an explicit confirmation. ``SessionPolicy`` keeps
an ``ALLOW_ALWAYS`` decision for the chosen tool and risk class, only for the
current session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Literal, Mapping

from tools.agent.approval import Approver, Decision, auto_approve
from tools.effects import DOWNLOAD_FLAGS, WRITE_FLAGS, artifact_write_requires_consent

if TYPE_CHECKING:
    from tools.agent.events import ToolCallProposed

__all__ = [
    "Decision",
    "RiskTag",
    "TOOL_RISK",
    "DOWNLOAD_FLAGS",
    "Approver",
    "auto_approve",
    "risk_tags",
    "needs_confirmation",
    "SessionPolicy",
    "policy_approver",
]

RiskTag = Literal["slow", "keyed", "writes"]

TOOL_RISK: dict[str, frozenset[RiskTag]] = {
    "run_full_hr_pipeline": frozenset({"slow"}),
    "run_full_hr_pipeline_from_catalog": frozenset({"slow"}),
    "extract_photometry_from_fits": frozenset({"slow"}),
    "run_photometry_on_target": frozenset({"slow"}),
    "search_ads": frozenset({"keyed"}),
    "get_paper_abstract": frozenset({"keyed"}),
    "get_citing_papers": frozenset({"keyed"}),
    "get_referenced_papers": frozenset({"keyed"}),
    "build_literature_review": frozenset({"keyed"}),
    "sonify_pulsar": frozenset({"writes"}),
    "plot_pulsar": frozenset({"writes"}),
    "plot_field_sed": frozenset({"writes"}),
}

# Routine archive-table writes are explicit private-artifact exemptions.
# The shared DOWNLOAD_FLAGS add consent/cost risk only for a fetch; WRITE_FLAGS
# independently protects modification of an input FITS header.


def risk_tags(
    name: str, arguments: Mapping[str, Any] | None = None
) -> frozenset[RiskTag]:
    """Return the risk tags for one proposed call.

    ``arguments`` is optional so the table can still be read by name alone,
    and is what :data:`DOWNLOAD_FLAGS` needs to tell a search from a fetch.
    """

    tags = TOOL_RISK.get(name, frozenset())
    if artifact_write_requires_consent(name):
        tags |= frozenset({"writes"})
    flag = DOWNLOAD_FLAGS.get(name)
    if flag and arguments and arguments.get(flag):
        tags |= frozenset({"writes", "slow"})
    flag = WRITE_FLAGS.get(name)
    if flag and arguments and arguments.get(flag):
        tags |= frozenset({"writes"})
    return tags


def needs_confirmation(
    name: str, arguments: Mapping[str, Any] | None = None
) -> bool:
    """Whether a proposed call's risk requires a caller to ask."""

    return bool(risk_tags(name, arguments))


@dataclass
class SessionPolicy:
    """Apply risk defaults and remember per-tool, per-risk allow-always decisions."""

    ask: Approver
    _always_allowed: set[tuple[str, frozenset[RiskTag]]] = field(default_factory=set, init=False)

    def approve(self, proposed: "ToolCallProposed") -> Decision:
        """Return the decision for one proposed tool call."""

        tags = risk_tags(proposed.name, proposed.arguments)
        if not tags:
            return Decision.ALLOW
        key = (proposed.name, tags)
        if key in self._always_allowed:
            return Decision.ALLOW

        decision = self.ask(proposed)
        if decision is Decision.ALLOW_ALWAYS:
            self._always_allowed.add(key)
            return Decision.ALLOW
        return decision


def policy_approver(policy: SessionPolicy) -> Approver:
    """Adapt a session policy to the engine's approver callable contract."""

    return policy.approve
