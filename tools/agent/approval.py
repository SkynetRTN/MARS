"""Approval vocabulary for the agent loop.

The engine calls an ``Approver`` before dispatching each tool call. Its
headless default denies risky calls; ``auto_approve`` is an explicit opt-in
for trusted callers such as the benchmark's replay plane. Interactive callers
use ``tools.agent.policy.SessionPolicy`` to ask a person.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tools.agent.events import ToolCallProposed

__all__ = ["Decision", "Approver", "auto_approve"]


class Decision(str, Enum):
    """A string enum: an approver returns one of these for each proposed call.

    ``ALLOW_ALWAYS`` persists for the session -- the *approver* remembers it
    (see ``SessionPolicy``), so the engine treats it exactly like ``ALLOW``.
    """

    ALLOW = "allow"
    DENY = "deny"
    ALLOW_ALWAYS = "allow_always"


#: Any callable taking a proposed call and returning a :class:`Decision`.
Approver = Callable[["ToolCallProposed"], Decision]


def auto_approve(proposed: "ToolCallProposed") -> Decision:
    """Explicit opt-in for trusted execution planes; never blocks."""

    return Decision.ALLOW
