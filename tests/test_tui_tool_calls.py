"""The console's tool calls (tools/tui/tool_calls.py): owned workers Ctrl+C
can stop, with instant lookups kept in-process."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

from tests import runtime_fakes as fake
from tools import artifacts
from tools.registry import TOOL_FUNCTIONS
from tools.runtime.limits import CallLimits
from tools.tui.tool_calls import (
    INLINE_TOOLS,
    INTERRUPTED,
    owned_tool_functions,
    session_artifacts,
)

posix_only = pytest.mark.skipif(os.name != "posix", reason="worker probes run on POSIX here; CI covers Windows in test_runtime_limits")


def test_only_local_tools_run_in_process():
    """A call that waits on the network is exactly the kind that needs
    stopping, so no remote or mixed tool may skip the worker."""

    from tools.bench.plane import TOOL_CLASSES

    assert INLINE_TOOLS <= set(TOOL_FUNCTIONS)
    assert {name: TOOL_CLASSES[name] for name in INLINE_TOOLS if TOOL_CLASSES[name] != "local"} == {}


def test_lookups_stay_as_they_are_and_everything_else_is_wrapped():
    functions = owned_tool_functions(TOOL_FUNCTIONS, threading.Event())

    assert set(functions) == set(TOOL_FUNCTIONS)
    for name, function in functions.items():
        if name in INLINE_TOOLS:
            assert function is TOOL_FUNCTIONS[name], name
        else:
            assert function is not TOOL_FUNCTIONS[name], name


def test_a_call_after_the_interrupt_never_starts_a_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path)
    interrupt = threading.Event()
    interrupt.set()
    call = owned_tool_functions({"stall": fake.stall}, interrupt)["stall"]

    assert call(ready=str(tmp_path / "ready")) == INTERRUPTED
    assert not (tmp_path / ".mars-runtime").exists()


@posix_only
def test_an_interrupt_stops_a_running_worker_at_once(tmp_path, monkeypatch):
    """A tool that would run for a minute ends within moments of Ctrl+C, and
    its worker process is gone."""

    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path)
    interrupt = threading.Event()
    ready = tmp_path / "ready"
    call = owned_tool_functions({"stall": fake.stall}, interrupt, CallLimits(timeout_s=60))["stall"]

    def press_ctrl_c_once_running():
        while not ready.exists():
            time.sleep(0.05)
        interrupt.set()

    threading.Thread(target=press_ctrl_c_once_running, daemon=True).start()
    started = time.monotonic()
    result = call(ready=str(ready))
    stopped_after = time.monotonic() - started

    assert result == INTERRUPTED
    assert stopped_after < 30
    pid = int(ready.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@posix_only
def test_a_workers_artifacts_are_listed_with_the_session(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path)
    call = owned_tool_functions({"write": fake.write_artifact}, threading.Event())["write"]

    with artifacts.scoped_artifacts("sessions/s1"):
        result = call()

    assert result["status"] == "ok"
    session = tmp_path / "sessions" / "s1"
    (session / "session_manifest.json").write_text("{}")
    listed = [Path(item.file.path).name for item in session_artifacts(session)]
    assert "session_manifest.json" in listed
    assert any(name.startswith("made_in_a_worker") for name in listed)
