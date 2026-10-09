# MARS Tool Collection Architecture

Date: 2026-08-10
Status: active architecture

MARS (MCP Astronomy Research Suite) is an astronomy tool collection for Python callers, scripts, notebooks,
agents, and future CLI/application surfaces. It is not an orchestration
framework. The public tool layer should expose small, ordinary Python functions
that prepare inputs, call the extracted algorithms, and return compact typed
results or local artifact paths.

The working design rule is:

> Astropy-native inside, JSON-and-artifact-native outside.

Algorithm packages can use Astropy, NumPy, SciPy, Pydantic, FITS/WCS objects,
tables, local solver data, and astronomy-specific containers. Public tools
should summarize those objects into small Pydantic models, warnings/errors, and
artifacts with enough metadata to reproduce the operation.

---

## 1. Current Repository Shape

```text
tools/
  __init__.py
  astrometry.py       # WCS/header summary tools
  calibration.py      # zero-point tools
  catalogs.py         # catalog declarations and band helpers
  simbad.py           # SIMBAD object, measurement, and bibliography tools
  ned.py              # NED historical table tools
  vizier.py           # broad VizieR catalog search tools
  atnf.py             # ATNF pulsar catalog tools
  pulsar.py           # pulsar pipeline: scan resolution, light curve, periodogram, fold, sonify, plot
  photometry.py       # local aperture photometry over the bundled FITS library
  hr_diagram.py       # FITS-to-HR-diagram pipeline orchestration (plus a catalog-only entry point)
  radio_sources.py    # radio FITS -> catalog-identified sources -> labeled SED plot
  ads.py              # ADS literature search/review tools
  mast.py             # MAST archive/product tools
  mpc.py              # Minor Planet Center observation tools
  casda.py            # CASDA archive tools
  resolve.py          # SIMBAD-backed target resolution
  registry.py         # optional agent/tool schema registry
  sessions.py         # per-run session manifest recording + the loop's cache-key helper
  agent/              # headless agent loop: run_session, events, the moved SYSTEM_PROMPT
  llm/                # provider-neutral model port -- see section 10
  tui/                # the `mars` console over the loop -- see section 10.2
  bench/              # model benchmark harness -- see section 10.1
  workspace.py        # local artifact helpers
  models.py           # shared result, warning/error, WCS, catalog, artifact models
  config.py           # small environment-backed settings helpers
  artifacts.py        # local artifact path and file metadata helpers

algorithms/
  __init__.py
  wcs/                  # Python WCS algorithms
  photometry/           # Python source extraction and aperture photometry
  fieldcal/             # Python zero-point field calibration
  skylib_lite/          # shared vendored Skylib subset
  catalogs/             # Python catalog/provider declarations, no network calls
  query/                # Python remote catalog access
  hrdiagram_py/         # Python HR-diagram pipeline: parity port + optimizer, not an extraction
  radio/                # Python radio spectral-index fitting + catalog cross-matching, new capability

  pulsar/               # Python pulsar pipeline: ingest, periodogram, folding,
                        #   sonification (a PORT, not an extraction)
  variable_star/        # Python variable-star light curve, periodogram, folding
docs/
```

The Python distribution discovers the `tools*` and `algorithms*` packages;
package data such as
`ngc2000.dat` belongs to the corresponding `algorithms.skylib_lite.*` package path.

---

## 2. Public Tool Layer

**One public tool call is MARS's execution boundary.** No run, stage, session,
or batch object spans two calls; no tool writes state another tool reads. A
caller that needs a value from an earlier step passes it in, or passes the
artifact path the earlier call returned. The processing-run architecture that
used to carry that state was removed by the stateless rollout (S0–S6), along
with `algorithms/fieldcal/deps.py` — cross-domain values are explicit function
arguments now, not injected module-level names.

Tools are the public surface. They should stay thin:

- accept normal Python values, file paths, or small Pydantic models;
- normalize and validate inputs locally;
- call an existing algorithm package rather than reimplementing astronomy math;
- return compact summaries, warnings/errors, and artifact metadata;
- write large arrays, tables, generated FITS files, and plots to disk instead
  of embedding them in inline results.

The first local, no-network tools are:

- `tools.optical.list_optical_frames(directory=None, image_filter=None)` /
  `tools.optical.resolve_optical_frame(name, directory=None)` -- Stage 0 for
  image work. Searches the primary optical root *and* the archive download
  root, so a product fetched by `tools.mast`/`tools.casda` resolves by name
  through the same registry every image tool already takes a path from.
  Both bounds on that search are operator settings rather than tool
  parameters: the download root is walked recursively only while it resolves
  inside `MARS_DATA_DIR` (outside it, searched flat with a
  `download_root_outside_data_dir` warning), and `MARS_MAX_FRAMES`
  (default 200) caps how many frames one listing reads headers for from each
  root, with a `listing_truncated` warning naming the total when it bites.
  `search_mast(download=true)` reports the directories products landed in, so
  `directory=` can reach a specific product past the cap.
- `tools.astrometry.describe_image_wcs(path)`
- `tools.catalogs.list_photometric_catalogs()`
- `tools.catalogs.resolve_reference_band(catalog, image_filter)`
- `tools.calibration.solve_zeropoint_from_measurements(measurements, catalog_sources)`
- `tools.photometry.calibrate_zeropoint(path, catalog_sources=None, catalog_fixture=None, catalogs=None, compare_to=None)`
  -- extraction -> photometry -> catalog match -> reference magnitude ->
  `calc_solution`. Local only when `catalog_sources` is injected or
  `catalog_fixture` names a recorded input (`"selected_rows"`, the matched
  APASS rows; `"full_response"`, the recorded response for the whole field
  plus its VSX filter); without either the calibration-input helper queries
  a reference catalog over the network.
- `tools.fieldcal_reference.list_zeropoint_references()` /
  `load_zeropoint_reference(field)` / `compare_zeropoint_to_reference(...)` /
  `replay_field_calibration(field)` -- the four recorded Skynet zero-point
  solves, the offline replay inputs (`replay_catalog_sources`,
  `replay_variable_sources`) that drive a real solve against them, and the
  end-to-end selection replay that re-chooses NGC 5128 B's 35 calibration
  stars from the recorded 132-row APASS cone (45 candidates once clipped to
  the frame, as the live query path clips) and reproduces the recorded
  solve bit for bit.
- `tools.pulsar.list_pulsar_scans(...)` / `tools.pulsar.resolve_pulsar_scan(...)`
- `tools.pulsar.load_pulsar_lightcurve(path, ...)`
- `tools.pulsar.compute_pulsar_periodogram(path, ...)`
- `tools.pulsar.fold_pulsar_lightcurve(path, period_s, ...)`
- `tools.pulsar.sonify_pulsar(path, period_s=None, ...)`
- `tools.pulsar.plot_pulsar(...)`
- `tools.photometry.list_photometry_targets()`
- `tools.photometry.run_photometry_on_target(target, ...)`
- `tools.workspace.list_artifacts(directory=None)`
- `tools.workspace.describe_artifact(path)`

The split remote database/archive tools follow the same boundary: bounded
inline previews, complete result artifacts, provider warnings/errors, and no
live calls in default validation:

- `tools.resolve.resolve_target(name)`
- `tools.simbad.search_simbad(name)`
- `tools.simbad.search_simbad_measurements(name, table="flux")`
- `tools.simbad.search_simbad_bibliography(name)`
- `tools.ned.search_ned(name, table="photometry")`
- `tools.vizier.list_vizier_catalogs(keywords)`
- `tools.vizier.search_vizier(...)`
- `tools.atnf.search_atnf(name)`
- `tools.ads.search_ads(...)`
- `tools.ads.build_literature_review(...)`
- `tools.mast.search_mast(name, ...)`
- `tools.mpc.search_mpc(designation)`
- `tools.casda.search_casda(...)`

`tools.hr_diagram` composes several of the above (`tools.vizier.search_vizier`
for both Gaia DR3 and cluster-literature lookups) with the pure
`algorithms.hrdiagram_py` package rather than adding a new query layer:

- `tools.hr_diagram.extract_photometry_from_fits(fits_path)`
- `tools.hr_diagram.crossmatch_gaia(csv_path, ...)`
- `tools.hr_diagram.crossmatch_gaia_by_position(cluster_name, ...)` -- no FITS frame; fetches
  Gaia DR3 directly around the cluster's own resolved position
- `tools.hr_diagram.get_literature_cluster_params(cluster_name)`
- `tools.hr_diagram.select_cluster_members(csv_path, cluster_name, ...)`
- `tools.hr_diagram.fit_and_compare_hr_diagram(members_csv_path, cluster_name, ...)`
- `tools.hr_diagram.run_full_hr_pipeline(fits_path, cluster_name, ...)`
- `tools.hr_diagram.run_full_hr_pipeline_from_catalog(cluster_name, ...)` -- the
  `run_full_hr_pipeline` composite with `extract_photometry_from_fits` +
  `crossmatch_gaia` swapped for `crossmatch_gaia_by_position`, so a plain "HR
  diagram for cluster X" request needs no FITS file at all

`tools.photometry` is a thin wrapper reusing `tools.claude_photometry_haiku_tool`'s
already-tested pipeline directly (not a reimplementation), so a tool-use call
produces exactly what the standalone CLI script produces. It intentionally
does not share extraction settings with `tools.hr_diagram.extract_photometry_from_fits`:
the two need different things from `algorithms.photometry` (a calibrated
zero point and fixed apertures here; cheap "auto" Kron-like apertures and no
zero point there, since the HR-diagram pipeline discards the frame's own
magnitude once Gaia's is fetched). `run_photometry_on_target(...,
write_source_table=True)` writes a CSV in the `ra_deg`/`dec_deg` column shape
`tools.hr_diagram.crossmatch_gaia` expects, as the one deliberate bridge
between the two.

`tools.radio_sources` composes `algorithms.photometry` (source extraction, its
own settings again -- neither a Gaia handoff nor an optical zero point apply
to a radio map), `algorithms.radio` (spectral fitting, catalog cross-match),
`tools.vizier.search_vizier(category="radio")`, and `tools.ned.search_ned`:

- `tools.radio_sources.plot_field_sed(fits_path, ...)` -- the main entry point:
  identify sources in a radio FITS frame against VizieR's radio catalogs, then
  plot every identified source's spectral energy distribution (from NED)
  together on one labeled plot, each with its own fitted spectral index.
- `tools.radio_sources.identify_radio_sources(fits_path, ...)` -- the spatial
  half alone: detected sources cross-matched against radio catalogs by
  position, with no plot.
- `tools.radio_sources.analyze_source_spectrum(name=..., csv_path=..., frequencies_hz=..., fluxes_jy=...)`
  -- the spectral half alone, for one already-identified/named source.

`tools.wcs.solve_astrometry(path, *, index_path=None, write_header=False,
timeout_s=None, force=False, search_radius_deg=None, min_scale_arcsec=None,
max_scale_arcsec=None)` wraps the extracted plate solver with its required
per-call backend configuration, structured unavailable and no-solution outcomes,
attempted-backend reporting, and guarded FITS-header persistence. A single tool
call is MARS's execution boundary: no run or stage state is retained between
calls.

Omitted attempt timeouts use 300 seconds unless that backend's environment
setting overrides it; explicit values are finite 1–900 seconds. Astrometry.net
adds a 30-second outer wall-clock grace and terminates its owned POSIX process
group, including children surviving the leader. ATLAS bounds only the blind
matcher loop. Extraction, catalog loading, oriented matching and fresh retry
allowances mean this is **not** a total-call deadline or general cancellation
contract (WCS-21/MCP-01).

The three search bounds are opt-in (P6). Unset, the solve is the extracted
all-sky search over 0.1–60 arcsec/px; set, they are validated at the tool
boundary (`invalid_search_bounds`), reach the algorithm as one
`algorithms.wcs.config.WcsSearchBounds`, and the result's `search` reports the
radius, scale window, and pointing centre astrometry.net was asked to search,
with `explicit` naming which bounds the caller set and, when the ATLAS
backend ran, the narrower window it was given (`atlas_*`; ATLAS takes no
radius). A radius below 180
is centred on the frame's own pointing hint; a frame that yields none gets
`search_radius_without_hint`, not a silent all-sky search. On the development
host, against its 4200-series indexes, the M15 fixture solves in ~14 s at
`search_radius_deg=1, min_scale_arcsec=0.4, max_scale_arcsec=0.8` and in
~285 s all-sky, to the same solution.

Next Python tools should follow the same pattern before adding new layers:

- `extract_sources(path, settings=None)`
- `measure_photometry(path, sources, settings=None)`
- `search_catalog(catalog, region, limit=50)`
- `search_catalogs_for_image(path, limit=50)`

`calibrate_zeropoint` and `solve_astrometry` were on this list and have since
landed; both are above.

---

## 3. Algorithm Packages

The algorithm packages are the source of truth for scientific behavior. Tool
and architecture work should not silently change numerical behavior or fix
algorithm bugs. Structural moves such as `algorithms.skylib_lite` must be mechanical
import/package rewiring. Bug fixes belong in focused remediation PRs with the
smallest targeted tests that prove the affected behavior.

Current algorithm ownership:

| Package | Owns | Notes |
| --- | --- | --- |
| `algorithms.wcs` | FITS-header WCS construction, astrometry.net solving, ATLAS solving, WCS validation, FITS header write-back | Requires solver binaries/indexes or local UCAC data for end-to-end solving. |
| `algorithms.photometry` | Source extraction and aperture photometry | Uses `algorithms.skylib_lite` extraction, calibration, photometry, and utility code. |
| `algorithms.fieldcal` | Catalog-source matching, reference-magnitude resolution, zero-point solving | Uses dependency seams for photometry/WCS and defaults catalog queries to `algorithms.query`. |
| `algorithms.catalogs` | Catalog/provider declarations, band tables, filter mappings, SIMBAD vocabulary, ADS field metadata, NED table names, ATNF parameter vocabulary | Declaration only; importing it should not perform network work. |
| `algorithms.query` | VizieR, SDSS, SIMBAD, cache policy, WCS-footprint query orchestration | Owns remote catalog calls; live calls stay out of default checks. |
| `algorithms.hrdiagram_py` | Star-cluster CMD/HR-diagram fitting: CM<->HR transform, extinction, local isochrone loading, distance/E(B-V)/age optimizer, field-star removal, geometric matching | A parity **port** of Astromancer's TypeScript plus a new optimizer, not a byte-preserving extraction. The historical `_py` suffix avoids a disruptive package rename after the TypeScript extraction was retired. Gaia/VizieR fetching lives in `tools.hr_diagram` via `tools.vizier.search_vizier`; `isochrones.py` fits exact operator-installed Girardi tracks without downloads. Its application-config dependency is tracked as ARC-04 in the master continuation plan. |
| `algorithms.radio` | Radio spectral-index/log-parabola fitting (`spectral_fitting.py`) and generic RA/Dec-column-guessing catalog cross-match (`matching.py`) | New first-party capability, no upstream Skynet/Astromancer equivalent. Performs no network I/O -- VizieR/NED fetching lives in `tools.radio_sources`. |
| `algorithms.pulsar` | Pulsar file ingest, background subtraction, Lomb-Scargle periodogram, phase folding/binning, and audio synthesis | An Astromancer Python **port**, marked `# PORTED:`. Stage order is a dependency chain — see `docs/pulsar-tool-pipeline.md`. |
| `algorithms.variable_star` | Variable-star source ingestion, differential light curves, error-weighted Lomb-Scargle periodograms, and phase folding | Exact-parity Python port of the Astromancer algorithms. |

---

## 4. Shared Models And Artifacts

Keep shared Python models small until a tool needs more:

- warning/error records;
- file and artifact metadata;
- agent session manifests;
- table summaries;
- WCS summaries;
- catalog summaries;
- reference-band and zero-point results.

Future result envelopes can grow toward a richer `ToolResult` shape when
retrieval, provenance, pagination, and remote provider warnings require it:

```python
class ToolResult(BaseModel):
    status: Literal["ok", "partial", "not_found", "error"]
    data: dict | list[dict] | None
    warnings: list[ToolWarning]
    errors: list[ToolError]
    artifacts: list[Artifact]
    provenance: list[Source]
    query: QueryTrace | None
    pagination: Pagination | None
```

Important modeling rules:

- Coordinates serialize as decimal degrees plus frame.
- Quantities serialize with value, unit, and uncertainty when known.
- Times serialize as ISO strings plus scale where known.
- Tables expose column metadata rather than dumping huge payloads.
- Measurements preserve uncertainty, method, calibration assumptions, and source.
- Artifacts include local path, MIME type, size, created time, and producing tool.
- Agent-loop artifacts are session-scoped under
  `artifacts/sessions/<session_id>/...`; the engine writes
  `session_manifest.json` in that directory with the ordered tool-call trace,
  cache hits, warning/error summaries, and artifact paths. To resume safely,
  current manifests also retain the complete neutral conversation, including
  prompts and tool arguments/results; the diagnostic trace itself still omits
  full result payloads. These are local, sensitive session records: on POSIX,
  each session directory is owner-only (`0700`) and its manifest is `0600`.
  Resume accepts at most a 1 MiB manifest and a 256 KiB history (128 messages,
  256 blocks, 64 KiB per field); content is not redacted because the provider
  protocol needs the exact prior exchange. Remove the session artifact
  directory when that retention is no longer appropriate.

---

## 5. Extracted Skylib Inventory

Several Python algorithms originally vendored overlapping pieces of Skynet's
`skylib`. They are consolidated into `algorithms.skylib_lite` so every extracted
Skylib call uses one local implementation without depending on an external
`skylib` installation.

Originally extracted package-local skylib subsets:

| Algorithm extraction | Extracted skylib subset |
| --- | --- |
| WCS | `astrometry/` including `anet/`, `atlas/`, solver types, and `ngc2000.dat`; `calibration/background.py`; `extraction/main.py`; `extraction/centroiding.py`; `io/fits_compression.py`; `util/angle.py`; `util/fits.py`. |
| Photometry | `calibration/background.py`; `extraction/main.py`; `extraction/centroiding.py`; `photometry/aperture.py`; `photometry/aperture_numba.py`; `photometry/exposure.py`; `util/angle.py`; `util/fits.py`; `util/overlap.py`; `util/stats.py`. |
| Field calibration | `util/angle.py`; `util/fits.py`; `util/stats.py`. |

Consolidation target:

```text
algorithms/skylib_lite/
  __init__.py
  astrometry/
  calibration/
  extraction/
  io/
  photometry/
  util/
```

Consolidation rules:

- Move extracted files mechanically and update imports to
  `algorithms.skylib_lite.*`.
- Preserve numerical code, constants, comments, and data files.
- Remove package-local `skylib` copies only after every import path is updated.
- Do not combine this with algorithm bug fixes or helper rewrites.

---

## 6. Future Services

Services are internal building blocks, not public API commitments. Add them only
when multiple tools need the same careful behavior.

Likely service areas:

- target resolution;
- catalog search and row normalization;
- archive discovery and product fetching;
- local FITS/table/product inspection;
- image, photometry, time-series, and spectrum workflows;
- plot and artifact creation;
- table normalization, joins, and crossmatch;
- ADS/literature search and citation metadata;
- provenance, cache, and limits.

Do not turn every dependency into an architecture layer. `astropy`, `astroquery`,
`pyvo`, `photutils`, `ads`, `numpy`, `scipy`, and related packages are
implementation dependencies selected by tool capability. Higher-order scientific
dependencies are allowed when the tool or algorithm needs them; the architecture
should bound public inputs and outputs, not remove valid science dependencies.

---

## 7. Runtime Policy

Configuration should come from environment variables, optional config files, and
direct constructor/function arguments. Keep settings explicit and small at the
tool boundary.

Runtime behavior should be bounded:

- conservative defaults for row counts, radius, byte size, and timeouts;
- no live remote calls in default validation;
- partial results when one provider in a multi-provider tool fails;
- credentials redacted from logs and outputs;
- recursive local file scans avoided by default;
- large payloads returned as artifacts plus summaries.
- `tools.agent` persists a session manifest when a session starts, after each
  tool call, and at terminal states (`end_turn`, `max_turns`, `interrupted`, or
  an exception), so another caller can inspect the exact session context
  without re-running remote queries. The console resumes a session from one.

Serving is optional. A Python caller must be able to import and call every tool
without running a server. If a serving surface is added later, generate it from
the same tool functions and models rather than designing the package around a
server. `tools/mcp/` is that surface (section 10.3): generated from the registry,
behind an optional dependency group, on no import path a plain Python caller
touches.

---

## 8. Validation Policy

Default checks stay lightweight and deterministic:

- `python3 -m compileall tools algorithms`
- smoke imports for `tools.*` and `algorithms.*`
- `git diff --check`

End-to-end WCS, photometry, catalog-query, and field-calibration validation
requires FITS data, solver binaries, local catalog data, and native astronomy
dependencies. Those checks should be targeted to the PR that changes the
behavior and should not become a broad architecture gate.

---

## 9. Non-Goals

- No orchestration framework.
- No mandatory serving framework.
- No broad numerical remediation in architecture PRs.
- No remote-provider live tests in default checks.
- No large model tree before public tools need it.

---

## 10. The Agent Loop and Model Port

Serving/agent-loop code stays optional (section 7): every tool is callable
from plain Python without any of this. When an agent loop *is* wanted, it is
built in two layers.

`tools/agent/` is the headless loop. `run_session()` drives a model backend
over the tool registry and yields a stream of twelve event types
(`SessionStarted`, `TurnStarted`, `TextDelta`, `ThinkingDelta`, `UserMessage`,
`ToolCallProposed`/`Started`/`Finished`/`Denied`, `ProtocolFault`,
`TurnFinished`, `SessionFinished`); a `Decision` flows back in through an
approver callable. It imports no UI toolkit. `SYSTEM_PROMPT` lives in
`tools/agent/prompt.py`.

`ThinkingDelta` is never merged into `TextDelta`. A model's working is a
different kind of claim from its answer — it may contradict the answer — and a
consumer that rendered them alike would let a discarded hypothesis read as a
finding.

Three optional callables let an interactive caller stay in a run, and the loop
is unchanged without them:

| Hook | When | What it does |
| --- | --- | --- |
| `on_delta` | Inside `complete()`, per chunk | Receives `TextDelta` and `ThinkingDelta` as they stream, **instead of** their being emitted afterwards. A generator cannot yield from a callback, so without it the engine buffers and emits on return. Either way a delta is delivered exactly once. |
| `pending_input` | Top of every turn | Drained; what it returns is merged into the **trailing user message**, which is the one carrying the tool results. Two consecutive user messages are not a shape every provider accepts, and a note is an addition to what the user last said, not a turn of its own. `UserMessage` announces the turn it landed in. |
| `should_stop` | Top of every turn, and before each tool call | Ends the session with outcome `interrupted`. A pending tool call takes the denial path with an `interrupted` result rather than being abandoned: every `tool_use` needs a `tool_result` or the conversation cannot be sent again. A hook that raises is read as "keep going". |

`tools/llm/` is the provider-neutral **model port**. Two rules govern it:

> The core owns the loop; adapters own the dialect.
>
> Replay the tools, never the model.

- A backend is named by a `provider/model` spec, split on the **first slash
  only** (`ollama/llama3.1:8b`, `openai/meta-llama/Llama-3-8b`). Recognized
  providers: `anthropic`, `openai`, `ollama`, `gemini`. `build_backend(spec)`
  constructs one; `spec` defaults to `MARS_MODEL_BACKEND`.
- Environment: `MARS_MODEL_BACKEND` (default spec), `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY` / `OPENAI_BASE_URL`, `GEMINI_API_KEY`, `OLLAMA_BASE_URL`. A
  provider key from the environment reaches only that provider's default host;
  a non-default base URL needs a key passed explicitly with it. With
  `MARS_MODEL_BACKEND` unset the default is Anthropic. Examples:
  `anthropic/claude-sonnet-5`, `openai/gpt-4.1`, `ollama/qwen3.8:27b-mlx`
  (`OLLAMA_BASE_URL` defaults to `http://localhost:11434/v1`, no key),
  `gemini/gemini-2.5-pro`; `OLLAMA_TIMEOUT_S` is in section 10.2.
- `.env` at the repository root is read when the console launches and again
  on every `/backend`, so a key added while the console is open takes effect
  on the next switch. The real environment always wins over the file, and the
  file is gitignored.

  ```bash
  MARS_MODEL_BACKEND=openai/gpt-4.1 OPENAI_API_KEY=... uv run mars
  ```
- The loop is equally callable from plain Python:

  ```python
  from tools.agent.engine import run_session
  from tools.llm.factory import build_backend

  for event in run_session(
      "all historical radio data on Cassiopeia A",
      backend=build_backend("ollama/qwen3.8:27b-mlx"),
  ):
      print(event)
  ```

  Every run writes a session manifest (`tools.sessions.AgentSession`) under
  `artifacts/sessions/<session_id>/session_manifest.json`, recording each turn
  and tool call, cache hits included; an identical repeat call within a
  session is served from the loop's cache with no network round trip.
- `complete()` is the **only required method** of a `ModelBackend`, and it is
  non-streaming. Streaming is a capability flag with a one-shot fallback.
  Schema translation into a backend's dialect and pre-dispatch argument
  validation are the caller's job (`tools/llm/schema.py`,
  `tools/llm/validation.py`), so adapters never import `tools/registry.py`.
- Zero new third-party dependencies: the `anthropic` SDK is reused; the OpenAI,
  Ollama, and Gemini adapters are raw `httpx`.

### 10.1 The Benchmark Harness

`tools/bench/` answers two questions about swapping one model for another on
this tool surface: **which model is actually better, and at what** (answer
correctness), and **at what cost in work** (efficiency). Everything else it
reports exists to explain one of those. The full architecture is
`docs/benchmarking/harness.md`.

**It adds nothing to the tool surface.** It owns no tool, registers nothing,
and is listed in `tests/test_tool_registry_coverage.py::NOT_TOOL_MODULES`
beside `tools.llm` and `tools.agent`. It *reads* `tools/registry.py`'s schemas
and substitutes `run_session()`'s `tool_functions=` mapping; the engine needs
no change to provide that seam. The dependency runs one way:
`tools.bench` → `tools.agent` → `tools.llm` → `tools.registry`. Nothing under
`algorithms/` or `tools/llm/` imports it.

**The tool surface is three surfaces, and the harness treats each
differently** (`tools/bench/plane.py::TOOL_CLASSES`):

| Class | Count | Treatment |
| --- | --- | --- |
| **L** — local, deterministic | 26 | **Run live.** They read the bundled fixture tree and compute. Replaying `compute_pulsar_periodogram` would let the task author, not the data, decide whether a model's mistake is visible. |
| **R** — remote | 22 | **Always replayed** from a recorded fixture. Never executed in a run. |
| **M** — local code behind a network-capable argument | 7 | **Decided per call** from the call's own arguments. A task must pin the offline path (`use_field_cal=false`; `catalog_fixture` *and* `compare_to` together) or the tool is replayed. |

The classification is **per tool, never per module**: `get_literature_cluster_params`
returns Cantat-Gaudin & Anders (2020) parameters and looks local, but
`algorithms/hrdiagram_py/literature.py` fetches them through `search_vizier`.
`tools.hr_diagram` alone spans all three classes.

**The plane is closed.** A registered tool with no classification raises rather
than defaulting, and a test asserts `set(TOOL_CLASSES) == set(TOOL_FUNCTIONS)`.
Every default would be wrong: defaulting to live opens a socket mid-run,
defaulting to replay measures a fixture miss instead of the tool. **A new
registry tool must be classified in the same commit that adds it.**

**Four verbs over a directory on disk** (`mars-bench`, a console script
beside `mars`): `run` produces evidence, `grade` produces
verdicts, `compare` produces the matrix, and `record` captures a fixture for
human review. Grading is separate from running because the first version of any
grader is wrong and re-grading must not cost a re-spend. `--max-tokens` is
required for any live backend, with no default.

**Inputs are tracked under `benchmarks/`; output goes under `artifacts/`,**
which `.gitignore` already covers. Naming the input directory `data/` would put
it in the fixture tree; putting output in it would make every run a dirty
working tree.

Nothing added here opens a socket under a plain `uv run pytest`, and that is a
test rather than a convention: the smoke suite runs end to end with both sides
replayed, under a socket guard, in milliseconds. There is **no CI benchmark
job** — CI stays offline, deterministic, and keyless.

### 10.2 The MARS Console

`tools/tui/` is the Textual console over the same loop, and the repository's
one model-driven entry point: `mars`, with **no required arguments**, because
everything it needs is chosen inside the session. It is the only package
permitted new dependencies -- `textual` and `textual-image` are the two it
added, over the already-pinned `pillow` and `rich`. `tools/agent/` and
`tools/llm/` stay zero-new-dependency, which is what keeps the loop callable
from plain Python.

**Using it.** `uv run mars` opens on the default backend; flags only choose a
different start:

```bash
uv run mars --backend ollama       # start on the local daemon
uv run mars --thinking-budget 0    # without asking for reasoning
uv run mars --max-turns 40         # with a higher ceiling than 20
```

```text
╭─ M A R S ──────────────────────────────────────────────────────────────────╮
│ astronomy research console · anthropic/claude-sonnet-5                     │
╰────────────────────────────────────────────────────────────────────────────╯

  › how far away is M31?

  Session 20260918T164552Z_2ac41045d42a started.

  Turn 1 started.

  ▊  ✻ thinking
  ▊  NED's resolver is weaker on colloquial names than SIMBAD's, so
  ▊  resolve first.

  ✓ search_simbad  (696 ms)

  Turn 1 finished: tool_use.

  Turn 2 started.

  M31 is the Andromeda Galaxy, 2.5 Mly away.

  Turn 2 finished: end_turn.

  Session finished: end_turn.

 ▊▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▎
 ▊  Ask MARS…                                                             ▎
 ▊▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▎
  2/20 turns • 1 artifact • halfblock graphics • F3 artifacts • F4 sessions
```

The header names the session's `provider/model`; the status bar counts turns
against the ceiling, token usage once a turn reports it, the artifacts
written, and the graphics tier detected for this terminal. It needs a backend
before it will answer anything — a key for the provider it opens on, or a
local Ollama daemon, which needs none — but if the default cannot be used the
console still opens and says why, and `/backend` fixes it from inside the
session (section 10 lists the environment).

| Command | Aliases | Does |
| --- | --- | --- |
| `/help` | `/?` | List the commands, generated from the registry. |
| `/backend [name\|spec] [model]` | `/b` | List the backends, or switch (below). |
| `/artifacts` | `/a` | Browse what this session wrote, with previews. |
| `/sessions` | `/s` | Browse saved sessions and resume one. |
| `/resume <id>` | `/r` | Resume a saved session by id. |
| `/quit` | `/q`, `/exit` | Exit. |

`/status`, `/tools`, `/approve`, `/prompt` and `/new` are registered and
offered by the menu, but not implemented yet: they answer with a notice
rather than doing anything.

| Key | Does |
| --- | --- |
| `Tab` | Complete the slash command being typed. |
| `F3` / `F4` | Artifact browser · session browser. |
| `Esc` | Stop the running turn at its next safe point; close a browser. |
| `o` | In the artifact browser, open the selected file in the desktop handler. |
| `Ctrl+Q` | Quit. |

Everything a run writes is kept: tool artifacts land under
`artifacts/sessions/<session_id>/`, `F3` browses them with image and waveform
previews, and the session manifest beside them is what `/sessions` and
`/resume` read back.

**Threading.** The engine is synchronous, so the console runs it in a Textual
thread worker and posts each event to the UI thread as a message. Approval runs
the other way: the worker posts a request carrying a `threading.Event`, blocks
on it, and the UI thread sets it when the modal is answered. Nothing about the
engine knows a UI exists.

**Approval.** `tools/agent/policy.py` holds `Decision` (`ALLOW`, `DENY`,
`ALLOW_ALWAYS` — the last persisting for the session), the per-tool risk tags,
and `policy_approver`. A denied call never dispatches: it returns an error
result to the model and the loop continues. The headless default denies risky
calls; trusted callers such as the benchmark replay plane opt in explicitly
with `auto_approve`.

**Private-artifact exemption (AUD-01).** `tools/effects.py` is the closed,
shared inventory for MCP local-effect hints and agent consent. Routine tables,
intermediate time-series/HR products and solver logs deliberately do not need
write confirmation. The three explicitly tagged audio/plot tools still do;
download and FITS-header flags override any routine-artifact exemption. Slow
and keyed tags remain independent. An MCP hint describes the effect, not the
consent decision: every artifact writer remains non-read-only. Unknown or new
unreviewed tools require write consent, and a registry-partition test requires
an explicit disposition before they can pass CI. Headless default approval is
not a filesystem sandbox and does not block all private-artifact writes.

Two properties of the ask itself:

- **Risk can live in an argument, not only in a tool.** `search_mast` and
  `search_casda` return a table when asked to search and pull the matched
  products into the data tree when asked to download — 121,515 of them for
  Cassiopeia A. `DOWNLOAD_FLAGS` tags the call rather than the tool, so an
  ordinary search stays unprompted and a fetch asks.
- **The modal shows the arguments.** Approving `search_vizier` says nothing
  about what it would query, and the transcript node carrying the arguments is
  behind the modal. They are rendered as bounded plain text.
- **Quitting answers every pending ask with `DENY`.** A thread worker blocked
  on a decision cannot be cancelled — it waits on an event only the interface
  sets — and Python joins its executor threads at exit, so an unreleased
  modal turns a quit into a hung process rather than a closed one.

**Slash commands** (`tools/tui/commands.py`) are UI-level and never reach the
model — a mistyped command would otherwise cost a turn and pollute the
transcript. The registry is declarative (name, aliases, help, handler, optional
argument completer), so `/help` is generated from it rather than maintained. A
doubled leading slash escapes to a literal one. Typing `/` lists every command;
Tab completes one match whole and several only as far as they agree, the shell
rule, because guessing between equal candidates puts a command nobody asked for
into the prompt. A completer is handed every argument word typed so far, which
is what lets `/backend` answer with providers for the first argument and with a
host's models for the second. The module imports no Textual, so all of it is
testable without a terminal.

**Backend selection** (`tools/tui/backends.py`) is live: `/backend` lists what
is offered and switches the running session, retitling the header. Three rules
make that safe to offer mid-session.

- **Probe before swap, in two steps.** Anthropic fails at construction when its
  key is missing; Ollama does not. A backend pointed at a stopped daemon builds
  perfectly and raises a connection error several seconds into the first
  question, and *a daemon that is up is not a daemon that has your model* —
  an unknown one answers with a 404 from `/v1/chat/completions` at the same
  point. So `open_backend` checks the service and then the model, and the
  session's backend is replaced only after both pass. A failed listing is `()`,
  meaning "could not ask", never "holds nothing".
- **A bare provider name asks rather than assumes.** `/backend ollama` opens a
  picker of what the daemon reports, marking the running model and the default;
  naming a model outright switches directly. A host that cannot be asked offers
  nothing and the switch proceeds to the default, because an unanswerable
  question must not stop the switch that was asked for.
- **Never mid-turn.** `run_session()` was handed the backend by value when the
  turn started; swapping it would retitle the header for a turn the old backend
  is still finishing.

A question *about* a daemon is not timed like a turn: `OLLAMA_TIMEOUT_S`
defaults to 600 s because a local turn is bounded by the host's hardware, while
`is_available()` and `installed_models()` use a five-second probe timeout. One
Tab against a host that accepts connections and then says nothing would
otherwise freeze the interface for ten minutes.

**The interactive turn.** The console is where the three engine hooks above are
used, and the properties they buy are all the same property: the person
watching a run is the one best placed to correct it.

- What you typed stays in the transcript; an answer read without the question
  that produced it is a different claim.
- Reasoning is rendered where the provider reveals it, in its own muted block
  per turn, never styled like the answer. The console asks for it by default
  (`--thinking-budget`, 4096 tokens, `0` to switch it off) — everywhere else
  thinking stays off, because asking for it costs `temperature` and with it the
  benchmark's determinism claim.
- The prompt never closes. What is typed mid-turn is queued, marked queued
  until the engine reports it delivered, and merged into the next turn; a note
  the session ended before taking goes back into the prompt rather than the
  void.
- Escape stops the turn at its next safe point, and says so rather than
  pretending it stopped instantly.

**Artifact rendering** probes the terminal once at startup —
`KITTY_WINDOW_ID`/`TERM`, then `TERM_PROGRAM`, then a Sixel device-attributes
query under a short timeout — and picks a `GraphicsTier` of `KITTY`, `ITERM2`,
`SIXEL` or `HALFBLOCK`. Half-blocks are the floor and always work, so a
terminal that cannot be probed loses resolution rather than the picture. The
native-protocol library is imported **on use, not at import**: it measures the
terminal's cell size at import time and divides by the reported column count,
so a tty that reports no size at all — a pty opened by a wrapper — killed the
console before it drew anything.

**Three traps worth keeping written down.**

- A `_leading_underscore` method on a Textual subclass is in *Textual's*
  namespace, not a private one of ours. `ToolNode` built its renderable in a
  method called `_render_content`, which is also Textual's per-repaint hook:
  every tool call painted as a blank row while `state`, `content` and
  `render()` all stayed correct. Tests that assert widget state cannot catch
  that; one that asserts `render_line(0)` can.
- **A `Static` given a plain string parses it as content markup.** Anything
  carrying model output, a tool's error text, or a path sets `markup=False`;
  everything else passes a Rich `Text`, which is never parsed. Both halves
  matter: markup would let a model mint a clickable `[@click=…]` action link
  in the transcript, and it silently eats ordinary astronomy text, since
  `The [OIII] line` renders as `The  line`.
- Textual 8's `Static` exposes `content`, not `renderable`.

**A preview fails the way its library fails, not the way it looks like it
does.** Pillow's `DecompressionBombError`, `wave.Error` and `struct.error` are
all bare `Exception`s rather than the `OSError`/`ValueError` a reader assumes,
so a catch list written from the obvious guess let a large PNG, or any
non-WAV file named `.wav`, raise out of an event handler. And a preview reads
only the frames it draws: sampling a decoded file instead cost 0.75 s and
~300 MB on the bundled 10 MB example, on the UI thread.

**Testing.** Everything above runs under `uv run pytest` with no terminal:
Textual's headless pilot drives keypresses and asserts widget state, the
capability probe runs against faked environments, and the half-block renderer
is pinned byte-for-byte against a committed 4×4 PNG.

### 10.3 The MCP Server and the Agent Skill

`tools/mcp/` serves the registry to a coding agent's own console — Claude
Code, Codex, Cursor — over MCP on stdio, from a machine where **this
repository is not checked out**. It is the serving surface section 7 allows:
generated from `TOOL_SCHEMAS` and `TOOL_FUNCTIONS`, never the reverse. It is a
fourth consumer of the registry, beside the loop (10), the harness (10.1) and
the console (10.2), and it retires none of them. The console and harness
measure and drive models through MARS's own loop. A third-party host's
session is not graded by anything, because MCP gives the loop to the host.

**Shape.** One entry point, `mars-mcp`. A launch-time filter,
`--tools databases,optical,timeseries,hr,radio` (or `MARS_MCP_TOOLS`),
serves a subset. The groups are declared by tool module in
`tools/mcp/groups.py`, a test asserts they partition the registry, and the
filter narrows what is callable as well as what is listed. One server, not
five: a dispatcher with a `database` enum would discard the per-database
argument validation that makes the schemas worth having.

| Module | Owns |
| --- | --- |
| `roots` | Pins `MARS_ARTIFACT_DIR` and `MARS_DATA_DIR` into the environment **before** `tools.config` is imported. Several modules copy `ARTIFACT_DIR` at import, so reassigning it later moves nothing. |
| `surface` | What is served, with no SDK import: the tool list, the stringified-`"None"` pre-check, the result shape, inline media. A plain `uv run pytest` tests it. |
| `server` | The serving SDK import (`mcp`, optional `[mcp]`). Registry-schema validation rejects undeclared arguments and floats for integers. Calls run sequentially in owned, cancellable worker processes under finite whole-call deadlines. |
| `tools.runtime` | Worker lifetime, OS memory/file limits, sampled work/log/download byte/entry limits, bounded input/reply, private owned call trees and explicit cleanup. No SDK import; private parent-generated callable jobs are never client-supplied pickle. |
| `tools.downloads` | Per-provider bounded HTTP streaming: actual decoded bytes, product/file counts, path checks, response closure and exclusive atomic publication. SDK authentication/selection remain; cloud/resume/unbounded-content shortcuts are disabled. |
| `groups` | Five groups; open-world hints from `TOOL_CLASSES`, write effects from closed shared `tools/effects.py`, with download/header overrides. Routine private writers remain non-read-only even where agent consent exempts them. |
| `install` | The facts about this install that the instructions carry: artifact root, which data bundles are present, whether plate solving is configured, and whether `ADS_DEV_KEY` is set (never its value). |
| `bundles` | Builds and fetches the optional data bundles (below). |
| `selftest` | `mars-mcp self-test`: launches the installed server over stdio and detects B0329+54 from a measured period through the protocol. |

**Results.** Every result is `structuredContent` plus the same JSON as text,
serialised so NaN becomes `null`. `isError` follows the loop's
`status == "error"`. A failed validation (`invalid_input`), an unknown tool
(`unknown_tool`) or a raising tool (`tool_exception`) is that call's error
result, never a dead session. `tool_timeout`/`resource_limit` reject stopped or
over-budget work without advertising partial files. The absolute artifact path contract stands unchanged,
because the caller shares the filesystem. On top of it, a PNG or WAV artifact
also comes back **inline** as an image or audio block (5 MB and 16 MB limits, measured base64-encoded),
read only from inside the pinned artifact root, additionally bounded to 32 media
references / 20,000,000 encoded bytes total. No `outputSchema` is declared:
clients validate against one, and a NaN-as-`null` in a `number` field would
then fail on a user's machine.

Two registry descriptions are extended at serve time rather than edited.
`list_artifacts`/`describe_artifact` name the pinned root, and say that
`list_artifacts` lists direct children while tools write into per-tool
subdirectories. `sonify_pulsar`'s "the audio is never inlined" is replaced,
and a test pins the registry original.

**Where things go.** Artifacts default to a **per-user directory**, not the
host's launch directory: a host launches the server wherever it likes, and a
launch-directory default would drop an untracked `artifacts/` into the user's
repository. Everything MARS writes is under the per-user **MARS home**
(`tools/paths.py`: `~/.local/share/mars`, macOS Application Support,
`%LOCALAPPDATA%`, or `MARS_HOME`), and the server logs every root at
startup. The shared artifact writer rejects absolute or parent-traversing
subdirectories, symlinks that resolve outside the pinned root, and extensions
that contain path syntax. Session scopes are checked both when entered and
again at write time. A Python API with an explicit `output_dir` treats that
caller-selected directory as its root while still confining generated names
to one direct child.

**Runtime ownership and retention (MCP-01/AUD-03).** A process per call avoids
abandoning writing threads on cancellation; sequential locking remains. The
deadline includes capacity waiting. Private `.mars-runtime/<id>/` trees hold
job/reply, bounded logs, redirected scientific caches and `artifacts/`; downloads
have separately marked trees under their root. Matplotlib draws on the worker's
main thread with Agg. Prior successful artifacts remain readable at returned
paths. `build_server` substitutions must be importable callables, not local
closures; production workers import this install, never checkout test helpers.

POSIX cleanup stops the worker group and separately recorded owned solver
groups, including stubborn helpers. Linux birth ticks reject live reused PIDs;
the server's own group is never signalled. Windows joins a server-owned memory-limited
kill-on-close job before scientific imports or fails closed. The server bypasses
the venv redirector (retaining the venv), waits for the real interpreter's native
handle to signal (a cached `Popen` exit code is insufficient during termination),
and verifies zero active job processes before finishing/releasing the call.
Failed-worker diagnostics are bounded and forwarded to operator stderr, not
client payloads. macOS measures pre-tool virtual mappings and applies a finite
4-GiB address-space growth allowance above that bootstrap; Linux retains its
absolute 4-GiB ceiling. Stricter inherited ceilings are preserved. Native Windows and
macOS runtime checks are required CI gates. These are trusted-tool resource
controls, not a hostile-code/filesystem sandbox: absolute inputs and explicit
header writes remain intentional. Disk/log checks are sampled, POSIX memory
limits are per-process, and retained admission is not an atomic multi-server
quota. Abrupt parent death and deliberately escaped POSIX sessions are not
certified containment scenarios. Defaults and permanent dry-run-first cleanup
are documented in `installing.md`; legacy/console outputs and operator datasets
are never adopted for deletion.

**The skill.** `SYSTEM_PROMPT` is delivered by nothing when the host owns the
loop, so the server carries its guidance. **Claude Code delivers only about
the first 2,000 characters of a server's instructions** (measured), so the
served skill has two tiers:

- The instructions are `tools/skill/source/BRIEF.md` — the six rules that
  must survive truncation — plus the install facts. They are held under 1,900
  characters, worst case, by a test.
- `SKILL.md` and the per-domain references are MCP resources,
  `mars://skill/...`, read on demand.

`tools/skill/source/` is the one source. It renders the served text, and also
`skills/mars-tools/`, the repository copy that `.claude/skills/` links for
a coding agent in a checkout. `tests/test_skill_invariants.py` pins the
load-bearing rules as phrases in both `SYSTEM_PROMPT` and the skill, so a
correction to one that misses the other fails a test. The pulsar tools' own
descriptions carry measure-first as well, so that rule depends on neither
tier.

**Packaging.** A wheel carries the code (about 4 MB) and the **core data**
(about 7 MB: pulsar scans, zero-point references, Afterglow fixtures) at
`tools/_data`. In a checkout that path is a committed symlink to `data/`.
`config.BUNDLED_DATA_DIR` is how every tool reads bundled data, so a checkout
and a wheel find the same files the same way.

Two larger **optional bundles** are fetched with `mars-mcp fetch-data`: the
optical frame library (269 MB) and the Girardi isochrone grid (282 MB).

- Each is a deterministic, content-addressed plain `.tar` on the repository's
  standing `data` GitHub release.
- `tools/mcp/bundles.json` ships in the wheel and pins each archive's size and
  SHA-256, so a wheel accepts only its own bundles.
- Downloads resume by HTTP Range, and extraction goes through tarfile's `data`
  filter.
- Absent, a tool says so (`bundle_not_installed`). An empty listing is never
  presented as the answer.

- `--from URL_OR_DIR` (or `MARS_BUNDLE_URL`) fetches from a mirror or a local
  directory instead.

The fixture-write guard, the download root and `tools.optical`'s recursion
boundary are **re-anchored** for an installed layout, never weakened. Nothing
is written into the installed package.

- `solve_astrometry(write_header=true)` refuses to write into the bundled data
  or into a fetched bundle (`refusing_to_modify_fixture`). Downloaded products
  stay writable.
- `list_optical_frames` walks a download root recursively only inside the data
  directory or the MARS home's `fits_downloads/`. Anywhere else, it searches
  the root flat and says so.

An install writes under the MARS home (`MARS_HOME`; `docs/installing.md`).
Each subdirectory has its own override:

| Directory | Override |
| --- | --- |
| `artifacts/` | `MARS_ARTIFACT_DIR` |
| `fits_downloads/` | `MARS_FITS_DOWNLOAD_DIR`, or `MARS_DATA_DIR` (then its `fits_downloads/`) |
| `bundles/optical/`, `bundles/isochrones/` | `MARS_OPTICAL_DATA_DIR`, `MARS_ISOCHRONE_DIR` |
| `numba-cache/` | `NUMBA_CACHE_DIR` |

Each artifact name is claimed atomically, so two servers sharing the
directory never overwrite each other. A repeat call adds a numeric suffix.
`list_artifacts` returns the newest 100 entries of a directory, and refuses
one that climbs out (`..`). `CASDA_OPAL_USERNAME` enables CASDA downloads.

**Releases.** `.github/workflows/release.yml` publishes a `v<version>` tag,
with `docs/releasing.md` as the policy. It:

- checks the tag against the version;
- rebuilds `data/optical/` against the pinned manifest;
- installs the wheel on clean runners with no checkout, on Python 3.12 and
  3.13, and runs `mars-mcp self-test`;
- checks the `data` release by GitHub's asset digests;
- then publishes — the only job with write permission.

Python 3.12 and 3.13 are supported, and CI tests both against `uv.lock`, which
moves when a change needs it or for a security fix. 3.13 is the newest Python every
dependency ships wheels for: `sep` has none for 3.14, and `photutils` none
for Linux aarch64. Installing and registering is `docs/installing.md`.

**Dependency direction.** `tools/mcp → tools/registry`, plus
`tools/mcp/groups → tools/bench/plane` (import-light by design). `tools/mcp`
imports **nothing** from `tools/agent/` or `tools/llm/`, and nothing under
`algorithms/` imports `tools/mcp`. A test asserts both.
