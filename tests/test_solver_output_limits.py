"""Native, bounded WCS-21 capture and interruption probes, no solver data."""

import os
import subprocess
import sys
import time

import pytest

from algorithms.skylib_lite.astrometry.anet.backend import AstrometryNetBackend
from algorithms.skylib_lite.astrometry.anet.errors import SolveFieldFailed
from algorithms.skylib_lite.util import processes

pytestmark = pytest.mark.skipif(os.name != "posix", reason="astrometry.net is POSIX-only")


def test_native_solver_output_budget_stops_and_reaps(monkeypatch, tmp_path):
    monkeypatch.setattr(processes, "MAX_SOLVER_OUTPUT_BYTES", 32_768)
    started = time.monotonic()
    with pytest.raises(SolveFieldFailed, match="capture budget"):
        AstrometryNetBackend._invoke_solve_field(
            [sys.executable, "-c", "import os,time; os.write(1,b'x'*65536); time.sleep(60)"],
            tmp_path, 2)
    assert time.monotonic() - started < 7


def test_ordinary_solver_bytes_and_utf8_are_preserved(tmp_path):
    result = AstrometryNetBackend._invoke_solve_field(
        [sys.executable, "-c", "import sys; print('accepted Δ'); print('diagnostic',file=sys.stderr)"],
        tmp_path, 2)
    assert result.stdout == "accepted Δ\n"
    assert result.stderr == "diagnostic\n"


def test_interrupted_capture_reaps_owned_child(monkeypatch, tmp_path):
    import algorithms.skylib_lite.astrometry.anet.backend as backend
    owned = []
    original = subprocess.Popen
    def start(*args, **kwargs):
        proc = original(*args, **kwargs)
        owned.append(proc)
        return proc
    def interrupt(*args):
        raise KeyboardInterrupt
    monkeypatch.setattr(backend.subprocess, "Popen", start)
    monkeypatch.setattr(backend, "bounded_communicate", interrupt)
    with pytest.raises(KeyboardInterrupt):
        AstrometryNetBackend._invoke_solve_field(
            [sys.executable, "-c", "import time; time.sleep(60)"], tmp_path, 2)
    assert owned[0].poll() is not None
    assert owned[0].stdout.closed and owned[0].stderr.closed
