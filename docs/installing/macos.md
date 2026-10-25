# Installing MARS on macOS (Apple Silicon)

MARS in the Claude desktop app and in the ChatGPT desktop app's Codex
threads, on an Apple Silicon Mac. Both routes run the newest MARS release
from PyPI and need no checkout of this repository. Intel Macs are not
supported: `numba` and `llvmlite` publish no wheels for them. For Claude
Code, Cursor, VS Code or a hand-written config, see
[`../installing.md`](../installing.md).

Verified by the maintainer on 2026-10-23: Claude Desktop with the extension.
Codex in the ChatGPT app could not be tested in a macOS VM, which blocks
Codex messages by workspace settings (Issue #51667); its route is the one
verified on [Linux](linux.md).

## Claude Desktop

1. Download Claude from <https://claude.com/download>, drag it to
   Applications, open it, and sign in.
2. Download `mars.mcpb` from the newest
   [release](https://github.com/SkynetRTN/MARS/releases) that carries it (the
   first is the release after `0.1.0rc6`), or build it from a checkout with
   `python3 .github/scripts/pack_extension.py installers/claude-desktop mars.mcpb`.
3. Double-click `mars.mcpb`, or use *Settings → Extensions → Advanced
   settings → Install Extension…*. Claude says the extension is unsigned;
   accept. No Python or uv is needed first.
4. The three settings are optional: an *ADS API token* for the literature
   tools ([get one](https://ui.adsabs.harvard.edu/user/settings/token)),
   *Tool groups* to serve fewer tools, and a *MARS home* for where files go.
5. Open a new conversation. The first start downloads Python 3.13 and about
   700 MB of packages, so MARS takes a minute or more to show as connected;
   later starts are quick.

More: [`installers/claude-desktop/`](../../installers/claude-desktop/README.md),
including the optional data bundles.

## ChatGPT app with Codex

1. Install [uv](https://docs.astral.sh/uv/) and the Codex CLI, then open a
   new Terminal window:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   curl -fsSL https://chatgpt.com/codex/install.sh | sh
   ```

2. Install the ChatGPT desktop app from OpenAI's
   [Codex app page](https://chatgpt.com/codex?app-landing-page=true) and sign
   in.
3. Add MARS. Pass both `--sparse` paths; without them Codex clones the whole
   repository, data included:

   ```bash
   codex plugin marketplace add SkynetRTN/MARS --sparse .agents/plugins --sparse installers/codex
   codex plugin add mars@mars
   ```

4. Quit and reopen the ChatGPT app, check that MARS is installed in the
   **Plugins** tab, and start a Codex thread. The first start takes a minute
   or more, as above. Codex asks before any tool that writes a file.

More: [`installers/codex/`](../../installers/codex/README.md), including
settings, data bundles and updating the plugin.

## Check it works

MARS should show as connected (Claude) or installed (Codex), with 55 tools.
Then ask:

> Using MARS, detect the pulsar in the bundled B0329+54 scan without using
> its known period: measure the period, fold at it, plot the folded profile,
> and sonify it.

The model should measure about 0.7148 s, show the plot, and offer the sound.

MARS's own check runs the same release without either app (needs uv):

```bash
uvx --python 3.13 --from "skynet-mars[mcp]@latest" mars-mcp self-test
```

## Logs

| App | Where |
| --- | --- |
| Claude Desktop | `~/Library/Logs/Claude/` (MARS's output: `mcp-server-*.log`) |
| ChatGPT app (Codex) | `~/.codex/log/`; threads in `~/.codex/sessions/` |

## Uninstall

- Claude: *Settings → Extensions → MARS → Uninstall*.
- ChatGPT app: uninstall MARS from the *Plugins* tab.
- Free the space with `uv cache clean` and `uv python uninstall 3.13`. MARS's
  own files are in `~/Library/Application Support/mars`.
