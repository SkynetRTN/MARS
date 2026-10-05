"""M1 pulsar guards: unsafe work fails before loops or allocations."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from astropy.table import Table

from algorithms.pulsar import folding, limits, periodogram, sonification
from tools import pulsar


@pytest.mark.parametrize("expression", [
    "folding.float_mod(np.array([1.0]), 1e-300)",
    "folding.float_mod(np.array([np.inf]), 1.0)",
    "periodogram.lomb_scargle(np.arange(3.0), np.array([0., 1., 0.]), "
    "1.0, np.nextafter(1.0, 2.0), 1000)",
    "pulsar.fold_pulsar_lightcurve(path, 1e-300)",
    "pulsar.sonify_pulsar(path, sample_rate=1_000_000_000)",
    "pulsar.compute_pulsar_periodogram(path, start=1., "
    "stop=np.nextafter(1., 2.), steps=1000)",
])
def test_nonprogressing_work_is_rejected_in_a_bounded_subprocess(expression):
    # The READY marker distinguishes an import failure from a stuck call.
    # Always kill/reap the child on timeout; never stall pytest.
    source = (
        "import numpy as np\n"
        "from algorithms.pulsar import folding, periodogram\n"
        "from tools import pulsar\n"
        "from astropy.table import Table\n"
        "from pathlib import Path\n"
        "import tempfile\n"
        "directory = tempfile.TemporaryDirectory()\n"
        "path = Path(directory.name) / 'scan.ecsv'\n"
        "Table({'time_s': [0., 1., 2.], 'source1': [0., 1., 0.]}).write(path)\n"
        "print('READY', flush=True)\n"
        "input()\n"
        "try:\n"
        f"    result = {expression}\n"
        "except ValueError:\n"
        "    print('BLOCKED', flush=True)\n"
        "else:\n"
        "    assert hasattr(result, 'errors'), 'unsafe input was accepted'\n"
        "    assert [e.code for e in result.errors] == ['invalid_input']\n"
        "    assert result.artifact is None\n"
        "    print('BLOCKED', flush=True)\n"
    )
    child = subprocess.Popen(
        [sys.executable, "-u", "-c", source],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=Path(__file__).resolve().parents[1], text=True,
    )
    try:
        # communicate's total timeout bounds imports too; the newline releases
        # the call once the child has emitted READY.
        output, errors = child.communicate("\n", timeout=8)
    except subprocess.TimeoutExpired:
        child.kill()
        output, errors = child.communicate()
        pytest.fail(f"unsafe work did not terminate: {output!r} {errors!r}")
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()
    assert child.returncode == 0, errors
    assert output == "READY\nBLOCKED\n"


@pytest.mark.parametrize("settings", [
    {"sample_rate": 1_000_000_000},
    {"output_seconds": 1e300},
    {"output_seconds": float("nan")},
    {"speed": 1e-300},
    {"pass_seconds": 1e300},
    {"sample_rate": 192_000, "output_seconds": 25.0},
])
def test_audio_limits_precede_interpolation(monkeypatch, settings):
    def allocated(*args, **kwargs):
        pytest.fail("unsafe audio reached interpolation")

    monkeypatch.setattr(sonification, "interpolate_linear", allocated)
    arguments = {"pass_seconds": 1.0, "output_seconds": 0.1, **settings}
    with pytest.raises(ValueError):
        sonification.sonify(np.array([0.0, 1.0, 0.5]), **arguments)


@pytest.mark.parametrize("times, values", [
    ([0., 1., 2.], [1., 1., 1.]),
    ([0., 1., 2.], [np.nan, np.nan, np.nan]),
    ([0., 1., 2.], [0., np.inf, 1.]),
    ([1., 1., 1.], [0., 1., 0.]),
    ([0., 1.], [0., 1.]),
    ([0., 1., 2.], [0., 1e-300, 0.]),
])
def test_degenerate_periodograms_raise_a_declared_validation_error(times, values):
    with pytest.raises(ValueError):
        periodogram.compute_periodogram(
            np.array(times), np.array(values), start=0.1, stop=3.0, steps=10
        )


@pytest.mark.parametrize("settings", [
    {"speed": np.nan}, {"speed": np.inf},
    {"audio_seconds": np.nan}, {"sample_rate": 1_000_000_000},
    {"sample_rate": 1.5}, {"bins": 1_000_000_000, "period_s": 1.0},
])
def test_invalid_audio_settings_fail_before_loading(tmp_path, monkeypatch, settings):
    def loaded(*args, **kwargs):
        pytest.fail("invalid settings reached the data loader")

    monkeypatch.setattr(pulsar, "_load", loaded)
    result = pulsar.sonify_pulsar(tmp_path / "absent", **settings)
    assert [error.code for error in result.errors] == ["invalid_input"]


def test_constant_periodogram_is_a_structured_failure(tmp_path, artifact_dir):
    source = tmp_path / "constant.ecsv"
    Table({"time_s": [0., 1., 2.], "source1": [1., 1., 1.]}).write(source)
    result = pulsar.compute_pulsar_periodogram(source, start=0.1, stop=3., steps=10)
    assert [error.code for error in result.errors] == ["invalid_input"]
    assert result.artifact is None


def test_valid_small_audio_is_unchanged():
    result = sonification.sonify(
        np.array([0., 1., 0.]), pass_seconds=0.5, output_seconds=0.1, sample_rate=8000
    )
    assert result.frames == 800
    assert result.pcm.dtype == np.int16


def test_fold_work_budget_is_enforced_before_subtraction(monkeypatch):
    monkeypatch.setattr(limits, "MAX_FOLD_WORK", 1)
    with pytest.raises(ValueError, match="work budget"):
        folding.float_mod(np.array([0., 1., 2.]), 1.)


def test_periodogram_work_budget_precedes_trigonometry(monkeypatch):
    monkeypatch.setattr(limits, "MAX_PERIODOGRAM_WORK", 1)

    def expensive(*args, **kwargs):
        pytest.fail("oversized spectrum reached trigonometry")

    monkeypatch.setattr(periodogram.np, "sin", expensive)
    with pytest.raises(ValueError, match="work budget"):
        periodogram.compute_periodogram(
            np.arange(3.), np.array([0., 1., 0.]), start=0.1, stop=3., steps=10
        )


def test_interpolation_budget_precedes_allocation(monkeypatch):
    def allocated(*args, **kwargs):
        pytest.fail("oversized interpolation reached allocation")

    monkeypatch.setattr(sonification.np, "arange", allocated)
    with pytest.raises(ValueError, match="point budget"):
        sonification.interpolate_linear(np.array([0., 1.]), 4_000_000)


def test_file_budget_precedes_parsing(tmp_path, monkeypatch):
    source = tmp_path / "scan.txt"
    source.write_text("data exceeding the configured file budget")
    monkeypatch.setattr(limits, "MAX_INPUT_BYTES", 1)

    def parsed(*args, **kwargs):
        pytest.fail("oversized input reached the parser")

    monkeypatch.setattr(pulsar.ingest, "read_pulsar_file", parsed)
    result = pulsar.load_pulsar_lightcurve(source)
    assert [error.code for error in result.errors] == ["invalid_input"]


def test_nyquist_derived_overflow_is_a_validation_error():
    with pytest.raises(ValueError):
        periodogram.compute_periodogram(
            np.array([-1e308, 0., 1e308]), np.array([0., 1., 0.]), freq_mode=True
        )
