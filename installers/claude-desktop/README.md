# The Claude Desktop extension

A one-click install of MARS for Claude Desktop: a `.mcpb` desktop extension
of the MCPB manifest 0.4 `uv` type. It **always runs the newest MARS release
on PyPI** and names no version, so it never needs rebuilding to follow a
release. Claude Desktop runs

```bash
uv run --directory <unpacked extension> --locked src/server.py
```

`src/server.py` has no dependencies. It runs `mars-mcp` with `uv tool run`
(what `uvx` is), in two steps:

1. `--from "skynet-mars[mcp]@latest"` asks PyPI for the newest release and
   installs it into uv's cache if it is not there yet. The first launch also
   downloads Python 3.13 and the dependencies (about 700 MB); later launches
   only check, in well under a second. It prints the release's version.
2. `--offline`, naming that version, starts exactly that release. Naming it matters: given the bare name, uv prefers a
   `uv tool install` of MARS, however old, over the cache. Without a network,
   step 1 runs again offline, which finds the newest release in the cache,
   and that one starts.

The *MARS release* setting (`MARS_VERSION`) pins one release instead, for
both steps: the way to step back from a bad release. The Codex plugin runs
this same file (see [its README](../codex/README.md)); after changing it, run
`python3 .github/scripts/sync_codex_launcher.py`.

| File | What |
| --- | --- |
| `manifest.json` | Name, the extension's own version, the `uv run` command, and four optional settings shown in Claude Desktop: the ADS token (stored as a secret), the tool groups, the MARS home, and a MARS release to pin |
| `pyproject.toml`, `uv.lock` | The entry point's environment, empty on purpose: MARS comes from `uv tool run` |
| `src/server.py` | Removes settings the user left empty, then runs the newest `mars-mcp` |
| `icon.png` | The 512 px mark, exported by `docs/assets/make_brand.py` |

This README is not packed (`.mcpbignore`).

## Build

Releases after `0.1.0rc6` carry `mars.mcpb`, packed by the release workflow
from the tagged commit and run there on macOS and Windows before publishing
(`docs/releasing.md`). To build it yourself:

```bash
npx @anthropic-ai/mcpb@2.1.2 validate installers/claude-desktop/manifest.json
npx @anthropic-ai/mcpb@2.1.2 pack installers/claude-desktop mars.mcpb
```

Without Node, a plain zip of the five packed files is the same extension,
file for file and byte for byte:

```bash
cd installers/claude-desktop
zip -D ../../mars.mcpb manifest.json pyproject.toml uv.lock icon.png src/server.py
```

The result is under 300 kB, and `*.mcpb` is git-ignored. Neither route signs
it, so Claude Desktop shows it as unsigned. Install it in
Claude Desktop by double-clicking it, or with Settings → Extensions →
Advanced settings → Install Extension.

## Data bundles

The extension does not fetch the optional data bundles. With
[uv](https://docs.astral.sh/uv/) installed, run:

```bash
uvx --python 3.13 --from "skynet-mars[mcp]@latest" mars-mcp fetch-data optical
```

`@latest` is the release the extension runs, so the bundle matches what it
expects. If you set the extension's MARS home, run this with the same
directory in `MARS_HOME`. Otherwise the bundle lands where the server does
not look.

## Test without Claude Desktop

Unpack the `.mcpb` (it is a zip) outside the checkout, and run the manifest's
own command with an empty uv cache and **only uv-managed Pythons**. Otherwise
uv reuses a Python 3.13 already on the machine and the run understates a first
launch:

```bash
T=$(mktemp -d) && mkdir "$T/ext" && python3 -m zipfile -e mars.mcpb "$T/ext"
UV_CACHE_DIR="$T/cache" UV_PYTHON_INSTALL_DIR="$T/python" UV_PYTHON_PREFERENCE=only-managed \
  uv run --directory "$T/ext" --locked src/server.py self-test
rm -rf "$T"
```

This proves the whole launch: the newest release from PyPI, Python and its
dependencies, and the server, through a blind pulsar detection. It does
**not** exercise `src/server.py`'s handling of the settings, because
`self-test` launches its own server process. That handling, and the two
commands, are covered by `tests/test_claude_desktop_extension.py`.

## After a release

Nothing. The extension names no MARS version, and picks up a release the next
time it starts. Change `version` in `manifest.json` (and `pyproject.toml`)
only when the extension itself changes.

## Platforms

The manifest says macOS and Windows, but MCPB cannot name a CPU. `numba` and
`llvmlite` publish macOS wheels for **Apple Silicon only**; on an Intel Mac
the first launch would have to compile them and fails. `sep`, `pyerfa` and
others have no Windows ARM64 wheels, so on Windows on ARM the launcher runs
MARS on the x64 build of Python 3.13, which Windows runs under its own
emulation. Supported: Apple Silicon Macs (verified in Claude Desktop by the
maintainer, 2026-10-23) and Windows on ARM (the launch verified on Windows 11
ARM64, 2026-10-27). x64 Windows is no longer tested. Step-by-step installs:
[macOS](../../docs/installing/macos.md), [Windows](../../docs/installing/windows.md).
