# The Claude Desktop extension

A one-click install of MARS for Claude Desktop: a `.mcpb` desktop extension
of the MCPB manifest 0.4 `uv` type. The extension carries no Python and no
dependencies. On first launch, Claude Desktop runs

```bash
uv run --directory <unpacked extension> --locked src/server.py
```

which downloads Python 3.13 and installs exactly what `uv.lock` pins: the
published `skynet-mars[mcp]` release named in `pyproject.toml`, and its
dependencies (about 640 MB). Later launches reuse that environment.

| File | What |
| --- | --- |
| `manifest.json` | Name, version, the `uv run` command, and three optional settings shown in Claude Desktop: the ADS token (stored as a secret), the tool groups, and the MARS home |
| `pyproject.toml`, `uv.lock` | The environment: one exact `skynet-mars[mcp]` pin, locked for every platform |
| `src/server.py` | Removes settings the user left empty, then runs `mars-mcp` |
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
zip -r -D ../../mars.mcpb manifest.json pyproject.toml uv.lock icon.png src
```

The result is under 300 kB, and `*.mcpb` is git-ignored. Neither route signs
it, so Claude Desktop shows it as unsigned. Install it in
Claude Desktop by double-clicking it, or with Settings → Extensions →
Advanced settings → Install Extension.

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

This proves the environment: Python, the locked dependencies and the server,
through a blind pulsar detection. It does **not** exercise `src/server.py`'s
handling of the settings, because `self-test` launches its own server process.
That handling is covered by `tests/test_claude_desktop_extension.py`.

## After each release

The pin names a release that is already **on PyPI**, so the extension follows a
release rather than leading it. Once `v<version>` is published:

1. Set the new version in three places: `version` in `pyproject.toml` and
   the `skynet-mars[mcp]==` pin in PEP 440 form (`0.1.0rc5`), and `version`
   in `manifest.json` in semver form, as MCPB requires (`0.1.0-rc.5`).
2. Run `uv lock` in this directory.
3. Build and test as above.

`tests/test_claude_desktop_extension.py` checks that the four version fields
agree and that the pin is never ahead of the repository's version.
