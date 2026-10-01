# Installing MARS and serving its tools

How to put MARS (MCP Astronomy Research Suite) on a machine that has **no checkout** of this repository,
serve its tools to a coding agent's console over MCP, and add the optional
data. The design behind it is `archive/mcp-tool-surface.md` §3.5 and phases
C3–C7.

## What a wheel contains

| Part | Where | Size |
| --- | --- | ---: |
| `tools/` and `algorithms/` | the wheel | ~4 MB of code |
| **Core data**: the five pulsar scans, the recorded zero-point references, the Afterglow parity fixtures | the wheel, under `tools/_data/` | ~7 MB |
| **Optional bundles**: the optical frame library, the Girardi isochrone grid | fetched on request, `mars-mcp fetch-data` | 269 MB, 282 MB |
| astrometry.net indexes, the ATLAS UCAC5 catalogue | **never bundled**; operator-supplied | 78 GB, 5.3 GB |

Measured in C7 on a clean Python 3.14 virtual environment: MARS itself
installs to about 10 MB. The environment as a whole is about **640 MB**,
almost all of it dependencies — `llvmlite` (for `numba`) alone is 168 MB, then
`scipy`, `pandas`, `astropy` and `matplotlib`. `import tools.registry` takes
about 4.5 s the first time (bytecode compilation) and 1.3 s after that.

## Install

**You may need a C compiler.** Two dependencies do not publish pre-built
wheels for every platform, and pip compiles them from source where they are
missing:

| Dependency | Pre-built wheels | Compiles from source on |
| --- | --- | --- |
| `sep` 1.4.1 | Python 3.9–3.13: Linux (x86_64, aarch64), macOS, Windows | **Python 3.14, every platform** |
| `photutils` 3.0.0 | Linux x86_64, macOS, Windows | **Linux aarch64** (ARM servers, Raspberry Pi, Docker on Apple Silicon) |

**Python 3.13 is MARS's target** — what CI and the release workflow run,
and the newest Python every dependency ships wheels for; it is the version
`skynet-mars` requires and tests. Python 3.13 on x86_64 Linux, macOS or
Windows needs no compiler. Anywhere else, install
one first: `apt-get install gcc` on Debian or Ubuntu, `dnf
install gcc` on Fedora, or the Xcode command-line tools on macOS. Without one,
pip fails with `Failed building wheel for sep` (or `photutils`) and
`command 'gcc' failed`. Measured on the `v0.1.0rc1` release in a clean
`python:3.14-slim` container on aarch64.

```bash
python3.13 -m venv mars-env
mars-env/bin/pip install "skynet-mars[mcp]"
mars-env/bin/mars-mcp self-test
```

`[mcp]` brings the server. MARS is on PyPI as
[`skynet-mars`](https://pypi.org/project/skynet-mars/), first as `0.1.0rc4`.
While every release is a pre-release, pip installs the newest one without
`--pre`; once a stable release exists, pip prefers it, and a pre-release needs
`--pre` or an exact version (`"skynet-mars[mcp]==0.1.0rc4"`). Every release is
also a GitHub release, <https://github.com/SkynetRTN/MARS/releases>, whose
wheel installs the same way by URL (`"skynet-mars[mcp] @ <wheel URL>"`), as
does a wheel built with `uv build` in a checkout. `mars-mcp
self-test` launches the installed server as a host would and checks it end to
end; `releasing.md` describes what a release is.

## Register the server with a host

`mars-mcp` is a **local stdio server**. The host starts it as a child process
on your machine and exchanges MCP messages with it over stdin and stdout. It
opens no port and listens on no network, and it lives as long as the host's
session does. So it works in any host that can launch a local command: the
coding-agent CLIs, the IDEs and the Claude desktop app. It does **not** work
in a browser chat (claude.ai or ChatGPT on the web). Those connect only to a
remote server over HTTPS, which MARS does not provide; see
[`working/mcp-http-transport.md`](working/mcp-http-transport.md).

Every host needs the same one thing: the **absolute path** to `mars-mcp` in
the environment you installed it into. Find it with
`mars-env/bin/python -c "import shutil; print(shutil.which('mars-mcp'))"`, or
`mars-env\Scripts\mars-mcp.exe` on Windows. A bare `mars-mcp` works only if
that environment is on the `PATH` the host itself sees, which for a desktop
app is usually not your shell's. Each host below is shown serving all 55
tools; add `"args": ["--tools", "databases,timeseries"]` (or the host's
equivalent) to serve fewer.

Run `mars-mcp self-test` once before registering. It launches the server
exactly as a host would, so a failure there is an install problem, not a host
one.

### Claude Code

```bash
claude mcp add mars -- /path/to/mars-env/bin/mars-mcp
claude mcp add --scope user mars -- /path/to/mars-env/bin/mars-mcp   # every project
```

The default scope is the current project, for you only. `--scope project`
writes `.mcp.json` at the project root, to commit and share:

```json
{"mcpServers": {"mars": {"command": "/path/to/mars-env/bin/mars-mcp"}}}
```

`--env ADS_DEV_KEY=...` before the name passes a variable. Check with
`claude mcp list`, or `/mcp` inside a session. A plate solve can outlast the
default per-call wait; `MCP_TOOL_TIMEOUT` (milliseconds) raises it.

### Claude Desktop

Settings → Developer → **Edit Config** opens `claude_desktop_config.json`:

| OS | Path |
| --- | --- |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "mars": {
      "command": "/path/to/mars-env/bin/mars-mcp",
      "env": {"ADS_DEV_KEY": "your-token"}
    }
  }
}
```

Quit and reopen the app (closing the window is not enough). The desktop app
does not inherit your shell's environment, so a key exported in `.bashrc` or
`.zshrc` is not seen. Put it under `env`, or for ADS in `~/.ads/dev_key`; an
installed MARS reads no `.env` file (only a checkout's). If the
server does not appear, its stderr is in the app's MCP log
(`~/Library/Logs/Claude/mcp-server-mars.log` on macOS,
`%APPDATA%\Claude\logs\` on Windows); the root lines `mars-mcp` prints at
startup are there.

### Codex CLI

```bash
codex mcp add mars -- /path/to/mars-env/bin/mars-mcp
```

or in `~/.codex/config.toml`:

```toml
[mcp_servers.mars]
command = "/path/to/mars-env/bin/mars-mcp"
startup_timeout_sec = 30
tool_timeout_sec = 600

[mcp_servers.mars.env]
ADS_DEV_KEY = "your-token"
```

Raise both timeouts. The first launch compiles bytecode and numba functions
and can take longer than Codex's default startup wait, and a plate solve or an
exhaustive VizieR query outlasts its default per-call limit.

### Cursor

`~/.cursor/mcp.json` for every project, or `.cursor/mcp.json` in one:

```json
{"mcpServers": {"mars": {"command": "/path/to/mars-env/bin/mars-mcp"}}}
```

### VS Code (Copilot agent mode)

`.vscode/mcp.json` in a workspace, or **MCP: Open User Configuration** from
the command palette. VS Code's key is `servers`, not `mcpServers`, and it
takes an explicit `type`:

```json
{"servers": {"mars": {"type": "stdio", "command": "/path/to/mars-env/bin/mars-mcp"}}}
```

### Gemini CLI

`~/.gemini/settings.json`, or `.gemini/settings.json` in a project:

```json
{"mcpServers": {"mars": {"command": "/path/to/mars-env/bin/mars-mcp", "timeout": 600000}}}
```

`timeout` is per call, in milliseconds.

### Any other host

A host that launches stdio servers needs only the command, optionally its
arguments and environment. What varies is the file and the top-level key.

### What reaches the model

Every host gets the tools. The server also sends **instructions** (the skill
brief and what this install has) and the full skill as `mars://skill/...`
**resources**. Whether a host shows those to the model is the host's choice,
and not all do. Where the model never sees them, give it the skill another way:
in Claude Code or Claude Desktop, install `skills/mars-tools/` from a release
or checkout as a skill.

### Groups and startup facts

`mars-mcp --tools databases,timeseries` (or `MARS_MCP_TOOLS`) serves only
those groups: `databases`, `optical`, `timeseries`, `hr`, `radio`. The default
is all 55 tools. At startup the server logs to stderr every root it resolved,
each served group, and whether each data bundle is present. The same facts
reach the model in the server's instructions.

## Where things go

Everything MARS writes lives under one per-user directory, the **MARS
home**: `~/.local/share/mars` on Linux (`$XDG_DATA_HOME` honoured),
`~/Library/Application Support/mars` on macOS, and `%LOCALAPPDATA%\mars`
on Windows. `MARS_HOME` moves it. Nothing is ever written into the installed
package.

| Directory | What | Override |
| --- | --- | --- |
| `<home>/artifacts/` | every tool's output files, in per-tool subdirectories | `MARS_ARTIFACT_DIR` |
| `<home>/fits_downloads/` | `search_mast(download=true)` and `search_casda(download=true)` products | `MARS_FITS_DOWNLOAD_DIR`, or `MARS_DATA_DIR` (downloads then go to its `fits_downloads/`) |
| `<home>/bundles/optical/`, `<home>/bundles/isochrones/` | fetched data bundles | `MARS_OPTICAL_DATA_DIR`, `MARS_ISOCHRONE_DIR` |
| `<home>/numba-cache/` | numba's compiled-function cache, which numba would otherwise write into the installed package | `NUMBA_CACHE_DIR` |

Artifacts are never overwritten, even by two servers sharing the directory:
each name is claimed atomically, and a repeated call writes a new file with a
numeric suffix. So the directory grows; clear it yourself when you want to.
`list_artifacts` over MCP returns the newest 100 entries of a directory, and
says how many there are; a relative `directory` (`pulsar`, `vizier`) is taken
inside the artifact directory, and one that climbs out of it (`..`) is refused.

After `mars-mcp fetch-data`, restart any running `mars-mcp`: the server
reads its data locations when it starts.

### Upgrading from Kepler

Kepler was renamed MARS in `0.1.0rc3`, which also read Kepler's names for
that one pre-release. Releases after it do not, so an install configured as
Kepler is moved over by hand:

- **Install `skynet-mars` into a new environment** (or `pip uninstall kepler`
  first). The two distributions install the same `tools` and `algorithms`
  packages: installed over Kepler they share files, and a later
  `pip uninstall kepler` deletes files MARS needs. If that has happened,
  reinstall the `skynet-mars` wheel with `--force-reinstall`.
- **Rename every `KEPLER_*` variable to `MARS_*`**, in your shell, a host's
  configuration and any `.env`. A `KEPLER_*` variable is ignored.
- **Point the host at `mars-mcp`** under the key `mars`; the `kepler`,
  `kepler-mcp` and `kepler-bench` commands no longer exist.
- **Move what you want to keep** from the Kepler home
  (`~/.local/share/kepler`, and its macOS and Windows equivalents) into the
  MARS home -- at least `bundles/`, and `fits_downloads/` and `artifacts/` if
  you use them -- or set `MARS_HOME` to the old directory. Nothing moves it
  for you. Do not rename the directory itself if a MARS home already exists:
  the rename would nest one inside the other.

## The optional data bundles

```bash
mars-mcp fetch-data --list         # size and status of each
mars-mcp fetch-data optical        # or: isochrones, all
```

Each bundle is one archive whose size and SHA-256 are pinned in the installed
package's own manifest (`tools/mcp/bundles.json`). An installed MARS accepts
only the exact bytes it was released with. A download that fails partway
resumes from where it stopped when you run the command again. A bundle that is
already installed and verified is left alone. `--from URL_OR_DIR` (or
`MARS_BUNDLE_URL`) fetches from a mirror or a local directory instead.

What needs which bundle:

| Tools | Needs |
| --- | --- |
| the pulsar and variable-star chains; `list_zeropoint_references`, `load_zeropoint_reference`, `compare_zeropoint_to_reference` | nothing; core data |
| every database tool (SIMBAD, NED, VizieR, ATNF, MAST, MPC, CASDA, ADS, `resolve_target`) | nothing; remote services |
| `list_optical_frames`, `resolve_optical_frame`, `list_photometry_targets`, `run_photometry_on_target` on a bundled target, `replay_field_calibration`, `calibrate_zeropoint` with `catalog_fixture` | the **optical** bundle |
| `fit_and_compare_hr_diagram`, `run_full_hr_pipeline`, `run_full_hr_pipeline_from_catalog` (the isochrone fit) | the **isochrones** bundle |
| `solve_astrometry` | astrometry.net indexes or a local UCAC catalogue, **operator-supplied** |

Without its bundle, a frame tool says so with the `bundle_not_installed`
warning, naming the command to run. An empty listing is never presented as
the answer.

## Credentials

The server runs as you, with your environment. `ADS_DEV_KEY` enables the ADS
tools (get one at <https://ui.adsabs.harvard.edu/user/settings/token>), and
`CASDA_OPAL_USERNAME` enables CASDA downloads. The server tells the model
whether `ADS_DEV_KEY` is set, never its value.

## Operator-supplied, and what that looks like

Plate solving needs astrometry.net index files (`ANET_INDEX_PATH`) or a local
UCAC catalogue (`ATLAS_CATALOG_ROOT`). They are tens of gigabytes and are
never bundled. Without them, `solve_astrometry` returns its result with a
`solver_unavailable` warning rather than failing. A frame that already has a
WCS still reports it, and every other tool is unaffected.

## Guards that hold on an install

- `solve_astrometry(write_header=true)` refuses to write into the bundled data
  and into a fetched bundle (`refusing_to_modify_fixture`). A header written
  into a bundle frame would silently break its checksum. Downloaded products
  stay writable.
- `list_optical_frames` walks a download root recursively only inside the data
  directory or the MARS home's own `fits_downloads/`. Pointed anywhere else,
  the root is searched flat and the listing says so.
