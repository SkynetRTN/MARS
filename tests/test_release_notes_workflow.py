"""Exercise release-note staging and the actual GitHub release shell command."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/release.yml"
NOTES = "# MARS 0.1.0\n\nFix interrupted sessions. Literal `code` and $(touch unexpected).\n"


def _jobs():
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]


@pytest.mark.parametrize("available", [True, False])
def test_build_stages_the_selected_versions_notes_or_fails(tmp_path, available):
    build = _jobs()["build"]
    prepare = next((s for s in build["steps"] if s.get("name") == "Prepare release notes"), None)
    assert prepare is not None, "build must prepare versioned release notes on dry runs too"
    assert "if" not in prepare
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
    source = tmp_path / "docs/releases/0.1.0.md"
    source.parent.mkdir(parents=True)
    if available:
        source.write_text(NOTES)
    result = subprocess.run(["bash", "-e", "-c", prepare["run"]], cwd=tmp_path,
                            capture_output=True, text=True)
    if not available:
        assert result.returncode != 0
        return
    assert result.returncode == 0, result.stdout + result.stderr
    artifact = next(s for s in build["steps"]
                    if s.get("uses", "").startswith("actions/upload-artifact@")
                    and s["with"]["name"] == "release-notes")
    staged = tmp_path / artifact["with"]["path"]
    assert staged.read_text() == NOTES
    assert not staged.is_relative_to(tmp_path / "dist")
    assert not (tmp_path / "unexpected").exists()


def test_github_release_uses_the_downloaded_notes_file_verbatim(tmp_path):
    publish = _jobs()["publish"]
    download = next((s for s in publish["steps"]
                     if s.get("uses", "").startswith("actions/download-artifact@")
                     and s["with"]["name"] == "release-notes"), None)
    assert download is not None, "GitHub publication must download the build's release notes"
    destination = tmp_path / download["with"]["path"]
    destination.mkdir()
    (destination / "notes.md").write_text(NOTES)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "mars.whl").write_bytes(b"wheel")
    (dist / "mars.tar.gz").write_bytes(b"source distribution")
    extension = tmp_path / "extension"
    extension.mkdir()
    (extension / "mars.mcpb").write_bytes(b"extension")
    # Replace only the external publishing boundary; run the workflow's shell.
    # The stand-in records the exact note body delivered to the gh CLI.
    commands = tmp_path / "bin"
    commands.mkdir()
    gh = commands / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "notes = pathlib.Path(args[args.index('--notes-file') + 1]).read_text()\n"
        "pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps({'args': args, 'notes': notes}))\n"
    )
    gh.chmod(0o755)
    env = {**os.environ, "PATH": f"{commands}{os.pathsep}{os.environ['PATH']}",
           "CAPTURE": str(tmp_path / "capture.json"), "GH_TOKEN": "test",
           "REPO": "example/MARS", "TAG": "v0.1.0", "PRERELEASE": "false"}
    step = next(s for s in publish["steps"] if s.get("name") == "Create the GitHub release")
    result = subprocess.run(["bash", "-e", "-c", step["run"]], cwd=tmp_path,
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    captured = json.loads((tmp_path / "capture.json").read_text())
    assert captured["args"][:3] == ["release", "create", "v0.1.0"]
    assert "--latest" in captured["args"]
    assert captured["notes"] == NOTES
    assert not (tmp_path / "unexpected").exists()
