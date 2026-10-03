"""The Claude Desktop extension (``installers/claude-desktop/``) stays consistent.

The extension is a manifest, an empty ``pyproject.toml`` and its ``uv.lock``,
and an entry point that runs the newest ``skynet-mars`` release from PyPI
through ``uv tool run``. It names no MARS version anywhere, so it never needs
a rebuild to follow a release; these tests keep it that way. Nothing here
builds the extension, runs uv or opens a socket.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path

from tools.mcp.groups import TOOLS_ENV
from tools.paths import MARS_HOME_ENV

_ROOT = Path(__file__).resolve().parents[1]
_EXT = _ROOT / "installers" / "claude-desktop"
_MANIFEST = json.loads((_EXT / "manifest.json").read_text(encoding="utf-8"))
_EXT_PROJECT = tomllib.loads((_EXT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
_REPO_PROJECT = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
_VERSION = re.compile(r"\d+\.\d+(?:\.\d+)?(?:[-.]?(?:a|b|rc|alpha|beta|dev)\.?\d+)?")


def _entry_point():
    """Loaded without writing ``src/__pycache__``, which a plain zip of
    ``src`` would otherwise pack."""
    spec = importlib.util.spec_from_file_location("mars_desktop_entry", _EXT / "src" / "server.py")
    module = importlib.util.module_from_spec(spec)
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def test_the_extension_has_one_version_of_its_own():
    """The extension's version is the launcher's, not MARS's: semver, as
    MCPB requires, and the same in the manifest and pyproject.toml."""
    semver = r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-(alpha|beta|rc)\.(0|[1-9]\d*))?"
    assert re.fullmatch(semver, _MANIFEST["version"]), _MANIFEST["version"]
    assert _EXT_PROJECT["version"] == _MANIFEST["version"]


def test_the_extension_runs_python_3_13_the_supported_target():
    """uv installs Python from ``requires-python``. The manifest declares no
    ``runtimes.python``: Desktop could check that against a system Python the
    user does not have, when uv would have fetched one."""

    assert _EXT_PROJECT["requires-python"] == ">=3.13,<3.14"
    assert _entry_point().PYTHON == "3.13"
    assert "runtimes" not in _MANIFEST.get("compatibility", {})
    assert _REPO_PROJECT["requires-python"] == ">=3.13"


def test_the_manifest_is_the_uv_type_run_locked_from_its_own_directory():
    server = _MANIFEST["server"]
    assert _MANIFEST["manifest_version"] == "0.4"
    assert server["type"] == "uv"
    assert server["entry_point"] == "src/server.py"
    config = server["mcp_config"]
    assert config["command"] == "uv"
    assert config["args"] == ["run", "--directory", "${__dirname}", "--locked", "src/server.py"]


def test_every_setting_maps_to_a_declared_field_and_a_variable_mars_reads():
    env = _MANIFEST["server"]["mcp_config"]["env"]
    fields = _MANIFEST["user_config"]
    for value in env.values():
        match = re.fullmatch(r"\$\{user_config\.(\w+)\}", value)
        assert match and match.group(1) in fields, value
    assert set(env) == set(_entry_point().OPTIONAL_SETTINGS)
    assert {TOOLS_ENV, MARS_HOME_ENV} <= set(env)
    assert all(not field.get("required", False) for field in fields.values())
    assert fields["ads_dev_key"]["sensitive"] is True


def test_an_unfilled_setting_is_removed_before_mars_reads_it():
    """An unexpanded MARS_MCP_TOOLS stops mars-mcp at startup (unknown group),
    and an empty ADS_DEV_KEY stops astroquery reading ~/.ads/dev_key."""

    environ = {
        "ADS_DEV_KEY": "",
        "MARS_MCP_TOOLS": "${user_config.tool_groups}",
        "MARS_HOME": "   ",
        "UNRELATED": "",
    }
    _entry_point().drop_unset(environ)
    assert environ == {"UNRELATED": ""}


def test_a_filled_setting_is_passed_through_unchanged():
    environ = {"ADS_DEV_KEY": "token", "MARS_MCP_TOOLS": "databases,hr", "MARS_HOME": "/data/mars"}
    _entry_point().drop_unset(environ)
    assert environ == {"ADS_DEV_KEY": "token", "MARS_MCP_TOOLS": "databases,hr", "MARS_HOME": "/data/mars"}


def test_the_icon_is_the_exported_512_pixel_mark():
    assert _MANIFEST["icon"] == "icon.png"
    assert (_EXT / "icon.png").read_bytes() == (_ROOT / "docs/assets/mars-mark.png").read_bytes()


def test_a_local_environment_is_never_packed():
    ignored = (_EXT / ".mcpbignore").read_text(encoding="utf-8").split()
    assert ".venv/" in ignored


def test_the_extension_needs_no_model_key():
    """The model is the logged-in Claude Desktop session's; MARS serves tools
    only. No setting may ask for, or pass, a model provider's key."""

    providers = re.compile(r"ANTHROPIC|OPENAI|GEMINI|CLAUDE|MODEL", re.IGNORECASE)
    assert not any(providers.search(name) for name in _MANIFEST["server"]["mcp_config"]["env"])
    assert not any(providers.search(name) for name in _MANIFEST["user_config"])


def test_the_extension_names_no_mars_version():
    """It runs the newest release, so nothing it ships may name one: no
    dependency, no lock entry, no version in its commands or its README's."""

    assert _EXT_PROJECT["dependencies"] == []
    locked = tomllib.loads((_EXT / "uv.lock").read_text(encoding="utf-8"))["package"]
    assert [p["name"] for p in locked] == ["mars-claude-desktop"]
    for path in ("src/server.py", "README.md", "manifest.json"):
        text = (_EXT / path).read_text(encoding="utf-8")
        assert "skynet-mars[mcp]==" not in text and "skynet-mars==" not in text, path
    server = (_EXT / "src" / "server.py").read_text(encoding="utf-8")
    assert not [v for v in _VERSION.findall(server) if v != "3.13"], "only the Python version may appear"


def test_the_entry_point_refreshes_to_the_latest_release_then_serves_it():
    """Step 1 asks PyPI for the newest release, with its output kept off
    stdout (the MCP stream); step 2 starts the newest one in uv's cache."""

    entry = _entry_point()
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return type("Done", (), {"returncode": 0})()

    environ = {"UV": "/opt/uv/bin/uv", "ADS_DEV_KEY": ""}
    code = entry.main(["--tools", "databases"], environ=environ, run=run, execv=lambda path, argv: calls.append((argv, path)))
    refresh, _ = calls[0]
    assert refresh[:3] == ["/opt/uv/bin/uv", "tool", "run"]
    assert "skynet-mars[mcp]@latest" in refresh and "--offline" not in refresh
    assert calls[0][1]["stdout"] is sys.stderr
    serve = calls[1][0]
    assert serve[serve.index("--from") + 1] == "skynet-mars[mcp]" and "--offline" in serve
    assert serve[-3:] == ["mars-mcp", "--tools", "databases"]
    assert "ADS_DEV_KEY" not in environ
    assert code in (0, None)


def test_without_a_network_the_last_release_fetched_still_starts(capsys):
    entry = _entry_point()
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return type("Done", (), {"returncode": 2 if "skynet-mars[mcp]@latest" in command else 0})()

    entry.main([], environ={"UV": "uv"}, run=run, execv=lambda path, argv: commands.append(argv))
    assert "--offline" in commands[-1]
    assert "starting the last one fetched" in capsys.readouterr().err
