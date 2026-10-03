# Repository Folder Guide

This guide explains the current source folders in MARS (MCP Astronomy Research Suite). It documents the
repository as it exists now: root-level tool modules, distinguished extracted
algorithm modules, and planning material for future tool work.

Generated folders such as `__pycache__/`, Git internals such as `.git/`, and
workspace support folders are not part of the source layout.

## `.github/`

Repository automation and ownership policy.

- `CODEOWNERS` assigns maintainer ownership for the repository.
- `pull_request_template.md` defines the review checklist shape.
- `workflows/ci.yml` runs the current lightweight Python/repository-shape checks.
- `workflows/secret-scan.yml` runs gitleaks against the tree and history.
- `workflows/workflow-safety.yml` runs actionlint and zizmor against workflows.
- `workflows/release.yml` builds, verifies (a clean install on Python 3.12 and 3.13
  running `mars-mcp self-test`) and publishes a release from a
  `v<version>` tag, and checks the standing `data` release holds the pinned
  bundles. Policy: [releasing.md](releasing.md).

Keep workflow changes narrow and security-conscious. The current checks are
deliberately small because the extracted science code still needs native
dependencies, external catalog data, and reference FITS fixtures for full
end-to-end validation.

## `installers/`

Build inputs for installers that are not the wheel.

- `claude-desktop/` is the Claude Desktop extension: a `.mcpb` manifest of the
  `uv` type, an empty environment, and an entry point that runs the newest
  `mars-mcp` on PyPI through `uv tool run`. It names no MARS version, so a
  release needs no change here. Its README has the build and test steps.
- `codex/` is the Codex plugin, for the ChatGPT desktop app's Codex threads,
  the Codex CLI and the IDE extension: a `.codex-plugin/plugin.json`, a
  `.mcp.json` that runs the same entry point as the extension (a byte-for-byte
  copy of its `src/server.py`), and the skill, rendered by
  `python -m tools.skill`. `.agents/plugins/marketplace.json` at the root lists
  it, which makes the repository a Codex marketplace. Its README has the Fedora
  install and test steps.

## `skills/`

`skills/mars-tools/` is the rendered repository copy of the agent skill:
how to use MARS's tools correctly (stage orders, identifier forms, period
provenance, silently wrong results). It is **generated** from
`tools/skill/source/` by `uv run python -m tools.skill`; edit the source, never
this copy. `.claude/skills/mars-tools` links to it, so a coding agent in a
checkout loads it as a skill. A test fails if the copy is stale.

## `tools/`

Important files and subfolders:

- `models.py`: small shared result, warning/error, WCS, catalog, zero-point,
  remote query, and artifact summary models.
- `config.py`: small environment-backed settings helpers for the tool layer,
  including `BUNDLED_DATA_DIR` -- the one way tools read bundled data.
- `paths.py`: the per-user MARS home (`~/.local/share/mars`, or
  `MARS_HOME`) and `tools/_data`. Resolves nothing at import.
- `_data`: in a checkout, a committed symlink to `data/`; in a wheel, the
  core data (`pulsar/`, `fieldcal/`, `afterglow/`) that `pyproject.toml`'s
  package-data ships.
- `artifacts.py`: local artifact description and listing helpers.
- `photometry_pipeline.py`: the reusable automated photometry behind
  `tools.photometry` -- loads a FITS image, runs source extraction and
  aperture photometry, resolves an optional verified zero point through a
  live field-calibration catalog solve, and saves plots. It has no CLI and no
  model-provider client. Listing and resolving a target are offline; field
  calibration is not: `run_photometry_on_target` defaults to
  `use_field_cal=True`, which queries VizieR for reference magnitudes. Pass
  `use_field_cal=False` for instrumental magnitudes, or `zero_point_mag` when
  a trusted value is already known. The offline recorded-solve replays are
  `calibrate_zeropoint(..., catalog_fixture=...)` and
  `fieldcal_reference.replay_field_calibration` (below, and
  [data/README.md](../data/README.md)); only `ngc5128_galaxy_b_001.fits` can
  be driven that way end to end.
- `astrometry.py`, `calibration.py`, `catalogs.py`, `fieldcal_reference.py`,
  `optical.py`, `pulsar.py`, `photometry.py`, `variable_star.py`,
  `workspace.py`: local plain Python user-facing tool wrappers
  (`fieldcal_reference.py` is the recorded zero-point ground truth and its
  offline replays, `optical.py` the bundled-frame registry).
- `simbad.py`, `ned.py`, `vizier.py`, `atnf.py`, `ads.py`, `mast.py`,
  `mpc.py`, `casda.py`, `resolve.py`: split remote database/archive tools.
- `hr_diagram.py`: FITS-to-HR-diagram pipeline orchestration, backed by
  `algorithms.hrdiagram_py` plus `tools.vizier.search_vizier` for the Gaia
  DR3 and cluster-literature catalog lookups.
- `radio_sources.py`: radio FITS -> catalog-identified sources -> labeled SED
  plot, backed by `algorithms.radio` plus `tools.vizier.search_vizier` and
  `tools.ned.search_ned`.
- `registry.py`: the optional agent schema registry over the same ordinary
  Python tool functions.
- `agent/`: the headless agent loop -- `run_session()`, the twelve event
  dataclasses, the approval policy, and `SYSTEM_PROMPT`. It imports no UI
  toolkit and no provider SDK.
- `llm/`: the provider-neutral model port -- neutral types, the
  `ModelBackend` protocol, schema translation, pre-dispatch validation, the
  `provider/model` spec factory, and adapters for Anthropic, OpenAI-compatible
  servers, Ollama and Gemini.
- `tui/`: the Textual `mars` console over the loop -- application shell,
  slash commands and their completion, backend and model selection,
  transcript, artifact and session browsers.
- `bench/`: the model benchmark harness (`mars-bench`). It owns no tool.
- `mcp/`: the MCP server (`mars-mcp`) -- a fourth consumer of the registry,
  served over stdio to a coding agent's console on a machine with no
  checkout. `roots` pins the artifact and data roots before `tools.config`
  loads; `surface` decides what is served with no SDK import; `server` is the
  only `mcp` SDK import (optional `[mcp]` group); `groups` holds the five
  tool groups and the derived annotations; `install` states the install's
  data and credentials; `bundles` (with `bundles.json`) builds and fetches the
  optional data bundles; `selftest` is `mars-mcp self-test`. Imports
  nothing from `agent/` or `llm/`. See
  [tool-architecture.md](tool-architecture.md) section 10.3 and
  [installing.md](installing.md).
- `skill/`: the agent skill's one source, `source/` (`SKILL.md`, `BRIEF.md`,
  and per-domain references), and the renderer (`python -m tools.skill`)
  that writes the repository copy `skills/mars-tools/`. The MCP server
  serves the brief as its instructions and the rest as resources.
- `sessions.py`: `AgentSession` and `make_cache_key` -- per-run manifest
  recording (tool calls, cache hits, artifacts, turns) plus the shared cache
  key used both by the loop's in-memory repeat-call cache and by the
  manifest's own cache-hit bookkeeping. Manifests are written under
  `artifacts/sessions/<session_id>/session_manifest.json`; `list_session_manifests`
  and `read_session_manifest` read them back.

Current tools:

- `astrometry.describe_image_wcs(path)`: describe celestial WCS metadata in a
  FITS header.
- `catalogs.list_photometric_catalogs()`: list local catalog declarations
  without querying remote services.
- `catalogs.resolve_reference_band(catalog, image_filter)`: summarize the local
  filter-to-reference-band mapping MARS would use.
- `calibration.solve_zeropoint_from_measurements(measurements, catalog_sources)`:
  solve a zero point from local measurement and catalog-source records.
- `pulsar.resolve_pulsar_scan(...)` / `pulsar.list_pulsar_scans(...)`,
  `pulsar.load_pulsar_lightcurve(path)`, `pulsar.compute_pulsar_periodogram(path)`,
  `pulsar.fold_pulsar_lightcurve(path, period_s)` and
  `pulsar.sonify_pulsar(path, period_s=None)`: the pulsar pipeline, local
  only, each stage's artifact feeding the next. `pulsar.plot_pulsar(...)`
  renders any stage's artifact as a PNG. See
  [pulsar-tool-pipeline.md](pulsar-tool-pipeline.md).
- `photometry.list_photometry_targets()` and
  `photometry.run_photometry_on_target(target, ...)`: local aperture
  photometry (source extraction, optional live zero-point verification) over
  a fixed bundled FITS library -- a thin wrapper reusing
  `tools.claude_photometry_haiku_tool`'s pipeline, not a reimplementation.
  Not a substitute for the HR-diagram pipeline below (no Gaia crossmatch, no
  isochrone fit); `run_photometry_on_target(..., write_source_table=True)`
  writes a CSV that bridges into it (see `hr_diagram.crossmatch_gaia` below).
- `workspace.list_artifacts(directory=None)` and
  `workspace.describe_artifact(path)`: inspect local artifact files.
- `resolve.resolve_target(name)`: resolve a target through SIMBAD.
- `simbad.*`, `ned.search_ned`, `vizier.*`, `atnf.search_atnf`,
  `ads.*`, `mast.search_mast`, `mpc.search_mpc`, and `casda.search_casda`:
  query remote astronomy databases and archives, returning bounded previews
  plus local artifact paths for complete tables or reviews.
- `hr_diagram.extract_photometry_from_fits`, `crossmatch_gaia`,
  `get_literature_cluster_params`, `select_cluster_members`,
  `fit_and_compare_hr_diagram`, `run_full_hr_pipeline`: FITS frame -> HR
  diagram -> literature comparison, chained through
  `algorithms.hrdiagram_py` and `tools.vizier.search_vizier`. Deliberately
  cheaper, uncalibrated source extraction than `photometry.py` above -- the
  frame's own magnitude is discarded once Gaia's is fetched.
- `hr_diagram.crossmatch_gaia_by_position`, `run_full_hr_pipeline_from_catalog`:
  the same HR-diagram pipeline with no FITS frame required -- Gaia DR3 is
  fetched directly around the cluster's own resolved position instead of
  matched against a frame's detected sources. Prefer this path whenever the
  user has not supplied a FITS file.
- `radio_sources.plot_field_sed(fits_path, ...)`: the main radio entry point --
  identifies sources in a radio FITS frame against VizieR's radio catalogs
  (`identify_radio_sources`), then plots every identified source's spectral
  energy distribution from NED on one labeled plot, each with its own fitted
  spectral index (`analyze_source_spectrum`, callable standalone for one
  already-named source). Replaces the non-functional `Spectral_Plot.py` /
  `Best_Fit_Analysis.py` scratch scripts.

## `algorithms/`

Extracted algorithm packages and shared algorithm support code.

Important files and subfolders:

- `algorithms/wcs/`, `algorithms/photometry/`, `algorithms/fieldcal/`,
  `algorithms/catalogs/`, `algorithms/query/`: extracted Python algorithm
  packages.
- `algorithms/skylib_lite/`: consolidated local subset of Skynet's `skylib` used
  by the extracted Python algorithms.
- `algorithms/pulsar/`, `algorithms/variable_star/`,
  `algorithms/hrdiagram_py/`: Python ports of Astromancer algorithms.

## `algorithms/catalogs/`

Extracted Python catalog declarations from Skynet and Afterglow.

What MARS knows about catalogs and provider vocabularies, and nothing about
reaching them: no module here imports `astroquery`, `psrqpy`, or opens a
socket. Photometric catalog declarations cover eleven catalogs — APASS,
Landolt, PanSTARRS, SDSS, SkyMapper, Stetson, 2MASS, Tycho-2, UCAC5, USNO-B1,
VSX.

Each plugin declares its band table (`mags`), its filter/colour transforms
(`filter_lookup`), its column mapping, and its VizieR table ID. Three plugins
also carry photometric conversions applied to their rows.

Important files:

- `catalog.py`: the plugin base class — the declaration contract.
- `<name>_catalog.py`: one module per catalog.
- `catalog_options.py`: the second, smaller registry (`CATALOG_OPTIONS`) that
  reference-magnitude resolution reads. It is *not* redundant with `CATALOGS`;
  see [extraction.md](extraction.md), Catalogs §4.
- `schemas.py`: `CatalogSource` and friends — the data contract between
  `algorithms.catalogs` and `algorithms.query`.
- `simbad.py`: the 206-entry SIMBAD object-type vocabulary.
- `ads.py`: ADS field lists and citation formatting helpers for `tools.ads`.
- `atnf.py`: ATNF pulsar-parameter vocabulary for `tools.atnf`.
- `ned.py`: NED table-name and photometry-format vocabulary for `tools.ned`.
- [extraction.md](extraction.md), Catalogs: provenance, renames, preserved
  behaviours, verification.

Current caveats:

- Two registries exist and disagree deliberately. Merging them changes which
  reference band a narrowband or unfiltered image calibrates against.

## `docs/`

Project documentation. The top level holds the reference documents; three
subdirectories hold everything else. See [`README.md`](README.md) for the full
map and the document lifecycle.

- `tool-architecture.md` — the master package architecture: public tools,
  algorithm ownership, shared models, `skylib_lite` consolidation, runtime and
  validation policy.
- `extraction.md` — the master extraction record for every algorithm package
  under `algorithms/`.
- `repository-folders.md` — this current-state folder guide.
- `pulsar-tool-pipeline.md` — the four-stage pulsar tool chain and the extracted
  Astromancer code behind each stage.
- `installing.md` — installing MARS with no checkout, registering
  `mars-mcp` with a host, and the optional data bundles.
- `releasing.md` — version and tag policy, the release workflow, and the
  standing `data` release.
- `analysis/` — point-in-time review and external-research output (dated).
- `benchmarking/` — the model benchmark: harness design, sweep results, the
  generated report, and the figures.
- `archive/` — completed track documents, kept as records.
- `working/` — plans under active development. Empty today.
- `examples/` — committed sample output.
- `assets/` — the brand images and `make_brand.py`, which exports every one
  of them (see below).

### The brand palette

MARS stays visibly part of Skynet, so its assets (the banner, the mark, the MCP
server and extension icons) and the console's themes (`tools/tui/theme.py`)
use the exact Skynet palette, by hex value, never sampled from a raster. The
source is the Skynet/UNC proposal template, `beamer/beamercolorthemeskynet.sty`.

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
dark-mode interface surfaces. They are not Skynet palette colors, and neither
is the template's UNC-Chapel Hill palette.

### Names and the package namespace

The distribution is **`skynet-mars`**, not `mars`: `mars` is taken on PyPI (an
unrelated project), and Alibaba's `pymars` imports as `mars`. `skynet-` adds
provenance, since the algorithms come from the Skynet Robotic Telescope
Network.

`tools` and `algorithms` stay top-level packages for now. They are generic
enough that another installed project's `tools` package can collide with them,
and moving them under one namespace is the durable fix. That move touches
every import, test and extraction marker, so it is a change of its own (ARC-02
in the master continuation plan). Until then no new top-level package is
added (`tests/test_rebrand_guard.py`), and a namespace choice must not be
`mars`, for the reason above.

## `algorithms/fieldcal/`

Extracted Python photometric field-calibration code from Skynet.

Primary responsibilities:

- Match catalog sources to detected image sources.
- Reject known variable stars from the variable-source rows the caller supplies.
- Resolve reference magnitudes for the image filter.
- Run aperture photometry on matched sources.
- Solve the photometric zero point with Chauvenet rejection.
- Write `PHOT_M0`, `PHOT_M0E`, and `PHOT_CAL` into the FITS header when possible.

Important files and subfolders:

- `field_cal.py`: main calibration workflow, exposed as
  `perform_field_calibration`.
- `solution.py`: zero-point solver, exposed as `calc_solution`.
- `ref_mag.py`: reference-magnitude/filter-resolution logic.
- `algorithms.skylib_lite`: shared vendored utility subset used by calibration.
- [extraction.md](extraction.md), Field Calibration: provenance, severed Skynet
  dependencies, known parity behavior, dependency notes, and verification.

Current caveats:

- Field calibration does not own catalogs. Band tables and colour transforms
  live in `algorithms.catalogs`; catalog selection and querying live in
  `algorithms.query`.
- `perform_field_calibration` receives WCS, catalog rows, optional variable-star
  rows, and optional detected sources explicitly. Tools perform catalog queries.
- `numba` and `scipy` are required for real numeric execution.

## `algorithms/hrdiagram_py/`

A Python parity **port** of Astromancer's cluster/HR-diagram computations, plus
a real optimizer Astromancer never had. It retains the historical `_py` suffix
to avoid a disruptive package rename after the TypeScript extraction was
retired. See [extraction.md](extraction.md), "HR Diagram (Python)".

Important files:

- `hrfit.py`: the CM<->HR transform (`computePlotDelta`/`getExtinction`
  ported from `isochrone-matching/isochrone-plot.util.ts` /
  `cluster.util.ts`), CCM extinction, isochrone loading, and the
  distance/E(B-V)/age optimizer (`fit_distance_reddening`, `fit_cluster`) --
  a new capability, Astromancer's own tool is manual/by-eye only.
  `isochrone_cmd` drops PARSEC/COLIBRI thermally-pulsing-AGB rows (`label`
  column > 7) by default -- a raw PARSEC download's dust/mass-loss modelling
  breaks down there, and left in, it both scribbles the plotted track and
  biases the optimizer's cost. That cost measures each star to the resampled
  track, with a 0.02 mag floor and a per-star cap (`docs/extraction.md`,
  HR Diagram (Python)).
- `observations.py`: FITS frame -> detected sources, via `algorithms.photometry`.
  Cheap "auto" Kron-like apertures, no zero-point solve -- the frame's own
  magnitude is discarded once Gaia's is fetched.
- `matching.py`: detected sources <-> a fetched comparison-catalog table, by
  sky position (mutual nearest-neighbour).
- `literature.py`: a fetched cluster-catalog row (Cantat-Gaudin & Anders 2020)
  -> age/distance/E(B-V). Open clusters only.
- `membership.py`: field-star removal -- a per-source error-scaled parallax
  window, and Astromancer's own elliptical proper-motion acceptance region
  (ported from `cluster-data.service.util.ts::updateClusterFieldSources`,
  with each source's own ellipse semi-axes sized from its proper-motion error
  and a distance-aware velocity-dispersion floor -- the ellipse's *shape*
  alone doesn't help without that, since a circle and a fixed-radius ellipse
  reject the same points).
- `isochrones.py`: the one module here with its own network call -- fetches
  PARSEC isochrones from stev.oapd.inaf.it directly, since no existing tool
  wraps that service.

`algorithms/hrdiagram_py/` never imports `tools.*`; all network I/O besides
the PARSEC fetch above (Gaia DR3, cluster-literature lookups) lives one layer
up in `tools/hr_diagram.py`, via `tools.vizier.search_vizier`.

## `algorithms/radio/`

New first-party capability -- no upstream Skynet/Astromancer equivalent, so
there is no parity to preserve here.

Important files:

- `spectral_fitting.py`: pure-numpy flux-vs-frequency model fitting --
  `fit_power_law` (log-log OLS, the standard `S_nu ~ nu**spectral_index`
  radio spectral index), `fit_log_parabola` (quadratic in log-log space, for
  spectral curvature/turnover), and `analyze_spectrum`, which fits both and
  reports whichever the data actually supports. Every candidate model is fit
  against the same target (`log10(flux)`), so their R^2 values are directly
  comparable -- unlike an earlier draft of this fit, which compared R^2
  across models fit to different targets and was fixed here, not preserved.
- `matching.py`: `guess_radec_columns` (tries common VizieR RA/Dec
  column-name conventions, since a `category="radio"` catalog search returns
  one differently-shaped table per matched survey) and
  `match_sources_to_catalog` (flat-sky KD-tree nearest-neighbour, not
  mutual -- catalog density varies too much between radio surveys for a
  mutual-nearest-neighbour requirement to be appropriate the way it is for
  `algorithms/hrdiagram_py/matching.py`'s Gaia-specific version).

`algorithms/radio/` never imports `tools.*`; VizieR/NED network I/O lives one
layer up in `tools/radio_sources.py`.

## `algorithms/pulsar/`

Python pulsar time-series ingest and sonification. One of the Astromancer
Python ports under `algorithms/`, it carries the TypeScript sonifier into
Python because that code is welded to `Blob`, `document` and `AudioContext`
and cannot run headless. Seams are marked `# PORTED:`, not `# EXTRACTED:`.

One module per pipeline stage, in the order they must run.

Primary responsibilities:

- Parse Green Bank / Skynet pulsar files, both flavours (two-polarization
  `.cal.txt` continuum scans and prefolded single-column "standard" files),
  drop the leading noise-diode calibration block, rebase the time axis, and
  subtract a running-median background.
- Compute the Lomb-Scargle periodogram, locate its peak, and give the peak a
  false-alarm confidence level.
- Fold the light curve at a period and bin it into a pulse profile.
- Render either the profile or the raw scan as amplitude-modulated noise, and
  encode 16-bit PCM WAV.

Important files and subfolders:

- `ingest.py`: file parsing, header extraction, `median` /
  `background_subtraction`.
- `periodogram.py`: `lomb_scargle`, `find_global_max`, `confidence_threshold`,
  `nyquist_periodogram_range`, `compute_periodogram`.
- `folding.py`: `float_mod`, `fold_to_phase`, `bin_data`, `fold_and_bin`,
  `duplicate_if_needed`, `difference_and_sum`, `fold_lightcurve`.
- `sonification.py`: `interpolate_linear`, `window_sonification_input`,
  `folded_sonification_input`, `sonify`, `write_wav`.
- [Pulsar Tool Pipeline](pulsar-tool-pipeline.md): the stage-by-stage
  architecture and the extracted Astromancer code behind each stage.
- [extraction.md](extraction.md), Pulsar Sonification: provenance, the seams
  cut, the port's deliberate divergences, and the preserved upstream quirks.

Current caveats:

- **Stage order is a dependency, not a convention.** Only the periodogram
  produces a period, and folding at a wrong period returns a flat profile
  rather than an error — which is why each stage reports a quality number.
- The rendered audio is not real-time: the synthesis ignores sample timestamps,
  so a period measured off it is wrong by a few tenths of a percent (folded) to
  a few percent (unfolded). `tools/pulsar.py` reports it as `playback_stretch`.
  Catalogued periods come from `tools.atnf.search_atnf`.
- The noise carrier is seeded for determinism; upstream's `Math.random()` is
  not reproducible, so no byte-for-byte reference render exists to diff against.
- `sonificationBrowser` is not ported — it exists to drive an `AudioContext`.
- No dedispersion, no barycentric correction, no period uncertainty. Upstream
  has none of these either.

## `algorithms/variable_star/`

Exact-parity Python ports of Astromancer's variable-star computations.

Important files:

- `lightcurve.py`: source-row merging, differential magnitudes, and propagated
  errors.
- `periodogram.py`: the error-weighted Lomb-Scargle calculation and fixed grid.
- `folding.py`: phase folding, display duplication, and error-bar alignment.
- [extraction.md](extraction.md), Light Curve and Periodogram: upstream source
  provenance, preserved quirks, and the retired TypeScript extraction record.

## `algorithms/skylib_lite/`

Consolidated local subset of Skynet's `skylib` used by the extracted Python
algorithm packages.

Important files and subfolders:

- `astrometry/`: astrometry.net subprocess backend, ATLAS triangle solver,
  solver data, and related types used by `algorithms.wcs`.
- `calibration/`: background estimation and SEP compatibility helpers.
- `extraction/`: SEP-based source extraction and centroiding.
- `io/`: FITS compression/HDU selection helper used by the WCS solver stack.
- `photometry/`: aperture photometry, exact aperture sums, and exposure helpers.
- `util/`: angle, FITS, overlap, and statistics helpers shared across WCS,
  photometry, and field calibration.

Current caveats:

- This is vendored legacy science code. Architecture work should move imports
  and package boundaries only; numerical fixes belong in targeted remediation
  PRs with tests.

## `algorithms/photometry/`

Extracted Python source-extraction and aperture-photometry code from Skynet.

Primary responsibilities:

- Extract image sources with the vendored SEP-based detector.
- Build WCS objects from FITS headers for source coordinate conversion.
- Run aperture or automatic photometry on detected/provided sources.
- Preserve legacy Afterglow numeric behavior around WCS application, centroided
  positions, and aperture-correction settings.

Important files:

- `source_extraction.py`: FITS-header WCS construction and source
  extraction entry points.
- `photometry.py`: `run_photometry` over explicit detections and optional WCS/background inputs.
- `schemas.py`: Pydantic settings and data models.
- `algorithms.skylib_lite`: vendored algorithmic core for aperture photometry,
  exact aperture overlap, centroiding, background estimation, and statistics.
- [extraction.md](extraction.md), Photometry: source provenance, dependency
  requirements, parity behaviors, and verification.

Current caveats:

- `numba` and `sep` are hard runtime requirements.
- Full parity checks need real FITS fixtures and native science dependencies.
- This folder intentionally owns photometry, not WCS plate solving or field
  calibration.

## `algorithms/query/`

Extracted Python remote catalog access from Skynet and Afterglow.

Every network call in the catalog path. Sits above `algorithms.catalogs` and imports
it; never the reverse.

Primary responsibilities:

- Query VizieR-hosted catalogs: derive the column list, issue box/circle/object
  queries, map rows onto `CatalogSource`.
- Query SDSS through SkyServer SQL, which VizieR does not serve.
- Narrow a catalog list to those that can resolve an image's filter.
- Build query regions from solved WCS, clip results to the detector, deduplicate
  across overlapping fields.
- Resolve free-text identifiers against SIMBAD.
- Keep the astroquery response cache pruned, and keep cache failures from
  failing queries.

Important files:

- `registry.py`: the live, queryable catalog registry — the usual entry point.
- `runner.py`: orchestration; `query_catalogs` and `query_catalogs_for_image`.
- `vizier.py`: the VizieR engine.
- `sdss.py`, `skymapper.py`: the two catalogs needing their own backend.
- `binding.py`: joins declarations to backends through the MRO.
- `selection.py`: filter-aware catalog selection.
- `geometry.py`: sky and image geometry — pure, no network.
- `cache.py`, `config.py`: astroquery cache policy and settings seam.
- `simbad.py`: identifier resolution.
- [extraction.md](extraction.md), Query: provenance, seams cut, preserved
  behaviours, verification.

Current caveats:

- Recorded APASS/VSX provider rows are exercised, and opt-in APASS live coverage
  exists. Other response-shape and cache-validation gaps remain; see VAL-02 in
  [the master continuation plan](working/master-continuation-plan.md) and the
  Query verification section of [extraction.md](extraction.md).
- Live remote calls must stay out of default checks; see the repository
  conventions.

Configuration (environment, read by `config.py`'s `QuerySettings`):

- `VIZIER_SERVER`: VizieR mirror hostname, defaulting to `vizier.cds.unistra.fr`.
- `VIZIER_CACHE_ENABLED`: whether astroquery caches responses on disk
  (default on).
- `VIZIER_CACHE_AGE_DAYS`: cache retention, defaulting to 30.

With the cache enabled, query regions are snapped to a fixed grid so that
near-identical fields share a cache entry. This is observable near a field
edge; see [extraction.md](extraction.md), Query §5.1.

## `algorithms/wcs/`

Extracted Python astrometric WCS-calibration code from Skynet.

Primary responsibilities:

- Extract bright sources for plate solving.
- Derive coordinate, scale, and parity hints from settings and FITS headers.
- Try astrometry.net through the system `solve-field` binary.
- Fall back to the in-process ATLAS triangle solver against local UCAC data.
- Validate candidate solutions and write accepted WCS metadata to FITS headers.

Important files and subfolders:

- `wcs.py`: main plate-solving pipeline, exposed as `solve_wcs`.
- `source_extraction.py`: source list and FITS-header WCS helpers.
- `header_utils.py`: pixel-scale and RA/Dec guessing from FITS headers.
- `schemas.py`: WCS settings and data models.
- `config.py`: environment-backed solver configuration seam.
- `results.py`: `WcsSolveMetadata` and `WcsSolveResult`, the frozen dataclasses
  a solve returns. Replaced `state.py` (ORM-row stand-ins), which the stateless
  rollout deleted along with persistence.
- `algorithms.skylib_lite`: vendored astrometry stack, including astrometry.net and
  ATLAS backends.
- [extraction.md](extraction.md), WCS: full provenance, backend requirements,
  and validation notes.

Current caveats:

- End-to-end solving requires a configured backend: astrometry.net indexes plus
  `solve-field`, or a local UCAC4/UCAC5 catalog for ATLAS.
- Without solver data, imports still work and solves degrade to no solution.
- `numba`, `sep`, `scipy`, `astropy`, and Pydantic v2 are required for the real
  runtime path.

Configuration (environment, read by `tools.wcs` into a per-call
`SolverSettings`):

- `ANET_INDEX_PATH`: astrometry.net index directory, or `os.pathsep`-separated
  directories that hold index files directly.
- `ANET_TIMEOUT_S`: astrometry.net low-level solve-attempt limit in seconds
  (minimum 1).
- `ATLAS_CATALOG_ROOT`: local UCAC4/UCAC5 catalog root for the ATLAS fallback.
- `ATLAS_CATALOG`: catalog name, defaulting to `ucac5`.
- `ATLAS_TIMEOUT_S`: ATLAS matcher timeout in seconds.

The two backends serve different workflows. The normal order is
astrometry.net first, then ATLAS as its fallback. For a quick local solve of a
frame with trustworthy pointing and pixel-scale keywords, configure only ATLAS
(leave `ANET_INDEX_PATH` unset): ATLAS uses the header hints to narrow its
local UCAC triangle search. For a blind solve, configure astrometry.net: it
needs `solve-field` on `PATH` (or a supported `SKYLIB_*` override) and indexes
in `ANET_INDEX_PATH`. If neither is configured the package still imports, but
plate solving produces no solution.

The UCAC catalog is an operator-owned dependency, like the HR-diagram
isochrone grid: do not download, copy, or commit it under MARS. The supplied
UCAC5 tree on the development host is:

```bash
export ATLAS_CATALOG_ROOT=/srv/agents/catalogs/ATLAS/UCAC5
export ATLAS_CATALOG=ucac5
```

Supported layouts:

```text
# UCAC5: ATLAS_CATALOG_ROOT may be either directory
<root>/u5z/u5index.asc
<root>/u5z/z001 ... z900

# UCAC4: ATLAS_CATALOG_ROOT is the directory holding zone files
<root>/Z000.UC4 ... Z179.UC4
```

Reserve at least 6 GB for a local UCAC5 installation (the supplied tree is
5.3 GB) and at least 10 GB for UCAC4 (about 8.5 GB). Verify the reader can
instantiate and query the catalog without network access before a solve:

```bash
uv run python -c "from pathlib import Path; from algorithms.skylib_lite.astrometry.atlas.catalog import get_catalog_spec; import os; root = Path(os.environ['ATLAS_CATALOG_ROOT']); catalog = os.environ.get('ATLAS_CATALOG', 'ucac5'); index = get_catalog_spec(catalog).index_factory(root); result = index.query_box(0.0, 0.25, -0.1, 0.1); print(f'{catalog}: {len(result.ra_deg)} stars in preflight box')"
```

The operator-only ATLAS validation route:

```bash
ATLAS_CATALOG_ROOT=/srv/agents/catalogs/ATLAS/UCAC5 ATLAS_CATALOG=ucac5 \
  uv run pytest tests/test_wcs_solution.py::test_atlas_looks_up_operator_catalog_with_an_explicit_scale_window -v
```

For blind astrometry.net validation on the development host, use the indexes
under `/srv/agents/catalogs/astrometry` rather than the ATLAS catalog tree.
