"""Private parent-created job execution; never accepts a client-supplied pickle."""

import json
import os
from pathlib import Path
import pickle
import signal
import sys


def _interrupt(signum, frame):
    raise KeyboardInterrupt


def _limits(limits):
    if os.name == "posix":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (limits.memory_bytes, limits.memory_bytes))
        # A hard per-file backstop accompanies the parent's aggregate checks.
        maximum = max(limits.work_bytes, limits.download_bytes)
        resource.setrlimit(resource.RLIMIT_FSIZE, (maximum, maximum))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    elif os.name == "nt":
        from .windows import own_job
        return own_job(limits.memory_bytes)
    else:
        raise RuntimeError("No bounded worker runtime for this platform.")


def main():
    work = Path(sys.argv[1])
    from .limits import CallLimits
    with (work / "limits.json").open("rb") as handle:
        raw = handle.read(4097)
    if len(raw) > 4096:
        raise ValueError("Oversized worker limits record.")
    limits = CallLimits(**json.loads(raw))
    owned_job = _limits(limits)  # Lifetime intentionally spans the worker.
    # File is private and created by this install's parent; the callable is
    # from the validated served registry, not serialized by an MCP caller.
    with (work / "input.pickle").open("rb") as handle:
        name, arguments, function, limits = pickle.load(handle)
    if os.name == "posix":
        signal.signal(signal.SIGTERM, _interrupt)
    from tools import artifacts
    from tools.mcp.surface import call_tool, error_payload
    from tools.models import ToolError
    try:
        with artifacts.scoped_artifacts(f".mars-runtime/{work.name}/artifacts"):
            payload = call_tool(name, arguments, {name: function})
    except MemoryError:
        payload = error_payload(ToolError(code="resource_limit", message="Tool worker exhausted its memory budget."))
    stage = work / "reply.part"
    total = 0
    with stage.open("x", encoding="utf-8") as handle:
        os.chmod(stage, 0o600)
        for chunk in json.JSONEncoder(ensure_ascii=False).iterencode(payload):
            total += len(chunk.encode("utf-8"))
            if total > limits.reply_bytes:
                raise ValueError("Tool reply exceeds its byte budget.")
            handle.write(chunk)
    stage.replace(work / "reply.json")


if __name__ == "__main__":
    main()
