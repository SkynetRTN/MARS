# Desktop acceptance: MARS in the real Claude and ChatGPT desktop apps

Started 2026-10-23 for the M4 item **Real desktop use** in the
[release checklist](master-continuation-plan.md#m4-supported-installations-and-real-solver-runs-must-work).
Installer and app-server checks so far ran on Linux without either app's
interface: the `.mcpb` launch command on Fedora aarch64, where Claude Desktop
does not run, and the Codex plugin through `codex app-server` in Fedora 44
containers ([dated host proposal](../analysis/mcp-desktop-hosts.md) §5). This
document is the procedure a person runs at each real desktop, and the record
of what each run showed. The item closes when every cell below is filled with
an observed result or an explicit "not run" and its reason.

**Build under test.** By maintainer decision (2026-10-23), the runs use the
routes as shipped, which install the newest PyPI release: `0.1.0rc6`. M1 and
M3 are not in rc6, so tool behavior seen here is rc6's. Registration,
instructions, approvals and media are host behavior and carry over; on the
next release candidate, rerun steps 1, 4 and 5 on one host per app and note
the version.

**Preflight on Linux, 2026-10-23.** A `.mcpb` packed from
`installers/claude-desktop/` at `fb8b19e` was unpacked and its manifest
command run cold under `env -i`, with an empty uv cache and only uv-managed
Pythons: it fetched rc6, served 55 tools, 6 skill resources and 1,503
characters of instructions, and passed `self-test` (B0329+54 blind at
204.4σ, sonification returned as audio) in 35 s with 752 MB of cache. So a
host failure below is the host's, not the launch command's.

## Hosts

| Cell | App | OS and CPU | Route |
| --- | --- | --- | --- |
| C-mac | Claude Desktop | macOS, Apple Silicon | `.mcpb` extension |
| C-win | Claude Desktop | Windows, x64 | `.mcpb` extension |
| C-manual | Claude Desktop | macOS (and Windows if time allows) | `uv tool install` plus `mcpServers` config, as `../installing.md` says |
| G-fedora | ChatGPT desktop app, Codex threads | Fedora 44 Workstation | Codex plugin from GitHub |
| G-mac | ChatGPT desktop app, Codex threads | macOS, Apple Silicon | Codex plugin from GitHub |
| G-win | ChatGPT desktop app, Codex threads | Windows, x64 | Codex plugin from GitHub |

Claude Desktop does not run on Linux, so there is no C-fedora cell. Intel
Macs and Windows on ARM are unsupported (no wheels; see
`../../installers/claude-desktop/README.md`, Platforms) and are not tested.
If an app on macOS or Windows runs Codex threads only through a separate
Codex app, or does not take plugins, record what it offers and use the manual
`~/.codex/config.toml` route from `../installing.md` instead.

## Before each run

Use a machine, or a fresh user account, where MARS has not run before, so
the first launch is a real one. Remove or rename any earlier MARS
registration. On macOS and Windows install uv with its own installer; on
Fedora use `sudo dnf install uv git gcc` (`../../installers/codex/README.md`).

Releases after rc6 attach `mars.mcpb`; use that once one exists. rc6 has
none, so for now build it from a checkout:

```bash
cd installers/claude-desktop
zip -r -D ../../mars.mcpb manifest.json pyproject.toml uv.lock icon.png src -x '*__pycache__*'
```

## Procedure

Run every step in a new conversation (a new Codex thread for G cells) unless
it says otherwise. Copy prompts as written. Record what happens, including
failures and workarounds; a step that needs a workaround is a finding, not a
pass.

1. **Versions.** Record the OS version and build, the app version (Claude:
   *About Claude*; ChatGPT: *Settings → About*), `uv --version`, and the date.
   After step 2, record the MARS release the host runs:

   ```bash
   uv tool run --offline --python 3.13 --from "skynet-mars[mcp]" python -c "import importlib.metadata as m; print(m.version('skynet-mars'))"
   ```

2. **Registration.** Install by the cell's route: for `.mcpb`, double-click
   the file or drag it onto *Settings → Extensions*, and leave every setting
   empty; for the plugin, follow `../../installers/codex/README.md`, *Install
   on Fedora 44* (the same commands on macOS and Windows), and check that the
   Plugins Directory lists MARS. Then start a conversation and time how long
   until the app shows the server as connected. Record the time, and whether
   the app showed progress, a timeout, or an error during the first launch.
   Then quit and reopen the app and record the warm start.

   If it fails, collect the server log (Claude: `~/Library/Logs/Claude/mcp-server-mars.log`
   on macOS, `%APPDATA%\Claude\logs\` on Windows; Codex: the thread's MCP
   error and `codex mcp list`), and run the cell's self-test from the
   installer README.

3. **Tool list and settings.** Record how many MARS tools the app shows
   (expected 55). For C-mac or C-win, set *Tool groups* to `databases`,
   restart, and record the count (expected 16); then clear it again. Record
   whether an empty optional setting broke anything.

4. **Instructions and skill.** Ask, before any tool has been called:

   > Without calling any tool, quote the first sentence of the MARS server's
   > instructions exactly, and list the skill files it tells you to read.

   The right answer starts "MARS: astronomy tools." and names
   `mars://skill/SKILL.md` and the five `mars://skill/references/*.md`
   guides. Record the answer. Then ask the model to
   read the `mars://skill/SKILL.md` resource (on Claude, also try attaching
   it from the conversation's attachment or `+` menu) and record whether the
   resource was reachable and by which means. On G cells, also check whether
   the `mars:mars-tools` skill is listed for the thread.

5. **Calls and period provenance.** Ask:

   > Using MARS, detect the pulsar in the bundled B0329+54 scan without using
   > its known period: measure the period, fold at it, plot the periodogram
   > and the folded profile, and sonify it. Then compare your period with the
   > catalogue value.

   Pass when the model calls `list_pulsar_scans` or resolves the scan, then
   `load_pulsar_lightcurve`, `compute_pulsar_periodogram`,
   `fold_pulsar_lightcurve` at the *measured* period (about 0.7148 s),
   `plot_pulsar`, and `sonify_pulsar`, in that order, and reports the
   catalogue value only as a comparison. Repeat with B1133+16 and record
   whether it detected the pulsar blind or fell back to the catalogued period,
   and whether it said so. Both are acceptable outcomes; reporting a fallback
   fold as a detection is not. Then, in a new conversation, ask for SIMBAD's
   basic data on M31 (`search_simbad`, a live network call).

6. **Approvals.** During step 5, record which calls asked for approval and
   what each prompt offered (once, always, deny). On G cells the plugin sets
   `writes`: `list_pulsar_scans` and `resolve_target` are read-only and
   should not ask; `load_pulsar_lightcurve` and the other pipeline tools
   write artifacts and should. Deny one write call once and record what the
   model was told and what it did next.

7. **Media.** Record what the `plot_pulsar` PNG and the `sonify_pulsar` WAV
   became in the conversation: an image shown inline, an audio player, an
   attachment, a file path only, or nothing. Ask the model to describe the
   folded-profile plot, and record whether its answer shows it saw the image
   (one narrow pulse in phase).

8. **Errors.** Ask for `search_ads` on any query with no ADS token
   configured, and record whether the user sees a usable message (code
   `dependency_missing`, "No ADS API token configured") rather than a generic
   failure. The message names only the `ADS_DEV_KEY` environment variable,
   which a desktop app does not read from the shell; record whether the
   tester could tell where to set it (the extension's *ADS API token*
   setting, `~/.ads/dev_key`, or the plugin's forwarded variable).

## Record

One column per cell. Write the observed result, `fail: <what>`, or `not
run: <reason>`. Keep logs and screenshots outside the repository and name
where they are.

| Check | C-mac | C-win | C-manual | G-fedora | G-mac | G-win |
| --- | --- | --- | --- | --- | --- | --- |
| Tester, date | | | | | | |
| OS version, build, CPU | | | | | | |
| App version | | | | | | |
| uv version | | | | | | |
| MARS release served | | | | | | |
| 2 Registration route works | | | | | | |
| 2 Cold start (s), what the app showed | | | | | | |
| 2 Warm start (s) | | | | | | |
| 3 Tools shown; with `databases` | | | | | | |
| 4 Instructions quoted correctly | | | | | | |
| 4 Skill resource or skill reachable | | | | | | |
| 5 B0329+54 blind detection, order right | | | | | | |
| 5 B1133+16 outcome and how reported | | | | | | |
| 5 `search_simbad` M31 | | | | | | |
| 6 Approval prompts seen; deny handled | | | | | | |
| 7 PNG became | | | | | | |
| 7 WAV became | | | | | | |
| 7 Model saw the plot | | | | | | |
| 8 Missing ADS key message | | | | | | |
| Workarounds and other findings | | | | | | |

## Closing the item

When the table is filled, fold the supported OS and app versions into
`../installing.md` and the two installer READMEs, correct anything the runs
contradict, and close the M4 item with this document as its evidence. Every
platform or host that `../installing.md` names but no cell covered (Cursor,
VS Code, Gemini CLI, Claude Desktop on Windows if C-win is not run, and so on)
stays listed there as untested.
