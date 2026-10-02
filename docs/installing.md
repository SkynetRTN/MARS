# Installing MARS

How to install MARS (MCP Astronomy Research Suite) from PyPI, with no checkout
of this repository, and register its MCP server with an agent host. How the
package and its data are built is `tool-architecture.md` §10.3.

## Install

With [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uv tool install --python 3.13 "skynet-mars[mcp]"
mars-mcp self-test
```

This creates a private environment for MARS and puts its commands
(`mars-mcp`, the `mars` console, `mars-bench`) on your `PATH`. uv fetches
Python 3.13 itself if you do not have it. `self-test` launches the server the
way a host would. If it passes, the install works. If `mars-mcp` is not
found, uv's command directory is not on your `PATH` yet: run
`uv tool update-shell` and open a new shell, or call it by its full path
(below).

**Where it goes.** Hosts need the full path to `mars-mcp`. `uv tool dir --bin`
prints the directory that holds it:

| OS | `mars-mcp` | The environment |
| --- | --- | --- |
| Linux, macOS | `~/.local/bin/mars-mcp` | `~/.local/share/uv/tools/skynet-mars/` |
| Windows | `%USERPROFILE%\.local\bin\mars-mcp.exe` | `%APPDATA%\uv\data\tools\skynet-mars\` |

Write the path out in full (`/Users/you/.local/bin/mars-mcp`). A config file
does not expand `~`. Upgrade with `uv tool upgrade skynet-mars`, and remove
with `uv tool uninstall skynet-mars`.

**Without uv**, use a virtual environment you choose the location of. The
environment is a directory, and `mars-mcp` is inside it:

```bash
python3.13 -m venv ~/mars-env
~/mars-env/bin/pip install "skynet-mars[mcp]"
~/mars-env/bin/mars-mcp self-test     # Windows: ~\mars-env\Scripts\mars-mcp.exe
```

**Python 3.13** is the supported version. On Python 3.13 on x86_64 Linux,
Apple Silicon macOS or x64 Windows, every dependency has a pre-built wheel.
Elsewhere, something builds from source: `sep` on Python 3.14, `photutils` on
Linux ARM, and `numba`'s `llvmlite` on an Intel Mac, which needs an LLVM
toolchain as well as a C compiler (`gcc`, or the Xcode command-line tools). The install takes about
700 MB, nearly all of it dependencies.

Every release is a pre-release for now, so the commands above install the
newest one. To install a specific release, use
`"skynet-mars[mcp]==0.1.0rc4"`.

**To verify the download**, fetch the wheel and `SHA256SUMS` from the
[GitHub release](https://github.com/SkynetRTN/MARS/releases), and run
`sha256sum --check SHA256SUMS --ignore-missing` in that directory (`shasum -a
256` on macOS). Then install the verified wheel with `[mcp]`.

## Register the server with a host

`mars-mcp` is a local stdio server. The host starts it on your machine and
talks to it over stdin/stdout, with no port and no network listener. So it
works in the agent CLIs, the IDEs, Claude Desktop and the ChatGPT desktop app
(in its Codex threads, not its ordinary chats), but not in a browser chat (claude.ai, ChatGPT on the web). See the
[dated host proposal](analysis/mcp-desktop-hosts.md) §6. Real desktop-host
validation is still an open gate in the
[master plan](working/master-continuation-plan.md#9-desktop-host-rollout-d0d4).

In the examples below, replace `/path/to/mars-mcp` with the full path from
[Install](#install).

**Claude Code**

```bash
claude mcp add --scope user mars -- /path/to/mars-mcp
```

**Claude Desktop.** The simplest route is the extension, a `.mcpb` file that
installs with a double-click and needs no Python or config file, on an Apple
Silicon Mac or x64 Windows. Releases do
not carry the extension yet; see
[`installers/claude-desktop/`](../installers/claude-desktop/README.md) to
build it. To register it by hand instead, go to Settings → Developer → Edit
Config and add:

```json
{"mcpServers": {"mars": {"command": "/path/to/mars-mcp"}}}
```

Then quit and reopen the app.

**Codex CLI and the ChatGPT desktop app** share `~/.codex/config.toml`
(in the app: Settings → MCP servers → Add server):

```toml
[mcp_servers.mars]
command = "/path/to/mars-mcp"
startup_timeout_sec = 30
tool_timeout_sec = 600
default_tools_approval_mode = "writes"
```

The longer timeouts are needed because the first launch and a plate solve both
outlast Codex's defaults. `writes` makes Codex ask before any tool that writes
an artifact.

**Cursor** (`~/.cursor/mcp.json`) and **Gemini CLI**
(`~/.gemini/settings.json`):

```json
{"mcpServers": {"mars": {"command": "/path/to/mars-mcp"}}}
```

Gemini starts a server only in a folder you have trusted.

**VS Code** (`.vscode/mcp.json`) uses a different key:

```json
{"servers": {"mars": {"type": "stdio", "command": "/path/to/mars-mcp"}}}
```

**To serve fewer tools**, pass `--tools databases,timeseries` as an argument,
or set `MARS_MCP_TOOLS`. The groups are `databases`, `optical`, `timeseries`,
`hr` and `radio`. All 55 tools are served by default.

**Keys.** `ADS_DEV_KEY` enables the ADS tools
([get a token](https://ui.adsabs.harvard.edu/user/settings/token)). Desktop
apps do not see your shell's environment, so set the key in the host's `env`
block, or write it to `~/.ads/dev_key`. An installed MARS reads no `.env` file.
CASDA downloads need `CASDA_OPAL_USERNAME` and that account's OPAL password
stored in the system keyring under `astroquery:casda.csiro.au`; the server
never prompts for it.

**The skill.** The server sends its usage guide to the host as instructions
and `mars://skill/...` resources. For an agent that loads `SKILL.md` skills,
also install it natively (it refuses to overwrite a modified copy):

```bash
mars-mcp install-skill ~/.claude/skills/mars-tools
# or ~/.codex/skills/mars-tools, ~/.cursor/skills/mars-tools
```

**If the server does not appear**, run `mars-mcp self-test` first. When it
passes, the problem is the host config. Claude Desktop logs the server's
output to `~/Library/Logs/Claude/mcp-server-mars.log` on macOS, and under
`%APPDATA%\Claude\logs\` on Windows.

## Optional data

With the Claude Desktop extension there is no `mars-mcp` on your `PATH`; use
the command in its [README](../installers/claude-desktop/README.md#data-bundles)
instead.

```bash
mars-mcp fetch-data --list        # what exists, and what is installed
mars-mcp fetch-data optical       # or: isochrones, all
mars-mcp fetch-data --verify      # rehash what is installed
mars-mcp self-test --with-data    # exercise the bundles through the server
```

- **optical** (269 MB) is the bundled frame library. The frame listing,
  photometry on bundled targets, and the recorded-solve replays
  (`replay_field_calibration`, `calibrate_zeropoint` with `catalog_fixture`)
  need it. The zero-point reference tools use data in the package.
- **isochrones** (282 MB) is the isochrone grid. The H-R diagram fits need it.

Everything else works without these bundles. The database tools query remote
services. The pulsar and variable-star tools use data in the package. The
server tells the model which bundles are missing, and the frame listing names
the command to run. Restart the host after fetching, because the server reads
data locations at startup.

Plate solving (`solve_astrometry`) needs astrometry.net index files
(`ANET_INDEX_PATH`) or a local UCAC catalogue (`ATLAS_CATALOG_ROOT`), which
you supply yourself. Without them, it reports `solver_unavailable`.

## Where things go

MARS writes only under the **MARS home**: `~/.local/share/mars` on Linux,
`~/Library/Application Support/mars` on macOS, and `%LOCALAPPDATA%\mars` on
Windows. Set `MARS_HOME` to move it.

| Directory | What |
| --- | --- |
| `artifacts/` | tool output files. Never overwritten, so clear it yourself. |
| `fits_downloads/` | MAST and CASDA downloads |
| `bundles/` | the optional data |
| `numba-cache/` | compiled-function cache |

On Linux and macOS the default artifact directory and its files are private to
you (`0700` and `0600`).
