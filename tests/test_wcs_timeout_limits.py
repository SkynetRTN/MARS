"""WCS-02: finite attempt budgets and termination of the owned solver group."""

from __future__ import annotations

import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from algorithms.skylib_lite.astrometry.anet.backend import AstrometryNetBackend
from algorithms.skylib_lite.astrometry.anet.config import AstrometryNetConfig
from algorithms.skylib_lite.astrometry.atlas.config import AtlasConfig
from algorithms.skylib_lite.astrometry.anet.errors import SolveFieldTimeout
from algorithms.skylib_lite.astrometry.atlas.backend import AtlasBackend
from algorithms.skylib_lite.astrometry.types import SolveRequest
from algorithms.wcs.wcs import build_anet_config, build_atlas_config
from tools.wcs import solve_astrometry


@pytest.mark.parametrize("config_class", [AstrometryNetConfig, AtlasConfig])
@pytest.mark.parametrize("value", [None, 1., 12.5, 900., "17"])
def test_direct_config_has_a_finite_attempt_budget(config_class, value):
    config = config_class(timeout_s=value)
    assert config.timeout_s == (300. if value is None else float(value))


@pytest.mark.parametrize("config_class", [AstrometryNetConfig, AtlasConfig])
@pytest.mark.parametrize("value", [0, .5, -1, True, False, float("nan"), float("inf"), 901, 10**400, "bad"])
def test_direct_config_rejects_unbounded_or_invalid_budgets(config_class, value):
    with pytest.raises(ValueError, match="timeout"):
        config_class(timeout_s=value)


@pytest.mark.parametrize("builder", [build_anet_config, build_atlas_config])
@pytest.mark.parametrize("value", [None, "nan", "bad", 0, 901])
def test_duck_typed_builder_never_silently_removes_a_deadline(builder, value, tmp_path):
    settings = SimpleNamespace(ANET_INDEX_PATH=tmp_path, ATLAS_CATALOG_ROOT=tmp_path,
                               ANET_TIMEOUT_S=value, ATLAS_TIMEOUT_S=value)
    if value is None:
        assert builder(settings).timeout_s == 300.
    else:
        with pytest.raises(ValueError, match="timeout"):
            builder(settings)


@pytest.mark.parametrize("backend", ["anet", "atlas"])
@pytest.mark.parametrize("explicit", [None, 12.5])
def test_tool_defaults_and_explicit_environment_precedence(monkeypatch, tmp_path, backend, explicit):
    from algorithms.wcs.results import WcsSolveMetadata, WcsSolveResult

    for name in ("ANET_TIMEOUT_S", "ATLAS_TIMEOUT_S", "ANET_INDEX_PATH", "ATLAS_CATALOG_ROOT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANET_INDEX_PATH" if backend == "anet" else "ATLAS_CATALOG_ROOT", str(tmp_path))
    if explicit is not None:
        monkeypatch.setenv("ANET_TIMEOUT_S", "bad")
        monkeypatch.setenv("ATLAS_TIMEOUT_S", "bad")
    monkeypatch.setattr("tools.wcs._configured_backend_warnings", lambda _: ([], []))
    captured = []

    def fake_solve(*args, solver_settings, **kwargs):
        captured.append(solver_settings)
        return WcsSolveResult(wcs=None, catalog_sources=(), metadata=WcsSolveMetadata())

    monkeypatch.setattr("tools.wcs._solve_wcs", fake_solve)
    result = solve_astrometry(Path("data/optical/m15_globular_open_000.fits"), timeout_s=explicit)
    assert not result.errors
    assert len(captured) == 1
    expected = 300. if explicit is None else explicit
    assert captured[0].ANET_TIMEOUT_S == expected
    assert captured[0].ATLAS_TIMEOUT_S == expected


@pytest.mark.parametrize("backend", ["ANET", "ATLAS"])
@pytest.mark.parametrize("value", ["bad", "nan", "901"])
def test_invalid_configured_environment_budget_returns_a_structured_error(monkeypatch, tmp_path, backend, value):
    for name in ("ANET_INDEX_PATH", "ATLAS_CATALOG_ROOT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANET_INDEX_PATH" if backend == "ANET" else "ATLAS_CATALOG_ROOT", str(tmp_path))
    monkeypatch.setenv(f"{backend}_TIMEOUT_S", value)
    result = solve_astrometry(Path("data/optical/m15_globular_open_000.fits"))
    assert [error.code for error in result.errors] == ["invalid_timeout"]
    assert f"{backend}_TIMEOUT_S" in result.errors[0].message


@pytest.mark.parametrize("value", [True, False, 901, float("inf")])
def test_tool_invalid_budget_is_structured_and_cannot_reach_solver(monkeypatch, value):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid timeout reached solver")

    monkeypatch.setattr("tools.wcs._solve_wcs", forbidden)
    result = solve_astrometry(Path("data/optical/m15_globular_open_000.fits"), timeout_s=value)
    assert [error.code for error in result.errors] == ["invalid_timeout"]


@pytest.mark.parametrize("config_class", [AstrometryNetConfig, AtlasConfig])
def test_omitted_direct_config_budget_is_finite(config_class):
    assert config_class().timeout_s == 300.


@pytest.mark.parametrize("backend_class, config_class", [
    (AstrometryNetBackend, AstrometryNetConfig), (AtlasBackend, AtlasConfig),
])
@pytest.mark.parametrize("value", [float("nan"), 0, 901])
def test_mutated_configs_are_rejected_before_backend_work(backend_class, config_class, value, tmp_path):
    config = config_class()
    config.timeout_s = value
    with pytest.raises(ValueError, match="timeout"):
        backend_class().solve(SolveRequest(image_path=tmp_path / "absent.fits"), config)


@pytest.mark.parametrize("value, expected", [(None, 300.), (12.5, 12.5)])
def test_anet_deadline_reaches_cpu_and_subprocess_limits(monkeypatch, tmp_path, value, expected):
    captured = []

    def invoke(cmd, work, timeout):
        captured.append((cmd, timeout))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(AstrometryNetBackend, "_invoke_solve_field", staticmethod(invoke))
    AstrometryNetBackend()._run("fake-solve-field", tmp_path / "image.fits", tmp_path,
                              tmp_path / "config", SolveRequest(), use_hint=True,
                              config=AstrometryNetConfig(timeout_s=value))
    cmd, timeout = captured[0]
    assert int(cmd[cmd.index("--cpulimit") + 1]) == int(expected)
    assert timeout == expected + 30.


def test_invoke_omission_has_finite_outer_backstop(monkeypatch, tmp_path):
    captured = []

    class Process:
        returncode = 0

        def communicate(self, *, timeout):
            captured.append(timeout)
            return "", ""

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: Process())
    AstrometryNetBackend._invoke_solve_field(["fake"], tmp_path, None)
    assert captured == [330.]


def test_hinted_miss_retry_retains_the_finite_attempt_contract(monkeypatch, tmp_path):
    import algorithms.skylib_lite.astrometry.anet.backend as backend_module

    monkeypatch.setattr(backend_module, "find_solve_field", lambda _: "fake-solve-field")
    monkeypatch.setattr(backend_module, "validate_index_dirs", lambda _: ([str(tmp_path)], []))
    captured = []

    def invoke(cmd, work, timeout):
        captured.append(("--ra" in cmd, timeout))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(AstrometryNetBackend, "_invoke_solve_field", staticmethod(invoke))
    result = AstrometryNetBackend().solve(
        SolveRequest(image_path=tmp_path / "image.fits", radius=1, retry_lost=True),
        AstrometryNetConfig(index_path=str(tmp_path), timeout_s=3))
    assert result.wcs is None
    assert captured == [(True, 33.), (False, 33.)]


@pytest.mark.parametrize("value", [0, float("nan"), float("inf"), 931])
def test_invalid_outer_backstop_rejects_before_process_creation(monkeypatch, tmp_path, value):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid subprocess budget reached Popen")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    with pytest.raises(ValueError, match="timeout"):
        AstrometryNetBackend._invoke_solve_field(["fake"], tmp_path, value)


_CHILD = "import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print(os.getpid(),flush=True); time.sleep(60)"
_PARENT = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',sys.argv[1]]); time.sleep(60)"


def _is_running(pid):
    try:
        # A killed grandchild can briefly be a zombie under the host's init;
        # it is no longer running or retaining the inherited pipe.
        return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1][0] != "Z"
    except FileNotFoundError:
        return False


@pytest.mark.skipif(sys.platform != "linux", reason="Linux process-group/procfs regression")
@pytest.mark.parametrize("leader_already_exited", [False, True])
def test_termination_kills_stubborn_children_even_after_group_leader_exits(leader_already_exited):
    proc = subprocess.Popen([sys.executable, "-c", _PARENT, _CHILD],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            start_new_session=True)
    try:
        with selectors.DefaultSelector() as ready:
            ready.register(proc.stdout, selectors.EVENT_READ)
            assert ready.select(3), "owned child did not become ready"
            child_pid = int(proc.stdout.readline())
        if leader_already_exited:
            os.kill(proc.pid, signal.SIGTERM)
            proc.wait(timeout=2)
        started = time.monotonic()
        AstrometryNetBackend._kill_process_group(proc)
        until = time.monotonic() + 1
        while _is_running(child_pid) and time.monotonic() < until:
            time.sleep(.01)
        assert not _is_running(child_pid), "SIGTERM-resistant solver child survived cleanup"
        assert time.monotonic() - started < 7
        proc.communicate(timeout=1)
        assert proc.returncode is not None
    finally:
        # Every failure path cleans up only the session this test created.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate(timeout=2)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux process-group/procfs regression")
def test_actual_timeout_reaps_leader_kills_child_and_preserves_diagnostics(monkeypatch, tmp_path):
    # Capture only the process created by this invocation, for failure cleanup.
    original = subprocess.Popen
    owned = []

    def popen(*args, **kwargs):
        proc = original(*args, **kwargs)
        owned.append(proc)
        return proc

    monkeypatch.setattr(subprocess, "Popen", popen)
    try:
        started = time.monotonic()
        with pytest.raises(SolveFieldTimeout) as failure:
            AstrometryNetBackend._invoke_solve_field(
                [sys.executable, "-c", _PARENT, _CHILD], tmp_path, 1.)
        assert time.monotonic() - started < 8
        assert failure.value.timeout_sec == 1.
        child_pid = int(failure.value.stdout.strip())
        until = time.monotonic() + 1
        while _is_running(child_pid) and time.monotonic() < until:
            time.sleep(.01)
        assert not _is_running(child_pid)
        assert owned[0].returncode is not None
        assert owned[0].stdout.closed and owned[0].stderr.closed
    finally:
        for proc in owned:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate(timeout=2)
