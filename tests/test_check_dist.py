"""The wheel check CI and the release workflow run before shipping (.github/scripts)."""

from __future__ import annotations

import importlib.util
import shlex
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
import yaml

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


def test_release_source_parity_rejects_stale_incremental_build_modules(tmp_path):
    wheel = _wheel(tmp_path, extra=["tools/retired.py"])
    problems = check_dist.check_wheel(wheel, verify_source=True)
    assert "stale/unknown module tools/retired.py" in problems
    assert "source differs for tools/__init__.py" in problems
    assert "missing source module tools/mcp/server.py" in problems


def _release_publication_check():
    """Use the licensed gate and checkout actually declared by the workflow."""
    workflow = yaml.safe_load((_SCRIPT.parents[1] / "workflows/release.yml").read_text())
    jobs = workflow["jobs"]
    checks = [
        (name, job, step)
        for name, job in jobs.items()
        for step in job["steps"]
        if "run" in step
        and ".github/scripts/check_dist.py" in shlex.split(step["run"])
        and "--require-license" in shlex.split(step["run"])
    ]
    assert len(checks) == 1, "release needs one shared licensed source-parity gate"
    return jobs, checks[0]


def _ancestors(jobs, name):
    needs = jobs[name].get("needs", [])
    if isinstance(needs, str):
        needs = [needs]
    return set(needs).union(*(_ancestors(jobs, parent) for parent in needs))


def _workflow_checkout(tmp_path, job):
    # Removing either package from sparse-checkout must break the real checker,
    # rather than merely fail an assertion about the workflow's source text.
    source = tmp_path / "source"
    source.mkdir()
    modules = {
        "tools/__init__.py": b"# tools\n",
        "tools/current.py": b"CURRENT = True\n",
        "algorithms/__init__.py": b"# algorithms\n",
        "algorithms/current.py": b"CURRENT = True\n",
        **{name: b"# required runtime module\n" for name in check_dist.REQUIRED
           if name.endswith(".py")},
    }
    for name, content in modules.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    script = source / ".github/scripts/check_dist.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(_SCRIPT, script)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    checkout_step = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@"))
    patterns = checkout_step.get("with", {}).get("sparse-checkout")
    if patterns is None:
        shutil.copytree(source, checkout, dirs_exist_ok=True)
    else:
        # The release gate uses literal files/directories in non-cone mode.
        # Reject unsupported patterns instead of silently approximating them.
        assert checkout_step["with"]["sparse-checkout-cone-mode"] is False
        for pattern in patterns.splitlines():
            assert not any(char in pattern for char in "*!?[]"), pattern
            path = source / pattern.strip().strip("/")
            target = checkout / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.is_dir():
                shutil.copytree(path, target)
            else:
                shutil.copyfile(path, target)
    return checkout, modules


@pytest.mark.parametrize("event", ["push", "workflow_dispatch"])
def test_release_gate_accepts_complete_wheel_in_its_declared_checkout(tmp_path, event):
    jobs, (gate_name, gate, step) = _release_publication_check()
    # A manual dry run must execute the same command, without publishing.
    conditions = [jobs[name].get("if") for name in _ancestors(jobs, gate_name)]
    for condition in [*conditions, gate.get("if"), step.get("if")]:
        if condition is not None:
            assert condition == "github.event_name == 'push'", condition
            assert event == "push", "manual dry run skips the publication gate"
    checkout, modules = _workflow_checkout(tmp_path, gate)
    _publication_wheel(checkout, modules)
    result = subprocess.run(["bash", "-e", "-c", step["run"]], cwd=checkout,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ": ok" in result.stdout


def _publication_wheel(checkout, modules, *, defect=None):
    entries = {name: b"fixture data" for name in check_dist.REQUIRED}
    entries.update({f"tools/_data/pulsar/scan{i}.cal.txt": b"scan" for i in range(5)})
    entries.update(modules)
    if defect == "obsolete":
        entries["tools/retired.py"] = b"# stale cache\n"
    elif defect == "missing":
        del entries["algorithms/current.py"]
    elif defect == "different":
        entries["tools/current.py"] = b"CURRENT = False\n"
    metadata = "Name: skynet-mars\n"
    if defect != "licence":
        metadata += "License-Expression: GPL-3.0-only\n"
    entries["skynet_mars-0.dist-info/METADATA"] = metadata.encode()
    dist = checkout / "dist"
    dist.mkdir()
    wheel = dist / "skynet_mars-0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


@pytest.mark.parametrize(("defect", "diagnostic"), [
    ("obsolete", "stale/unknown module tools/retired.py"),
    ("missing", "missing source module algorithms/current.py"),
    ("different", "source differs for tools/current.py"),
    ("licence", "no licence declared"),
])
def test_release_gate_rejects_bad_wheel_in_its_declared_checkout(tmp_path, defect, diagnostic):
    _, (_, gate, step) = _release_publication_check()
    checkout, modules = _workflow_checkout(tmp_path, gate)
    _publication_wheel(checkout, modules, defect=defect)
    result = subprocess.run(["bash", "-e", "-c", step["run"]], cwd=checkout,
                            capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert diagnostic in result.stdout


def test_publications_wait_for_the_unprivileged_publication_gate():
    jobs, (gate_name, gate, _) = _release_publication_check()
    for name in ("publish", "publish-testpypi", "publish-pypi"):
        assert gate_name in _ancestors(jobs, name), f"{name} can upload before the publication gate"
    assert gate.get("permissions", {"contents": "read"}) == {"contents": "read"}
    assert "environment" not in gate
