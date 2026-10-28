# Installing MARS on Linux (ARM)

MARS in the ChatGPT desktop app's Codex threads on Linux, written for Fedora
on aarch64; the same steps work on x86_64. The route runs the newest MARS
release from PyPI and needs no checkout of this repository. Claude Desktop
has no Linux build; for Claude Code, Cursor, VS Code or a hand-written
config, see [`../installing.md`](../installing.md).

Verified by the maintainer: Codex in the ChatGPT app on Fedora Workstation,
and earlier in clean Fedora 44 containers (x86_64 and aarch64) through
Codex's app server.

## ChatGPT app with Codex

1. Install the ChatGPT desktop app (in preview on Linux) from
   [OpenAI's Linux page](https://learn.chatgpt.com/docs/linux/linux-app).
   OpenAI publishes `.rpm` packages for Fedora 43 and 44; pick the one for
   your CPU (`uname -m`):

   ```bash
   curl -LO https://persistent.oaistatic.com/codex-app-prod/linux/rpm/latest/chatgpt.aarch64.rpm   # x86_64: chatgpt.x86_64.rpm
   sudo dnf install ./chatgpt.aarch64.rpm
   ```

2. Install uv and git **from Fedora**:

   ```bash
   sudo dnf install uv git
   ```

   Fedora's `uv` is in `/usr/bin`, which an app started from the desktop
   always sees; uv's own installer puts it in `~/.local/bin`, which such an
   app may not.
3. Install the Codex CLI if `codex --version` does not find it, then open a
   new terminal:

   ```bash
   curl -fsSL https://chatgpt.com/codex/install.sh | sh
   ```

4. Add MARS. Pass both `--sparse` paths; without them Codex clones the whole
   repository, data included:

   ```bash
   codex plugin marketplace add SkynetRTN/MARS --sparse .agents/plugins --sparse installers/codex
   codex plugin add mars@mars
   ```

5. Open ChatGPT from the applications menu (restart it if it was open),
   check that MARS is installed in the **Plugins** tab, and start a Codex
   thread. The first start downloads Python 3.13 and about 700 MB of
   packages and compiles `photutils`, so it takes a minute or more. Codex
   asks before any tool that writes a file.

More: [`installers/codex/`](../../installers/codex/README.md), including
settings, data bundles, updating the plugin, and the start-up errors seen on
a clean Fedora.

## Check it works

MARS should show as installed, with 55 tools. Then ask:

> Using MARS, detect the pulsar in the bundled B0329+54 scan without using
> its known period: measure the period, fold at it, plot the folded profile,
> and sonify it.

The model should measure about 0.7148 s, show the plot, and offer the sound.

MARS's own check runs the same release without the app. Fedora's uv does not
download Python by default, so allow it as the plugin does:

```bash
export UV_PYTHON_DOWNLOADS=automatic
uvx --python 3.13 --from "skynet-mars[mcp]@latest" mars-mcp self-test
```

## Logs

Codex logs to `~/.codex/log/` and keeps threads in `~/.codex/sessions/`.
`codex mcp list` shows how it resolved the server.

## Uninstall

- Uninstall MARS from the ChatGPT app's *Plugins* tab.
- Free the space with `uv cache clean` and `uv python uninstall 3.13`. MARS's
  own files are in `~/.local/share/mars`.
