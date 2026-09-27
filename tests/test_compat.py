"""Kepler's variables and home are honoured for one pre-release (R2).

``docs/working/mars-rebrand.md`` §6.3: a ``KEPLER_*`` value is used when its
``MARS_*`` twin is unset and ignored when the twin is set, both said out loud;
a leftover ``kepler`` home is pointed out, never moved.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tools.compat import adopt_legacy_environment, legacy_home_notice

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_a_legacy_variable_is_adopted_when_its_twin_is_unset():
    environ = {"KEPLER_MAX_FRAMES": "5", "MARS_ARTIFACT_DIR": "", "KEPLER_ARTIFACT_DIR": "/a"}

    found = adopt_legacy_environment(environ)

    assert environ["MARS_MAX_FRAMES"] == "5" and environ["MARS_ARTIFACT_DIR"] == "/a"
    assert [(f.legacy, f.current, f.adopted) for f in found] == [
        ("KEPLER_ARTIFACT_DIR", "MARS_ARTIFACT_DIR", True),
        ("KEPLER_MAX_FRAMES", "MARS_MAX_FRAMES", True),
    ]
    assert "deprecated" in found[0].message() and "0.1.0rc3" in found[0].message()
    assert "/a" not in found[0].message()
    assert environ["KEPLER_MAX_FRAMES"] == "5"


def test_a_set_twin_wins_and_the_legacy_variable_is_reported_ignored():
    environ = {"KEPLER_HOME": "/old", "MARS_HOME": "/new"}

    (found,) = adopt_legacy_environment(environ)

    assert environ["MARS_HOME"] == "/new"
    assert not found.adopted and "ignored" in found.message()


def test_an_empty_legacy_variable_is_not_adopted_and_adoption_is_idempotent():
    environ = {"KEPLER_DATA_DIR": "", "KEPLER_MCP_TOOLS": "hr"}

    first = adopt_legacy_environment(environ)
    second = adopt_legacy_environment(environ)

    assert "MARS_DATA_DIR" not in environ
    assert first == second and environ["MARS_MCP_TOOLS"] == "hr"


def test_a_leftover_kepler_home_is_pointed_out_and_not_moved(tmp_path):
    environ = {"XDG_DATA_HOME": str(tmp_path)}
    (tmp_path / "kepler" / "bundles").mkdir(parents=True)

    notice = legacy_home_notice(environ, platform="linux", home=tmp_path)

    assert notice and str(tmp_path / "kepler") in notice and str(tmp_path / "mars") in notice
    assert (tmp_path / "kepler" / "bundles").is_dir() and not (tmp_path / "mars").exists()


def test_the_home_notice_never_advises_a_rename_onto_an_existing_home(tmp_path):
    """Review finding: mars-mcp creates the mars home right after the notice,
    so "rename kepler to mars" turned into `mv` nesting kepler inside it, and
    the notice, silenced by the new home, never said so again."""
    environ = {"XDG_DATA_HOME": str(tmp_path)}
    (tmp_path / "kepler").mkdir()
    (tmp_path / "mars" / "artifacts").mkdir(parents=True)

    notice = legacy_home_notice(environ, platform="linux", home=tmp_path)

    assert notice and "move what is inside it" in notice and "rename" not in notice


def test_the_home_notice_stops_when_the_old_home_is_gone_or_mars_home_is_set(tmp_path):
    environ = {"XDG_DATA_HOME": str(tmp_path)}
    assert legacy_home_notice(environ, platform="linux", home=tmp_path) is None
    (tmp_path / "kepler").mkdir()
    assert legacy_home_notice({**environ, "MARS_HOME": "/x"}, platform="linux", home=tmp_path) is None
    assert legacy_home_notice(environ, platform="linux", home=tmp_path)
    (tmp_path / "kepler").rmdir()
    assert legacy_home_notice(environ, platform="linux", home=tmp_path) is None


def _run(code: str, **env: str) -> subprocess.CompletedProcess[str]:
    clean = {
        k: v for k, v in os.environ.items() if not k.startswith(("KEPLER_", "MARS_"))
    }
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT,
        env={**clean, "PYTHONPATH": str(_REPO_ROOT), **env},
        capture_output=True,
        text=True,
        check=True,
    )


def test_gate_an_install_configured_as_kepler_behaves_as_it_did(tmp_path):
    """R2's gate, first half: only KEPLER_* set, and the tools read it."""
    result = _run(
        "from tools import config; print(config.ARTIFACT_DIR, config.DEFAULT_MAX_FRAMES)",
        KEPLER_ARTIFACT_DIR=str(tmp_path / "k"),
        KEPLER_MAX_FRAMES="7",
    )
    assert result.stdout.split() == [str(tmp_path / "k"), "7"]


def test_gate_a_mars_setting_ignores_its_kepler_twin(tmp_path):
    """R2's gate, second half."""
    result = _run(
        "from tools import config; print(config.ARTIFACT_DIR)",
        KEPLER_ARTIFACT_DIR=str(tmp_path / "k"),
        MARS_ARTIFACT_DIR=str(tmp_path / "m"),
    )
    assert result.stdout.strip() == str(tmp_path / "m")


def test_mars_mcp_names_both_variables_on_stderr_never_stdout(tmp_path):
    result = _run(
        "import sys; from tools.mcp.__main__ import main; sys.exit(main(['fetch-data', '--list']))",
        KEPLER_PREVIEW_ROWS="3",
        MARS_HOME=str(tmp_path),
    )
    assert "KEPLER_PREVIEW_ROWS" in result.stderr and "MARS_PREVIEW_ROWS" in result.stderr
    assert "KEPLER_" not in result.stdout


def test_a_library_caller_of_the_model_factory_gets_its_legacy_backend():
    """Review finding: tools.llm never imports tools.config, so a caller with
    only KEPLER_MODEL_BACKEND set was told MARS_MODEL_BACKEND was unset."""
    result = _run(
        "from tools.llm import factory; print(type(factory.build_backend(None)).__name__)",
        KEPLER_MODEL_BACKEND="ollama/llama3.1",
    )
    assert result.stdout.strip() == "OllamaBackend"
