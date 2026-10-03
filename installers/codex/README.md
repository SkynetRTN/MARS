# The Codex plugin

MARS as a Codex plugin, for the **ChatGPT desktop app** (in its Codex
threads), the Codex CLI and the Codex IDE extension. All three share
`~/.codex`, so one install serves all of them. The plugin carries the MCP
server's launch configuration and the `mars-tools` skill. It carries no Python
and no dependencies. Codex starts the server with

```bash
uv run --locked mars-mcp        # in the installed plugin's directory
```

which downloads Python 3.13 the first time and installs exactly what `uv.lock`
pins: the published `skynet-mars[mcp]` release named in `pyproject.toml`, and
its dependencies (about 640 MB). Later launches reuse that environment.

| File | What |
| --- | --- |
| `.codex-plugin/plugin.json` | Name, version, what the Plugins Directory shows, and where the skill and server are |
| `.mcp.json` | The `uv run` command, the timeouts, the approval mode, and the variables forwarded to the server |
| `pyproject.toml`, `uv.lock` | The environment: one exact `skynet-mars[mcp]` pin, locked for every platform |
| `skills/mars-tools/` | The skill as the pinned release renders it (`mars-mcp install-skill`). Do not edit it here |
| `assets/icon.png` | The 512 px mark, exported by `docs/assets/make_brand.py` |

`.agents/plugins/marketplace.json`, at the repository root, lists the plugin.
That makes the repository a Codex marketplace named `mars`.

## Why Codex's own manifest, not the portable one

Codex also reads the portable Agent Plugins layout (`plugin.json` and
`mcp.json` at the plugin root). Its `mcp.json` accepts only `command`, `args`,
`env` and `cwd` for a local server, so it cannot raise Codex's limits of 10 s
to start a server and 60 s per tool call. A first launch outlasts the first
limit (44 s measured, on a fast link), and an all-sky plate solve (about
285 s) outlasts the second. Codex's own `.mcp.json` sets
`startup_timeout_sec` and `tool_timeout_sec`.

## Install on Fedora 44

The ChatGPT desktop app for Linux is in preview. OpenAI publishes `.rpm`
packages for Fedora 43 and 44, for x86_64 and aarch64.

1. Install the app from OpenAI's `.rpm` (`sudo dnf install ./<downloaded>.rpm`),
   and install `uv`, `git` and `gcc` from Fedora:

   ```bash
   sudo dnf install uv git gcc
   ```

   Use Fedora's `uv`, which lands in `/usr/bin`. An app started from the
   desktop may not see `~/.local/bin`, where uv's own installer puts it, and
   Codex starts the server with the app's `PATH`. Fedora configures its `uv`
   not to download Python (`python-downloads = "manual"` in
   `/etc/uv/uv.toml`), and Fedora 44's own Python is 3.14, so the plugin sets
   `UV_PYTHON_DOWNLOADS=automatic` for its server. `gcc` is needed on aarch64
   only: `photutils` 3.0.0 has no Python 3.13 wheel for ARM64 Linux, so the
   first start compiles it.

2. Add the marketplace and install the plugin. With the Codex CLI:

   ```bash
   codex plugin marketplace add SkynetRTN/MARS --sparse .agents/plugins --sparse installers/codex
   codex plugin add mars@mars
   ```

   Always pass both `--sparse` paths: without them Codex clones the whole
   repository, fixtures included. In the desktop app, restart it after adding
   the marketplace. Then you can also install from the Plugins Directory,
   where MARS appears under the `mars` marketplace.

3. Start a Codex thread. The first start installs Python and the dependencies.
   This takes about a minute on a fast connection and longer on a slow one,
   within the plugin's 10-minute start limit. Ask for something that uses a
   tool, for example the plugin's suggested pulsar prompt.

Codex asks before any tool that writes an artifact
(`default_tools_approval_mode = "writes"`).

**Updating.** Run `codex plugin marketplace upgrade mars`, then
`codex plugin add mars@mars`. Each version installs into its own directory,
`~/.codex/plugins/cache/mars/mars/<version>/`, with its own environment.

## Settings

The plugin sets one variable, `UV_PYTHON_DOWNLOADS=automatic`, and no secret.
Codex starts the server with a small fixed environment (`HOME`, `PATH`,
`USER`, `LANG` and a few more), plus these variables if the app itself was
started with them:

| Variable | Effect |
| --- | --- |
| `ADS_DEV_KEY` | Enables the ADS literature tools. Simpler for a desktop app: write the token to `~/.ads/dev_key` |
| `MARS_HOME`, `XDG_DATA_HOME` | Where artifacts, downloads and data bundles go. Default: `~/.local/share/mars` |
| `MARS_MCP_TOOLS` | A subset of tool groups to serve: `databases`, `optical`, `timeseries`, `hr`, `radio` |
| `CASDA_OPAL_USERNAME` | CASDA downloads. The password is read from the system keyring, which needs `DBUS_SESSION_BUS_ADDRESS` (or `XDG_RUNTIME_DIR`); both are forwarded |
| `ANET_INDEX_PATH`, `ANET_TIMEOUT_S`, `ATLAS_CATALOG_ROOT`, `ATLAS_CATALOG`, `ATLAS_TIMEOUT_S` | The plate solvers' index and catalogue data ([installing](../../docs/installing.md)) |

Codex forwards a variable as the app has it, an empty value included. An
`ADS_DEV_KEY` exported empty therefore hides `~/.ads/dev_key`.

A desktop app does not see your shell's variables. To restrict tools without
one, add a policy to `~/.codex/config.toml`:

```toml
[plugins."mars@mars".mcp_servers.mars]
enabled_tools = ["search_simbad", "search_ned"]
```

## Data bundles and the self-test

Run `mars-mcp` from the plugin's own environment, so nothing is downloaded
twice. Use the version `codex plugin list` shows for `mars@mars`:

```bash
P=~/.codex/plugins/cache/mars/mars/0.1.0rc5      # that version
export UV_PYTHON_DOWNLOADS=automatic             # as the plugin does, for Fedora's uv
uv run --directory "$P" --locked mars-mcp self-test
uv run --directory "$P" --locked mars-mcp fetch-data optical    # or: isochrones, all
```

On a slow connection, running the self-test once before the first thread also
installs the environment ahead of time. If you set `MARS_HOME` for the app,
set it for these commands too. Otherwise the bundle lands where the server
does not look.

## If the server does not start

- **`MCP startup failed: No such file or directory (os error 2)`**: Codex
  could not find `uv` on the `PATH` the app was started with. Install it with
  `sudo dnf install uv`, then restart the app.
- **`handshaking with MCP server failed: connection closed`**: the server
  exited before it started. Run the self-test above to see why. Two causes
  seen on a clean Fedora 44: uv refusing to download Python 3.13 (the plugin
  now allows it), and, on aarch64, no `cc` to build `photutils`
  (`sudo dnf install gcc`).
- **A timeout on the first start**: the dependency download outlasted the
  10-minute limit. Run the self-test above once, which installs the same
  environment, then start a new thread.
- Otherwise, run the self-test. When it passes, the problem is in Codex's
  configuration: `codex mcp list` shows how Codex resolved the server.

## Test without the desktop app

`codex app-server` speaks the same protocol the desktop app does. With a
throwaway `CODEX_HOME` and an empty `HOME`, add the marketplace from a
checkout (`codex plugin marketplace add /path/to/MARS`), run
`codex plugin add mars@mars`, then send `initialize` and
`mcpServerStatus/list` over stdin. This starts the server exactly as the app
would, with the same environment, and lists its tools.
`mcpServer/tool/call` (after `thread/start`) runs one, and needs no model
login. To measure a true first launch, also put
`python-preference = "only-managed"` in the empty home's
`.config/uv/uv.toml`. Otherwise uv reuses a Python 3.13 already on the
machine.

## After each release

The pin names a release that is already **on PyPI**, so the plugin follows a
release rather than leading it. Once `v<version>` is published:

1. Set the new version in three places, all in PEP 440 form (`0.1.0rc5`):
   `version` in `pyproject.toml`, the `skynet-mars[mcp]==` pin, and `version`
   in `.codex-plugin/plugin.json`.
2. Run `python installers/codex/sync_lock.py` from the repository root, not a
   bare `uv lock`. It locks every package shared with the root `uv.lock` at
   the root's version.
3. Re-render the skill from the release itself, so it describes the server
   the plugin runs and not the repository's newer source:

   ```bash
   rm -rf installers/codex/skills/mars-tools installers/codex/.venv
   uv run --directory installers/codex --locked mars-mcp install-skill "$PWD/installers/codex/skills/mars-tools"
   rm -rf installers/codex/.venv
   ```

`tests/test_codex_plugin.py` checks that the version fields agree, that the
pin is never ahead of the repository's version, that the two locks agree, and
that the skill copy is complete.

## Platforms

Verified in clean Fedora 44 containers, x86_64 and aarch64, through Codex
0.160's app server, installing from GitHub with Fedora's `uv`. On aarch64
the first start also compiles `photutils` with `gcc`. macOS and Windows use
the same wheels as the Claude Desktop extension, and the same limits apply. `numba` and `llvmlite` have no Intel Mac wheels, and
several dependencies have none for Windows on ARM.
