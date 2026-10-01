"""The wheel check CI and the release workflow run before shipping (.github/scripts)."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "check_dist.py"
_spec = importlib.util.spec_from_file_location("check_dist", _SCRIPT)
check_dist = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_dist)


def _wheel(tmp_path: Path, *, extra=(), drop=(), metadata="Name: skynet-mars\n") -> Path:
    names = [*check_dist.REQUIRED]
    names += [f"tools/_data/pulsar/scan{i}.cal.txt" for i in range(5)]
    names += ["tools/__init__.py", "algorithms/__init__.py", *extra]
    path = tmp_path / "skynet_mars-0-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name in names:
            if name not in drop:
                archive.writestr(name, "x")
        archive.writestr("skynet_mars-0.dist-info/METADATA", metadata)
    return path


def test_a_complete_wheel_passes(tmp_path):
    assert check_dist.check_wheel(_wheel(tmp_path)) == []


def test_missing_core_data_fails_as_a_symlink_less_build_would(tmp_path):
    wheel = _wheel(tmp_path, drop={f"tools/_data/pulsar/scan{i}.cal.txt" for i in range(5)})
    assert any("pulsar scans" in p for p in check_dist.check_wheel(wheel))


@pytest.mark.parametrize("asset", check_dist.REQUIRED)
def test_missing_package_data_fails(tmp_path, asset):
    wheel = _wheel(tmp_path, drop={asset})
    assert check_dist.check_wheel(wheel) == [f"missing {asset}"]


@pytest.mark.parametrize(
    "stray",
    [
        "tests/test_x.py",
        "tools/_data/optical/frame.fits",
        "tools/__pycache__/x.cpython-313.pyc",
        ".env",
        "scripts/helper.py",
    ],
)
def test_what_must_never_ship_fails(tmp_path, stray):
    assert check_dist.check_wheel(_wheel(tmp_path, extra=[stray]))


def test_the_licence_gate_is_opt_in_and_accepts_any_declared_form(tmp_path):
    bare = _wheel(tmp_path)
    assert check_dist.check_wheel(bare) == []
    assert any("licence" in p for p in check_dist.check_wheel(bare, require_license=True))
    licensed = _wheel(tmp_path, metadata="Name: skynet-mars\nLicense-Expression: MIT\n")
    assert check_dist.check_wheel(licensed, require_license=True) == []


def test_another_distribution_name_fails(tmp_path):
    assert check_dist.check_wheel(_wheel(tmp_path, metadata="Name: some-other-project\n"))
