"""The Claude Desktop extension (``installers/claude-desktop/``) stays consistent.

The extension is a manifest, a ``pyproject.toml`` and its ``uv.lock``, and a
two-line entry point. Claude Desktop runs ``uv run --locked`` in it, which
installs a **published** ``skynet-mars`` from PyPI. So the pin trails the
repository's version between a bump and its release, and these tests require
only that it never runs ahead, and that the extension's own four version
fields agree. Nothing here builds the extension or opens a socket.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path

from packaging.version import Version

from tools.mcp.groups import TOOLS_ENV
from tools.paths import MARS_HOME_ENV

_ROOT = Path(__file__).resolve().parents[1]
_EXT = _ROOT / "installers" / "claude-desktop"
_MANIFEST = json.loads((_EXT / "manifest.json").read_text(encoding="utf-8"))
_EXT_PROJECT = tomllib.loads((_EXT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
_REPO_PROJECT = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


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


def _pinned_version() -> str:
    (requirement,) = _EXT_PROJECT["dependencies"]
    match = re.fullmatch(r"skynet-mars\[mcp\]==(\S+)", requirement)
    assert match, f"the extension must pin exactly one release: {requirement!r}"
    return match.group(1)


def test_the_extension_version_fields_agree():
    """The manifest spells the version in semver, as MCPB requires
    (``0.1.0-rc.4``); the Python side spells the same version in PEP 440
    (``0.1.0rc4``). Both parse to one ``Version``."""

    locked = tomllib.loads((_EXT / "uv.lock").read_text(encoding="utf-8"))
    (mars,) = [p for p in locked["package"] if p["name"] == "skynet-mars"]
    pinned = _pinned_version()
    assert _EXT_PROJECT["version"] == pinned == mars["version"]
    assert Version(_MANIFEST["version"]) == Version(pinned)


def test_the_manifest_version_is_semver():
    semver = r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-(alpha|beta|rc)\.(0|[1-9]\d*))?"
    assert re.fullmatch(semver, _MANIFEST["version"]), _MANIFEST["version"]


def test_the_pin_never_runs_ahead_of_the_repository():
    assert Version(_pinned_version()) <= Version(_REPO_PROJECT["version"])


def test_the_extension_runs_python_3_13_the_supported_target():
    """uv installs Python from ``requires-python``. The manifest declares no
    ``runtimes.python``: Desktop could check that against a system Python the
    user does not have, when uv would have fetched one."""

    assert _EXT_PROJECT["requires-python"] == ">=3.13,<3.14"
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


def test_the_extension_locks_the_versions_ci_tests():
    """Resolved on its own, the extension's lock picked newer numpy, numba and
    llvmlite than the root lock the parity suite runs against. Every package
    the two share must be at the root's version (``sync_lock.py``)."""

    def versions(lock):
        return {p["name"]: p["version"] for p in tomllib.loads(lock.read_text(encoding="utf-8"))["package"]}

    root, ours = versions(_ROOT / "uv.lock"), versions(_EXT / "uv.lock")
    drift = {name: (root[name], ours[name]) for name in ours if name in root and root[name] != ours[name]}
    assert drift == {}, f"run installers/claude-desktop/sync_lock.py: {drift}"
