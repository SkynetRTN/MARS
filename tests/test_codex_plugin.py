"""The Codex plugin (``installers/codex/``) stays consistent.

The plugin is what the ChatGPT desktop app (in its Codex threads), the Codex
CLI and the IDE extension install: a ``.codex-plugin/plugin.json``, a
``.mcp.json`` that starts ``uv run --locked src/server.py`` in the installed
plugin, an empty ``pyproject.toml`` and its ``uv.lock``, and the rendered
skill. ``src/server.py`` is the Claude Desktop extension's entry point,
byte for byte: it runs the newest ``skynet-mars`` release through
``uv tool run``, so the plugin names no MARS version and needs no change to
follow a release. ``.agents/plugins/marketplace.json`` lists the plugin.

It uses Codex's own manifest format, not the portable Agent Plugins one,
because only Codex's ``.mcp.json`` can raise ``startup_timeout_sec`` and
``tool_timeout_sec``; the portable ``mcp.json`` rejects both
(``deny_unknown_fields`` in codex-rs ``agent_plugin_config.rs``). A cold first
launch took 43 s through ``codex app-server`` 0.160 against a 10 s default.

Nothing here runs Codex or uv, builds anything or opens a socket.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from tools.mcp.groups import TOOLS_ENV
from tools.paths import MARS_HOME_ENV
from tools.skill import CODEX_PLUGIN_COPY, RENDERED_COPIES, check_repository_copy

_ROOT = Path(__file__).resolve().parents[1]
_PLUGIN = _ROOT / "installers" / "codex"
_MANIFEST = json.loads((_PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
_SERVERS = json.loads((_PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
_MARKETPLACE = json.loads((_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
_PLUGIN_PROJECT = tomllib.loads((_PLUGIN / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def test_the_plugin_has_one_version_of_its_own():
    """Codex installs a plugin under ``plugins/cache/<marketplace>/<plugin>/<version>``
    and upgrades when this changes. It is the plugin's version, not MARS's."""

    assert re.fullmatch(r"\d+\.\d+\.\d+", _MANIFEST["version"]), _MANIFEST["version"]
    assert _PLUGIN_PROJECT["version"] == _MANIFEST["version"]


def test_the_plugin_names_no_mars_version():
    """It runs the newest release, so nothing it ships may pin one."""

    assert _PLUGIN_PROJECT["dependencies"] == []
    locked = tomllib.loads((_PLUGIN / "uv.lock").read_text(encoding="utf-8"))["package"]
    assert [p["name"] for p in locked] == ["mars-codex"]
    for path in ("README.md", ".mcp.json", ".codex-plugin/plugin.json", "src/server.py"):
        text = (_PLUGIN / path).read_text(encoding="utf-8")
        assert "skynet-mars[mcp]==" not in text and "skynet-mars==" not in text, path
        assert not re.search(r"0\.\d+\.\d+rc\d+", text), path


def test_the_entry_point_is_the_claude_desktop_extensions():
    """One launcher, two installers: the refresh-then-serve logic, the offline
    fallback and the removal of empty settings are tested in
    ``tests/test_claude_desktop_extension.py``. A copy, because Codex installs
    only the plugin's own directory."""

    ours = (_PLUGIN / "src" / "server.py").read_bytes()
    assert ours == (_ROOT / "installers" / "claude-desktop" / "src" / "server.py").read_bytes()


def test_the_plugin_runs_python_3_13_a_supported_version():
    assert _PLUGIN_PROJECT["requires-python"] == ">=3.13,<3.14"


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


def test_the_server_runs_the_entry_point_from_the_installed_plugin():
    """A relative ``cwd`` is joined to the installed plugin root, which holds
    ``pyproject.toml``, ``uv.lock`` and ``src/server.py``. ``command`` is a
    bare name: Codex resolves it on the PATH the app was started with."""

    (name,) = _SERVERS
    server = _SERVERS[name]
    assert name == "mars"
    assert server["command"] == "uv"
    assert server["args"] == ["run", "--locked", "src/server.py"]
    assert server["cwd"] == "."


def test_the_timeouts_outlast_a_first_launch_and_a_plate_solve():
    """Codex's defaults are 10 s to start and 60 s per call. The first launch
    installs Python and ~640 MB (43 s measured on a fast link); an all-sky
    plate solve takes ~285 s."""

    server = _SERVERS["mars"]
    assert server["startup_timeout_sec"] >= 300
    assert server["tool_timeout_sec"] >= 300
    assert server["default_tools_approval_mode"] == "writes"


def test_only_variables_mars_reads_are_forwarded():
    """Codex starts a stdio server with a small fixed environment (HOME, PATH,
    USER, ...); ``env_vars`` forwards these from the app's own when set.

    ``XDG_DATA_HOME`` decides the default MARS home, so without it the server
    and a ``fetch-data`` run in a shell could disagree about where bundles
    live. The CASDA password comes from the keyring, which reaches the Secret
    Service over the session bus (``DBUS_SESSION_BUS_ADDRESS``, or
    ``XDG_RUNTIME_DIR``'s socket). The solver variables locate plate-solving
    data, which the 600 s call limit exists for."""

    server = _SERVERS["mars"]
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


def test_uv_may_download_python_3_13():
    """Fedora's packaged uv ships ``python-downloads = "manual"`` in
    ``/etc/uv/uv.toml``, and Fedora 44's system Python is 3.14, so without
    this the server stops at "No interpreter found for Python ==3.13.*"
    (found in a clean Fedora 44 container). An environment variable outranks
    uv's configuration files, and the entry point passes its environment on to
    ``uv tool run``. It is the plugin's only value, and no secret."""

    assert _SERVERS["mars"]["env"] == {"UV_PYTHON_DOWNLOADS": "automatic"}


def test_the_plugin_needs_no_model_key():
    """The model is the logged-in ChatGPT/Codex session's; MARS serves tools only."""

    providers = re.compile(r"ANTHROPIC|OPENAI|GEMINI|CLAUDE|MODEL", re.IGNORECASE)
    server = _SERVERS["mars"]
    assert not any(providers.search(name) for name in [*server["env_vars"], *server["env"]])


def test_the_icon_is_the_exported_512_pixel_mark():
    icon = _PLUGIN / _MANIFEST["interface"]["logo"]
    assert icon.read_bytes() == (_ROOT / "docs/assets/mars-mark.png").read_bytes()


def test_the_plugin_carries_the_rendered_skill():
    """Codex copies a plugin without its symlinks, so the skill is a second
    rendered copy, written by ``python -m tools.skill`` with the first. The
    plugin runs the newest release, which is cut from the same source."""

    assert CODEX_PLUGIN_COPY in RENDERED_COPIES
    assert CODEX_PLUGIN_COPY == _PLUGIN / "skills" / "mars-tools"
    assert not CODEX_PLUGIN_COPY.is_symlink()
    assert check_repository_copy(CODEX_PLUGIN_COPY) == [], (
        "installers/codex/skills/mars-tools/ is stale; run `uv run python -m tools.skill`"
    )
