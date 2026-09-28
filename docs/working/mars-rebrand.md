# Renaming Kepler to MARS

**Status:** Proposal, 2026-09-25. Names decided by the maintainer: the
distribution and repository are **`skynet-mars`** (§1). The repository is
renamed (`kepler` → `mars-suite` → `skynet-mars`, all on 2026-09-25), and both
earlier names redirect (§3). All
questions in §6 are decided. The logo files are in `brand/` (§4). Work is on
the feature branch `mars-rebrand` (§5); **R1–R4 are done** (2026-09-27).
**Prerequisites:** The MCP tool-surface track, complete and archived
(`../archive/mcp-tool-surface.md`), and the maintainer's logo files (§4).
**Unblocks:** Every public surface — package, commands, repository, releases,
docs — carrying the new name before a wider release.

This document is architecture and sequencing. It contains no implementation
code.

> [!note] Written against `mcp-support`
> This plan was measured and written on the `mcp-support` branch at
> `b0388e0`, where the MCP tool-surface track is complete. That branch has
> since merged into `dev` (PR #88, `8ec0003`), and the rollout starts from
> the merged state.

---

## 1. The names

**MARS — MCP Astronomy Research Suite.** Decided 2026-09-25.

| Surface | Name | Why this form |
| --- | --- | --- |
| Brand: prose, titles, README, logo | **MARS**; spelled out once per document as *MCP Astronomy Research Suite* | An acronym. The capitals are what separate it from the planet, which matters in an astronomy tool. |
| Distribution (`pyproject.toml` `name`; the future PyPI release) | **`skynet-mars`** | `mars` is taken on PyPI (an unrelated "Agentic TUI"), and Alibaba's `pymars` imports as `mars`, so the distribution needs a qualifier. The qualifier must add something the acronym does not already say, and `skynet-` adds provenance: the algorithms are extracted from the Skynet Robotic Telescope Network. Rejected: `mars-suite` ("…Research Suite suite", briefly chosen and then dropped), `mars-mcp`, `mars-astro` and `mars-research`, which restate the acronym; `mars-sky` and `mars-observatory`, which read as the planet's sky; `mars-ai`, `unc-mars` and `mars-core`, the runners-up. |
| Repository | **`archon774/skynet-mars`**, renamed 2026-09-25 | Matching the distribution gives one name to search and an obvious install URL. |
| Commands | **`mars`** (the console), **`mars-mcp`**, **`mars-bench`** | Lowercase, per convention. |
| MCP server name (`Implementation.name`, the host's `mcpServers` key) | **`mars`** | |
| Agent skill | **`mars-tools`** | |
| Skill resources | **`mars://skill/...`** | |
| Environment variables | **`MARS_*`** | Capitals are the env-var convention anyway. |
| Per-user home | **`~/.local/share/mars`** (macOS `~/Library/Application Support/mars`, Windows `%LOCALAPPDATA%\mars`), or `MARS_HOME` | |

---

## 2. What "Kepler" means in this repository today

Measured on `mcp-support` at `b0388e0`: 1,234 lines in 228 tracked files.

**None of them refers to the Kepler space telescope.** A search for the
mission, the Kepler Input Catalog, K2, Kepler's laws and "Keplerian" finds
only the project's own name. That is what makes a mechanical rename safe — and
why phase R3 adds a guard. A future tool that queries the Kepler mission's
data must be able to say "Kepler" without a rebrand test objecting, and
nothing may rename it by accident.

The occurrences fall into four classes, and each is treated differently:

| Class | Examples | Treatment |
| --- | --- | --- |
| **Interfaces** people type or configure | `kepler`, `kepler-mcp`, `kepler-bench`; 22 `KEPLER_*` variables (`KEPLER_ARTIFACT_DIR` 26×, `KEPLER_OPTICAL_DATA_DIR` 28×, `KEPLER_MODEL_BACKEND` 21×, …); `~/.local/share/kepler`; `kepler://skill/`; the `kepler-tools` skill; server name `"kepler"`; distribution `kepler` | Renamed, with compatibility where a user could already depend on it (§6.3). |
| **Code identifiers** | `KeplerApp` (78×), `KeplerToolModel` (34×), `KeplerBaseModel` (18×), `KeplerHeader`, `KeplerSDSS` | Renamed. They are this project's own names, not upstream symbols. |
| **Prose** | docstrings, comments, README, `docs/`, `CLAUDE.md`, `AGENTS.md`; the project name inside `algorithms/` provenance comments ("In Kepler the …", "PORTED from the Kepler TypeScript extraction") | Renamed. The `# EXTRACTED: was <symbol>` markers keep their `was <symbol>` part exactly: it names an *upstream* symbol, and the markers are the index of what was cut. |
| **Recorded evidence** | `docs/archive/`, `docs/analysis/` (dated), `docs/benchmarking/report.json` and its figures (which record real paths such as `/home/claude/Kepler/artifacts/...`), the vault's history | **Not rewritten.** A record says what was true when it was made. Each gets a one-line dated note at the top where it would confuse a reader. |

Two generated artefacts change by regeneration, not by hand:
`tests/fixtures/llm/schemas/*.json` (`KEPLER_REGEN_SCHEMA_GOLDEN`) and
`skills/mars-tools/` (`python -m tools.skill`).

---

## 3. Things that already exist outside this repository

- **The repository was renamed from `kepler` to `archon774/mars-suite` on
  2026-09-25**, before `skynet-mars` was chosen, and the redirects were
  verified the same day. `github.com/archon774/kepler` redirects to the new
  repository. The `v0.1.0rc1` wheel and the `data` bundle, requested by their
  old `…/kepler/releases/download/…` URLs, both redirect to GitHub's asset
  host and answer a Range request with `206`, so existing installs still
  fetch and resume. **The second rename, to `archon774/skynet-mars`, was done
  the same day and re-verified.** Both `kepler` and `mars-suite` redirect: the
  repository, the `v0.1.0rc1` wheel, and both `data` bundles, each answering
  `206`. That holds **as long as neither `kepler` nor `mars-suite` is ever
  reused**. The checkout's `origin` points at `skynet-mars`.
- **`v0.1.0rc1` is published** under the distribution name `kepler`, and its
  `bundles.json` pins `https://github.com/archon774/kepler/releases/download/data/…`.
  GitHub redirects a renamed repository's URLs — git remotes, pages and
  **release-asset downloads** — to the new name. So that wheel keeps
  installing and keeps fetching its bundles, **as long as no new repository is
  ever created under the old name `kepler`.** Keep that name unused.
- **The `data` release's assets keep their names and bytes.**
  `kepler-optical-0472c67e2f46.tar` and `kepler-isochrones-12f8359efc78.tar`
  are content identifiers, and `docs/releasing.md` says a published name
  always means the same bytes. MARS's manifest points at the same assets under
  the new repository URL. Nothing is re-uploaded, and old and new wheels share
  one set of bundles.
- **Users' machines** may have `~/.local/share/kepler` (artifacts, fetched
  bundles, downloads), `KEPLER_*` in their shell or host configuration, and a
  host entry launching `kepler-mcp`. §6.3 decides how gently to meet them.
- **The shared vault** (`[[Kepler MCP Tool Surface]]` and related notes) and
  the local checkout directory. Renamed last, through their own workflows.

---

## 4. The logo

The only branding in the repository today is the README banner:
`docs/assets/kepler-banner-{light,dark}.svg`, 880×108, swapped by
`prefers-color-scheme`. The rebrand needs:

| Use | Asset |
| --- | --- |
| README banner | Wide wordmark, **SVG, light and dark** (or PNG at 1760×216) |
| MCP server icon (`Implementation.icons`: `src`, `mime_type`, `sizes`, `theme`), shown by hosts beside the server's name | Square mark, **SVG plus PNG 64×64 and 128×128**, light and dark if needed. It must read at 16–32 px. |
| GitHub social preview (repository settings, not committed) | **PNG 1280×640**, under 1 MB |

Master files — SVG or design source — for the wordmark and the mark, with a
transparent background, let every other size be exported rather than redrawn.

### Official Skynet color palette

The MARS assets remain visibly part of Skynet. Use the exact Skynet palette
recorded by the Skynet/UNC proposal template in
`beamer/beamercolorthemeskynet.sty`; do not sample approximate colors from a
raster logo.

| Color | Hex | RGB |
| --- | --- | --- |
| Brand Navy | `#2B3345` | `43, 51, 69` |
| Navy (banner) | `#1F2633` | `31, 38, 51` |
| Deep Night Blue | `#35556E` | `53, 85, 110` |
| Slate Sky Blue | `#5E86A4` | `94, 134, 164` |
| Mist Blue | `#B8D2E1` | `184, 210, 225` |
| Warm Gold | `#D99633` | `217, 150, 51` |
| Soft Apricot | `#EFC48A` | `239, 196, 138` |
| Off White | `#F7F6F2` | `247, 246, 242` |

The template also defines `#353E52`, `#414B60` and `#A9B4C4` as derived
dark-mode interface surfaces. They are not additional Skynet palette colors.
Its UNC-Chapel Hill palette is likewise separate from the Skynet palette.

---

## 5. Rollout

Phases **R1–R6**, committed in order on the one feature branch
`mars-rebrand`, cut from `dev` at `ec5b7e1`. Every phase ends with the
default suite green on Python 3.13, with and without `[mcp]`.

### R1 — Identity: the distribution, commands, server and skill

- `pyproject.toml`: `name = "skynet-mars"`, version **`0.1.0rc3`** (§6.4).
  Scripts `mars`, `mars-mcp` and `mars-bench`, with `kepler`, `kepler-mcp`
  and `kepler-bench` kept as deprecated aliases (§6.3). `uv lock`.
- MCP server name `mars`; resources `mars://skill/...`; skill `mars-tools`
  (source unchanged, rendered copy and `.claude/skills/` link renamed).
- The version comes from package metadata, which changes with the
  distribution name. `_package_version()` reads `skynet-mars`.

**Gate:** a wheel named `skynet_mars-…` installs, and `mars-mcp self-test`
passes on it.

**Done 2026-09-27.** The `skynet_mars-0.1.0rc3` wheel installed into a clean
Python 3.13 environment, `mars-mcp self-test` passed, and each `kepler*`
alias named its successor on stderr and ran it. The aliases live in
`tools/aliases.py`. One departure: the skill source's three `kepler-mcp
fetch-data` mentions became `mars-mcp`, so the skill does not teach a
deprecated command; its prose is otherwise R3's.

### R2 — Environment and paths

- `MARS_*` for every variable, and `MARS_HOME` with the `mars` per-user home.
- Compatibility per §6.3: a `KEPLER_*` value is honoured when its `MARS_*`
  twin is unset, and the server logs a deprecation line naming both.
  A user with `~/.local/share/kepler` and no `mars` home is told, once, what
  to move. Nothing is moved automatically, because a fetched bundle is
  hundreds of megabytes of the user's disk.
- `tests/test_mcp_surface.py`'s roots tests and the `tools.config` tests are
  extended to both names.

**Gate:** an install with only `KEPLER_*` set behaves as it did (per §6.3),
and one with `MARS_*` set ignores `KEPLER_*`.

**Done 2026-09-27.** `tools/compat.py` adopts each `KEPLER_X` into an unset
`MARS_X` right after `.env` loads in every entry point (and silently when
`tools.config` is imported), so every reader knows only `MARS_*`. Each is
reported on stderr, adopted or ignored. The notice about a leftover `kepler`
home repeats at every start until that home is gone or `MARS_HOME` is set,
and says to move its contents, not rename it (review fix: `mars-mcp` creates
the `mars` home at startup, so a rename nested the old home inside it).
`tools.llm.factory` adopts too, because `tools.llm` never imports
`tools.config`. On an installed wheel with only `KEPLER_HOME` set, `mars-mcp
self-test` passed and used that home. Two things kept their names on purpose:
the fetched-bundle marker `.kepler-bundle.json`, an on-disk format a moved
Kepler home still carries, and the three `KEPLER_ISOCHRONE_DIR` messages in
`algorithms/hrdiagram_py/`, which are R3's (the one phase that edits
`algorithms/`).

### R3 — Code identifiers and prose

- Rename `KeplerApp`, `KeplerToolModel`, `KeplerBaseModel`, `KeplerHeader`,
  `KeplerSDSS` and their references, and every prose mention outside the
  records of §2.
- `algorithms/`: the project name in prose only. `# EXTRACTED: was …`
  markers keep their upstream symbol verbatim. No algorithm, constant or
  preserved bug changes. This is the one phase that edits `algorithms/`, and
  its PR says so.
- A **guard test**: no `kepler`, case-insensitive, outside an allowlist. The
  allowlist is the records of §2, the compatibility shims of R2, and a
  documented exemption for the Kepler *mission*, so a future tool can name the
  telescope.

**Gate:** the guard passes, and `git grep -i kepler` returns only allowlisted
paths.

**Done 2026-09-27**, with the guard (`tests/test_rebrand_guard.py`) scoped to
the code trees — `tools`, `tests`, `algorithms`, `benchmarks`, `skills`,
`data`, `.github`, `.claude`, `pyproject.toml`. The documentation is R4's, and
joins the scope there. The guard allows the shims, published names
(`ARCHIVE_PREFIX = "kepler-"`, the two bundle archives, `.kepler-bundle.json`,
`archon774/kepler`) and the mission's forms (`MISSION`), each by content,
never a whole file outside the shims. It also pins §6.2's "no new top-level
package". Decided on the way:

- The classes follow PEP 8's capitalised acronyms, as `SDSSQueryBackend`
  already does: `MARSApp`, `MARSToolModel`, `MARSBaseModel`, `MARSHeader`,
  `MARSSDSS`.
- Textual names a message handler after the app class, and turns `MARSApp`
  into `marsapp`, so the rename silently unhooked the console's four
  `on_kepler_app_*` handlers. They are now bound with `@on(Message)`, which
  no class name can break.
- The bundle builder keeps the `kepler-` archive prefix: a name is part of an
  archive's content-addressed identity, and `--check` compares it.
- All 30 `# EXTRACTED: was …` markers keep their upstream symbols; only the
  "In Kepler the …" prose after them changed.

### R4 — Documentation and the logo

- README (banner, title, the MCP section's install lines), `docs/*.md`,
  `CLAUDE.md`, `AGENTS.md`, `docs/installing.md`, `docs/releasing.md`.
- The logo assets and exact Skynet color palette of §4 committed under
  `docs/assets/`, and the square mark wired into the server's
  `Implementation.icons`.
- A dated one-line note at the top of each record in §2 that names the old
  project, saying it was renamed MARS on the date.

**Gate:** no dead links; the banner renders in both schemes; a host shows the
server's icon (or the PR records which hosts ignore `icons`).

**Done 2026-09-27**, except the last gate item:

- `docs/assets/make_brand.py` exports everything from the masters in
  `brand/`, and reproduces the committed files byte for byte: the README
  banner `docs/assets/mars-banner.png` (1760×360, the mark beside the
  wordmark and tagline lifted from the social preview, on Navy (banner)), the
  mark at 512 px, and the server icons `tools/mcp/icons/mars-{64,128}.png`.
  The banner carries its own plate, so one PNG serves both schemes and the
  light/dark SVG pair is retired.
- The server introduces itself as `mars`, titled *MARS — MCP Astronomy
  Research Suite*, with both icons as `data:` URIs (a stdio server has no URL
  to serve), shipped in the wheel. A test reads them from a real handshake.
  **Not yet seen in a host's UI**; which hosts display `icons` is still to be
  recorded.
- Current documents say MARS and spell it out once; records carry a dated
  note under their titles instead of being rewritten. The guard now covers
  the documentation, with the records, the "Upgrading from Kepler" section of
  `docs/installing.md`, and "Keplerian"/"Kepler's laws" (which
  `docs/working/obs-report.md` uses for orbits) allowed.
- No new dead links. The README's install line names the `v0.1.0rc3`
  `skynet_mars` wheel, which exists once R5 tags it.

### R5 — Repository and release

- ~~**Maintainer action:** rename the repository to `skynet-mars`, and
  confirm that both earlier names redirect.~~ **Done and verified
  2026-09-25** (§3).
- `bundles.json` URLs and every `archon774/kepler` reference move to the new
  repository. The assets stay as they are (§3).
- Tag the first MARS pre-release. The workflow publishes `skynet-mars`.

**Gate:** from a clean container, `pip install "skynet-mars[mcp] @ <release
URL>"`, then `mars-mcp self-test` and `mars-mcp fetch-data optical`.
Separately, `v0.1.0rc1` (`kepler`) still installs and fetches through the
redirect.

### R6 — Outside the repository

- The shared vault: rename `[[Kepler MCP Tool Surface]]` and related notes
  through the vault's own transaction workflow, keeping an alias for the old
  name.
- Optionally, the local checkout directory. It is named in this machine's
  agent memory paths and the vault, so change it deliberately or not at all.
  **Done 2026-09-27**, at the maintainer's direction: `/home/claude/Kepler`
  is now `/home/claude/mars`, and `.venv` was rebuilt (its scripts carry
  absolute paths). Its agent-memory directory was empty. Records that quote
  the old path keep it, as records do. The vault still names the old path,
  and is the rest of R6.

---

## 6. Decisions

All decided by the maintainer on 2026-09-25.

1. **Distribution and repository: `skynet-mars`.** `mars-suite` was chosen
   first, and the repository renamed to it, but it restates the acronym
   ("…Research Suite suite"). `skynet-mars` replaced it the same day, and the
   repository was renamed to it (§3).
2. **The import namespace moves later, in its own track.** `tools` and
   `algorithms` stay top-level packages through this rebrand. They are
   generic enough that another installed project's `tools` package collides
   with them, and moving them under one namespace (`mars.tools`,
   `mars.algorithms`) is the durable fix. But it touches every import, test and
   extraction marker, and it stays reviewable only as a change of its own.
   R3's guard therefore permits no new top-level package.
3. **Kepler names become deprecated aliases for one pre-release** (R2):
   - `KEPLER_*` is honoured when its `MARS_*` twin is unset, and the server
     logs a deprecation line naming both;
   - the `kepler`, `kepler-mcp` and `kepler-bench` commands remain, as aliases
     that print the new name;
   - a leftover `~/.local/share/kepler` with no MARS home is pointed out once
     and never moved.

   All of it is removed in the release after `0.1.0rc3`. Only the
   compatibility shims are allowlisted by R3's guard, and each carries its
   removal version.
4. **The first MARS version is `0.1.0rc3`**, continuing the series: the next
   candidate of the same software, under its new name. Testers compare it
   directly with `0.1.0rc2`. *(Corrected 2026-09-26: this said `0.1.0rc2`,
   which the MCP track took when it landed on `dev` after three review
   rounds, still as Kepler.)* On PyPI, `skynet-mars` and `kepler` are different
   projects, so nothing clashes.
