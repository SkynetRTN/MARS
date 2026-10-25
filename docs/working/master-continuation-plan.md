# MARS release closure gate

Updated 2026-10-20 against `main` at `a6785aa`, after pulling the latest changes.
M0, M1 and M3 are closed. M1 merged through PR #118 and M3 through PRs #122
and #123; their changes are absent from the published `0.1.0rc6`. Publication remains deferred until the remaining
gates below have been worked through. The next release needs a new version.

M2 is open in full. PR #120 is abandoned as an implementation path and supplies
no closure evidence. Reassess its subjects against main along with the rest of
M2; do not continue from that branch or count its tests as acceptance.

Each unchecked item describes a failure or a specific unanswered question.
Close it with evidence of the required behavior, or an explicit maintainer
decision to retain the limitation and tell users about it. Check old reports
against current callers before treating them as current bugs. Passing tests
that preserve an old answer does not establish that it is right. This checklist
states what needs to change or be verified; implementation choices belong in
the subsequent work.

## M2: results must mean what their labels and units say

- [ ] **Pulsar channels and axes.** Sum and YY spectra are plotted as
  "Polarization XX" because saved spectra omit the selected channel. Frequency
  spectra use the period chart's label and logarithmic axis. Artifacts, plots
  and metadata must identify the actual channel and distinguish seconds from
  hertz, including older artifacts whose channel is unknown.
- [ ] **Pulsar candidates and confidence.** `top_peaks.x` changes units by
  mode, so callers can fold at the wrong period. Candidate and search-bound
  units must be unambiguous. Confidence counts grid points as independent
  trials; the search limit uses mean spacing despite gaps. Their scientific
  meaning still needs validation.
- [ ] **Variable-star powers and errors.** Weighted spectra mix weighted and
  unweighted normalization, changing the reported strength of periodic signals;
  differential errors are divided by two. Powers and uncertainties need
  independent scientific checks before being presented as reliable measurements.
- [ ] **Cluster ages and membership.** Legacy HR helpers discard ages above
  13.8 million years, can miss ID `10` when joining IDs in numerical versus
  alphabetical order, and exclude exactly zero proper motion. Supported
  results must retain valid old clusters, matching sources and zero motions.
- [ ] **Legacy coordinates, extinction and mass.** Negative sexagesimal
  coordinates lose their sign; W1 extinction returns zero outside the
  implemented law; the extinction multiplier ignores a non-default `rv`.
  The V-band wavelength and velocity-dispersion statistic also need scientific
  checks. Establish which current results use these helpers and which values
  are valid. The newer HR fitter's corrections do not close these legacy
  issues. The cancelling mass/radius unit factors are not a separate bug.
- [ ] **Accepted sky positions and reference stars.** Without a scale hint,
  the WCS position check can admit a distant solution. After an ATLAS solve,
  reference stars are queried around the original hint rather than the solved
  field. The southern-declination fallback returns zero. Accepted positions
  and reference-star coverage must describe the actual image.
- [ ] **Photometric calibration.** Outlier rejection does not run for ten
  or fewer calibration stars; brightness trimming can retain saturated stars
  and mishandle magnitude zero. The fit reports extra scatter even when
  measurement errors explain the residuals, and explicit gain `1` can be
  replaced by the FITS header. Selection, uncertainties and the gain used must
  agree with the requested measurement.
- [ ] **Catalog magnitudes and filters.** Photographic B/R and Tycho BT/VT
  are offered under standard band names; UCAC's Open magnitude can satisfy
  every filter; catalog-name mismatches prevent some transform lookups.
  Catalog selection and magnitude calculation disagree on H-alpha values.
  Establish the supported bands and validity of J-K, APASS I and SkyMapper
  conversions and narrowband zero points.
- [ ] **Catalog coverage and sufficiency.** Polar footprints can omit stars;
  brightness-limited responses and stopping at the first nonempty catalog can
  leave a biased or insufficient calibration sample. SkyMapper also changes
  caller constraints. Results must disclose incomplete coverage and inadequate
  calibration, and one query must not change later queries.
- [ ] **Warnings and benchmark claims.** Reachable retained numerical bugs
  are not consistently disclosed in tool results. The answer grader can accept
  invented author attribution when numbers are sourced. Users need relevant
  limitations, and benchmark conclusions must account for attribution errors.

Evidence: [pulsar tool](../../tools/pulsar.py),
[legacy HR helpers](../../algorithms/hrdiagram_py/legacy.py),
[algorithm review](../analysis/algorithm-remediation-plan.md),
[pulsar review](../analysis/pulsar-pipeline-review.md),
[benchmark results](../benchmarking/results.md).

## M3: failed inputs and services must produce usable failures

- [x] **Catalog lookup failures.** SDSS named-object lookup still calls
  `query_object`; M1 repaired only regions. APASS U references an unavailable
  band. SIMBAD's first initialization failure disables resolution for the
  process lifetime. Lookups must return data or explain the specific failure,
  and transient failure must have defined recovery.
  *Closed:* SDSS objID lookup uses the bounded, quality-filtered SQL contract,
  batched under SkyServer's 2,048-byte URL limit, and leaves non-objID names
  out; APASS U returns `unsupported_filter` naming the missing `uprime` and
  catalogs with a real U transform before any query; a failed SIMBAD probe is
  retried after 30 s, and `resolve_target` and `search_casda` report an outage
  as `provider_unavailable` (a missing astroquery as `dependency_missing`),
  not `not_found`. Evidence: `tests/test_m3_catalog_lookup_failures.py`
  (offline) and `tests/test_m3_catalog_lookup_live.py` (`network`; passed
  2026-10-21 against live SkyServer, SIMBAD, VizieR APASS and CASDA with an
  empty astroquery cache), `docs/extraction.md` Catalogs §5.7 and Query updates.
- [x] **Malformed calibration inputs.** Confirm reported failures with mixed
  catalog row shapes/epochs, absent coordinates, missing FWHM in adaptive
  apertures and degenerate zero-point header writes. These cases must not
  escape as exceptions or advertise a usable calibration. Reproduced live
  2026-10-21: a U-band NGC 5128 calibration with default catalogs selects
  SkyMapper, whose rows carry `numpy.int32` ids, and field calibration's
  `CatalogSource` revalidation rejects them as `field_calibration_failed`.
  *Closed:* all four reports and the live integer-id failure reproduced, then
  fixed in field calibration: integer ids are coerced, epochs no longer abort
  matching, positionless rows and non-finite magnitudes are left out (with
  specific errors when nothing usable remains), solves without a finite zero
  point and positive uncertainty raise `DegenerateCalibrationError` before any
  header write (`no_solution` from both calibration tools), and `mode="auto"`
  receives the detected FWHM. Refusing a single-star solve diverges from
  upstream, which returns it with a NaN error. Evidence: `tests/test_m3_calibration_inputs.py`,
  `tests/test_m3_calibration_inputs_live.py` (`network`, live SkyMapper and
  UCAC), `docs/extraction.md` Field Calibration §5b. The live runs show
  SkyMapper and UCAC B zero points 1.27 and 0.72 mag from APASS through the
  preferred-band fallback and the UCAC wildcard; that is M2's catalog
  magnitudes and filters item, not validated here.

- [x] **Direct light-curve helpers.** Missing errors can misalign variable
  folds; all-null dates raise; constant weighted spectra retain NaNs; empty peak
  selection has an unfinished helper contract. Legacy histograms fail on
  singleton or tied data. Public spectrum guards already exist; remaining
  supported helper calls need defined results for these inputs.
  *Closed:* each input reproduced, then given a defined result. Folds pair
  every point with its own bounds (`None`, masked by the tool with an
  `unbounded_points_folded` warning, when a row lacks a combined error) and
  return `([], [])` when nothing folds. An undated baseline is `0.0`; constant
  or non-finite weighted spectra raise `ValueError`, matching the pulsar
  helpers. Peak selection ignores non-finite power. Singleton/tied histograms
  return one bin, Sturges' rule or the value itself. Ordinary results are
  unchanged. Evidence: `tests/test_m3_lightcurve_helpers.py`, the updated
  pinned tests, and `docs/extraction.md` (Python M3 direct-helper contracts).
- [x] **WCS setup and I/O failures.** Recheck no-hint ATLAS input and textual
  equinoxes such as `J2000`. Missing binaries, bad catalog roots and a full
  output disk must be distinguishable from a genuine no-solution result.
  *Closed:* rechecked, and all three still reproduced. ATLAS without a hint
  is skipped with a named reason instead of `TypeError`. `J2000`/`B1950`
  equinoxes keep the hint (a J2000-only M15 frame now solves live).
  `WcsSolveMetadata.solver_failures` records a missing `solve-field`, a bad
  catalog root and a full disk on every path, labelled by backend, so only an
  empty list without a WCS is `no_solution`. Evidence:
  `tests/test_m3_wcs_failures.py`, live runs with the operator solver data,
  `docs/extraction.md` WCS §9. The `solver_data` blind test still skips
  because it omits configured settings, which is M4's.
- [x] **Provider response changes.** Renamed, missing or non-finite columns
  can make populated responses look empty. Landolt/USNO, SDSS, SkyMapper and
  SIMBAD mappings, Gaia/literature cluster steps and radio VizieR/NED chains
  need focused contract evidence. ADS `abs:`/`object:` grouping remains an
  unconfirmed workaround. Distinguish no matches from unusable responses.
  *Closed:* every listed mapping and chain was checked live and fixed where a
  populated response looked empty or escaped as an exception; unusable
  responses raise `ProviderResponseError` / `unusable_response`. Live findings
  fixed: Landolt crashed on every query, 2MASS lost every id to a column
  rename, B1950-only radio catalogs (3C among them) could never match, and
  cached SkyServer error pages made SDSS queries fail until expiry. The ADS
  grouping was never the cause: live with a key (2026-10-22), the search
  rejects `object:` in every form, so `object_name` never worked. `tools.ads`
  now translates it through `POST /v1/objects/query` first, parses all result
  pages together (any result past the first page used to crash), and refuses
  the sorts, years, doctypes and query syntax ADS silently ignores as
  `invalid_input`. Evidence: `tests/test_m3_provider_responses.py`, its
  `_live` counterpart (19 passed with `ADS_DEV_KEY`), `docs/extraction.md`
  Query §5.12, PR #123. ADS moves to Science Explorer (SciX) on 2026-11-16;
  the API and tokens are stated to carry over, and on 2026-10-22 the same
  token answered on `api.scixplorer.org`. By maintainer decision the item is
  closed now, and the post-cutover rerun of the live ADS tests is tracked
  outside this plan. The token and search-syntax links shown to users still
  name ADS, whose links SciX will redirect; SciX's own URLs could not be
  confirmed before the cutover.
- [x] **Pulsar controls.** Background subtraction and plot labels, background
  and size controls exist in Python but are hidden from registered callers.
  State which are supported publicly; schemas and skill guidance must match.
  *Closed:* stated in `docs/pulsar-tool-pipeline.md` §6b. Background
  (`back_scale`, `subtract_background`) is public on `load_pulsar_lightcurve`
  only, where it always applies. `sonify_pulsar` no longer offers it, since it
  is ignored for the artifact the pipeline passes. Plot labels and sizes,
  `cal`, sonify `phase`, `max_input_seconds` and `sample_rate` stay
  Python-only, with reasons. The stage-2 description, prompt and skill now
  say to retune `back_scale` by rerunning stage 1. Ignored settings warn
  `background_settings_ignored`. Evidence: `tests/test_m3_pulsar_controls.py`
  and regenerated schema goldens.

Evidence: [query backends](../../algorithms/query/),
[coverage and remaining gaps](../../tests/README.md),
[registered schemas](../../tools/registry.py).

## M4: supported installations and real solver runs must work

- [x] **Real desktop use.** Installer and Fedora app-server checks do not
  establish use in the actual Claude and ChatGPT desktop apps. Record supported
  OS/app versions and demonstrate registration, calls, instructions, approvals
  and media. Missing macOS/Windows and other advertised-host evidence must
  remain explicit.
  *Done 2026-10-23,* by the maintainer, following
  [desktop-acceptance.md](../archive/desktop-acceptance.md): Claude Desktop with the
  `.mcpb` verified on an Apple Silicon Mac and x64 Windows, and Codex in the
  ChatGPT app on x64 Windows and Linux (Fedora Workstation). Claude Desktop
  on Linux is closed (no build). Codex on the Mac is accepted untested: the
  maintainer's macOS VM blocks Codex messages by workspace settings (Issue
  #51667), and the route is the Unix one verified on Fedora; test it on a
  physical Mac when one is available.
- [x] **Desktop install guides.** Once real desktop use is verified, archive
  the desktop guide and fold its Claude Desktop and Codex install steps into
  per-platform guides under `../installing/`: Windows (x64), macOS (Apple
  Silicon) and Linux (ARM), with the verified OS and app versions.
  *Done 2026-10-23:* [Windows](../installing/windows.md),
  [macOS](../installing/macos.md) and [Linux](../installing/linux.md), linked
  from `../installing.md`, which stays where it is because shipped wheels and
  the `.mcpb` manifest link to it; the guide is
  [archived](../archive/desktop-acceptance.md). No OS or app versions were
  recorded, so the guides name none.
- [ ] **Updates and offline startup.** Both launchers follow the latest
  release; only Claude has a cached offline fallback. Plugin skills can lag
  behind the server, and the native skill installer rejects older pristine
  copies. Upgrade, startup failure, offline use and rollback need documented,
  verified behavior that preserves user changes.
- [ ] **Installed commands and data.** `mars-bench` ships without its
  checkout-only assets. Verify its installed behavior and cross-platform bundle
  installation, interruption and recovery. Record current cold/warm startup
  where host timeouts matter. Claude's MCPB is built manually and is absent
  from release assets; the advertised installation route must say so.
  *In progress:* the release workflow now packs `mars.mcpb`, runs its launch
  command through `self-test` against the release build on macOS and
  Windows runners, and attaches it to the GitHub release; the install guide
  says which releases carry it. No release has shipped it yet, and the
  workflow job has not run.
- [ ] **Configured solver success.** A blind WCS test can skip after failing
  even when resources exist, and omits configured settings. ATLAS reachability
  does not establish blind convergence. A supported known-solution fixture
  must solve within position, scale and rotation tolerances; missing data must
  be reported separately.
- [ ] **Scientific plot content.** Dimensions and specification strings do
  not prove that traces, peak markers or confidence lines are drawn. Verify
  supported plots' content, including both pulsar spectrum modes.
- [ ] **Console first launch.** An installed `mars` with no key or reachable
  model exits before its interface opens, telling the user to edit "the
  repository's .env", which an installed copy has neither of nor reads.
  `../installing.md` does not cover the console, and the default Ollama
  model's `-mlx` tag may exist only on Apple Silicon. A clean install on
  each supported OS must reach a working session or an accurate next step.
- [ ] **Console terminals and long runs.** Nothing records the console in
  Windows Terminal, macOS Terminal or iTerm2, tmux or over SSH. Open
  questions: F-keys on macOS, Esc delay under tmux, the graphics probe, the
  forced dark theme on light terminals, `NO_COLOR`, and an 80-column status
  line that cuts off the stop hint and never names a quit key. Esc cannot
  stop a running tool, quitting during a plate solve may wait for it, and
  progress reads in raw milliseconds. Record supported terminals and the
  measured stop and quit behavior during a real solve.
- [ ] **Console failures and commands.** A tool that returns an error is
  marked ✓, and a backend failure mid-turn reports only "Session finished:
  error." `/status`, `/tools`, `/approve`, `/prompt` and `/new` are listed
  in the menu and `/help` but have no handler, so context can be cleared
  only by restarting. Approval needs the mouse or Tab focus, and Esc's
  effect on an open approval is unclear. Failures must name their cause and a
  next step, approvals must work from the keyboard, and each listed command
  must work or be removed. Resume showing only assistant text needs a
  decision.

Animations, Markdown rendering, input history, notifications, inline
scrollback and theme memory are polish, not release requirements; add any of
them as a gate only with a failing supported use case.

Evidence: [installation guide](../installing.md),
[console](../../tools/tui/),
[Claude installer](../../installers/claude-desktop/README.md),
[Codex installer](../../installers/codex/README.md),
[test coverage](../../tests/README.md).

## M5: resolve the specific older reports that remain unverified

These are questions to check, not newly confirmed bugs. Record whether each is
reachable now, what it does, and whether the release needs a change or caveat.

- [ ] **Coordinates and image geometry.** Check whether RA strings are read
  as hours instead of degrees, scale keywords get wrong units, or rotated and
  unequally binned images lose sky coverage. Other reports describe lost stars
  near poles/RA zero, CRPIX at image edges failing, fields wider than 360 degrees
  shrinking, and stripped headers yielding impossible field sizes. Establish
  whether valid small-field triangles are rejected, far-side stars project
  nearby, source ellipses keep wrong axes, or catalog depth/epoch mismatch loses
  usable stars.
- [ ] **Measured flux and source position.** Do nonpositive fluxes appear
  valid, empty annuli omit sky subtraction, downsampling misplace saturated
  sources, or growth-curve neighbor checks fail? Check pixel origins,
  matching tolerances, SNR/fit weights and the tentative ellipse-clipping
  arithmetic report. M1's crash containment is already closed.
- [ ] **Repeated calls and FITS writes.** Check whether reusing settings,
  source arrays or headers changes later results; old coordinate-frame or
  distortion keywords survive a new solution; solvers interpret automatic
  image parity differently; or omitting flux bypasses the source-count limit.
- [ ] **Light-curve and HR boundaries.** Check period steps rounded to zero,
  maximum-time samples lost in binning, exact multiples assigned phase one,
  channels paired by index rather than phase and prefolded-file axes. Legacy
  isochrone splicing drops a point; luminosity framing and edge-on projection
  scales also need their intended meaning established.
- [ ] **Catalog parsing, caches and identity.** Check whether padded filter
  names fail, zero values disappear, Landolt/Stetson expressions request
  nonexistent columns, or SIMBAD loses common object types. Can cache rounding
  omit edge stars, cache failures break queries, invalid values look absent,
  or APASS IDs change after re-ingestion? Confirm UCAC disk layout against an
  actual zone and its specification before claiming a reader defect.
- [ ] **Obsolete reports and instructions.** Close retired helper reports
  after checking for surviving callers. Reconcile Python 3.13-only agent-guide
  wording with current Python 3.12/3.13 support and remove stale execution
  instructions. Recheck the calibration reference driver's swallowed failures
  against current replay evidence. Historical review text remains dated evidence.

Evidence: [original finding register](../analysis/algorithm-remediation-plan.md#9-full-finding-register),
[extraction and preservation record](../extraction.md),
[pre-rewrite dispositions and M1 acceptance](https://github.com/SkynetRTN/MARS/blob/a6785aa/docs/working/master-continuation-plan.md).

## M6: record the release decision and its limits

- [ ] **Scope decisions.** Eager domain imports, generic package-name
  collisions, heavy base dependencies and HR code's dependence on application
  configuration need a failing supported use case before becoming release
  requirements. Output schemas, new transports, local catalog backends and
  new timing capabilities require separate decisions. Browser hosting remains
  deferred. The unpinned external Skynet review does not establish MARS bugs
  and is not a prerequisite for this release.
- [ ] **Release evidence.** Record the final merged revision and outstanding
  user-visible limitations. Run supported Python suites, installed-wheel
  source/data/skill/protocol checks, native runtime checks and security/workflow
  jobs; identify skipped external checks. Keep benchmark claims within the
  tested corpus and disclose provider-dialect and corpus-selection biases.
  Formal review is not required by the existing maintainer decision.

M0/M1 acceptance remains in the linked baseline record. Do not reopen completed
containment work or infer that merged changes protect rc6 users. Release once
unchecked work has recorded outcomes and final checks pass; the
[release procedure](../releasing.md) owns publication.
