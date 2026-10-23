# Desktop acceptance: MARS in the real Claude and ChatGPT desktop apps

Started 2026-10-23 for the M4 item **Real desktop use** in the
[release checklist](master-continuation-plan.md#m4-supported-installations-and-real-solver-runs-must-work).
This is a step-by-step guide for a person at a real desktop: install the app,
install MARS into it, run eight tests, and hand back the transcripts and logs
([Part 4](#part-4-collecting-transcripts-and-logs)). The tester only tests and
records; a coding agent works from what comes back. The item
closes when every cell of the [record](#record) holds an observed result or
"not run" with a reason.

Installer checks so far ran on Linux without either app's interface (the
`.mcpb` launch command on Fedora aarch64, and the Codex plugin through
`codex app-server` in Fedora 44 containers; [host proposal](../analysis/mcp-desktop-hosts.md)
§5). What only a real desktop shows is how the app itself behaves: install
dialogs, the first-launch wait, approval prompts, images and audio, and error
messages.

## What runs where

| Machine | Cell | App | How MARS gets in | About |
| --- | --- | --- | --- | --- |
| Apple Silicon Mac | **C-mac** | Claude Desktop | `.mcpb` extension, double-click | 30 min |
| | **C-manual** | Claude Desktop | `uv tool install` and a config entry | 20 min |
| | **G-mac** | ChatGPT desktop app, Codex | Codex plugin from GitHub | 30 min |
| x64 Windows | **C-win** | Claude Desktop | `.mcpb` extension, double-click | 30 min |
| | **G-win** | ChatGPT desktop app, Codex | Codex plugin from GitHub | 30 min |
| Fedora 44 Workstation | **G-fedora** | ChatGPT desktop app, Codex | Codex plugin from GitHub | 30 min |

Run the cells on one machine in the order listed: each later cell needs a
tool an earlier one installs. Claude Desktop has no Linux build, so Fedora
has only the Codex cell. Intel Macs and Windows on ARM are unsupported
(several dependencies publish no wheels for them;
`../../installers/claude-desktop/README.md`, Platforms) and are not tested.

**Build under test.** By maintainer decision (2026-10-23), the runs use the
routes as shipped, which install the newest PyPI release, `0.1.0rc6`. M1 and
M3 are not in rc6, so tool behavior seen here is rc6's. App behavior
(install, instructions, approvals, media) carries over to later releases. On
the next release candidate, rerun tests T1, T4 and T5 on one machine per app
and note the version.

**Linux preflight, 2026-10-23.** The `.mcpb`'s launch command, run cold with
an empty uv cache, fetched rc6, served 55 tools and passed `self-test` in
35 s with 752 MB of cache. A failure below is therefore the app's, not the
launch command's.

## Part 1: Before you start

You need:

- a **Claude account** (Mac and Windows) and a **ChatGPT account** with
  Codex access (all three machines);
- about **2 GB free disk** and a reasonable connection: the first start of
  MARS downloads Python 3.13 and about 700 MB of packages;
- a **fresh user account** on each machine, or one where MARS has never run,
  so the first launch is a real first launch;
- a copy of the record table below (a spreadsheet or this file) and a folder
  outside the repository for screenshots and logs.

**Get `mars.mcpb`** (Mac and Windows only). Releases after rc6 attach it:
download it from the [newest release](https://github.com/SkynetRTN/MARS/releases)
that has it. Until then, build it on any machine with Python 3 and a
checkout, and copy the file to the test machines:

```bash
git clone --depth 1 https://github.com/SkynetRTN/MARS.git && cd MARS
python3 .github/scripts/pack_extension.py installers/claude-desktop mars.mcpb
```

(On Windows, `py` in place of `python3`.) It is under 300 kB.

**Rules for every test.** Start a new conversation (a new Codex thread in
the ChatGPT app) for each test unless it says otherwise. Paste prompts
exactly, and save every conversation's transcript as Part 4 says. When a step
fails, do not try to fix it: collect the logs, mark it failed, and go on with
the next test that can still run. A step that needed any deviation from this
guide is a finding, not a pass. Keep timing with a phone stopwatch.

## Part 2: Install, machine by machine

### Apple Silicon Mac

**C-mac: Claude Desktop with the extension**

1. Download Claude for macOS from <https://claude.com/download>, open the
   `.dmg`, drag Claude to Applications, open it, and sign in.
2. Do **not** install uv yet. The extension claims to need no Python and no
   uv; this cell tests that claim.
3. Double-click `mars.mcpb`. If that does nothing, open Claude → *Settings →
   Extensions → Advanced settings → Install Extension…* and pick the file.
   Claude warns that the extension is unsigned; accept.
4. The install dialog shows three optional settings (*ADS API token*, *Tool
   groups*, *MARS home*). **Leave all three empty.** Finish the install and
   make sure the extension is switched on.
5. Start the stopwatch, open a new conversation, and stop it when MARS shows
   as connected (under the tools or connectors menu in the message box). This
   is the **cold start**: expect a minute or more. Note whether the app
   showed progress, a spinner, a timeout, or an error meanwhile.
6. If the server does not connect, take a screenshot of what Claude shows,
   collect the logs (Part 4), and mark the cell failed.
7. Quit Claude completely (⌘Q), reopen it, and time the **warm start** the
   same way.
8. Run [the tests](#part-3-the-tests), T1–T8.

**C-manual: Claude Desktop configured by hand**

1. In Terminal, install uv and MARS:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # open a new Terminal window, then:
   uv tool install --python 3.13 "skynet-mars[mcp]"
   mars-mcp self-test
   uv tool dir --bin          # prints the folder holding mars-mcp
   ```

   The self-test should end with a pass. Note the full path to `mars-mcp`
   (for example `/Users/you/.local/bin/mars-mcp`).
2. In Claude: *Settings → Extensions*, turn the MARS extension **off** (so
   two copies do not run at once).
3. *Settings → Developer → Edit Config* opens `claude_desktop_config.json`.
   Make it contain (merge with anything already there):

   ```json
   {"mcpServers": {"mars": {"command": "/Users/you/.local/bin/mars-mcp"}}}
   ```

   with your full path; `~` does not work here. Save, then quit and reopen
   Claude.
4. Time the start until MARS shows as connected, then run tests T1–T8. T3's
   group setting does not apply here; mark it "n/a".

**G-mac: ChatGPT desktop app with the Codex plugin**

1. Install the Codex CLI, which adds the plugin:

   ```bash
   curl -fsSL https://chatgpt.com/codex/install.sh | sh
   codex --version
   ```

2. Install the ChatGPT desktop app from OpenAI's
   [Codex app page](https://chatgpt.com/codex?app-landing-page=true) (or run
   `codex app`), open it, and sign in.
3. Add MARS. Both `--sparse` paths matter; without them Codex clones the
   whole repository, data included:

   ```bash
   codex plugin marketplace add SkynetRTN/MARS --sparse .agents/plugins --sparse installers/codex
   codex plugin add mars@mars
   ```

4. Quit and reopen the ChatGPT app. Open the **Plugins** tab and check that
   MARS is listed and installed (under the `mars` marketplace). If it is
   listed but not installed, install it there with the plus button and record
   that you had to.
5. MARS's packages are already in uv's cache from C-manual, so this start
   will be warm. To time a real first start, first run `uv cache clean` and
   `uv python uninstall 3.13` (this costs another ~700 MB download).
6. Start a new Codex thread and time it until MARS's tools are available
   (ask "Which MARS tools do you have?" if the app shows no indicator). Quit
   and reopen for the warm start.
7. Run tests T1–T8. T3's group setting does not apply; mark it "n/a".

### x64 Windows

**C-win: Claude Desktop with the extension**

1. Download the **x64** Claude installer from <https://claude.com/download>,
   run it, and sign in.
2. Do **not** install uv yet. Follow C-mac steps 3–8 (Windows: right-click the
   tray icon → *Quit* to quit fully).

C-manual on Windows is optional; if time allows, follow the Mac steps with
the path `C:\Users\you\.local\bin\mars-mcp.exe` written with doubled
backslashes in the JSON (`"C:\\Users\\you\\.local\\bin\\mars-mcp.exe"`).

**G-win: ChatGPT desktop app with the Codex plugin**

1. Install uv in PowerShell, then open a new PowerShell window and check
   `uv --version`:

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
2. Install the Codex CLI and check it:

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"
   codex --version
   ```

3. Follow G-mac steps 2–7. The `codex plugin` commands are the same in
   PowerShell.

### Fedora 44 Workstation

**G-fedora: ChatGPT desktop app with the Codex plugin**

1. Install the ChatGPT app ([OpenAI's Linux page](https://learn.chatgpt.com/docs/linux/linux-app)).
   Check the CPU with `uname -m`, then:

   ```bash
   cd ~/Downloads
   curl -LO https://persistent.oaistatic.com/codex-app-prod/linux/rpm/latest/chatgpt.x86_64.rpm   # aarch64: chatgpt.aarch64.rpm
   sudo dnf install ./chatgpt.x86_64.rpm
   ```

2. Install uv, git and gcc **from Fedora**, not with uv's own installer: the
   app is started from the desktop and may not see `~/.local/bin`.

   ```bash
   sudo dnf install uv git gcc
   ```

3. Check for the Codex CLI with `codex --version`. If it is not found,
   install it: `curl -fsSL https://chatgpt.com/codex/install.sh | sh`, then
   open a new terminal.
4. Open **ChatGPT** from the applications menu and sign in. Note whether the
   session is Wayland or X11 (`echo $XDG_SESSION_TYPE`).
5. Follow G-mac steps 3, 4, 6 and 7. This is the machine's first MARS start,
   so it is a real cold start without any cleaning.

## Part 3: The tests

Run all eight in each cell. What to write down goes in the matching rows of
the [record](#record).

**T1. Versions.** Write down the OS version and CPU, the app version
(Claude: *Claude → About Claude*; ChatGPT: *Settings → About*), `uv
--version` if uv is installed, and the date. After the server has started
once, find which MARS release it runs:

```bash
uv tool run --offline --python 3.13 --from "skynet-mars[mcp]" python -c "import importlib.metadata as m; print(m.version('skynet-mars'))"
```

Expected `0.1.0rc6` (or the release you are testing). If it says the
package is not available offline, the app used a different uv cache; note
that and read the version from the server log instead.

**T2. Start-up.** Already timed during install: write down the cold and warm
start times and what the app showed while waiting.

**T3. Tool list and settings.** Count the MARS tools the app lists:
**expected 55**. Extension cells only: open *Settings → Extensions → MARS*,
set *Tool groups* to `databases`, restart Claude, and count again:
**expected 16**. Clear the setting and restart. Note anything that broke
because a setting was empty.

**T4. Instructions and skill.** Before any tool has been called in the
conversation, paste:

> Without calling any tool, quote the first sentence of the MARS server's
> instructions exactly, and list the skill files it tells you to read.

Pass: the answer starts "MARS: astronomy tools." and names
`mars://skill/SKILL.md` and five `mars://skill/references/*.md` guides. Then
ask "Read the `mars://skill/SKILL.md` resource and summarize it in two
lines." and note whether the model could reach it. On Claude, also check
whether the resource can be attached from the message box's `+` menu. On
Codex, type `@` and check whether the `mars-tools` skill is offered.

**T5. A real analysis.** Paste:

> Using MARS, detect the pulsar in the bundled B0329+54 scan without using
> its known period: measure the period, fold at it, plot the periodogram
> and the folded profile, and sonify it. Then compare your period with the
> catalogue value.

Pass: the model calls, in this order, `list_pulsar_scans` (or resolves the
scan), `load_pulsar_lightcurve`, `compute_pulsar_periodogram`,
`fold_pulsar_lightcurve` at the **period it measured** (about 0.7148 s),
`plot_pulsar` and `sonify_pulsar`, and gives the catalogue value only as a
comparison. Approve calls as they come, except the one T6 asks you to deny.

Then, in a new conversation, the same prompt with **B1133+16**. Either
outcome is fine: a blind detection, or a fallback to the catalogued period
*that the model says is a fallback*. A fallback presented as a detection is
a fail. Finally, in a new conversation: "Using MARS, get SIMBAD's basic data
for M31." (`search_simbad`, a live network call).

**T6. Approvals.** During T5, note which calls asked for approval and what
each prompt offered (allow once, always allow, deny). Codex should **not**
ask for `list_pulsar_scans` or `resolve_target` (read-only) and **should**
ask for `load_pulsar_lightcurve` and the other pipeline tools (they write
files). Deny one of those once, and note what the model was told and what it
did next.

**T7. Images and sound.** Note what the `plot_pulsar` PNG became in the
conversation (an inline image, an attachment, a file path only, or nothing)
and the same for the `sonify_pulsar` WAV (an audio player, an attachment, a
path, nothing). Then ask "Describe the folded-profile plot you just made."
Pass: the description fits what the plot shows (one narrow pulse in phase),
showing the model saw the image rather than guessing.

**T8. A helpful error.** With no ADS token set anywhere, paste "Using MARS,
search ADS for papers on PSR B0329+54." Pass: the user sees a clear message
(code `dependency_missing`, "No ADS API token configured"), not a generic
failure. The message names only the `ADS_DEV_KEY` environment variable, which
a desktop app does not read from your shell. Note whether you could tell
where to set it instead: the extension's *ADS API token* setting, the file
`~/.ads/dev_key`, or the variable the Codex plugin forwards.

## Part 4: Collecting transcripts and logs

Hand back one folder per cell, named after it (`C-mac/`, `G-fedora/`, …),
kept outside the repository. A coding agent reworks MARS from this folder
alone, so include everything below even when every test passed.

**1. A transcript of every test**, one file per conversation, named after the
test (`T5-B0329.md`, `T5-B1133.md`, …):

- **Claude Desktop** keeps no transcript file. In the conversation, copy the
  whole thing (each tool call expanded, so its arguments and result show) and
  paste it into the file. Add screenshots of approval prompts, images, the
  audio player and any error, named after the test.
- **ChatGPT app (Codex)** saves every thread as a file. Copy the threads
  from the test session: `~/.codex/sessions/<year>/<month>/<day>/rollout-*.jsonl`
  (Windows: `%USERPROFILE%\.codex\sessions\…`). Add screenshots as above;
  the file does not show what the app drew.

**2. The app's logs**, copied whole after the last test (and right after
any failure, before restarting the app):

| App | Copy this folder |
| --- | --- |
| Claude Desktop, macOS | `~/Library/Logs/Claude/` (MARS's own output is in `mcp-server-*.log`) |
| Claude Desktop, Windows | `%APPDATA%\Claude\logs\` |
| ChatGPT app (Codex), macOS and Fedora | `~/.codex/log/` |
| ChatGPT app (Codex), Windows | `%USERPROFILE%\.codex\log\` |

For Codex cells, also save the output of `codex mcp list` and
`codex plugin list` (or a screenshot of the Plugins tab).

**3. MARS's own check**, run once in a terminal after the tests. It starts
the same release the apps start and runs a pulsar detection without any app,
which tells the coding agent whether a failure is MARS's or the app's. Save
its whole output as `self-test.txt`:

```bash
uvx --python 3.13 --from "skynet-mars[mcp]@latest" mars-mcp self-test
```

(On Fedora, run `export UV_PYTHON_DOWNLOADS=automatic` first, as the plugin
does. On a Mac or Windows cell with no uv, write "no uv" instead.)

**4. The filled column of the record** below, and `notes.md` with anything
else you saw: timings, deviations from this guide, and what you expected
instead.

## Part 5: Between cells and afterwards

- **Remove the extension**: Claude → *Settings → Extensions → MARS →
  Uninstall*.
- **Remove the manual install**: delete the `mars` entry from
  `claude_desktop_config.json`, then `uv tool uninstall skynet-mars`.
- **Remove the plugin**: uninstall it from the ChatGPT app's *Plugins* tab.
- **Free the space**: `uv cache clean` and `uv python uninstall 3.13`; MARS's
  own files are in the MARS home (`~/Library/Application Support/mars` on
  macOS, `%LOCALAPPDATA%\mars` on Windows, `~/.local/share/mars` on Linux;
  `tools/paths.py` is authoritative).

## Record

One column per cell. Write the observed result, `fail: <what>`, or `not
run: <reason>`. Keep logs and screenshots outside the repository and say
where they are.

| Check | C-mac | C-win | C-manual | G-fedora | G-mac | G-win |
| --- | --- | --- | --- | --- | --- | --- |
| Tester, date | | | | | | |
| T1 OS version, CPU | | | | | | |
| T1 App version | | | | | | |
| T1 uv version (or "none") | | | | | | |
| T1 MARS release served | | | | | | |
| T2 Install route worked as written | | | | | | |
| T2 Cold start (s), what the app showed | | | | | | |
| T2 Warm start (s) | | | | | | |
| T3 Tools shown; with `databases` | | | | | | |
| T4 Instructions quoted correctly | | | | | | |
| T4 Skill resource or skill reachable | | | | | | |
| T5 B0329+54 blind detection, order right | | | | | | |
| T5 B1133+16 outcome and how reported | | | | | | |
| T5 `search_simbad` M31 | | | | | | |
| T6 Approval prompts seen; deny handled | | | | | | |
| T7 PNG became | | | | | | |
| T7 WAV became | | | | | | |
| T7 Model saw the plot | | | | | | |
| T8 Missing ADS key message | | | | | | |
| Deviations and other findings; folder of transcripts and logs | | | | | | |

## Closing the item

When the table is filled, fold the supported OS and app versions into
`../installing.md` and the two installer READMEs, correct anything the runs
contradict, and close the M4 item with this document as its evidence. Every
platform or host that `../installing.md` names but no cell covered (Cursor,
VS Code, Gemini CLI, Claude Desktop on Windows if C-win is not run, and so on)
stays listed there as untested.
