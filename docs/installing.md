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

**Python 3.12 and 3.13** are supported, and CI tests both; the commands above
use 3.13. On either, on x86_64 Linux, Apple Silicon macOS or x64 Windows,
every dependency has a pre-built wheel.
Elsewhere, something builds from source: `sep` on Python 3.14, `photutils` on
Linux ARM, and `numba`'s `llvmlite` on an Intel Mac, which needs an LLVM
toolchain as well as a C compiler (`gcc`, or the Xcode command-line tools). The install takes about
700 MB, nearly all of it dependencies.

Every release is a pre-release for now, so the commands above install the
newest one. To install a specific release, use
`"skynet-mars[mcp]==<version>"`.

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
Silicon Mac or x64 Windows. It always runs the newest MARS release. Releases do
not carry the extension yet; see
[`installers/claude-desktop/`](../installers/claude-desktop/README.md) to
build it. To register it by hand instead, go to Settings → Developer → Edit
Config and add:

```json
{"mcpServers": {"mars": {"command": "/path/to/mars-mcp"}}}
```

Then quit and reopen the app.

**Codex CLI and the ChatGPT desktop app** share `~/.codex`. The simplest
route is the plugin, which needs no Python and no path, only `uv` and `git`
(on Fedora: `sudo dnf install uv git`, plus `gcc` on aarch64):

```bash
codex plugin marketplace add SkynetRTN/MARS --sparse .agents/plugins --sparse installers/codex
codex plugin add mars@mars
```

It also brings the skill. See [`installers/codex/`](../installers/codex/README.md),
including the ChatGPT desktop app on Fedora 44. To register the server by hand
instead, edit `~/.codex/config.toml` (in the app: Settings → MCP servers → Add
server):

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

With the Claude Desktop extension or the Codex plugin there is no `mars-mcp`
on your `PATH`; use the command in the extension's
[README](../installers/claude-desktop/README.md#data-bundles) or the plugin's
[README](../installers/codex/README.md#data-bundles-and-the-self-test)
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
data locations at startup. After upgrading MARS, run `mars-mcp fetch-data` again:
it checks what is installed against the new release's pins, keeps a copy whose
bytes still match, and downloads only what changed.

Plate solving (`solve_astrometry`) needs astrometry.net index files
(`ANET_INDEX_PATH`) or a local UCAC catalogue (`ATLAS_CATALOG_ROOT`), which
you supply yourself. Without them, it reports `solver_unavailable`.

## Where things go

MARS writes only under the **MARS home**: `~/.local/share/mars` on Linux,
`~/Library/Application Support/mars` on macOS, and `%LOCALAPPDATA%\mars` on
Windows. Set `MARS_HOME` to move it.

| Directory | What |
| --- | --- |
| `artifacts/` | tool outputs; MCP uses private `.mars-runtime/<call-id>/artifacts/` trees. |
| `fits_downloads/` | MAST and CASDA downloads |
| `bundles/` | the optional data |
| `numba-cache/` | compiled-function cache |

On Linux and macOS the default artifact directory and its files are private to
you (`0700` and `0600`).

Artifact subdirectories and session scopes must remain beneath the artifact
root: absolute paths, parent traversal, escaping symlinks and path-like filename
extensions are rejected before a file is created. Python APIs that explicitly
accept an `output_dir` may instead use that caller-selected directory as their
write root; generated names are still confined to it. These checks assume a
trusted local user; they are not a sandbox against concurrent filesystem changes.

## MCP runtime limits and cleanup

MCP is a trusted local, single-user stdio interface, not an authenticated shared
service. Caller-selected absolute input paths and configured external data roots
are intentional. Do not expose this server to untrusted remote users. These
guards apply to MCP dispatch, not arbitrary direct Python calls or the console's
in-process agent loop.

Each call runs in an owned process. Its default whole-call deadline is **600
seconds**, including waiting for sequential capacity, preprocessing, queries,
solver retries and rendering. Operators may set `MARS_MCP_CALL_TIMEOUT_S` to a
finite positive value up to **1800 seconds**; tool arguments cannot remove it.
MCP cancellation terminates/reaps owned work before releasing capacity. A host
merely ceasing to wait is not cancellation. Stopped work never advertises
partial files as completed artifacts; query metadata can remain a valid partial
result. Check `tool_timeout`, `resource_limit` and partial-result errors.

| Per-call budget | Default / enforcement |
| --- | --- |
| Memory | Linux: absolute 4 GiB address space per process via `RLIMIT_AS`. macOS: finite `RLIMIT_AS` ceiling equal to the worker's measured pre-tool bootstrap mappings plus a 4 GiB additional address-space allowance; large OS/loader mappings are not a tool allocation. POSIX children inherit the ceiling; stricter inherited limits are preserved. Windows: 4 GiB job-wide committed memory, owned by the server with kill-on-close and verified empty-job cleanup. Setup failure refuses the call. Native behavior is gated in CI, not inferred from Linux. |
| Managed work/artifacts/caches | 256 MiB, 10,000 entries; supervised every 50 ms |
| Downloads | 32 products, 512 MiB actual decoded streamed bytes; CASDA permits 64 URLs including checksums, counted in the same byte budget |
| Logs / reply / input | 1 MiB combined stdout/stderr; 4 MiB JSON reply; 1 MiB serialized call input |
| Solver pipes | 8 MiB combined, checked before buffer extension |
| Inline media | 32 references, 20,000,000 encoded bytes total, plus 5 MB PNG / 16 MB WAV per-file limits |

POSIX has an additional hard per-file 512-MiB backstop. Aggregate directory/log
checks are sampled and can briefly overshoot; they are not filesystem quotas.
Retained managed trees at each root have a **5-GiB admission ceiling**, not a
globally atomic multi-server/user quota. Inputs, indexes and bundles are not
adopted as runtime outputs. Downloads are not silently sliced: narrow filters
after a refusal. Existing download files are never overwritten; SDK cloud,
resume and unbounded-content shortcuts are disabled. Atomic publication needs
filesystem hard-link support.

Windows launches the actual interpreter while preserving its virtual environment,
so launcher exit cannot stand in for worker exit. Cleanup also waits for job-wide
active-process accounting to reach zero. Worker failures forward at most 64 KiB
from each stdout/stderr log to **operator stderr**, never into client results;
the private managed logs retain diagnostic context for troubleshooting.

Finished owned trees are kept until explicitly cleaned; **30 days** is the
default retention selection. Inspect first:

```bash
mars-mcp cleanup
mars-mcp cleanup --days 30 --apply
```

Dry-run creates no output namespace. `--apply` permanently removes only listed
expired, finished, marked call trees under the artifact/download roots. It
leaves running calls, links, unmarked legacy outputs, console sessions, bundles
and operator datasets alone. Selected arguments, logs and research outputs are
not recoverable through MARS; retain anything needed before applying cleanup.
Abrupt server death may leave a `running` marker: inspect/recover it manually
after verifying no owned work remains; cleanup never guesses that it is safe.
