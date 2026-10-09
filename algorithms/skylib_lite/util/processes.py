"""First-party finite pipe capture and optional owned-process receipts.

Receipts let a containing runtime clean up solver groups that start separate
sessions. They are written only for freshly created Popen children, never for
a caller-supplied PID. No dependency on the tools/application layer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import selectors
import subprocess
import time

MAX_SOLVER_OUTPUT_BYTES = 8 * 1024 * 1024
OWNED_GROUPS_ENV = "MARS_OWNED_PROCESS_RECEIPTS"


def process_birth(pid: int) -> str | None:
    """Linux start tick for PID-reuse detection; absent on other platforms."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def record_owned_group(proc: subprocess.Popen) -> Path | None:
    directory = os.environ.get(OWNED_GROUPS_ENV)
    if not directory:
        return None
    path = Path(directory) / str(proc.pid)
    with path.open("x", encoding="utf-8") as handle:
        os.chmod(path, 0o600)
        json.dump({"pid": proc.pid, "birth": process_birth(proc.pid)}, handle)
    return path


def bounded_communicate(proc: subprocess.Popen, timeout: float) -> tuple[str, str]:
    """POSIX pipe capture: combined bytes bounded *before* buffer extension."""
    deadline = time.monotonic() + timeout
    buffers = [bytearray(), bytearray()]
    total = 0
    with selectors.DefaultSelector() as selector:
        for index, stream in enumerate((proc.stdout, proc.stderr)):
            selector.register(stream, selectors.EVENT_READ, index)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(proc.args, timeout,
                                                output=bytes(buffers[0]), stderr=bytes(buffers[1]))
            for key, _ in selector.select(min(.1, remaining)):
                chunk = os.read(key.fileobj.fileno(), 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                total += len(chunk)
                if total > MAX_SOLVER_OUTPUT_BYTES:
                    raise ValueError("Solver stdout/stderr exceeds the 8 MiB capture budget.")
                buffers[key.data].extend(chunk)
        proc.wait(timeout=max(.001, deadline - time.monotonic()))
    return tuple(bytes(buffer).decode("utf-8", "replace") for buffer in buffers)
