# MARS release closure gate

Updated 2026-10-23 against `main` at `9544782` (M3 PR #122), with the first nine M2 checkpoints
closed on the single working branch `feature/m2`. Keep the remaining M2
work on this branch. It includes the channels-and-axes checkpoint at `27bdceb`.
M0 and M1 are closed. M1 merged through PR #118; its changes are absent from
the published `0.1.0rc6`. Publication remains deferred until the remaining
gates below have been worked through. The next release needs a new version.

M2 remains open after the first nine checkpoints
below. PR #120 is abandoned as an implementation path and supplies no closure evidence. Reassess
its subjects against main along with the rest of M2; do not continue from that
branch or count its tests as acceptance.

Each unchecked item describes a failure or a specific unanswered question.
Close it with evidence of the required behavior, or an explicit maintainer
decision to retain the limitation and tell users about it. Check old reports
against current callers before treating them as current bugs. Passing tests
that preserve an old answer does not establish that it is right. This checklist
states what needs to change or be verified; implementation choices belong in
the subsequent work.

## M2: results must mean what their labels and units say

- [x] **Pulsar channels and axes.** New spectrum artifacts retain the selected
  channel and attach seconds or hertz to their coordinate column. Plots and
  their metadata identify Sum, XX or YY; period spectra use logarithmic seconds
  and frequency spectra use linear hertz. Both label spectral power and include
  units on peak coordinates. Older artifacts with missing or unrecognized
  channel metadata show "Unknown channel" and warn, while their saved coordinate
  column determines the axis even without a reliable mode flag. Non-string
  channel metadata also takes that fallback. Standard-format single-flux
  spectra use "Data" without claiming a polarization, preserving the selected
  `sum` or `source1` channel. Evidence:
  [spectrum acceptance tests](../../tests/test_pulsar_spectrum_semantics.py)
  inspect actual matplotlib traces, axes, peak markers and confidence lines
  across all three channels and both modes, plus legacy artifacts.
  Validation: Python 3.13.15 with locked dependencies and `[mcp]`, full offline
  suite **3,409 passed, 49 skipped**; compileall, generated-skill consistency
  and `git diff --check` pass. Skips retain the live-service, untracked benchmark,
  native Windows and external solver-data gates. Changes are local to this
  feature branch and are not in published `0.1.0rc6`.
- [x] **Pulsar candidates and confidence.** Every candidate exposes `period_s`,
  `frequency_hz` and `power` in either mode; search bounds have `search_unit`,
  and `evaluated_trials` counts the actual saved grid. Defaults use twice
  median positive spacing through 3 s (the reciprocal frequency band).
  Irregular epochs get an explicit search heuristic and warning, with no
  claimed hard Nyquist limit; all stages rederive sampling from the data.
  Legacy confidence fields return null/empty. Their replacement is a
  finite-sample Gaussian-noise tail with a Bonferroni union bound over actual
  trials, without assuming independent frequencies. Numerically degenerate
  Nyquist trials use a stable SVD projection. Results/plots state the noise
  model; old artifact thresholds are uncalibrated. Independent review's
  maximum-power endpoint defect is corrected: directly fitted RSS/TSS retains
  the resolvable tail near `1.05e-8` in its four-sample reproduction. Fits below
  estimated solver resolution return null and warn; this estimate is not a
  certified numerical error enclosure. Threshold inverses use 80-digit Decimal
  arithmetic isolated from host Decimal settings, round toward larger powers
  and omit unrepresentable levels with a warning. Earlier Gaussian artifacts
  without the residual-statistic marker also plot as uncalibrated; see the
  [review correction](../analysis/pulsar-candidates-confidence.md#review-follow-up-endpoint-probability-correction).
  Exact constants, including fractional values whose rounded means fabricate
  positive variance, fail before power/significance evaluation; public results
  return `invalid_input` without a spectrum or noise bound. One-ULP variation
  remains accepted. Neither the bound nor
  empirical fold SNR is a pulsar/correct-period probability. Correlated or
  filtered radio noise, RFI and repeated retuning remain outside that model.
  Evidence: [derivation and acceptance record](../analysis/pulsar-candidates-confidence.md),
  [independent references and regressions](../../tests/test_pulsar_candidates_confidence.py),
  [34 numerical precision regressions](../../tests/test_pulsar_probability_precision.py),
  and actual rendered threshold checks in both modes. All five scans complete;
  only B0329 matches its reference at the revised defaults. Frozen historical
  benchmark verdict keys remain unchanged; no model sweep was rerun/regraded.
  Latest review follow-up: exact-constant regressions passed after eight observed
  failures; independent review found no remaining issues and verified 44
  nonconstant controls bit-for-bit against pre-fix results. Validation:
  Python 3.13.15, full offline suite **3,812 passed, 75 skipped**;
  compileall, schema goldens, generated-skill consistency, repository shape and
  `git diff --check` pass. The changes remain local, unmerged and unpublished.
- [x] **Variable-star powers and errors.** Weighted floating-mean least squares
  uses the same inverse-variance weights for the response, fitted columns and
  reference variance. Standard power in [0, 1] is fractional weighted chi-square
  improvement, not a detection probability. Response offsets are scaled before
  squared energies to preserve powers at tiny and large amplitudes. SVD uses
  an estimated solver/phase resolution policy for collapsed aliases; exact constants remain rejected
  publicly. Differential standard errors use independent quadrature without
  halving; covariance, shared systematics and uncertainty in the fixed reference
  magnitude are excluded. Public stages rederive old cached errors from source
  components, reject unrepresentable full error bars and identify days,
  magnitudes, normalization and uncertainty convention in results/artifacts.
  The period grid, work bounds and fold ordering remain. Evidence:
  [derivation and acceptance record](../analysis/variable-star-powers-errors.md),
  [25 scientific regressions](../../tests/test_variable_star_science.py),
  independent Astropy/full-model QR comparisons and public ECSV handoffs.
  Review found and verified constant-series and response-amplitude corrections;
  final review has no outstanding findings. Validation: Python 3.13.15,
  full offline suite **3,503 passed, 49 skipped**; compileall, schema goldens, generated-skill
  consistency, repository shape and `git diff --check` pass. M3 subsequently
  defines direct constant rejection and masked missing fold bounds; the
  [integration record](../analysis/m2-m3-integration.md) checks coexistence with
  M2's science. M2 changes remain local, unmerged and unpublished.
- [x] **Cluster ages and membership.** Legacy HR helpers convert MWSC log-year
  ages to Myr within the retained 13.8 Gyr display window, keeping valid old
  clusters. FSR joins use exact IDs independent of source/result order and
  numeric conversion; source order, in-place updates and first duplicate
  results are retained. Membership accepts finite zero proper motion and
  rejects missing/nonfinite components, including with unbounded selection.
  Zero-width ellipse axes define closed lines or points. Post-commit review
  corrected NumPy integer-age arithmetic and exact decimal ellipse endpoints
  while rejecting immediately adjacent outside values. These exported legacy
  helpers have no registered-tool callers; the separate registered membership
  implementation already accepts zero motion, verified through its written
  ECSV output. No membership probabilities are claimed. Evidence:
  [scope and acceptance record](../analysis/cluster-ages-membership.md),
  [34 regressions](../../tests/test_cluster_ages_membership.py), and independent
  follow-up review with no outstanding findings. **73 cluster/HR tests** pass.
  Validation: Python 3.13.15, full offline suite **3,514 passed, 49 skipped**;
  compileall, schema goldens, generated-skill consistency, repository shape and
  `git diff --check` pass. Changes remain local, unmerged and unpublished.
- [x] **Legacy coordinates, extinction and mass.** Signed DMS/HMS triples carry
  the angle's sign in their first component, including negative zero below one
  degree/hour. The legacy CCM89 IR/optical helper rejects unsupported WISE
  bands, honors R(V) throughout, propagates it through plot parameters and uses
  nominal V wavelength 0.55 microns. Supported domains and monochromatic
  passband limitations are explicit. The old trimmed radial mean is replaced
  by observed isotropic one-dimensional PM RMS about the supplied center,
  with no intrinsic/noise-free dispersion claim. Summaries identify units,
  methods and limitations: projected number radius and eta=10 virial mass
  proxy, with unverified structural/equilibrium assumptions. Protected mass
  and radius conversion arithmetic is unchanged and independently checked.
  Caller searches found no registered-tool use of these exported legacy APIs;
  the newer HR fitter remains separate. Evidence:
  [derivation and acceptance record](../analysis/legacy-coordinates-extinction-mass.md),
  [51 scientific cases](../../tests/test_hrdiagram_legacy_science.py), independent
  Astropy/CCM89/Decimal references, and review with no outstanding findings.
  Validation: **144 focused tests passed**; Python 3.13.15 full offline suite
  **3,565 passed, 49 skipped**. Compileall, schema goldens, generated-skill
  consistency, repository shape and `git diff --check` pass. Changes remain
  local, unmerged and unpublished.
- [x] **Accepted sky positions and reference stars.** Missing-scale position
  checks now derive image size from the solved WCS, preserving the one-degree
  floor and three-diagonal tolerance. Header-WCS hints and candidate centres
  use ICRS; nonfinite/singular geometry is rejected before header write-back.
  ATLAS references use the solved centre and a padded, sampled outer-pixel
  footprint, including rotation, shear, offset CRPIX and SIP edge curvature.
  RA seams and pole-crossing follow-ups retain coverage with bounded queries;
  oversized footprints fail before catalog initialization. Southern no-WCS
  fallback coordinates retain their sign, including `-00` degrees. Evidence:
  [acceptance record and scope limits](../analysis/accepted-sky-positions.md),
  [19 pipeline cases](../../tests/test_wcs_accepted_positions.py), signed
  fallback regressions, independent analytical TAN/cap checks and fresh review
  with no outstanding findings. M3 PR #122 was integrated and validated in
  `160b3e4` before this work. Final Python 3.13.15 offline suite:
  **3,798 passed, 75 skipped**. Compilation, schema goldens, generated-skill
  consistency, repository shape and whitespace checks pass. Native convergence,
  sampled-distortion limits and catalog completeness retain their separately
  documented evidence gates. Changes remain local to `feature/m2`.
- [x] **Photometric calibration.** PHOT-03/09/10/14: rejection runs for small
  samples while retaining at least two stars; weighted residuals use each
  star's measurement error plus fitted scatter. The likelihood admits zero
  additional variance, preserves heterogeneous weights and compares positive
  minima with the boundary. Known saturated measurements are removed before
  brightness trimming, magnitude zero sorts normally, and explicit gain `1`
  is honored. Solver and plot share an exact surviving-row mask. Empirical
  zero-point errors avoid the former cancellation crash; M3's degenerate-solve
  safeguards remain. Evidence: [acceptance, independent references and limits](../analysis/photometric-calibration.md),
  22 new scientific cases, real-frame gain control, independent joint fits on
  all four unchanged recorded inputs and fresh review with no outstanding
  findings. The corrected NGC 5128 result exceeds the historical parity
  tolerance; comparisons disclose this without changing fixtures or thresholds.
  Final Python 3.13.15 offline suite: **3,834 passed, 75 skipped**. Compilation,
  schema goldens, generated guidance, repository shape and whitespace checks
  pass. PHOT-06 downsampled saturation counts, calibration sufficiency and
  retained numerical limitations remain open in their separate gates.
  Changes remain local to `feature/m2`.
- [x] **Catalog magnitudes and filters.** Implementation is complete and reviewed
  on `feature/m2`: selection, numeric resolution and tool reports use one
  production-aligned map; photographic/associated optical and Tycho bands keep
  distinct names; UCAC Open cannot satisfy arbitrary filters. Source-name
  aliases and spelling/case handling agree across entry points, finite zeros
  survive, and results disclose retained approximations and relative narrowband
  references. All 65 numerical catalog expressions, including APASS H-alpha's
  production Lupton R expression, are unchanged by explicit maintainer request.
  Evidence: [acceptance, supported bands and retained limits](../analysis/catalog-magnitudes-filters.md),
  82 initial offline cases and 18 review regressions, 135 production magnitude/error
  pairs and 45 selection lists. Follow-up review fixes source-name override
  priority and carries actual reference provenance through the exact solver
  survivor mask; provided/native references and rejected proxies cannot cause
  false transformation disclosures. Independent review also checked 14,663
  production magnitude/error pairs over partial band sets with no differences
  and found no outstanding actionable findings. The full offline suite passes
  **3,934 tests, 85 skipped**. Fresh VizieR checks
  pass 2,688 values across 294 stars in nine calibration catalogs, plus two M3
  identifier checks. After earlier connection timeouts, the concluding fresh
  SDSS retry passes **667 values across 23 stars**, including its unchanged
  narrowband aliases. Together the ten calibration catalogs pass **3,355 value
  comparisons across 317 stars**; all ten catalogs and both M3 identifier
  checks passed again during follow-up review. Compilation, schema goldens, generated
  guidance, repository shape and whitespace checks pass. Changes remain local
  to `feature/m2`; the following checkpoint addresses coverage/sufficiency,
  and the separate retained-defect warnings/benchmark gate remains open.
- [x] **Catalog coverage and sufficiency.** Both WCS runner entry points use
  enclosing cones and detector clipping, including RA seams, pole-crossing
  fields, anisotropic scales and off-detector CRPIX. Explicit polar boxes keep
  a conservative full-RA declination band instead of dropping stars or failing
  on NaN. Cached cones compensate for their rounded centre. Distorted/non-TAN
  footprints, including internally normalized TPV, use sampled boundaries and
  disclose unverified coverage. SkyMapper copies constraints before defaults.
  Raw VizieR/SDSS limits are disclosed before mapping/clipping hides the cap,
  including brightness bias and the SDK default limit. First-nonempty fallback
  names unqueried alternatives; skipped queries and failed variable-star
  checks remain visible. All registered fits disclose unverified sufficiency
  and report actual solver survivors, not rejected candidates. Direct
  degenerate fits share M3's no-solution policy. Numerical transforms and solver
  arithmetic remain unchanged. Evidence: [acceptance and retained limits](../analysis/catalog-coverage-sufficiency.md),
  45 new offline cases, 613 focused passes, review findings fixed with
  failing-then-passing regressions, and **3,979 passed, 88 skipped** in the full
  suite. All **15 live checks** pass, including near-pole/ordinary detector
  queries, a capped response and 3,355 matching magnitude/filter values across
  317 stars in ten catalogs. Compilation, schema goldens, generated guidance,
  repository shape and whitespace checks pass. Changes remain local to `feature/m2`.
- [ ] **Warnings and benchmark claims.** Reachable retained numerical bugs
  are not consistently disclosed in tool results. The answer grader can accept
  invented author attribution when numbers are sourced. Users need relevant
  limitations, and benchmark conclusions must account for attribution errors.
  Calibration limitations include PHOT-06 downsampled saturation counts and
  the near-flat SNR regression's implausible limiting magnitudes; see the
  [calibration acceptance record](../analysis/photometric-calibration.md).

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
