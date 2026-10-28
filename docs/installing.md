# Installing MARS

How to install MARS (MCP Astronomy Research Suite) from PyPI, with no checkout
of this repository, and register its MCP server with an agent host. How the
package and its data are built is `tool-architecture.md` §10.3.

**For the Claude or ChatGPT desktop app**, follow the step-by-step guide for
your platform: [Windows on ARM](installing/windows.md),
[macOS (Apple Silicon)](installing/macos.md) or
[Linux (ARM)](installing/linux.md). This page is the reference for every
other host and for what the guides leave out.

## Install

With [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uv tool install --python 3.13 "skynet-mars[mcp]"
mars-mcp self-test
```

This creates a private environment for MARS and puts its commands
(`mars-mcp`, the `mars` console, `mars-bench`) on your `PATH`. `mars-bench`
benchmarks models on suites kept in a checkout's `benchmarks/`, which the
package does not ship; run it from the root of a clone. uv fetches
Python 3.13 itself if you do not have it. `self-test` launches the server the
way a host would. If it passes, the install works. If `mars-mcp` is not
found, uv's command directory is not on your `PATH` yet: run
`uv tool update-shell` and open a new shell, or call it by its full path
(below).

**Plate solving is a machine dependency.** It needs the astrometry.net
solver and its index files installed on your machine, which no MARS install
route provides; without them, every other tool works. See
[Plate solving](#plate-solving).

**Windows on ARM:** `--python 3.13` picks the native ARM64 Python, for which
`sep` and `pyerfa` have no wheels. Name the x64 build, which Windows runs
under emulation:

```powershell
uv tool install --python cpython-3.13-windows-x86_64-none "skynet-mars[mcp]"
```

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
use 3.13. On either, on Linux (x86_64 or ARM), Apple Silicon macOS or x64
Windows, every dependency has a pre-built wheel; on Windows on ARM, use an
x64 Python (above).
Elsewhere, something builds from source: `sep` on Python 3.14, and `numba`'s
`llvmlite` on an Intel Mac, which needs an LLVM toolchain as well as a C
compiler (the Xcode command-line tools). A checkout on Linux ARM also
compiles `photutils`, which `uv.lock` pins to 3.0.0, the release before its
ARM wheels, so `uv sync` there needs `gcc`. The install takes about
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
[dated host proposal](analysis/mcp-desktop-hosts.md) §6. The maintainer
verified Claude Desktop on macOS and Windows and the ChatGPT app on Windows
and Linux on 2026-10-23 ([record](archive/desktop-acceptance.md)); the
ChatGPT app on macOS, Cursor, VS Code and Gemini CLI are untested.

In the examples below, replace `/path/to/mars-mcp` with the full path from
[Install](#install).

**Claude Code**

```bash
claude mcp add --scope user mars -- /path/to/mars-mcp
```

**Claude Desktop.** The simplest route is the extension, a `.mcpb` file that
installs with a double-click and needs no Python or config file, on an Apple
Silicon Mac or a Windows on ARM PC. It always runs the newest MARS release. Download
`mars.mcpb` from the newest release on the
[releases page](https://github.com/SkynetRTN/MARS/releases); how it
is built is in
[`installers/claude-desktop/`](../installers/claude-desktop/README.md). It is
unsigned, so Claude Desktop says so when installing it. To register it by hand
instead, go to Settings → Developer → Edit Config and add:

```json
{"mcpServers": {"mars": {"command": "/path/to/mars-mcp"}}}
```

Then quit and reopen the app.

**Codex CLI and the ChatGPT desktop app** share `~/.codex`. The simplest
route is the plugin, which needs no Python and no path, only `uv` and `git`
(on Fedora: `sudo dnf install uv git`):

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
output to `~/Library/Logs/Claude/mcp-server-MARS — MCP Astronomy Research Suite.log` on macOS, and under
`%APPDATA%\Claude\logs\` on Windows.

## Updates, offline use and rollback

| | Claude Desktop extension, Codex plugin | `uv tool install` |
| --- | --- | --- |
| **New release** | Picked up at the next start: the launcher asks PyPI for the newest release each time. Nothing to do. | `uv tool upgrade skynet-mars` |
| **No network** | Starts the newest release in uv's cache, and says so in the app's log. Only a first start needs the network. | Runs what is installed. |
| **Roll back** | Set the extension's *MARS release* setting, or `MARS_VERSION` for Codex, to an earlier release (for example `0.1.0rc5`). Clear it to return to the newest. | `uv tool install --force --python 3.13 "skynet-mars[mcp]==<version>"` |
| **Fails to start** | Run the self-test below; when it passes, the fault is in the app's configuration. The app's log has the server's output. | `mars-mcp self-test` |

```bash
uvx --python 3.13 --from "skynet-mars[mcp]@latest" mars-mcp self-test
```

An update never touches your files. Artifacts, downloads and bundles stay in
the MARS home; after an upgrade, `mars-mcp fetch-data` re-checks installed
bundles against the new release's pins and downloads only what changed. The
skill copy `mars-mcp install-skill` wrote is upgraded by running it again if
you have not edited it; with your edits it is left alone and the edited files
are named. The Codex plugin's own copy of the skill updates with the plugin
(`codex plugin marketplace upgrade mars`); the server always sends its current
guide as instructions and resources.

## The `mars` console

The install above also puts `mars` on your `PATH`: a terminal console where a
model calls MARS's tools itself, with no agent host. It needs a model:

- **Anthropic** (the default): set `ANTHROPIC_API_KEY` in your shell before
  starting `mars`. An installed MARS reads no `.env` file; only a checkout
  does.
- **A local Ollama model**, which needs no key: start `ollama serve`, then
  `mars --backend ollama/<model>` with a model from `ollama list`. The
  default, `qwen3.8:27b-mlx`, is an MLX build for Apple Silicon; on Linux
  and Windows, name another model. MARS's instructions and tools take about
  19,000 tokens, more than Ollama's default context window on a machine
  with less memory, which Ollama fills by silently dropping most of the
  prompt. Start the daemon with a larger window,
  `OLLAMA_CONTEXT_LENGTH=32768 ollama serve`; `mars` stops a turn with this
  advice when it sees a prompt cut short.

`MARS_MODEL_BACKEND=provider/model` sets the default backend, and `/backend`
switches inside the console. If the backend it starts on cannot be used,
`mars` exits and says what to set or which model to name. `/help` lists the
commands. Sessions and their artifacts are kept in the MARS home
([Where things go](#where-things-go)).

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

Plate solving needs software and data of its own, installed on your machine;
see [Plate solving](#plate-solving).

## Plate solving

`solve_astrometry` needs two things MARS does not ship, because they are
installed on your machine rather than in Python: the **astrometry.net solver**
(the `solve-field` program) and its **index files**. Without them it reports
`solver_unavailable`, and everything else in MARS works as usual.

**1. Install the solver** from your system's package manager:

| System | Command |
| --- | --- |
| macOS (Homebrew) | `brew install astrometry-net` |
| Fedora | `sudo dnf install astrometry` |
| Debian, Ubuntu | `sudo apt install astrometry.net` |
| Windows | No native build. astrometry.net runs under WSL or Cygwin, and MARS has not been run against either; on Windows, see ATLAS below. |

Check it with `solve-field --help`. MARS finds `solve-field` on the `PATH`
of whatever starts it, so install it where that program looks: a desktop app
started from the Dock or Start menu may not see the folders your shell adds.

**2. Get index files** covering your images' field of view. astrometry.net's
rule is indexes whose sizes run from about 10% to 100% of the image's width:

| Index series | Field of view it serves | Where |
| --- | --- | --- |
| 4107–4119 (Tycho-2) | wide: 22 arcmin and up | Fedora `astrometry-data-4107-4119` (340 MB); Debian/Ubuntu `astrometry-data-tycho2` |
| 5200 or 4200 series | narrow: 2–22 arcmin | <http://data.astrometry.net/> (tens of GB for the smallest scales); Debian/Ubuntu `astrometry-data-2mass-*` (contrib) |

The bundled frames are about 10 arcmin wide and need the narrow series; the
4200 series solves them.

**3. Point MARS at them** with `ANET_INDEX_PATH`: the folder, or folders,
that hold the `index-*.fits` files directly (a parent folder is refused),
joined with `:` (`;` on Windows). For example, with Fedora's package:

```bash
export ANET_INDEX_PATH=/usr/share/astrometry/data
```

Set it where the program that runs MARS reads its environment: your shell
for `mars`, `mars-mcp` and Claude Code; the environment the ChatGPT app starts
in for the Codex plugin, which forwards it. The Claude Desktop extension has
no setting for it yet, so plate solving is not available there.

A full catalog is fine: MARS has astrometry.net load one index at a time,
so a large set (the whole 4200 series is about 32 GB) fits within the 4 GiB
memory limit MARS runs a solve under.

**ATLAS** is MARS's second solver: pure Python, so it needs no program, only a
local UCAC4 or UCAC5 catalogue (`ATLAS_CATALOG_ROOT`, and `ATLAS_CATALOG` for
UCAC4). It solves only near a known pointing and scale, never blind. It has
not been tested on Windows.

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
so launcher exit cannot stand in for worker exit. Cleanup requires the native
process handle to signal, not merely a cached Python exit code, and waits for job-wide
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
