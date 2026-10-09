"""Importable offline callables for native process-isolation tests."""

from pathlib import Path
import os
import subprocess
import sys
import time


def noisy():
    from tools.models import ToolResult
    print("[source_extraction] total_flux=1.0 num_sources=3")
    return ToolResult(status="ok", count=0)


def render(png, wav):
    from tools.models import ArtifactRef, ToolResult
    return ToolResult(status="ok", artifacts=[ArtifactRef(path=png, format="png"),
                                               ArtifactRef(path=wav, format="wav")])


def stall(ready):
    Path(ready).write_text(str(os.getpid()))
    time.sleep(60)


def write_then_stall(ready):
    from tools import artifacts
    path = artifacts.reserve_artifact_path("incomplete", ext="txt")
    path.write_text("partial, not a valid returned result")
    Path(ready).write_text(str(os.getpid()))
    while True:
        with path.open("a") as handle:
            handle.write("still running\n")
        time.sleep(.02)


def oversized_reply():
    from tools.models import ToolResult
    return ToolResult(status="ok", preview=[{"text": "x" * 100_000}])


def overflow_work():
    from tools import artifacts
    path = artifacts.reserve_artifact_path("large", ext="txt")
    with path.open("wb") as handle:
        handle.write(b"x" * 100_000)
    time.sleep(60)


def exhaust_memory():
    from tools.models import ToolResult
    allocation = bytearray(512 * 1024**2)
    return ToolResult(status="ok", count=len(allocation))


def overflow_log():
    print("x" * 100_000, flush=True)
    time.sleep(60)


def cache_roots():
    from astropy.config.paths import get_cache_dir
    from tools.models import ToolResult
    return ToolResult(status="ok", preview=[{"astropy": get_cache_dir(),
                                             "numba": os.environ["NUMBA_CACHE_DIR"]}])


def leave_child():
    from tools.models import ToolResult
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    return ToolResult(status="ok", preview=[{"child": child.pid}])


def solver_descendant(ready):
    from algorithms.skylib_lite.astrometry.anet.backend import AstrometryNetBackend
    # The solver starts its own session. Its receipt must let the parent stop
    # both it and a TERM-resistant helper after the runtime worker dies.
    child = "import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print(os.getpid(),flush=True); time.sleep(60)"
    parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',sys.argv[1]]); time.sleep(60)"
    Path(ready).write_text(str(os.getpid()))
    AstrometryNetBackend._invoke_solve_field([sys.executable, "-c", parent, child], Path(ready).parent, 60)
