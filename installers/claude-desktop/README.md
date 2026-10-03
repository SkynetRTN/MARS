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
   only check, in well under a second.
2. `--offline --from "skynet-mars[mcp]"` starts the newest release in the
   cache. Without a network, step 1 fails and the last release fetched still
   starts.

| File | What |
| --- | --- |
| `manifest.json` | Name, the extension's own version, the `uv run` command, and three optional settings shown in Claude Desktop: the ADS token (stored as a secret), the tool groups, and the MARS home |
| `pyproject.toml`, `uv.lock` | The entry point's environment, empty on purpose: MARS comes from `uv tool run` |
| `src/server.py` | Removes settings the user left empty, then runs the newest `mars-mcp` |
| `icon.png` | The 512 px mark, exported by `docs/assets/make_brand.py` |

This README is not packed (`.mcpbignore`).

## Build

```bash
npx @anthropic-ai/mcpb validate installers/claude-desktop/manifest.json
npx @anthropic-ai/mcpb pack installers/claude-desktop mars.mcpb
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
`llvmlite` publish macOS wheels for **Apple Silicon only**, and
`sep`, `photutils` and others have no Windows-on-ARM wheels. On an Intel Mac
or an ARM Windows machine, the first launch would have to compile them and
fails. Supported: Apple Silicon Macs and x64 Windows.
