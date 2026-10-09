"""Offline real-worker bounds, cancellation, ownership and retention probes."""

import ctypes
from dataclasses import replace
import json
import os
from pathlib import Path
import time

import anyio
import pytest

from tests import runtime_fakes as fake
from tools.runtime.limits import CallLimits
from tools.runtime.runner import run_call, _owned_groups, _signal_group
from tools.runtime.storage import (CALL_FILE, cleanup, create_call, finish_call,
                                   managed_root, private_write, tree_size)
from tools.runtime.windows import Accounting, ExtendedLimits
from tools.runtime.darwin import TaskInfo


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _running(pid):
    if os.name == "nt":
        # os.kill(pid, 0) is NOT a safe existence probe on Windows.
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.WaitForSingleObject.restype = ctypes.c_uint32
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE only
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT
        finally:
            kernel.CloseHandle(handle)
    if os.name == "posix" and Path(f"/proc/{pid}/stat").exists():
        # A helper reparented to container PID 1 can be a zombie, not a writer.
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


async def _ready(path):
    with anyio.fail_after(10):
        while not path.exists():
            await anyio.sleep(.02)
    return int(path.read_text())


@pytest.mark.anyio
async def test_cancel_stops_writer_and_next_call_can_run(tmp_path):
    ready = tmp_path / "ready"
    root = tmp_path / "artifacts"
    scope = anyio.CancelScope()
    async def call():
        with scope:
            await run_call("write", {"ready": str(ready)}, {"write": fake.write_then_stall}, root, CallLimits(timeout_s=15))
    async with anyio.create_task_group() as tasks:
        tasks.start_soon(call)
        pid = await _ready(ready)
        scope.cancel()
    assert not _running(pid)
    calls = [p for p in (root / ".mars-runtime").iterdir() if p.is_dir()]
    assert len(calls) == 1
    assert json.loads((calls[0] / CALL_FILE).read_text())["state"] == "cancelled"
    size = tree_size(calls[0], max_files=100)
    await anyio.sleep(.1)
    assert tree_size(calls[0], max_files=100) == size
    result = await run_call("next", {}, {"next": fake.noisy}, root, CallLimits(timeout_s=10))
    assert result["status"] == "ok"


@pytest.mark.anyio
async def test_whole_call_deadline_stops_worker(tmp_path):
    ready = tmp_path / "ready"
    start = time.monotonic()
    result = await run_call("stall", {"ready": str(ready)}, {"stall": fake.stall}, tmp_path / "artifacts", CallLimits(timeout_s=2))
    assert result["errors"][0]["code"] == "tool_timeout"
    assert not result.get("artifacts")
    assert time.monotonic() - start < 10
    if ready.exists():
        assert not _running(int(ready.read_text()))


@pytest.mark.anyio
async def test_failed_worker_diagnostics_are_operator_only(tmp_path, capsys):
    result = await run_call("fail", {}, {"fail": fake.fail_before_reply},
                            tmp_path / "artifacts", CallLimits(timeout_s=10))
    assert result["errors"][0]["code"] == "resource_limit"
    assert "private-worker-diagnostic" not in json.dumps(result)
    captured = capsys.readouterr()
    assert not captured.out
    assert "private-worker-diagnostic" in captured.err
    assert "exited with code 17" in captured.err


def test_operator_diagnostics_are_byte_bounded(tmp_path, capsys):
    from tools.runtime.runner import _diagnostics
    (tmp_path / "stderr.log").write_bytes(b"x" * 100_000 + b"never-forward-this-tail")
    _diagnostics(tmp_path, 0)
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err == "x" * 65_536


@pytest.mark.anyio
@pytest.mark.parametrize("function,changes", [
    (fake.oversized_reply, {"reply_bytes": 1024}),
    (fake.overflow_work, {"work_bytes": 10_000}),
    (fake.overflow_log, {"log_bytes": 1024}),
    (fake.exhaust_memory, {"memory_bytes": 128 * 1024**2}),
])
async def test_real_worker_resource_failure_has_no_partial_artifact(tmp_path, function, changes):
    result = await run_call("bounded", {}, {"bounded": function}, tmp_path / "artifacts",
                            replace(CallLimits(timeout_s=10), **changes))
    assert result["status"] == "error"
    assert result["errors"][0]["code"] == "resource_limit"
    assert not result.get("artifacts")
    call = next(p for p in (tmp_path / "artifacts/.mars-runtime").iterdir() if p.is_dir())
    assert json.loads((call / CALL_FILE).read_text())["state"] == "failed"


@pytest.mark.anyio
@pytest.mark.skipif(not Path("/proc/self/stat").exists(), reason="Linux native solver/group probe")
async def test_cancel_stops_owned_separate_solver_group(tmp_path):
    root = tmp_path / "artifacts"
    ready = tmp_path / "ready"
    scope = anyio.CancelScope()
    async def call():
        with scope:
            await run_call("solve", {"ready": str(ready)}, {"solve": fake.solver_descendant}, root, CallLimits(timeout_s=15))
    async with anyio.create_task_group() as tasks:
        tasks.start_soon(call)
        worker = await _ready(ready)
        with anyio.fail_after(10):
            while True:
                receipts = list(root.glob(".mars-runtime/*/groups/*"))
                if receipts:
                    solver = int(receipts[0].name)
                    children = Path(f"/proc/{solver}/task/{solver}/children")
                    if children.exists() and children.read_text().strip():
                        helper = int(children.read_text().split()[0])
                        break
                await anyio.sleep(.02)
        scope.cancel()
    assert not _running(worker)
    with anyio.fail_after(5):
        while _running(solver) or _running(helper):
            await anyio.sleep(.02)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), 1801, True])
def test_timeout_is_never_unbounded(timeout):
    with pytest.raises(ValueError):
        CallLimits(timeout_s=timeout)


@pytest.mark.parametrize("field", [f for f in CallLimits.__dataclass_fields__ if f != "timeout_s"])
def test_byte_and_entry_budgets_are_positive_integers(field):
    with pytest.raises(ValueError):
        replace(CallLimits(), **{field: True})


def test_cleanup_dry_run_does_not_create_a_namespace(tmp_path):
    root = tmp_path / "unused"
    assert cleanup(root) == []
    assert not root.exists()


def test_cleanup_removes_only_expired_owned_finished_calls(tmp_path):
    root = tmp_path / "outputs"
    dataset = root / "operator.fits"
    root.mkdir()
    dataset.write_bytes(b"keep")
    managed = managed_root(root)
    old = create_call(managed)
    finish_call(old, "complete")
    record = json.loads((old / CALL_FILE).read_text())
    private_write(old / CALL_FILE, {**record, "created": time.time() - 31 * 86400})
    running = create_call(managed)
    recent = create_call(managed)
    finish_call(recent, "complete")
    unmarked = managed / ("a" * 32)
    unmarked.mkdir()
    assert cleanup(root) == [old]
    assert old.exists()
    assert cleanup(root, apply=True) == [old]
    assert not old.exists()
    assert dataset.read_bytes() == b"keep"
    assert running.exists() and recent.exists() and unmarked.exists()


def test_unowned_namespace_is_never_adopted(tmp_path):
    (tmp_path / ".mars-runtime").mkdir()
    with pytest.raises((ValueError, OSError)):
        managed_root(tmp_path)
    with pytest.raises((ValueError, OSError)):
        cleanup(tmp_path, apply=True)


@pytest.mark.skipif(os.name != "posix", reason="POSIX receipt signaling")
def test_own_or_reused_pid_receipts_never_get_signalled(tmp_path, monkeypatch):
    (tmp_path / "groups").mkdir()
    pid = os.getpid()
    (tmp_path / "groups" / str(pid)).write_text(json.dumps({"pid": pid, "birth": "old"}))
    with pytest.raises(ValueError):
        _owned_groups(tmp_path)
    calls = []
    monkeypatch.setattr("tools.runtime.runner.process_birth", lambda pid: "new")
    monkeypatch.setattr(os, "killpg", lambda *args: calls.append(args))
    _signal_group(pid + 999_999, 9, "old")
    assert calls == []


def test_windows_job_uses_windows_widths_not_host_long_width():
    assert ctypes.sizeof(Accounting) == 48
    assert Accounting.active_processes.offset == 40
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        assert ctypes.sizeof(ExtendedLimits) == 144
        assert ExtendedLimits.job_memory.offset == 120


def test_macos_task_info_matches_native_abi():
    assert ctypes.sizeof(TaskInfo) == 96
    assert TaskInfo.virtual_size.offset == 0
    assert TaskInfo.resident_size.offset == 8
    assert TaskInfo.policy.offset == 48


def test_macos_allowance_is_added_once_to_measured_bootstrap(monkeypatch):
    from tools.runtime import darwin
    monkeypatch.setattr(darwin, "bootstrap_size", lambda: 400 * 1024**3)
    assert darwin.memory_ceiling(128 * 1024**2) == 400 * 1024**3 + 128 * 1024**2


@pytest.mark.skipif(os.name != "posix", reason="POSIX memory setup seam")
@pytest.mark.parametrize("inherited", [-1, 256 * 1024**2])
def test_macos_memory_setup_is_finite_and_respects_inherited_limit(monkeypatch, inherited):
    import resource
    from tools.runtime import worker, darwin
    calls = []
    monkeypatch.setattr(worker.sys, "platform", "darwin")
    monkeypatch.setattr(darwin, "memory_ceiling", lambda allowance: 400 * 1024**3 + allowance)
    monkeypatch.setattr(resource, "getrlimit", lambda kind: (inherited, inherited))
    monkeypatch.setattr(resource, "setrlimit", lambda kind, values: calls.append((kind, values)))
    worker._limits(CallLimits())
    expected = 404 * 1024**3 if inherited == -1 else inherited
    assert calls[0] == (resource.RLIMIT_AS, (expected, expected))
    assert expected > 0


def test_windows_worker_command_bypasses_redirector_without_losing_venv(tmp_path, monkeypatch):
    from tools.runtime import runner
    monkeypatch.setattr(runner.sys, "executable", "C:/venv/Scripts/python.exe")
    monkeypatch.setattr(runner.sys, "_base_executable", "C:/Python313/python.exe")
    env = {}
    command = runner._worker_command(tmp_path, env, windows=True)
    assert command == ["C:/Python313/python.exe", "-m", "tools.runtime.worker", str(tmp_path)]
    assert env["__PYVENV_LAUNCHER__"] == "C:/venv/Scripts/python.exe"
    env = {}
    assert runner._worker_command(tmp_path, env, windows=False)[0] == "C:/venv/Scripts/python.exe"
    assert not env


@pytest.mark.anyio
async def test_interpreter_pid_and_venv_match_the_launched_process(tmp_path, monkeypatch):
    from tools.runtime import runner
    launched = []
    original = runner.subprocess.Popen
    def record(*args, **kwargs):
        proc = original(*args, **kwargs)
        launched.append(proc.pid)
        return proc
    monkeypatch.setattr(runner.subprocess, "Popen", record)
    result = await run_call("identity", {}, {"identity": fake.identity},
                            tmp_path / "artifacts", CallLimits(timeout_s=10))
    assert result["status"] == "ok"
    assert result["preview"] == [{"pid": launched[0], "prefix": runner.sys.prefix}]
    assert not _running(launched[0])


@pytest.mark.anyio
async def test_windows_stop_waits_for_job_even_after_interpreter_exit():
    from tools.runtime.runner import _stop_windows
    events = []
    class Process:
        def poll(self):
            return 0
        def kill(self):
            pytest.fail("Exited process must not be killed.")
    class Job:
        polls = 0
        def terminate(self):
            events.append("terminate")
        def empty(self):
            self.polls += 1
            return self.polls >= 3
        def close(self):
            assert self.polls >= 3
            events.append("close")
    await _stop_windows(Process(), Job())
    assert events == ["terminate", "terminate", "close"]


@pytest.mark.anyio
async def test_windows_stop_kills_interpreter_not_yet_in_job():
    from tools.runtime.runner import _stop_windows
    events = []
    class Process:
        alive = True
        def poll(self):
            return None if self.alive else 1
        def kill(self):
            events.append("kill")
            self.alive = False
    class Job:
        def terminate(self):
            events.append("terminate")
        def empty(self):
            return True
        def close(self):
            events.append("close")
    await _stop_windows(Process(), Job())
    assert events == ["terminate", "kill", "terminate", "close"]


@pytest.mark.anyio
async def test_windows_job_failure_is_not_reported_as_success():
    from tools.runtime.runner import _stop_windows
    class Job:
        closed = False
        def terminate(self):
            raise OSError("job termination failed")
        def close(self):
            self.closed = True
    job = Job()
    with pytest.raises(OSError, match="job termination failed"):
        await _stop_windows(None, job)
    assert job.closed


@pytest.mark.anyio
async def test_mcp_cancellation_releases_sequential_dispatch_lock(tmp_path):
    pytest.importorskip("mcp")
    from mcp.client.client import Client
    from tools.mcp.server import build_server
    ready = tmp_path / "ready"
    schemas = [{"name": "writer", "description": "offline writing cancellation probe",
                "input_schema": {"type": "object", "properties": {"ready": {"type": "string"}}}},
               {"name": "next", "description": "offline successful control",
                "input_schema": {"type": "object", "properties": {}}}]
    server = build_server(schemas, {"writer": fake.write_then_stall, "next": fake.noisy},
                          artifact_root=tmp_path / "artifacts", call_limits=CallLimits(timeout_s=15))
    scope = anyio.CancelScope()
    async with Client(server) as client:
        async def call():
            with scope:
                await client.call_tool("writer", {"ready": str(ready)})
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(call)
            pid = await _ready(ready)
            scope.cancel()
        with anyio.fail_after(10):
            result = await client.call_tool("next", {})
        assert result.structured_content["status"] == "ok"
        assert not _running(pid)


def test_cleanup_cli_dry_run_needs_no_sdk_and_creates_no_output_tree(tmp_path):
    import subprocess
    import sys
    root = tmp_path / "mars-home"
    proc = subprocess.run([sys.executable, "-m", "tools.mcp", "cleanup"],
                          env={**os.environ, "MARS_HOME": str(root),
                               "MARS_ARTIFACT_DIR": str(root / "artifacts"),
                               "MARS_FITS_DOWNLOAD_DIR": str(root / "downloads")},
                          capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, proc.stderr
    assert "Dry-run" in proc.stdout
    assert not root.exists()


@pytest.mark.anyio
async def test_scientific_caches_stay_inside_managed_work(tmp_path):
    root = tmp_path / "artifacts"
    result = await run_call("cache", {}, {"cache": fake.cache_roots}, root, CallLimits(timeout_s=10))
    assert result["status"] == "ok"
    for path in result["preview"][0].values():
        assert Path(path).is_relative_to(root / ".mars-runtime")


@pytest.mark.anyio
async def test_successful_worker_cannot_leave_a_writing_native_helper(tmp_path):
    result = await run_call("child", {}, {"child": fake.leave_child}, tmp_path / "artifacts", CallLimits(timeout_s=10))
    assert result["status"] == "ok"
    pid = result["preview"][0]["child"]
    if os.name == "nt":
        # Job accounting, not a delay in the test, must establish this boundary.
        assert not _running(pid)
    with anyio.fail_after(5):
        while _running(pid):
            await anyio.sleep(.02)
