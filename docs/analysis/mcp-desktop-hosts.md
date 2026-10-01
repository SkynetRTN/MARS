# MARS in the Desktop Apps: Claude Desktop and the ChatGPT Desktop App

**Status:** dated proposal from PR #97, 2026-10-01. Only D2 has started.
Scheduling and acceptance now live in the single
[master continuation plan](../working/master-continuation-plan.md#9-desktop-host-rollout-d0d4).
This snapshot preserves the rationale, host claims and vendor sources for
rechecking, not a competing execution plan. D2 has since been built, in
`installers/claude-desktop/`; its D2 results are below, and its open gate is
tracked in the master plan. **Browser support is parked**
at the maintainer's direction (§6).

**Prerequisites:** the MCP tool surface (archived 2026-09-25) and the per-host
setup in [`../installing.md`](../installing.md). Nothing under `algorithms/`,
`tools/agent/`, `tools/llm/` or `tools/registry.py` changes.

**Unblocks:** a researcher who does not use a terminal-based coding agent can
use MARS from the Claude or ChatGPT desktop app, with an install that does not
require editing JSON or finding a virtual environment's path.

Host facts below were checked against vendor documentation on 2026-10-01
(sources in §7). They change often. D0 re-checks them.

---

## 1. The problem

Both desktop apps can already run `mars-mcp`, because both launch **local stdio
servers**. That is the deployment shape the archived track chose
([`../archive/mcp-tool-surface.md`](../archive/mcp-tool-surface.md) §3.3), so
this track needs no new transport, no network authentication, and no
reversal of a recorded decision.

| App | How it runs `mars-mcp` | Configured by |
| --- | --- | --- |
| **Claude Desktop** (macOS, Windows; no Linux build) | Local `mcpServers` entry, or a `.mcpb` desktop extension | `claude_desktop_config.json`, or installing an extension |
| **ChatGPT desktop app**, in its Codex threads | Local stdio server, shared with the Codex CLI and IDE extension | `~/.codex/config.toml` (or a trusted project's `.codex/config.toml`), or Settings → MCP servers → Add server |

What stands between a non-terminal user and a working install is **friction**,
not capability:

1. **Python 3.13 and a virtual environment.** `pip install "skynet-mars[mcp]"`
   pulls about 640 MB of dependencies. On anything but Python 3.13 on x86_64
   Linux, macOS or Windows, it also needs a C compiler (`../installing.md`).
2. **An absolute path.** Neither app inherits the shell's `PATH`, so the config
   must name `mars-env/bin/mars-mcp` exactly.
3. **Environment.** Claude Desktop does not inherit the shell's variables, and an
   installed MARS reads no `.env`. `ADS_DEV_KEY` must go in the host's config, or
   in `~/.ads/dev_key`.
4. **Timeouts.** Codex defaults to a 10 s startup wait and a 60 s per-call
   limit. A first launch (bytecode and numba compilation; `import
   tools.registry` is about 4.5 s cold) and a plate solve (about 285 s all-sky)
   both outlast them.
5. **The data bundles.** `mars-mcp fetch-data optical` is a terminal command.

Items 2–4 are documentation, and PR #97 covers them for both apps. Item 1 is
the real barrier, and §3 is about it.

## 2. What both apps share, and where they differ

The server is unchanged for both apps: same tools, schemas, validation, groups,
annotations, media and skill resources. These parts are **unverified per app**
and are measured in D0, not assumed:

- whether the app passes the server's `instructions` (the skill brief plus
  install facts) to the model;
- whether the model can read `mars://skill/...` resources;
- what happens to inline audio. In Claude Code, audio is saved to a file and
  the model cannot hear it (archive C4). Images are seen.

The ChatGPT desktop app runs MCP servers for **Codex** threads. Per OpenAI's
documentation, ordinary ChatGPT chats are not the MCP host here; that
reading is inferred from "for the same Codex host" and is checked in D0.

## 3. A one-click install for Claude Desktop: the `.mcpb` extension

A desktop extension is a zip of a `manifest.json` plus the server, installed by
double-click or Settings → Extensions. The MCPB manifest (version 0.4) adds a
**`uv` server type**: the extension carries a `pyproject.toml` and an entry
point. The **host** creates the environment with `uv` and installs the
dependencies, "no user Python installation required", across Windows and
macOS, Intel and ARM, including compiled dependencies.

That fits MARS closely:

- **The extension is small.** It does not need to bundle `numba`, `scipy` or
  `astropy` per platform, which is what made a `python`-type extension
  expensive. Its `pyproject.toml` depends on an exact `skynet-mars[mcp]`
  release, and its entry point calls `tools.mcp.__main__:main`.
- **Python 3.13 is pinned** through `requires-python`, so `uv` fetches a
  managed 3.13. That also removes the C-compiler case on macOS and Windows,
  since `sep` and `photutils` ship 3.13 wheels there.
- **Secrets get a real UI.** `user_config` with `sensitive: true` collects
  `ADS_DEV_KEY` in the app's settings, stored securely and passed as `env`.
  Optional settings map the same way: `--tools` groups, `MARS_HOME`, and
  `ANET_INDEX_PATH`.

Open questions that decide whether this is worth building, each answered in
D2's spike:

- **Does Claude Desktop support manifest 0.4's `uv` type**, on both macOS and
  Windows? The spec defines it; host support was not confirmed on 2026-10-01.
- **First-launch time.** The host installs about 640 MB of dependencies on the
  first launch. Does the app wait, retry, or mark the server failed?
- **The data bundles.** Without a terminal, `fetch-data` needs another route:
  the extension's documentation (`uvx --from skynet-mars mars-mcp
  fetch-data`), or a dedicated tool. A tool would be a registry change, with
  its classification in `tools/bench/plane.py` in the same commit
  (`CLAUDE.md`). The cheaper answer is preferred unless D0 shows users
  stranded.
- **Releasing.** The `.mcpb` becomes a release asset beside the wheel. Its
  pinned version must equal the tag, and that check belongs in
  `release.yml`'s build job. The Claude connectors directory no longer accepts
  `.mcpb` submissions, so distribution is GitHub releases only.

If Claude Desktop does not support the `uv` type, the fallback is **not** a
bundled `python`-type extension (about 640 MB per platform). Instead, item 1 is
answered by documentation alone, with `uv`: `uv tool install
"skynet-mars[mcp]" --python 3.13` installs `mars-mcp` with a managed Python
and puts it at a stable path.

## 4. Writing the config for the user

The remaining friction for both apps is "edit a file and paste an absolute
path". A small command could do that, for example
`mars-mcp register claude-desktop|codex`. It would:

- write the entry with the running interpreter's own `mars-mcp` path;
- preserve every other entry;
- refuse to overwrite a different `mars` entry without `--force`;
- print what it wrote and the file.

Codex already has `codex mcp add`, so this pays mainly for Claude Desktop.
It is **optional**: D1 decides whether the `.mcpb` makes it unnecessary.

Any such command writes outside the MARS home, into another application's
configuration. It must parse and re-serialise the existing file, never
template it, and a test must show an unrelated entry surviving.

## 5. Rollout

Each phase is one PR. No phase begins before the one before it has landed.

### Phase D0: Verify both apps by hand

- Install from PyPI and register `mars-mcp` in Claude Desktop (macOS, and
  Windows if available) and in the ChatGPT desktop app's Codex, exactly as
  `../installing.md` says.
- In each, run the five-step pulsar detection that `mars-mcp self-test`
  checks, on B0329+54 and on B1133+16, and one live `search_simbad`.
- Record, for each app: whether instructions and skill resources reach the
  model, what inline images and audio become, and the cold-start time against
  the host's startup limit.
- Correct `../installing.md` wherever reality differs.
- **Exit:** findings recorded here; both apps complete the pulsar detection
  with correct period provenance.

### Phase D1: Documentation from D0

- Fold D0's findings into `../installing.md`, including the ChatGPT app's
  Settings → MCP servers route and any per-app caveat.
- Document the `uv tool install` route as the simplest manual install.
- **Exit:** a reader with only the docs reproduces D0.

### Phase D2: The `.mcpb` spike: built, awaiting a real install

- A `uv`-type extension against a published `skynet-mars` release.
- Answer §3's four questions on macOS and Windows.
- **Exit:** a build/no-build decision recorded here, with measurements.

Done on 2026-10-01. The extension was not thrown away: it is
`installers/claude-desktop/` (README there), pinned to `0.1.0rc4`, with
`tests/test_claude_desktop_extension.py`. What was verified, on Linux
aarch64, where Claude Desktop does not run:

- `mcpb` 2.1.2 validates the manifest and packs a 75 kB `.mcpb`. Its icon
  warning, which recommends 512×512, is met by exporting the mark from
  `docs/assets/make_brand.py`.
- **Cold first launch, as the host runs it.** The manifest's own `uv run
  --locked` was run in the unpacked `.mcpb` with an empty uv cache, only
  uv-managed Pythons (`UV_PYTHON_PREFERENCE=only-managed`), and `env -i`. It
  downloaded CPython 3.13.14, installed 89 packages, and passed `mars-mcp
  self-test` in **42 s**: blind detection of B0329+54 at 204σ, the skill
  resources served, and sonification returned as audio. That time is this
  host's network; a slower link scales the download, about 640 MB. (A first
  measurement of 38 s let uv reuse the system's Python 3.13; code review
  caught it.)
- **No Anthropic API key.** The same run had no `ANTHROPIC_API_KEY`, no
  `.env` and an empty home directory. The model is the logged-in Desktop
  session's; MARS serves tools only. The `anthropic` SDK is installed, because
  `skynet-mars` depends on it for the `mars` console, but the server process
  never imports it, `tools.agent` or `tools.llm` (checked in-process).
- **Unfilled settings.** Whether Desktop passes an empty optional field as
  `""` or as the unexpanded `${user_config...}` is not documented. The
  unexpanded form stopped bare `mars-mcp` at startup ("unknown tool
  group(s)"). An empty `ADS_DEV_KEY` would hide `~/.ads/dev_key`. So
  `src/server.py` removes both forms first. Driven through the exact
  manifest command, both forms serve 55 tools, `databases` serves 16, and a
  token is reported set.

§3's questions, answered so far:

- **`uv` type in Claude Desktop:** the MCPB repository's `hello-world-uv`
  example says Claude Desktop manages Python and the dependencies.
  Unconfirmed on a real install.
- **First launch:** 42 s here, Python download included. Whether Desktop's startup wait tolerates a slow
  first install is unconfirmed.
- **Data bundles:** unchanged. `uvx --python 3.13 --from "skynet-mars[mcp]==<version>"
  mars-mcp fetch-data optical` (verified with `--list`) is the documented route
  until D0 says otherwise. It must run with the extension's `MARS_HOME`, if one
  was set.
- **Releasing:** the pin trails a release (`installers/claude-desktop/README.md`,
  "After each release"); the `release.yml` step is D3.

**Remaining gate:** install the `.mcpb` in Claude Desktop on macOS (and
Windows if available), then run the pulsar detection. Record the first-launch
time and what the settings dialog passes for an empty field.

### Phase D3: The extension, released (only if D2 says build)

- Manifest source in the repository, built by `release.yml`, with a version
  check against the tag and the `.mcpb` attached to the GitHub release.
- `user_config` for `ADS_DEV_KEY` (sensitive), the tool groups and `MARS_HOME`.
- The release verify job installs and inspects the built `.mcpb` (manifest
  valid, version pinned); a real Desktop install stays a manual gate.
- **Exit:** a fresh macOS user installs by double-click and completes the
  pulsar detection.

### Phase D4: Documentation outcome and archive

- Fold the outcome into `../installing.md`, `../tool-architecture.md` §10.3
  and `CLAUDE.md`'s `tools/mcp/` rules.
- Close D0–D4 in the [master plan](../working/master-continuation-plan.md#9-desktop-host-rollout-d0d4)
  with evidence and fold durable outcomes into reference docs. This proposal
  remains dated evidence, not an active track to archive separately.

## 6. Parked: browser hosts (ChatGPT web, claude.ai)

Parked 2026-10-01 at the maintainer's direction. This section records why, so
the question is not re-researched from scratch.

**Why a browser cannot use a local server.** In ChatGPT and claude.ai the model
runs in the vendor's cloud, and the MCP calls come **from the vendor's
servers**. That includes Claude Desktop's *custom connectors*, as opposed to
its local `mcpServers`. A connector is a URL those servers fetch, so a
server on `localhost` is unreachable, and a web page cannot start a local
process anyway.

**What browser support would take.** Serve the same `Server` over Streamable
HTTP. The `mcp` 2.2 extra already brings `StreamableHTTPSessionManager`,
Starlette and uvicorn, so it needs no new dependency. Put it at a public HTTPS
endpoint with OAuth, change the result contract, and reopen archive §3.3.
The result contract fails in both directions for a remote caller:

- 36 of 55 tools return a local artifact path;
- 20 of 55 take a filesystem path argument.

Other constraints:

- claude.ai connector calls time out at 240 s, against about 285 s for an
  all-sky solve.
- Results are capped near 150,000 characters.
- Annotations become approval policy: ChatGPT treats any tool without
  `readOnlyHint` as a write.

**The conclusion that parked it.** A *personal* deployment (your own machine,
a tunnel and OAuth) serves almost nobody. Anyone able to run it can use a
desktop app with far less effort. The only shape that reaches new users
(students, mobile, browser-only ChatGPT) is a **hosted service run by Skynet**.
That is the archived track's deleted shape (b), with every cost it was deleted
for:

- per-user isolation and sign-in;
- cost ceilings a client cannot raise;
- operator-held keys;
- compute capacity;
- no way to upload user files.

Reopen it only as that service, and only when a classroom or similar audience
needs it.

## 7. Sources, checked 2026-10-01

- Codex MCP (ChatGPT desktop app, CLI, IDE extension share the config):
  <https://learn.chatgpt.com/docs/extend/mcp> (redirected from
  <https://developers.openai.com/codex/mcp>)
- MCPB manifest, including the `uv` server type (v0.4):
  <https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md>
- Claude desktop extensions: <https://claude.com/docs/connectors/building/mcpb>
- Connecting local servers to Claude Desktop:
  <https://modelcontextprotocol.io/docs/develop/connect-local-servers>
- Parked browser research: OpenAI developer mode
  <https://developers.openai.com/api/docs/guides/developer-mode>; Claude
  custom connectors <https://claude.com/docs/connectors/custom/remote-mcp> and
  <https://claude.com/docs/connectors/building>; Anthropic IP ranges
  <https://platform.claude.com/docs/en/api/ip-addresses>
