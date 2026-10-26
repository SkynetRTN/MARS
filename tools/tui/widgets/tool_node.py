"""One collapsible transcript node for a model-requested tool call."""

from __future__ import annotations

import json
import time
from typing import Any, Mapping

from rich.console import Group, RenderableType
from rich.syntax import Syntax
from rich.text import Text
from textual.widgets import Static

__all__ = ["ToolNode"]


class ToolNode(Static):
    """Render a proposed, running, finished, or denied tool call."""

    def __init__(
        self, call_id: str, name: str, arguments: Mapping[str, Any]
    ) -> None:
        super().__init__()
        self.call_id = call_id
        self.tool_name = name
        self.arguments = dict(arguments)
        self.state = "proposed"
        self.cache_hit = False
        self.result: dict[str, Any] | None = None
        self.artifacts: tuple[str, ...] = ()
        self.duration_ms: float | None = None
        self.reason: str | None = None
        self.expanded = False
        self._started_at: float | None = None
        self._refresh()

    def on_mount(self) -> None:
        """Keep a running call visibly alive without touching the engine."""

        self.set_interval(0.25, self._refresh_running_duration)

    def on_click(self) -> None:
        """Expand or collapse the full arguments and result details."""

        self.expanded = not self.expanded
        self._refresh()

    def start(self, cache_hit: bool) -> None:
        """Mark the call running and begin its elapsed-time display."""

        self.state = "running"
        self.cache_hit = cache_hit
        self._started_at = time.monotonic()
        self._refresh()

    def finish(
        self,
        result: Mapping[str, Any],
        artifacts: tuple[str, ...],
        duration_ms: float | None,
    ) -> None:
        """Record a completed result and its written artifacts."""

        self.state = "finished"
        self.result = dict(result)
        self.artifacts = tuple(artifacts)
        self.duration_ms = duration_ms
        self._refresh()

    def deny(self, reason: str) -> None:
        """Render a policy denial without pretending the call ran."""

        self.state = "denied"
        self.reason = reason
        self._refresh()

    def _refresh_running_duration(self) -> None:
        if self.state == "running":
            self._refresh()

    def _refresh(self) -> None:
        self.update(self._node_content())

    def _node_content(self) -> RenderableType:
        """Build this node's renderable.

        Named ``_node_content`` and not ``_render_content``: Textual's
        ``Widget._render_content`` is the private hook that fills the line
        cache every repaint. An override of that name with a different
        contract returns a renderable to a caller that wanted no return, the
        cache is filled with blanks, and every tool call in the transcript
        paints as an empty row while still reporting the right ``content``.
        """

        status, details = self._summary()
        header = Text(f"{status} {self.tool_name}{details}")
        if not self.expanded:
            return header

        parts: list[RenderableType] = [header, Text("Arguments:")]
        parts.append(Syntax(json.dumps(self.arguments, indent=2, default=str), "json"))
        if self.result is not None:
            parts.extend(
                [
                    Text("Result:"),
                    Syntax(json.dumps(self.result, indent=2, default=str), "json"),
                ]
            )
        if self.artifacts:
            parts.append(Text("Artifacts: " + ", ".join(self.artifacts)))
        if self.reason:
            parts.append(Text("Reason: " + self.reason))
        return Group(*parts)

    def _summary(self) -> tuple[str, str]:
        if self.state == "running":
            return "⠋", f" (running {_duration(self._elapsed_ms())})"
        if self.state == "finished":
            marker = " [cached]" if self.cache_hit else ""
            duration = "" if self.duration_ms is None else f" ({_duration(self.duration_ms)})"
            status, note = self._outcome()
            return status, f"{marker}{duration}{note}"
        if self.state == "denied":
            return "✗", " (denied)"
        return "…", " (proposed)"

    def _outcome(self) -> tuple[str, str]:
        """The marker and note a finished call earns from its own status.

        A call that ran is not a call that worked: a tool reports its failure
        as ``status: "error"`` in an ordinary result, and a ✓ beside it told
        the reader the opposite of what the model was told. Only ``ok`` gets
        the tick; the first error's message is shown, since it is the cause.
        """

        result = self.result or {}
        status = result.get("status")
        if status == "error":
            return "✗", f" — {_first_error(result) or 'failed'}"
        if status == "partial":
            return "!", f" — partial: {_first_error(result) or 'see result'}"
        if status == "not_found":
            return "∅", " — not found"
        return "✓", ""

    def _elapsed_ms(self) -> float:
        if self._started_at is None:
            return 0.0
        return (time.monotonic() - self._started_at) * 1000.0


def _duration(ms: float) -> str:
    """Milliseconds under a second, seconds under a minute, then minutes."""

    if ms < 1000:
        return f"{ms:.0f} ms"
    seconds = ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes} min {rest:02d} s"


def _first_error(result: Mapping[str, Any]) -> str:
    """The first error or warning message a result carries, bounded to a line."""

    for key in ("errors", "warnings"):
        entries = result.get(key)
        if isinstance(entries, list):
            for entry in entries:
                message = entry.get("message") if isinstance(entry, Mapping) else entry
                if message:
                    text = " ".join(str(message).split())
                    return text if len(text) <= 120 else text[:119] + "…"
    return ""
