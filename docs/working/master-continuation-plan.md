# MARS release closure gate

Updated 2026-10-26 against `main` at `9544782` (M3 PR #122), with all ten M2 checkpoints
closed locally on the single working branch `feature/m2`. It includes the
channels-and-axes checkpoint at `27bdceb`.
M0 and M1 are closed. M1 merged through PR #118; its changes are absent from
the published `0.1.0rc6`. Publication remains deferred until the remaining
gates below have been worked through. The next release needs a new version.

M2 is complete locally; its changes remain unmerged and unpublished. Other
release gates below remain open. PR #120 is abandoned as an implementation path and supplies no closure evidence. Reassess
its subjects against main along with the rest of M2; do not continue from that
branch or count its tests as acceptance.

This is the working document for all manual step gates, review-fix status and
closure evidence; keep those updates here rather than in separate gate plans.
Each unchecked item describes a failure or a specific unanswered question.
Close it with evidence of the required behavior, or an explicit maintainer
decision to retain the limitation and tell users about it. Check old reports
against current callers before treating them as current bugs. Passing tests
that preserve an old answer does not establish that it is right. This checklist
states what needs to change or be verified; implementation choices belong in
the subsequent work.

## M2: results must mean what their labels and units say

**Complete on `feature/m2`, including the comprehensive-review fixes in
`71d3a80`.** The changes are pushed for review, unmerged and unpublished.
Other release gates remain open. Technical derivations and detailed acceptance
evidence are linked below; this section records outcomes and remaining limits.

- [x] **Pulsar channels and axes.** Results, saved spectra and plots preserve
  the selected channel and consistently identify periods in seconds and
  frequencies in hertz. Legacy artifacts warn when channel metadata is missing
  or confidence levels are uncalibrated.
  [Evidence](../../tests/test_pulsar_spectrum_semantics.py).
- [x] **Pulsar candidates and confidence.** Candidates expose both period and
  frequency; bounds and evaluated trial counts describe the actual search.
  Sampling heuristics and conditional Gaussian false-alarm assumptions are
  explicit. Stable centering and residual fitting handle representable variation;
  constants are rejected and unresolved bounds warn. Older M2 spectra require
  recomputation before their thresholds are treated as current. The bound and
  empirical fold SNR are not pulsar probabilities; correlated noise, interference
  and repeated retuning remain outside the calibration.
  [Acceptance and limits](../analysis/pulsar-candidates-confidence.md).
- [x] **Variable-star powers and errors.** Weighted powers use consistent
  floating-mean least squares and remain stable across response amplitudes.
  Differential errors use independent quadrature; old cached errors are
  rederived. Results identify units, normalization and excluded uncertainty
  sources. Invalid or degenerate inputs have defined failures.
  [Acceptance and limits](../analysis/variable-star-powers-errors.md).
- [x] **Cluster ages and membership.** Legacy ages use the correct units and
  source joins use exact identifiers. Selection accepts measured zero motion,
  rejects missing/nonfinite components and handles degenerate boundaries.
  These legacy helpers remain distinct from registered membership tools; no
  membership probability is claimed.
  [Acceptance and scope](../analysis/cluster-ages-membership.md).
- [x] **Legacy coordinates, extinction and mass.** Sexagesimal signs, including
  negative zero, are preserved. Extinction honors its supported domain and
  supplied parameters. Motion scatter, radius and mass outputs identify their
  units and proxy assumptions. Protected radius/mass conversions are unchanged.
  [Acceptance and limits](../analysis/legacy-coordinates-extinction-mass.md).
- [x] **Accepted sky positions and reference stars.** Position checks and
  reference queries use solved WCS geometry in a consistent sky frame. Invalid
  and singular solutions are rejected before header writes. Footprints account
  for rotation, displaced reference pixels, seams and poles; sampled distortion
  coverage remains an estimate. Southern fallback coordinates retain their sign.
  [Acceptance and scope](../analysis/accepted-sky-positions.md).
- [x] **Photometric calibration.** Small-sample rejection, heterogeneous errors
  and fitted scatter are handled consistently. Saturation/brightness selection,
  zero magnitudes and explicit gain settings are respected. Solver and plots
  share the surviving rows; empirical errors avoid cancellation. Differences
  from historical fits are disclosed rather than hidden by changed fixtures.
  [Acceptance and limits](../analysis/photometric-calibration.md).
- [x] **Catalog magnitudes and filters.** Selection, numeric resolution and
  reporting share production filter precedence and preserve native band
  identities. Existing transforms, including H-alpha, are unchanged. Retained
  approximations and relative narrowband references are disclosed. Live catalog
  comparisons were recorded on 2026-10-23; the offline run below does not repeat
  those queries.
  [Acceptance and live evidence](../analysis/catalog-magnitudes-filters.md).
- [x] **Catalog coverage and sufficiency.** Queries enclose and clip to detector
  footprints, including seams, poles and cache rounding. Raw response caps,
  unqueried fallback catalogs and failed variable-star checks remain visible.
  Fits report actual survivors and disclose unverified sample sufficiency;
  distorted-footprint coverage is not guaranteed complete.
  [Acceptance and limits](../analysis/catalog-coverage-sufficiency.md).
- [x] **Warnings and benchmark claims.** Tool results disclose retained numerical
  and calibration limits, including through handled failures. Memory failures
  retain `resource_limit`; HR artifact failures retain extraction notices.
  Author citations require matching returned metadata and preserve bibcode
  association across supported prose/table forms. The grammar is bounded and
  does not verify every factual claim. Historical benchmark scores remain
  attribution-unchecked until the original sessions can be regraded together.
  [Acceptance and limits](../analysis/warnings-benchmark-claims.md).

### M2 review corrections

The comprehensive audit's six findings are resolved: pulsar centering, singular
WCS acceptance, author-qualification scope, bibcode association, memory-error
classification and HR warnings after artifact failure. Regression tests cover
those failures and the subsequent review cases, including genuine disclaimers,
wrapped citations and table boundaries. No catalog/H-alpha transform,
calibration equation, public input or historical benchmark score was changed.

Evidence: [pulsar precision](../../tests/test_pulsar_probability_precision.py),
[WCS acceptance](../../tests/test_wcs_accepted_positions.py),
[attribution](../../tests/test_bench_attribution.py),
[public failure handling](../../tests/test_numerical_warnings.py).

### M2 validation and remaining checks

Recorded full offline run, 2026-10-26: **4,094 passed, 88 skipped, 220 warnings**
with Python 3.13.15, locked dependencies and MCP. Compilation, schema goldens,
generated guidance, repository shape and whitespace checks passed. The following
are Python/test warning events, separate from structured MARS tool warnings;
repeated reads of the same fixtures account for most of the count.

| Warnings | Count | Meaning |
| --- | ---: | --- |
| Astropy FITS header notices | 214 | Repeated date-to-MJD normalization notices (213), plus the textual `J2000` equinox regression (1). |
| Poorly conditioned polynomial fits | 2 | Deliberate single-source/degenerate calibration cases. |
| Masked value converted to NaN | 1 | A malformed provider-row regression exercises missing-position handling. |
| Invalid division | 1 | The retained empty-background-annulus defect is deliberately exercised and disclosed by the tool. |
| Overflow while squaring | 2 | Extreme synthetic flux tests reach the fold-SNR standard-deviation fallback. Spectral assertions pass; that auxiliary diagnostic retains an extreme-scale numerical limitation. |

| Skipped tests | Count | Reason |
| --- | ---: | --- |
| Live catalog/network queries | 77 | Opt-in `MARS_TEST_NETWORK` was disabled. |
| Live ADS grouping check | 1 | `ADS_DEV_KEY` was unavailable; the M3 verification remains open. |
| Live Ollama provider check | 1 | Opt-in `MARS_TEST_MODEL_API` was disabled. |
| Historical benchmark falsification | 4 | Original untracked run artifacts were absent. |
| Native Windows allocation control | 1 | Requires Windows. |
| Native solver/catalog prerequisites | 3 | Local UCAC configuration or astrometry.net binary/index configuration was unavailable. |
| Blind native plate solve | 1 | Pipeline returned no WCS and the test self-skipped. The skip message suggests index coverage; this run does not establish the cause. |

Skipped tests provide no passing evidence. In particular, the blind-solve skip
leaves native solver success unverified by this run. Live-service, native-platform
and solver-data acceptance retain their separate gates; conditional-noise,
sampled-distortion and catalog-sufficiency limitations remain explicit above.

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
  consistent with M2's corrected scientific contracts. Evidence: `tests/test_m3_lightcurve_helpers.py`, the updated
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
- [ ] **Provider response changes.** Renamed, missing or non-finite columns
  can make populated responses look empty. Landolt/USNO, SDSS, SkyMapper and
  SIMBAD mappings, Gaia/literature cluster steps and radio VizieR/NED chains
  need focused contract evidence. ADS `abs:`/`object:` grouping remains an
  unconfirmed workaround. Distinguish no matches from unusable responses.
  *Progress 2026-10-21 (not closed):* every listed mapping and chain was
  checked live and fixed where a populated response looked empty or escaped as
  an exception. Unusable responses now raise `ProviderResponseError` /
  `unusable_response`. Live findings fixed: Landolt crashed on every query, 2MASS
  lost every id to a column rename, B1950-only radio catalogs (3C among them)
  could never match, and cached SkyServer error pages made SDSS queries fail
  until expiry. Evidence: `tests/test_m3_provider_responses.py`, its `_live`
  counterpart, `docs/extraction.md` Query §5.12. **Open:** ADS `abs:`/`object:`
  grouping still needs one live run with `ADS_DEV_KEY` (the test is in place).
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

- [ ] **Real desktop use.** Installer and Fedora app-server checks do not
  establish use in the actual Claude and ChatGPT desktop apps. Record supported
  OS/app versions and demonstrate registration, calls, instructions, approvals
  and media. Missing macOS/Windows and other advertised-host evidence must
  remain explicit.
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
- [ ] **Configured solver success.** A blind WCS test can skip after failing
  even when resources exist, and omits configured settings. ATLAS reachability
  does not establish blind convergence. A supported known-solution fixture
  must solve within position, scale and rotation tolerances; missing data must
  be reported separately.
- [ ] **Scientific plot content.** Dimensions and specification strings do
  not prove that traces, peak markers or confidence lines are drawn. Verify
  supported plots' content, including both pulsar spectrum modes.

Evidence: [installation guide](../installing.md),
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
