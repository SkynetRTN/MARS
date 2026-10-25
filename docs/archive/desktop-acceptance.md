# Desktop acceptance: MARS in the real Claude and ChatGPT desktop apps

> **Archived 2026-10-23.** M4's *Real desktop use* closed on this guide:
> the maintainer verified Claude Desktop with the `.mcpb` on an Apple Silicon
> Mac and x64 Windows, and Codex in the ChatGPT app on x64 Windows and
> Linux. Codex on the Mac was accepted untested (Issue #51667). No OS or app
> versions were recorded. The install steps moved to the per-platform guides
> in [`../installing/`](../installing/); this copy is the record.

Completed 2026-10-23 for the M4 item **Real desktop use** in the
[release checklist](../working/master-continuation-plan.md#m4-supported-installations-and-real-solver-runs-must-work).
This is the guide for installing MARS into the Claude and ChatGPT desktop
apps on a real machine and checking that it works. The tester installs,
tries the checks in Part 3, and says whether MARS behaved and looked as
expected; when something goes wrong, the transcript and logs in Part 4 are
what a coding agent reworks from.

## Status

| Platform | App | How MARS gets in | Status |
| --- | --- | --- | --- |
| Apple Silicon Mac | Claude Desktop | `.mcpb` extension | **Verified** 2026-10-23 by the maintainer: behavior and appearance as expected |
| Apple Silicon Mac | ChatGPT app (Codex) | Codex plugin | **Accepted untested** 2026-10-23 by the maintainer: see below |
| x64 Windows | Claude Desktop | `.mcpb` extension | **Verified** 2026-10-23 by the maintainer |
| x64 Windows | ChatGPT app (Codex) | Codex plugin | **Verified** 2026-10-23 by the maintainer |
| Linux (Fedora) | ChatGPT app (Codex) | Codex plugin | **Verified** by the maintainer |
| Linux | Claude Desktop | — | Closed: Claude Desktop has no Linux build |

**Codex on the Mac is accepted without a run, by maintainer decision (2026-10-23).** It
could not be tested: in the maintainer's macOS VM the ChatGPT app blocks
Codex messages by workspace settings (Issue #51667, "macOS VM: Codex
messages blocked by workspace settings"). It is assumed to work, because the
plugin's route is the same Unix one verified on Fedora Workstation, and it
did not block the M4 gate. Test it on a physical Mac, or once that issue is
fixed.

Intel Macs and Windows on ARM are unsupported (several dependencies publish
no wheels for them; `../../installers/claude-desktop/README.md`, Platforms)
and are not tested. When a platform passes, add its OS and app version to
its row.

The runs use the routes as shipped, which install the newest PyPI release
(`0.1.0rc6` when this started; maintainer decision, 2026-10-23). App behavior
carries over to later releases.

## Part 1: Before you start

- A **Claude account** (Mac, Windows) and a **ChatGPT account** with Codex
  access.
- About **2 GB free disk**: MARS's first start downloads Python 3.13 and
  about 700 MB of packages.
- Ideally a user account where MARS has never run, so the first start is a
  real one.
- **`mars.mcpb`** for Claude Desktop: download it from the
  [newest release](https://github.com/SkynetRTN/MARS/releases) that has it
  (releases after rc6), or build it on any machine with Python 3 and copy it
  over:

  ```bash
  git clone --depth 1 https://github.com/SkynetRTN/MARS.git && cd MARS
  python3 .github/scripts/pack_extension.py installers/claude-desktop mars.mcpb
  ```

  (On Windows, `py` in place of `python3`.)

## Part 2: Install

### Claude Desktop (Apple Silicon Mac, x64 Windows)

1. Download Claude from <https://claude.com/download> (on Windows, the
   **x64** installer), install it, open it, and sign in.
2. Double-click `mars.mcpb`, or use *Settings → Extensions → Advanced
   settings → Install Extension…*. Accept the warning that it is unsigned.
   No uv or Python is needed first.
3. Leave the three settings (*ADS API token*, *Tool groups*, *MARS home*)
   empty, finish, and make sure the extension is on.
4. Open a new conversation and wait for MARS to show as connected. The
   first start takes a minute or more.

### ChatGPT app with Codex (Apple Silicon Mac, x64 Windows, Linux)

1. **Install uv** (Windows and Mac; on Fedora, `sudo dnf install uv git gcc`
   instead, so the desktop-launched app finds it):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh                                  # Mac
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows
   ```

2. **Install the Codex CLI**, which adds the plugin, and open a new terminal:

   ```bash
   curl -fsSL https://chatgpt.com/codex/install.sh | sh                                  # Mac, Linux
   powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"  # Windows
   ```

3. **Install the ChatGPT desktop app** from OpenAI's
   [Codex app page](https://chatgpt.com/codex?app-landing-page=true) and sign
   in. On Fedora, use the rpm from
   [OpenAI's Linux page](https://learn.chatgpt.com/docs/linux/linux-app)
   (`chatgpt.x86_64.rpm` or `chatgpt.aarch64.rpm`, by `uname -m`).
4. **Add MARS.** Both `--sparse` paths matter; without them Codex clones the
   whole repository, data included:

   ```bash
   codex plugin marketplace add SkynetRTN/MARS --sparse .agents/plugins --sparse installers/codex
   codex plugin add mars@mars
   ```

5. Quit and reopen the ChatGPT app, check that MARS is installed in the
   **Plugins** tab, and start a new Codex thread.

## Part 3: What to check

Use a new conversation (or Codex thread) for each prompt, and approve tool
calls as they come. The questions are what to look for; a "no" is worth a
transcript and logs (Part 4).

1. **Does it connect?** MARS shows as connected or its tools are available,
   on the first start and after quitting and reopening the app. Roughly how
   long did the first start take, and did the app show it was waiting?
2. **Are all the tools there?** The app lists 55 MARS tools (or ask "Which
   MARS tools do you have?").
3. **Does the model get MARS's instructions?** Ask, before any tool call:
   "Without calling any tool, quote the first sentence of the MARS server's
   instructions exactly, and list the skill files it tells you to read." It
   should start "MARS: astronomy tools." and name `mars://skill/SKILL.md`.
4. **Does a real analysis work?** Ask: "Using MARS, detect the pulsar in the
   bundled B0329+54 scan without using its known period: measure the period,
   fold at it, plot the periodogram and the folded profile, and sonify it.
   Then compare your period with the catalogue value." It should measure
   about 0.7148 s before folding, and give the catalogue value only as a
   comparison.
5. **Do approvals make sense?** Which calls asked for approval, and what did
   the prompt offer? Deny one pipeline call once: does the model say so and
   carry on sensibly?
6. **Do images and sound show up?** Did the plot appear as an image and the
   WAV as something playable? Ask "Describe the folded-profile plot you just
   made": does the answer fit the plot (one narrow pulse)?
7. **Does a live query work?** "Using MARS, get SIMBAD's basic data for M31."
8. **Is a missing key explained?** With no ADS token set: "Using MARS, search
   ADS for papers on PSR B0329+54." The user should see "No ADS API token
   configured", not a generic failure.

## Part 4: Transcripts and logs

When a check goes wrong, collect these into one folder named after the
platform and app (`win-claude/`, `mac-codex/`, …) and hand it back:

- **The transcript.** Claude Desktop keeps no file: copy the conversation
  with each tool call expanded, and add screenshots of what the app showed.
  The ChatGPT app saves each Codex thread as
  `~/.codex/sessions/<year>/<month>/<day>/rollout-*.jsonl` (Windows:
  `%USERPROFILE%\.codex\sessions\…`).
- **The app's logs**, copied right after the failure, before restarting:

  | App | Folder |
  | --- | --- |
  | Claude Desktop, macOS | `~/Library/Logs/Claude/` (MARS's output is in `mcp-server-*.log`) |
  | Claude Desktop, Windows | `%APPDATA%\Claude\logs\` |
  | ChatGPT app (Codex), macOS and Linux | `~/.codex/log/` |
  | ChatGPT app (Codex), Windows | `%USERPROFILE%\.codex\log\` |

  For Codex, also the output of `codex mcp list` and `codex plugin list`.
- **MARS's own check**, which shows whether the fault is MARS's or the app's
  (needs uv; on Linux, `export UV_PYTHON_DOWNLOADS=automatic` first):

  ```bash
  uvx --python 3.13 --from "skynet-mars[mcp]@latest" mars-mcp self-test > self-test.txt 2>&1
  ```

- The OS and app versions, and a line on what you expected instead.

## Uninstalling

- Extension: Claude → *Settings → Extensions → MARS → Uninstall*.
- Plugin: uninstall it from the ChatGPT app's *Plugins* tab.
- Space: `uv cache clean` and `uv python uninstall 3.13`. MARS's own files
  are in the MARS home (`~/Library/Application Support/mars` on macOS,
  `%LOCALAPPDATA%\mars` on Windows, `~/.local/share/mars` on Linux;
  `tools/paths.py` is authoritative).

## Closing the item

The item closed on 2026-10-23: every row of the [status](#status) table is
verified, closed, or accepted by the maintainer. The install steps moved into
[`../installing/`](../installing/) and this document was archived (the M4
checkbox **Desktop install guides**).
