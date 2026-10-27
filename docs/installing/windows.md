# Installing MARS on Windows on ARM

MARS in the Claude desktop app and in the ChatGPT desktop app's Codex
threads, on a Windows on ARM (ARM64) PC. Both routes run the newest MARS
release from PyPI and need no checkout of this repository. MARS runs on the
x64 build of Python 3.13, under Windows' built-in x64 emulation: `sep` and
`pyerfa` publish no Windows ARM64 wheels. Both routes choose that Python
themselves; nothing extra is needed. x64 Windows is no longer tested. For
Claude Code, Cursor, VS Code or a hand-written config, see
[`../installing.md`](../installing.md).

Verified on Windows 11 ARM64 on 2026-10-27 through the routes' own launch
command: a first start from nothing in 86 s (1.7 GB of Pythons and
packages), an offline start and a pinned release, each serving 55 tools.
The maintainer verified both apps on Windows on 2026-10-23, before the
launcher chose the x64 Python.

## Claude Desktop

1. Download Claude for Windows from <https://claude.com/download>, run it,
   and sign in.
2. Download `mars.mcpb` from the newest release on the
   [releases page](https://github.com/SkynetRTN/MARS/releases).
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

1. Install [uv](https://docs.astral.sh/uv/) and the Codex CLI in PowerShell,
   then open a new PowerShell window:

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"
   ```

2. Install the ChatGPT desktop app from OpenAI's
   [Codex app page](https://chatgpt.com/codex?app-landing-page=true) and sign
   in.
3. Add MARS. Pass both `--sparse` paths; without them Codex clones the whole
   repository, data included:

   ```powershell
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

```powershell
uvx --python cpython-3.13-windows-x86_64-none --from "skynet-mars[mcp]@latest" mars-mcp self-test
```

## Logs

| App | Where |
| --- | --- |
| Claude Desktop | `%APPDATA%\Claude\logs\` |
| ChatGPT app (Codex) | `%USERPROFILE%\.codex\log\`; threads in `%USERPROFILE%\.codex\sessions\` |

## Uninstall

- Claude: *Settings → Extensions → MARS → Uninstall*.
- ChatGPT app: uninstall MARS from the *Plugins* tab.
- Free the space with `uv cache clean` and
  `uv python uninstall 3.13 cpython-3.13-windows-x86_64-none`. MARS's
  own files are in `%LOCALAPPDATA%\mars`.
