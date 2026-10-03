"""The Codex plugin (``installers/codex/``) stays consistent.

The plugin is what the ChatGPT desktop app (in its Codex threads), the Codex
CLI and the IDE extension install: a ``.codex-plugin/plugin.json``, a
``.mcp.json`` that starts the server with ``uv run --locked mars-mcp`` in the
installed plugin, that project's ``pyproject.toml`` and ``uv.lock``, and the
skill as the pinned release renders it. ``.agents/plugins/marketplace.json`` at the
repository root lists it.

It uses Codex's own manifest format, not the portable Agent Plugins one,
because only Codex's ``.mcp.json`` can raise ``startup_timeout_sec`` and
``tool_timeout_sec``; the portable ``mcp.json`` rejects both
(``deny_unknown_fields`` in codex-rs ``agent_plugin_config.rs``). A cold first
launch took 44 s through ``codex app-server`` 0.160 against a 10 s default.

Like the Claude Desktop extension, the pin names a **published** release, so
it trails the repository's version and must never run ahead of it. Nothing
here runs Codex, builds anything or opens a socket.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml
from packaging.version import Version

from tools.mcp.groups import TOOLS_ENV
from tools.paths import MARS_HOME_ENV
from tools.skill import SKILL_NAME

_ROOT = Path(__file__).resolve().parents[1]
_PLUGIN = _ROOT / "installers" / "codex"
_MANIFEST = json.loads((_PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
_SERVERS = json.loads((_PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
_MARKETPLACE = json.loads((_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
_PLUGIN_PROJECT = tomllib.loads((_PLUGIN / "pyproject.toml").read_text(encoding="utf-8"))["project"]
_REPO_PROJECT = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def _pinned_version() -> str:
    (requirement,) = _PLUGIN_PROJECT["dependencies"]
    match = re.fullmatch(r"skynet-mars\[mcp\]==(\S+)", requirement)
    assert match, f"the plugin must pin exactly one release: {requirement!r}"
    return match.group(1)


def _locked_versions(lock: Path) -> dict[str, str]:
    return {p["name"]: p["version"] for p in tomllib.loads(lock.read_text(encoding="utf-8"))["package"]}


def test_the_plugin_version_fields_agree():
    """Codex installs a plugin under ``plugins/cache/<marketplace>/<plugin>/<version>``,
    so the manifest version names the environment; it is the pin, verbatim."""

    assert _MANIFEST["version"] == _PLUGIN_PROJECT["version"] == _pinned_version()
    assert _locked_versions(_PLUGIN / "uv.lock")["skynet-mars"] == _pinned_version()


def test_the_pin_never_runs_ahead_of_the_repository():
    assert Version(_pinned_version()) <= Version(_REPO_PROJECT["version"])


def test_the_plugin_runs_python_3_13_the_supported_target():
    assert _PLUGIN_PROJECT["requires-python"] == ">=3.13,<3.14"
    assert _REPO_PROJECT["requires-python"] == ">=3.13"


def test_the_marketplace_lists_the_plugin_by_a_contained_local_path():
    """Codex requires ``./``, relative to the marketplace root (the repository
    root for ``.agents/plugins/marketplace.json``), and inside it."""

    (entry,) = _MARKETPLACE["plugins"]
    assert entry["name"] == _MANIFEST["name"] == "mars"
    assert entry["source"] == {"source": "local", "path": "./installers/codex"}
    assert (_ROOT / entry["source"]["path"]).resolve() == _PLUGIN


def test_the_manifest_points_at_files_that_exist():
    for key in ("skills", "mcpServers"):
        assert _MANIFEST[key].startswith("./"), key
        assert (_PLUGIN / _MANIFEST[key]).exists(), key
    interface = _MANIFEST["interface"]
    for key in ("composerIcon", "logo"):
        assert (_PLUGIN / interface[key]).is_file(), key


def test_the_server_runs_locked_from_the_installed_plugin():
    """A relative ``cwd`` is joined to the installed plugin root, which holds
    ``pyproject.toml`` and ``uv.lock``. ``command`` is a bare name: Codex
    resolves it on the PATH the app was started with."""

    (name,) = _SERVERS
    server = _SERVERS[name]
    assert name == "mars"
    assert server["command"] == "uv"
    assert server["args"] == ["run", "--locked", "mars-mcp"]
    assert server["cwd"] == "."


def test_the_timeouts_outlast_a_first_launch_and_a_plate_solve():
    """Codex's defaults are 10 s to start and 60 s per call. The first launch
    installs Python and ~640 MB (44 s measured on a fast link); an all-sky
    plate solve takes ~285 s."""

    server = _SERVERS["mars"]
    assert server["startup_timeout_sec"] >= 300
    assert server["tool_timeout_sec"] >= 300
    assert server["default_tools_approval_mode"] == "writes"


def test_only_variables_mars_reads_are_forwarded():
    """Codex starts a stdio server with a small fixed environment (HOME, PATH,
    USER, ...); ``env_vars`` forwards these from the app's own when set. The
    plugin sets no value itself, so it can carry no secret.

    ``XDG_DATA_HOME`` decides the default MARS home, so without it the server
    and a ``fetch-data`` run in a shell could disagree about where bundles
    live. The CASDA password comes from the keyring, which reaches the Secret
    Service over the session bus (``DBUS_SESSION_BUS_ADDRESS``, or
    ``XDG_RUNTIME_DIR``'s socket). The solver variables locate plate-solving
    data, which the 600 s call limit exists for."""

    server = _SERVERS["mars"]
    assert "env" not in server
    assert len(server["env_vars"]) == len(set(server["env_vars"]))
    assert set(server["env_vars"]) == {
        "ADS_DEV_KEY",
        MARS_HOME_ENV,
        TOOLS_ENV,
        "XDG_DATA_HOME",
        "CASDA_OPAL_USERNAME",
        "DBUS_SESSION_BUS_ADDRESS",
        "XDG_RUNTIME_DIR",
        "ANET_INDEX_PATH",
        "ANET_TIMEOUT_S",
        "ATLAS_CATALOG_ROOT",
        "ATLAS_CATALOG",
        "ATLAS_TIMEOUT_S",
    }


def test_the_plugin_needs_no_model_key():
    """The model is the logged-in ChatGPT/Codex session's; MARS serves tools only."""

    providers = re.compile(r"ANTHROPIC|OPENAI|GEMINI|CLAUDE|MODEL", re.IGNORECASE)
    assert not any(providers.search(name) for name in _SERVERS["mars"]["env_vars"])


def test_the_icon_is_the_exported_512_pixel_mark():
    icon = _PLUGIN / _MANIFEST["interface"]["logo"]
    assert icon.read_bytes() == (_ROOT / "docs/assets/mars-mark.png").read_bytes()


def test_the_plugin_carries_a_complete_loadable_skill():
    """The copy is rendered by the pinned release (``mars-mcp install-skill``,
    README "After each release"), so it describes the server the plugin runs,
    not the repository's newer source; it is not compared with ``tools/skill``.
    It must be a real directory: Codex copies a plugin without its symlinks."""

    skill = _PLUGIN / "skills" / SKILL_NAME
    assert skill.is_dir() and not skill.is_symlink()
    entry = (skill / "SKILL.md").read_text(encoding="utf-8")
    _, frontmatter, body = entry.split("---\n", 2)
    meta = yaml.safe_load(frontmatter)
    assert meta["name"] == SKILL_NAME and meta["description"]
    for target in re.findall(r"\]\(([^)\s#:]+\.md)\)", body):
        assert (skill / target).is_file(), f"SKILL.md links a missing {target}"


def test_the_plugin_locks_the_versions_ci_tests():
    """Every package the plugin shares with the root lock is at the root's
    version (``sync_lock.py``). skynet-mars itself is the published pin, which
    trails a version bump until the release reaches PyPI."""

    root, ours = _locked_versions(_ROOT / "uv.lock"), _locked_versions(_PLUGIN / "uv.lock")
    drift = {
        name: (root[name], ours[name])
        for name in ours
        if name in root and name != "skynet-mars" and root[name] != ours[name]
    }
    assert drift == {}, f"run installers/codex/sync_lock.py: {drift}"
