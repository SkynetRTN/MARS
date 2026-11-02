"""The console's tool calls: in owned workers it can stop, lookups excepted.

The engine calls each tool as a plain function on its own thread, and a thread
cannot be stopped: a plate solve or an archive download ran to its end
however long that took. So the console hands the engine functions that run
each call through the MCP server's owned-worker runtime
(``tools/runtime/runner.py``), which can kill a call -- and any solver it
started -- and which bounds its time, memory and disk as it does for MCP.

A worker costs a few seconds to start (about 2.5 s on the development host),
which a lookup that answers in milliseconds should not pay. The tools in
:data:`INLINE_TOOLS` run in-process; everything else, including any tool added
later, runs in a worker unless it is listed here deliberately. Only ``local``
tools may be listed (a test holds it): a call that waits on the network is
exactly the kind that needs stopping.

Artifacts: a worker writes them under the session folder, in
``.mars-runtime/<call>/artifacts/``; :func:`session_artifacts` lists those with
the session's own files.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping

from tools import artifacts
from tools.runtime.limits import CallLimits

if TYPE_CHECKING:
    from tools.models import ArtifactMetadata

__all__ = ["INLINE_TOOLS", "INTERRUPTED", "owned_tool_functions", "session_artifacts"]

#: Instant, local lookups: they read a bundled table, a directory or a header.
INLINE_TOOLS = frozenset(
    {
        "describe_artifact",
        "describe_image_wcs",
        "list_artifacts",
        "list_optical_frames",
        "list_photometric_catalogs",
        "list_photometry_targets",
        "list_pulsar_scans",
        "list_variable_star_fixtures",
        "list_zeropoint_references",
        "load_zeropoint_reference",
        "resolve_optical_frame",
        "resolve_pulsar_scan",
        "resolve_reference_band",
        "resolve_variable_star_fixture",
    }
)

#: What the model is told about a call the person stopped: the engine's own
#: wording for a call refused after a stop, so both read alike.
INTERRUPTED = {
    "status": "error",
    "errors": [{"code": "interrupted", "message": "stopped by the user"}],
}


def owned_tool_functions(
    functions: Mapping[str, Callable[..., Any]],
    interrupt: threading.Event,
    limits: CallLimits | None = None,
) -> dict[str, Callable[..., Any]]:
    """``functions``, with every tool not in :data:`INLINE_TOOLS` run in an
    owned worker that ``interrupt`` stops.

    Each wrapped call runs on the engine's thread, inside the session's
    artifact scope, and returns the worker's result -- or :data:`INTERRUPTED`
    once ``interrupt`` is set, after the worker and anything it started have
    been stopped.
    """

    limits = limits or CallLimits.from_environment()

    def owned(name: str) -> Callable[..., Any]:
        def call(**arguments: Any) -> dict[str, Any]:
            if interrupt.is_set():
                return dict(INTERRUPTED)
            root = Path(artifacts.ARTIFACT_DIR) / (artifacts.current_artifact_subdir() or "")
            return asyncio.run(_run_stoppable(name, arguments, functions, root, limits, interrupt))

        call.__name__ = name
        return call

    return {
        name: function if name in INLINE_TOOLS else owned(name)
        for name, function in functions.items()
    }


async def _run_stoppable(
    name: str,
    arguments: Mapping[str, Any],
    functions: Mapping[str, Callable[..., Any]],
    root: Path,
    limits: CallLimits,
    interrupt: threading.Event,
) -> dict[str, Any]:
    # Imported here: the runner pulls in the MCP surface, which a console
    # session that never calls a slow tool does not need.
    from tools.runtime.runner import run_call

    task = asyncio.ensure_future(run_call(name, dict(arguments), functions, root, limits))
    while not task.done():
        if interrupt.is_set():
            # The runner's cleanup is shielded: it stops the worker and its
            # solver groups before the cancellation reaches here.
            task.cancel()
            break
        await asyncio.sleep(0.05)
    try:
        return await task
    except asyncio.CancelledError:
        return dict(INTERRUPTED)


def session_artifacts(directory: Path) -> list["ArtifactMetadata"]:
    """A session folder's files: its own, then what its workers wrote."""

    from tools.workspace import describe_artifact, list_artifacts

    found = list(list_artifacts(directory))
    runtime = Path(directory) / ".mars-runtime"
    if runtime.is_dir() and not runtime.is_symlink():
        written = [
            path
            for call in sorted(runtime.iterdir())
            if (call / "artifacts").is_dir() and not (call / "artifacts").is_symlink()
            for path in sorted((call / "artifacts").rglob("*"))
            if path.is_file() and not path.is_symlink()
        ]
        found.extend(describe_artifact(path) for path in written)
    return found
