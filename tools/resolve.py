"""MARS: shared name resolution for ``tools``.

Wraps ``algorithms.query.simbad.resolve_simbad`` so every tool that needs "which sky
position is this object" goes through the same path, and a name that doesn't
resolve produces one consistent ``not_found`` result instead of a different
astroquery exception per service.

Most name-based astroquery calls (VizieR/NED/MAST ``query_object``) already
resolve names internally, so calling this first is not required before using
them -- it exists to give a caller ``resolve_target`` as a tool in its own
right (``docs/tool-architecture.md`` section 4) and a shared not-found path.
Resolution is strict: SIMBAD failing to answer is ``provider_unavailable``,
never ``not_found``, and the next call retries it.
CASDA's region query is the one backend here that only accepts coordinates,
not a name, so ``tools.casda`` uses ``resolve_target_coords`` directly.
"""

from __future__ import annotations

from typing import Optional

from algorithms.query.simbad import (
    ResolvedTarget,
    SimbadResponseError,
    SimbadUnavailableError,
    resolve_simbad,
)

from tools.models import ToolResult

__all__ = ["SimbadUnavailableError", "provider_error", "resolve_target", "resolve_target_coords"]


def provider_error(exc: SimbadUnavailableError) -> ToolResult:
    """The error result for a SIMBAD lookup that could not be made.

    ``provider_unavailable`` when SIMBAD failed and a later call may succeed;
    ``dependency_missing`` when astroquery itself is not importable.
    """
    if isinstance(exc, SimbadResponseError):
        return ToolResult(
            status="error",
            errors=[{"code": "unusable_response", "message": str(exc)}],
        )
    if not exc.retryable:
        return ToolResult(
            status="error",
            errors=[{
                "code": "dependency_missing",
                "message": f"{exc} Name resolution needs astroquery installed; "
                "retrying will not help.",
            }],
        )
    return ToolResult(
        status="error",
        errors=[{
            "code": "provider_unavailable",
            "message": f"{exc} The name was not looked up; retrying may succeed.",
        }],
    )


def resolve_target(name: str) -> ToolResult:
    """Resolve a free-text identifier to sky coordinates and an object type.

    Returns every SIMBAD match for an ambiguous name (there is usually one).
    A name that simply isn't a known SIMBAD object is an ordinary outcome,
    reported as ``not_found`` rather than an error. SIMBAD being unreachable
    is not, and is reported as ``provider_unavailable``.
    """
    if not name or not name.strip():
        return ToolResult(
            status="error",
            errors=[{"code": "invalid_input", "message": "name must not be blank"}],
        )

    try:
        matches = resolve_simbad(name, strict=True)
    except SimbadUnavailableError as exc:
        return provider_error(exc)
    if not matches:
        return ToolResult(status="not_found", count=0)

    preview = [
        {
            "object_name": m.object_name,
            "ra_deg": m.ra_deg,
            "dec_deg": m.dec_deg,
            "object_type": m.object_type,
            "source": m.source,
        }
        for m in matches
    ]
    return ToolResult(
        status="ok",
        count=len(preview),
        preview=preview,
        columns=["object_name", "ra_deg", "dec_deg", "object_type", "source"],
    )


def resolve_target_coords(name: str) -> Optional[ResolvedTarget]:
    """Return the first SIMBAD match for ``name``, or ``None`` for no match.

    For tools that need numeric coordinates directly (``tools.casda``)
    rather than a ``ToolResult`` to hand back to a caller. Raises
    :class:`SimbadUnavailableError` when SIMBAD could not be asked, so that
    an outage is not reported as an unknown name; ``provider_error`` turns
    it into the tool result.
    """
    matches = resolve_simbad(name, strict=True)
    return matches[0] if matches else None
