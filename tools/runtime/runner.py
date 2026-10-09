"""An owned, cancellable process per call; never abandon a writing thread."""

from __future__ import annotations

import json
import os
from pathlib import Path
import pickle
import signal
import subprocess
import sys
from dataclasses import asdict

import anyio

from algorithms.skylib_lite.util.processes import OWNED_GROUPS_ENV, process_birth
from tools import config
from tools.models import ToolError
from tools.mcp.surface import error_payload
from .limits import CallLimits
from .storage import create_call, finish_call, managed_root, private_write, tree_size


def _signal_group(pid: int, sig: int, birth: str | None = None) -> None:
    if pid <= 1 or pid in {os.getpid(), os.getpgrp()}:
        raise ValueError("Refusing to signal the runtime's own process group.")
    current = process_birth(pid)
    if birth is not None and current is not None and current != birth:
        return
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass


def _owned_groups(work: Path) -> list[tuple[int, str | None]]:
    groups = []
    directory = work / "groups"
    for index, receipt in enumerate(directory.iterdir()):
        if index >= 32:
            raise ValueError("Owned subprocess receipt budget exceeded.")
        if receipt.is_symlink() or receipt.stat().st_size > 4096:
            raise ValueError("Invalid owned subprocess receipt.")
        record = json.loads(receipt.read_text())
        pid = record["pid"]
        if (isinstance(pid, bool) or not isinstance(pid, int) or pid <= 1
                or pid in {os.getpid(), os.getpgrp()} or str(pid) != receipt.name):
            raise ValueError("Invalid owned subprocess PID.")
        birth = process_birth(pid)
        # A live reused PID must never be signalled. An exited POSIX group
        # leader may still own helpers; the live group retains its identifier.
        if record.get("birth") is not None and birth is not None and birth != record["birth"]:
            continue
        groups.append((pid, record.get("birth")))
    return groups


async def _stop(proc: subprocess.Popen, work: Path, birth: str | None) -> None:
    """Shielded, finite termination/reaping of this worker and owned groups."""
    if os.name == "posix":
        try:
            groups = _owned_groups(work)
        except (ValueError, OSError, KeyError, TypeError):
            # Invalid metadata must never prevent the fresh worker from being
            # killed. Do not act on unverifiable external group identifiers.
            groups = []
        for pid, started in [*groups, (proc.pid, birth)]:
            _signal_group(pid, signal.SIGTERM, started)
        await anyio.sleep(.1)
        # KILL also after a leader exits; TERM-resistant helpers are not done.
        for pid, started in [*groups, (proc.pid, birth)]:
            _signal_group(pid, signal.SIGKILL, started)
    elif proc.poll() is None:
        # The supported Windows runtime has taskkill; retain a finite direct
        # fallback if it is unavailable. Native tree tests are required M1 CI.
        command = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/taskkill.exe"
        try:
            subprocess.run([str(command), "/PID", str(proc.pid), "/T", "/F"],
                           timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            proc.kill()
    # Poll instead of a blocking wait in the async server, with a hard backstop.
    with anyio.move_on_after(5):
        while proc.poll() is None:
            await anyio.sleep(.02)
    if proc.poll() is None:
        proc.kill()
        with anyio.move_on_after(2):
            while proc.poll() is None:
                await anyio.sleep(.02)
    if proc.poll() is None:
        raise RuntimeError("Owned worker could not be reaped within the cleanup budget.")


async def run_call(name, arguments, functions, artifact_root: Path, limits: CallLimits) -> dict:
    function = functions.get(name)
    if function is None:
        return error_payload(ToolError(code="unknown_tool", message=f"No tool named {name!r} is served."))
    try:
        job = pickle.dumps((name, dict(arguments), function, limits), protocol=5)
    except (TypeError, AttributeError, pickle.PicklingError):
        return error_payload(ToolError(code="invalid_input", message="Served functions must be importable Python callables (not local closures)."))
    if len(job) > limits.input_bytes:
        return error_payload(ToolError(code="invalid_input", message="Tool arguments exceed the 1 MiB call-input budget."))
    work = download = proc = birth = None
    state = "failed"
    try:
        root = managed_root(Path(artifact_root))
        retained_work = tree_size(root, max_files=100_000)
        if retained_work + limits.work_bytes > limits.retained_bytes:
            raise ValueError("Retained runtime artifacts exceed the 5 GiB budget; run cleanup.")
        if arguments.get("download"):
            download_root = managed_root(Path(config.FITS_DOWNLOAD_DIR))
            retained_downloads = tree_size(download_root, max_files=100_000)
            if retained_downloads + limits.download_bytes > limits.retained_bytes:
                raise ValueError("Retained runtime downloads exceed the 5 GiB budget; run cleanup.")
        work = create_call(root)
        if arguments.get("download"):
            download = create_call(download_root, identifier=work.name)
        for directory in ("groups", "tmp", "cache", "artifacts"):
            (work / directory).mkdir(mode=0o700)
        for directory in ("cache/astropy", "cache/config", "cache/config/astropy", "cache/numba"):
            (work / directory).mkdir(mode=0o700)
        with (work / "input.pickle").open("xb") as handle:
            os.chmod(handle.name, 0o600)
            handle.write(job)
        private_write(work / "limits.json", asdict(limits))
        env = {**os.environ, "MARS_ARTIFACT_DIR": str(Path(artifact_root).resolve()),
               "MARS_DATA_DIR": str(config.DATA_DIR), "MPLBACKEND": "Agg",
               "TMPDIR": str(work / "tmp"), "TEMP": str(work / "tmp"), "TMP": str(work / "tmp"),
               "XDG_CACHE_HOME": str(work / "cache"),
               "XDG_CONFIG_HOME": str(work / "cache/config"),
               "ASTROPY_CACHE_DIR": str(work / "cache/astropy"),
               "ASTROPY_CONFIG_DIR": str(work / "cache/config/astropy"),
               "NUMBA_CACHE_DIR": str(work / "cache/numba"),
               OWNED_GROUPS_ENV: str(work / "groups"),
               "PYTHONPATH": os.pathsep.join(str(Path(path or os.curdir).resolve()) for path in sys.path)}
        # Bound import-time BLAS pools as well as work-time native allocations.
        for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
            env[key] = "1"
        if download is not None:
            env["MARS_FITS_DOWNLOAD_DIR"] = str(download)
        with (work / "stdout.log").open("xb") as out, (work / "stderr.log").open("xb") as err:
            os.chmod(out.name, 0o600)
            os.chmod(err.name, 0o600)
            proc = subprocess.Popen([sys.executable, "-m", "tools.runtime.worker", str(work)],
                                    env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                    start_new_session=(os.name == "posix"))
            birth = process_birth(proc.pid)
            with anyio.fail_after(limits.timeout_s):
                while True:
                    if tree_size(work, max_files=limits.files) > limits.work_bytes:
                        raise ValueError("Call work/artifact directory exceeds its byte budget.")
                    if download is not None and tree_size(download, max_files=limits.files) > limits.download_bytes:
                        raise ValueError("Call download directory exceeds its byte budget.")
                    if sum(path.stat().st_size for path in (work / "stdout.log", work / "stderr.log")) > limits.log_bytes:
                        raise ValueError("Call stdout/stderr exceeds its byte budget.")
                    if proc.poll() is not None:
                        break
                    await anyio.sleep(.05)
            reply = work / "reply.json"
            if proc.returncode != 0 or not reply.is_file() or reply.stat().st_size > limits.reply_bytes:
                return error_payload(ToolError(code="resource_limit", message="Owned tool worker failed or exceeded its resource budget; no partial artifact is advertised."))
            with reply.open("rb") as handle:
                data = handle.read(limits.reply_bytes + 1)
            if len(data) > limits.reply_bytes:
                raise ValueError("Call reply exceeds its byte budget.")
            payload = json.loads(data)
            if not isinstance(payload, dict):
                raise ValueError("Worker result is not a JSON object.")
            for path in (work / "stdout.log", work / "stderr.log"):
                with path.open("rb") as handle:
                    diagnostic = handle.read(65_536).decode("utf-8", "replace")
                if diagnostic:
                    sys.stderr.write(diagnostic)
            state = "failed" if payload.get("status") == "error" else "complete"
            return payload
    except TimeoutError:
        return error_payload(ToolError(code="tool_timeout", message=f"Tool call exceeded its {limits.timeout_s:g}-second whole-call budget; owned work was stopped."))
    except (ValueError, OSError) as exc:
        return error_payload(ToolError(code="resource_limit", message=str(exc)))
    except anyio.get_cancelled_exc_class():
        state = "cancelled"
        raise
    finally:
        with anyio.CancelScope(shield=True):
            if proc is not None:
                await _stop(proc, work, birth)
            if work is not None:
                finish_call(work, state)
            if download is not None:
                finish_call(download, state)
