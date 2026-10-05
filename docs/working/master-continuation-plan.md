# MARS Master Continuation Plan

**Status:** M0 closed and M1 active, 2026-10-02. This is the single execution
index for known continuing work. Items are sequenced below; implementation
owners and calendar dates are unassigned until a phase starts.
**Baseline:** fetched `origin/dev` at `38bf06a`, plus the remediation on
`feature/audit-remediation` at `a981c06`. The branch was rebased onto that `dev`
commit before this inventory was written.
The 2026-10-01 refresh found no further `dev` commits beyond `38bf06a`.
PR #98 subsequently integrated `origin/main` at `858b074` (the merge of that
same `dev` baseline; no additional source changes), then incorporated PR #97's
per-host installation documentation and desktop-host proposal. PR #98 merged
to `main` as `81017e6`; `dev` remains at `38bf06a`. Desktop D0–D4 joins M4 as
proposed, gated work, not implementation performed by the remediation PR.
Browser support remains expressly parked. The M0 closure branch subsequently
merged current `main` at `eacb1a7` (the urllib3 2.8 lock update) and repeated
the release-target gates recorded in §6, then merged through PR #101 as
`bd8b88e`. M1 starts from that merged `main` baseline.
**Prerequisites:** the extraction/preservation contract in `AGENTS.md` and
`CLAUDE.md`; current reference documents; explicit scientific-divergence scope
before changing preserved numerical behavior.
**Unblocks:** reviewable security, scientific-correctness, installation,
interoperability and validation PRs without losing findings between dated
reviews, archived plans, test notes and conversation history.

This plan owns scheduling and current disposition. The source reviews retain
their detailed arithmetic and provenance. Listing a historical claim here does
not establish that the current implementation has that defect. Completion
requires the evidence and acceptance checks below, not just a passing parity
suite. This inventory covers the reviewed repository and its existing records;
it cannot establish that no undiscovered defects remain.

## 1. Sources, evidence and status rules

| Source | What was reconciled | Inventory here |
| --- | --- | --- |
| [Algorithm review](../analysis/algorithm-remediation-plan.md), especially §§9–10 | All **110 IDs**: 28 WCS, 19 photometry, 32 catalogs/query, 31 former TypeScript. There are 109 originally actionable findings; TS-21 explicitly records no defect. | §5, with current Python paths and stale-claim corrections |
| [Pulsar review](../analysis/pulsar-pipeline-review.md) | All ten original bullets; plotting/schema controls are grouped together. | PUL-01–09, with ART-01 as a prerequisite |
| [Applied designs](../analysis/applicable-designs.md) | Five recommendations and deliberately rejected extensions. | SCI-01; completed/excluded decisions in §3 and §8 |
| [Test coverage](../../tests/README.md), [extraction record](../extraction.md), [optical archive](../archive/optical-tools.md) | Provider contracts, configured solver assertions, ATLAS convergence, historical evidence gaps. | VAL-01–05 and §6 |
| [Benchmark results](../benchmarking/results.md), [harness](../benchmarking/harness.md) | Attribution can pass numeric sourcing checks; deliberately hidden artifact destination arguments. | BEN-01, ART-01 |
| [Names and namespace](../repository-folders.md#names-and-the-package-namespace), [MCP archive](../archive/mcp-tool-surface.md), [model archive](../archive/model-backends.md) | Namespace deferral, host validation, installed benchmark scope, output-schema/transport decisions. | ARC-01–03, INS-01–03, MCP-02, §8 |
| [Desktop-host proposal from PR #97](../analysis/mcp-desktop-hosts.md) and [per-host installation docs](../installing.md) | New main-only D0–D4 rollout, conditional MCPB extension/config helper and explicitly parked browser service; vendor claims remain dated and require host evidence. | INS-01, D0–D4 in §9; parked transport in §8 |
| Current `tools/`, `algorithms/`, packaging and workflows | Approval/effect drift, resource budgets, artifact destinations, supply-chain pins, upgrade/retention behavior; fatal overlap preservation test. | AUD-01–05, MCP-01–02, INS-01–03, ALG-01 |
| [Skynet observations snapshot](../analysis/obs-report.md) | External scheduling/API findings and source availability limits. | EXT-SKY-01–12 in §7 |
| [TUI implementation record](../superpowers/plans/2026-09-14-tui-artifact-rendering.md) and source TODO scan | Implemented renderer/browser steps with stale unchecked boxes; intentional manifest-template TODO; abstract catalog methods. | DOC-01; exclusions in §8 |

Evidence labels in §5: **R** = a bounded probe reproduced the current behavior;
**C** = inspected current code or a preservation test shows the mechanism;
**H** = historical claim requiring focused reproduction or primary-source
evidence; **P** = a Python port or wrapper changed the old failure. A code
mechanism alone does not establish reachability, exploitability or its numeric
impact. Statuses are **open**, **partial**, **recheck**, **closed** and
**protected**. A partial wrapper mitigation does not close a remaining helper
defect. Closed rows stay visible to prevent reimplementing completed work.

Priorities: **P0** = interpreter/process exhaustion or the original blockers,
subject to current reachability; **P1** = misleading science, containment or
material reliability; **P2** = architecture, interoperability and coverage;
**P3** = hygiene or a capability decision. For unverified claims priority is a
triage order, not a newly proven severity. The historical review retains its
original severity values.

## 2. Execution order and gates

The work streams below are sections of this one plan, not separate active plans.
Independent packaging/validation work can run alongside science reproduction.
No numerical fix is authorized merely by this documentation update.

| Phase | Ordered scope | Prerequisites / owner role | Exit gate |
| --- | --- | --- | --- |
| M0 — integrated baseline — **closed 2026-10-02** | Reconcile current `dev`, retain rc4/Python 3.13/bounded dependency policy, exercise remediation and wheel/data release gates; DOC-01. | Repository/release maintainer | Met by the current-main, clean Python 3.13 wheel/data evidence in §6. Platform, actual-host, publishing and live-service checks remain explicitly assigned to later phases. |
| M1 — resource and containment | ALG-01; S1 algorithm rows; PUL-02/03/05/06; ART-01; AUD-01/02/03; MCP-01. First reproduce with bounded tests, then guard, isolate or intentionally correct. | Tool/runtime maintainer plus domain reviewer for numerical changes | Dangerous inputs fail with bounded structured results; crashing geometry is tested in a subprocess; destination containment and approval classifications are covered; valid fixtures preserve the declared contract. |
| M2 — scientific meaning | PUL-01/04/08; S2 algorithm rows; SCI-01; BEN-01. Start with channel labels and confirmed HR coordinate/unit/join bugs; CAT-01 band-selection safeguards are already assigned to M1. | Astronomy reviewer and tool/algorithm owner; preservation decision per finding | Independent scientific reference tests, explicit units/modes, before/after numeric effects, updated preservation assertions/provenance; saved benchmark transcripts regraded. |
| M3 — recoverable failures | S3 algorithm rows; PUL-07 after ART-01; VAL-01/02/05. | Provider/tool maintainer | Malformed/empty/provider inputs cannot escape the result contract; retries and missing-data distinctions are deterministic; schemas expose intended bounded arguments. |
| M4 — install and architecture | ARC-01–04; AUD-02 follow-through; INS-01–03; MCP-02; VAL-03/04; PUL-09; proposed desktop D0–D4 in §9. Measure before refactoring or accepting extension work. | Packaging/MCP maintainer, platform and domain reviewers | Import/dependency isolation, installed resource/entry-point parity, actual host/platform matrix evidence, solver convergence when correctly configured, safe skill upgrades; desktop build/no-build gate and recorded outcome. |
| M5 — remaining correctness and evidence | S4/S5 algorithm rows; remaining §6 investigations; DOC-01 follow-through. | Relevant domain/documentation owner | Each row is closed with evidence, deliberately retained with a public caveat, or explicitly deferred with a reason and revisit trigger. |
| M6 — external/capability decisions | BEN-02, §7 external findings and §8 optional extensions. | Upstream Skynet owner or capability sponsor | Pinned upstream source and owner/disposition first; accepted additions have requirements/provenance/tests. Rejected/deferred scope remains recorded. |

Every implementation PR names the IDs it addresses, intended contract, smallest
test that previously failed, source provenance and numeric/compatibility effect.
Algorithm fixes require explicit divergence from Skynet/Astromancer where
preservation tests currently pin the bug. Update the corresponding assertions
and `docs/extraction.md` in the same PR. The first-party HR fitter and
`hrdiagram_py/legacy.py` have different correction/parity contracts.

When source registers describe the same cause (for example TS-02/PUL-02),
implement and validate it once and close every applicable ID together. Keep
distinct mechanisms separate, especially tentative PHOT-19 versus fatal ALG-01.

Preserve two coupled decisions: TS-20 requires replacing the complete dispersion
statistic against a reference distribution; changing its percentile endpoints
alone worsens the mass result. TS-21 is **protected, not a bug**: its cancelling
unit factors must not be edited independently. Any dimensional redesign replaces
and tests the complete routine. Enumerate current callers of shared helpers;
historical duplicate-file counts and TypeScript paths are obsolete.

## 3. Already implemented or superseded

These are not queued for implementation again. Changes on `main` still need a
release before they reach installed users.

| Item | Current disposition / evidence |
| --- | --- |
| Rebrand and compatibility-shim removal | Completed upstream; `ce36f19` removes the old commands/env shims and `6839672` archives the plan. Namespace migration remains ARC-02. |
| Distribution/licence/index publishing | Latest `dev` adds GPL-3.0-only metadata, rc4, PyPI/TestPyPI trusted publishing, served-wheel comparison and distribution checks on PRs. Python floor/test policy is 3.13, runtime dependencies are bounded, pytest/packaging are development dependencies. Earlier 3.12/exact-runtime-freeze proposals are superseded. |
| Warning/error shape, optional MCP, session manifests and resume | Applied-designs §§3/5/6 shipped through `tools/codes.py`, `tools/models.py`, `tools/mcp/`, `tools/agent/`, `tools/sessions.py` and related tests. The old `tools.runner` locator is historical. |
| Solver unavailable versus genuine no solution | `tools/wcs.py` probes configuration and returns distinct structured diagnostics. Recheck individual low-level exception taxonomy under WCS-23 rather than reschedule the whole feature. |
| Remediation approval/annotations | Headless default denies **classified** risky calls; FITS `write_header` is argument-sensitive; allow-always is scoped by tool/risk class; MCP defaults conservatively classify writes. AUD-01 covers remaining inventory differences. |
| Remediation artifact privacy | Default POSIX artifact root is 0700, new files 0600, including FITS replacement. This does not close ART-01 containment or add per-client authorization. |
| Remediation bundle integrity/recovery | Extracted contents are rehashed against the wheel manifest; POSIX/Windows install locks and backup recovery exist; `fetch-data --verify` and `self-test --with-data` exist. Platform/recovery evidence remains INS-01. |
| Remediation install/skill/release | Native skill installer and host registration guidance exist. Expanded core-asset checks are integrated into `.github/scripts/check_dist.py`; both GitHub and TestPyPI publication depend on installed-data verification. Host validation/upgrade gaps remain INS-01/02. |
| Original WCS-13/WCS-15 | Stateless result fields use arcseconds explicitly and eliminate stale mutable solution state. §5 retains their closure rows. |
| TUI artifact rendering | Render capability, image/waveform and browser/app code and tests exist. The old unchecked implementation record needs a completion annotation, not a new renderer build. |

Data installation is intentionally split: core pulsar, variable-star,
zero-point and Afterglow fixtures are in the wheel; optical frames and the
Girardi grid are separate verified bundles; solver binaries/indexes, UCAC trees,
user FITS/radio maps and remote service credentials are operator supplied. That
boundary is documented in [installing](../installing.md) and is not an
unresolved request to commit or bundle tens of gigabytes of external catalogs.

## 4. Current audit and tool-level work register

All entries are open unless a disposition says otherwise. Locations are
repository-relative from this document. Each row's acceptance criterion is
required in addition to the shared gates in §2.

| ID / priority / phase | Finding and evidence | Action and acceptance criterion |
| --- | --- | --- |
| ALG-01 / P0 / M1 | **Closed 2026-10-02 / R+C for maintained photometry paths.** Fatal recursive ellipse clipping remains in `algorithms/skylib_lite/util/overlap.py`, distinct from tentative PHOT-19. `aperture_photometry` rejects non-finite or sub-0.5 px source ellipses before the automatic-radius search and after final axis derivation. The Numba dispatchers also validate every effective ellipse and elliptical-annulus axis before `prange`, with initializer checks protecting direct internal calls; fixed circles keep the independent circle kernel. Subprocesses retain the 0.40-safe/0.35-fatal helper evidence and prove clean rejection through direct, optimizer, annulus, fixed/default-auto, and registered HR/radio FITS paths. | The numerical overlap implementation remains preserved. Reopen only to correct clipping itself, with an independent area reference and explicit scientific-divergence review; the M1 containment requirement is met when the ordinary photometry regression suite remains green. |
| ART-01 / P1 / M1 | **Closed 2026-10-02 / R+C.** The shared artifact writer now rejects absolute, parent-traversing and cross-platform path-like subdirectories; resolves existing symlinks against the pinned artifact root; revalidates active session scopes at write time; and accepts only one alphanumeric filename extension. Rejections occur before directory or file creation. Explicit Python `output_dir` roots remain supported and generated names are confined to one direct child. | Keep destination validation centralized in `tools/artifacts.py` before exposing any hidden destination control such as `plot_pulsar.subdir` in PUL-07. The supported local single-user trust boundary and cleanup policy remain AUD-03, not part of this path-validation closure. |
| AUD-01 / P1 / M1 | `tools/agent/policy.py` and MCP effect annotations differ: many table/time-series/HR calls write private artifacts but have no agent write tag. | Define whether routine private artifacts require consent and document deliberate exemptions. Use a shared effect inventory where practical; test every registered writer plus download/header flags. Retain per-risk approvals. Do not claim current headless policy blocks every filesystem write. |
| AUD-02 / P2 / M1→M4 | Partially completed in PR #98: all workflow actions use verified commit SHAs, and CI/release uv is consistently version-pinned. Container images remain mutable tags and twine is major-pinned. | Pin reviewed container digests and remaining tool versions; add an update policy. Verify with actionlint, zizmor, secret scan and actual workflows. Action pins were required by the initial PR zizmor failure; record rerun evidence below before closing. |
| AUD-03 / P2 / M1 | Local artifacts/downloads accumulate; trusted stdio calls can read caller-selected paths. Private permissions do not provide a server sandbox. | Document supported local single-user trust and intentional absolute-path access. Define retention/disk budgets and safe cleanup boundaries. Any shared-service proposal requires a separate auth/containment design; test cleanup never removes operator datasets. |
| AUD-04 / P3 / M0 | Closed 2026-10-02: GitHub and TestPyPI publication intentionally run in parallel after the same build/install/data gates; `verify-testpypi` then byte-compares and self-tests the served wheel before PyPI. | Workflow comments and `docs/releasing.md` now describe the actual DAG. Parsed `needs` edges confirm both parallel jobs depend on `build`, `verify`, `data` and `verify-data`, while `publish-pypi` depends on `verify-testpypi`. |
| AUD-05 / P3 / M4 | `mars-bench` entry point ships, while benchmark assets are documented as checkout-only. | Exercise installed invocation with no checkout. Provide an actionable diagnostic or intentionally package the required assets; document the chosen scope. |
| ARC-01 / P2 / M4 | `tools/registry.py` imports all domains eagerly; filtering MCP groups does not isolate heavy imports or mandatory base dependencies. | Separate import-light definitions from callable loading; choose domain extras after measuring startup/size. A selected group avoids unrelated heavy domains and missing optional dependencies return structured errors; registry/schema/group identity stays compatible. |
| ARC-02 / P2 / M4 | Generic top-level `tools`/`algorithms` packages collide with other distributions; [`repository-folders.md`](../repository-folders.md#names-and-the-package-namespace) defers migration. | Choose a namespace and compatibility/version policy after checking conflicts, including that note's warning about another project's `mars` import. Migrate imports, package data, entry points, extraction markers and distribution checks together; installed coexistence tests pass. |
| ARC-03 / P2 / M4 | Heavy optional console/provider dependencies remain in the base install even for Python/MCP-only use. | Coordinate domain, console and model-adapter extras with ARC-01, measuring minimal supported installations. Selected features work without unrelated UI/provider packages; missing-feature diagnostics and installation docs are tested. |
| ARC-04 / P2 / M4 | `algorithms/hrdiagram_py/local_grid.py` and `isochrones.py` import `tools.config`, coupling algorithm loading to process-global application roots and bundle resolution. | Pass validated grid/settings from the tool layer through a documented seam. Test standalone algorithm imports and two independently configured calls without global monkeypatching; retain exact-track selection and missing-grid semantics. |
| MCP-01 / P1 / M1 | Sequential dispatch lock can be held by a long-running tool; no general deadline/cancellation or archive download byte/product budget. | Define per-call/resource/download budgets and cancellation semantics, coordinated with WCS/PUL limits. Stalled/cancelled work releases capacity; partial artifacts are not advertised as valid; prove bounded memory/disk/work without live bulk downloads. |
| MCP-02 / P3 / M4 | MCP output-schema declarations are deliberately deferred while structured results normalize non-finite numbers/bytes/errors. | Decide whether host benefit justifies exposing schemas. If accepted, validate every normalized success/error result class and actual host handling; otherwise retain an explicit deferral/revisit trigger. |
| INS-01 / P2 / M4 | Release install matrix is Linux/Python 3.13; actual macOS/Windows and Codex/Claude Code/Cursor host evidence is incomplete. PR #97 adds desktop-app configuration docs, not actual-host verification; D0–D4 in §9 now schedules that proposal. | Clean installed-wheel fetch/verify/self-test and concurrent/interrupted install tests on each supported OS; appropriate permission checks; actual host registration, calls, skill/resources, approval/media and icon behavior. Record host/OS versions and evidence. SDK tests/config examples alone do not close this. |
| INS-02 / P3 / M4 | Native skill installer refuses an older pristine generated copy as well as a modified copy. | Document a safe upgrade or implement provenance/version-aware atomic replacement. Test pristine-old, modified-old, identical-current and interrupted updates; preserve user modifications. |
| INS-03 / P3 / M4 | Installation size/import timings are historical C7/Python 3.14 measurements; current target is rc4/Python 3.13. | Label their scope and remeasure current locked target, OS/architecture and cold/warm import cost during INS-01/ARC-01. Do not silently reuse old timings as current measurements. |
| PUL-01 / P1 / M2 | Periodogram artifact omits selected channel; static chart says Polarization XX even when searching Sum or YY (`tools/pulsar.py`). | Persist channel and render Sum/XX/YY correctly. Round-trip each channel and use an explicit unknown label for old artifacts. |
| PUL-02 / P0 / M1 | Folding repeatedly subtracts tiny periods; sonification interpolation scales with rate × period; public rate/size/work limits are insufficient. | Bound finite periods, bins, sample rate, interpolation/output duration and work before allocation/loops. Tiny/non-finite/extreme cases fail promptly in structured results; ordinary parity fixtures remain valid. Crosswalk TS-02/24/25/26. |
| PUL-03 / P1 / M1 | Degenerate periodogram variance/non-finite input can raise arithmetic errors or report a NaN peak as success. | Define finite filtering/validation and minimum time/variance contract. Constant, all-NaN, short and degenerate-time inputs produce structured failures; ordinary peaks unchanged. Crosswalk TS-16/17. |
| PUL-04 / P1 / M2 | Frequency artifacts inherit Period (s)/log-axis chart semantics. | Render Frequency (Hz) on the intended frequency scale and return matching metadata; retain period-mode behavior. |
| PUL-05 / P1 / M1 | Malformed `.ecsv` read in `plot_pulsar` is not covered by its `_LoadError` handler. | Truncated, invalid and unreadable tables return declared parse/read errors without escaping the result boundary. |
| PUL-06 / P1 / M1 | Stage-0 header reads/stat can abort a scan listing or resolution. | Isolate per-file failures; retain readable scans, identify warnings/errors and handle disappearing/unreadable direct paths. |
| PUL-07 / P2 / M3 | Registry hides intended periodogram background controls and plot labels/background/size controls. | Expose validated intended public arguments through Python/schema/MCP; identify internal-only controls; regenerate schema fixtures/skill guidance. Destination controls depend on ART-01; resource knobs depend on PUL-02. |
| PUL-08 / P1 / M2 | `top_peaks.x` changes from seconds to Hz by mode; stop/range guidance stays period-oriented. | Return explicit period/frequency fields or typed mode-specific units; test both modes and prevent Hz values being folded as seconds. |
| PUL-09 / P3 / M4 | Plot tests assert dimensions/spec strings but cannot establish visible traces/markers/confidence lines. | Inspect axes artists or bounded image regions for scientific content and labels; avoid platform-sensitive exact raster goldens. |
| SCI-01 / P1 / M2 | Reachable preserved science defects are not comprehensively linked to runtime warnings (applied-designs §4). | Crosswalk §5 IDs to public tools and detectable triggers; add stable warning codes/caveats for retained limitations without changing computations. Test affected and unaffected conditions; record cases that cannot be reliably detected. |
| BEN-01 / P1 / M2 | Numeric sourcing grader misses fabricated bibliography author/name attribution (`results.md`, `tools/bench/graders/answer.py`). | Grade evidence-backed strings/attributions with background/negation handling. Add positive/adversarial transcripts; regrade saved runs without new paid calls and mark changed findings in the benchmark record. |
| BEN-02 / P2 / M6 | Benchmark front matter identifies unisolated schema-dialect effects and a corpus authored while watching the winning backend; existing rates cover 16 selected probes, not general astronomy work. | Design a dialect-separated comparison and independently reviewed corpus additions; preserve existing probes/keys and distinguish harness errors from model outcomes. Replay/falsification checks precede any new hosted sweep, which requires an explicit execution/token budget. Record bias and inference limits even if deferred. |
| VAL-01 / P2 / M3 | No automated network smoke for Gaia/literature cluster steps or radio VizieR/NED chains. | Add allowed recorded-provider contract tests and opt-in live checks for named paths. Default tests remain deterministic and socket-free. |
| VAL-02 / P2 / M3 | Landolt/USNO mappings, SDSS/SkyMapper/SIMBAD provider shapes and query-cache IO lack sufficient focused coverage. | Test renamed/missing/non-finite columns, pruning and IO failures; add credential/data-gated provider probes only where needed. Retain APASS/VSX completed evidence. |
| VAL-03 / P2 / M4 | A legacy blind WCS test omits configured solver settings and skips on no solution even when data exists. | Pass configured settings; skip only for absent/incompatible resources. A supported configured fixture must assert a solution or fail with diagnostic evidence. |
| VAL-04 / P2 / M4 | ATLAS tests establish UCAC reachability/bounded attempts, not blind triangle convergence. | Operator-gated known-solution case asserts position/scale/rotation tolerances and useful failures; missing catalog clearly skips. |
| VAL-05 / P2 / M3 | ADS `abs:`/`object:` grouping is a precaution without a confirmed parser fix (`tools/ads.py`, agent prompt). | Run a credential-gated minimal query matrix, isolate failure/retry behavior, then pin query construction and returned shapes offline; no default key/network requirement. |
| DOC-01 / P3 / M0→M5 | M0 portion closed: the master update fixed indexes/source crosslinks, moved the external snapshot, annotated TUI completion and replaced SIMBAD's obsolete deferred-ADS wording with current `tools.ads` locators. General stale-statement follow-through remains for M5. | Keep planning sources routed here and replace named stale statements with current code/evidence locators. Preserve dated history with corrections. Working contains this plan and its index; full closure records final checks and any retained documentation debt. |

## 5. Complete historical algorithm disposition register

The linked [source register](../analysis/algorithm-remediation-plan.md#9-full-finding-register)
supplies original severity/arithmetic/provenance for every ID below. Current
targets are `../../algorithms/wcs/`, `../../algorithms/photometry/`,
`../../algorithms/fieldcal/`, `../../algorithms/catalogs/`,
`../../algorithms/query/` and the shared `../../algorithms/skylib_lite/`.
Former TS targets now map to `../../algorithms/pulsar/`,
`../../algorithms/variable_star/`, `../../algorithms/hrdiagram_py/` and their
public tools. Retired TypeScript files are not implementation targets.

Stream **S1** belongs to M1 (bounds/blocker reassessment); **S2** to M2 (silent
science); **S3** to M3 (loud failure/recovery); **S4** to M5 (latent correctness,
mutation/units); **S5** to M5 (hygiene/provenance/retirement). Recheck rows first
get a bounded reproduction/reachability decision; open rows also need a targeted
test before fixes. Closed/protected rows have no independent fix queued.

### 5.1 WCS — all 28 IDs

| ID | Stream / status / evidence | Current problem, correction or next evidence |
| --- | --- | --- |
| WCS-01 | S1 / open / C | Missing scale can cause oversized ATLAS catalog loading before the cap; establish safe default radius/load cap with WCS-25. |
| WCS-02 | S1 / partial / C | Timeout config/public argument now exists; omitted timeout still defaults to `None`. Test a finite default and actual process termination. |
| WCS-03 | S2 / open / C | No-scale acceptance uses a weak default-scale separation gate; test a deliberately wrong solution before changing header acceptance. |
| WCS-04 | S1 / partial / C | Explicit bounded search hints now reach backends; default radius 180 remains deliberately all-sky. Decide safe default policy and preserve explicit blind use. |
| WCS-05 | S3 / recheck / H | Reproduce no-hint ATLAS `float(None)` through current all-sky path; bounded no-hint path is already guarded. |
| WCS-06 | S2 / recheck / H | Reproduce decimal-degree string RA interpreted as hours in current hint parsing; small numeric RA ambiguity is separately preserved. |
| WCS-07 | S2 / recheck / H | Verify small-field triangle collinearity threshold with current pixel/radian units and known correspondences. |
| WCS-08 | S2 / recheck / H | Synthetic alternative CDELT keywords establish degrees-versus-arcsec scaling and invalid scale bounds. |
| WCS-09 | S2 / open / C | Gnomonic projection divides by unguarded `cosc`; test far-side/antipodal rejection. |
| WCS-10 | S4 / open / C | RA widening clamps cos(dec) to 0.2; establish polar/pole-crossing geometry contract. |
| WCS-11 | S4 / recheck / H | Test UCAC4 query boxes wider than 360° against expected full-sky coverage. |
| WCS-12 | S4 / recheck / H | Use anisotropic CDELT/nontrivial PC to test matrix order; equal-scale fixtures cannot disprove the claim. |
| WCS-13 | closed / C | Stateless result names `delta_ra_arcsec`/`delta_dec_arcsec` supersede old `_deg` mismatch; document cos-dec convention if still unclear. |
| WCS-14 | S2 / open / C | Accepted ATLAS solution requeries at hint center/default maximum scale; test solved center/scale usage. |
| WCS-15 | closed / C | Mutable solution-clearing API removed; immutable per-call results and repository-shape guard supersede stale-state defect. |
| WCS-16 | S2 / recheck / H | Masked extraction assignments may write a copy; test axes swap/theta convention in the single consolidated helper. |
| WCS-17 | S2 / recheck / H | Assess brightness selection and epoch/proper-motion handling with synthetic sources and catalog schema evidence. |
| WCS-18 | S4 / open / C | Tests preserve stale EQUINOX/RADECSYS; inspect actual SIP regex coverage and define safe header cleanup. |
| WCS-19 | S5 / recheck / H | Real UCAC4 format/layout investigation, requiring authoritative format and one zone file; not yet an established port defect. |
| WCS-20 | S4 / open / C | Explicit parity passes through both backends; header/automatic mappings differ. Test blind ATLAS semantics and define public parity contract. |
| WCS-21 | S1 / partial / C | Deadline diagnostics exist, but default and preprocessing/retry/full-call budgets remain unbounded; coordinate MCP-01. |
| WCS-22 | S3 / recheck / H | Synthetic `EQUINOX='J2000'` must exercise current hint path and return an actionable diagnostic. |
| WCS-23 | S3 / partial / C | Broad exception now records detail; wrapper distinguishes unavailable solver. Test missing binary/bad root/full disk taxonomy before further changes. |
| WCS-24 | S5 / recheck / H | Recheck FOV estimate on stripped temporary FITS and whether missing-FOV guard is reachable. |
| WCS-25 | S1 / open / C | Radius/padding config remain unannotated class attributes; make intended cap constructible and test with WCS-01. |
| WCS-26 | S4 / open / C | `_write_xylist` source limit applies only with a flux array; test absent/bad flux cases. |
| WCS-27 | S2 / open / C | Southern-declination fallback returns zero; tests deliberately preserve it. Correct shared helper with southern/equatorial/northern cases. |
| WCS-28 | S4 / partial / C | Caller extraction settings still mutate; print-to-stdout half is gone. Establish copy/ownership semantics and repeated-call test. |

### 5.2 Photometry / field calibration — all 19 IDs

| ID | Stream / status / evidence | Current problem, correction or next evidence |
| --- | --- | --- |
| PHOT-01 | S2 / recheck / H | Trace nonpositive flux/magnitude-zero flags through current public result/SNR filtering. |
| PHOT-02 | S2 / recheck / H | Empty background annulus must establish subtraction/flag behavior with a tiny image. |
| PHOT-03 | S2 / open / C | `min_vals=10` stops rejection before processing small calibration sets; test outliers with ≤10 stars and report actual rejection. |
| PHOT-04 | S3 / open / C+H | Matching transposes catalog rows including epoch fields; reproduce mixed row shapes and handle proper motion consistently. |
| PHOT-05 | S3 / recheck / H | Missing/empty catalog positions should not abort cKDTree construction or reference undefined coordinates. |
| PHOT-06 | S2 / recheck / H | Test downsampled saturated-source coordinates/counts in consolidated extraction helper. |
| PHOT-07 | S4 / recheck / H | Compare 1-based/0-based isophotal center on known symmetric geometry. |
| PHOT-08 | S3 / open / C | Unguarded PHOT_M0 header assignment on degenerate solutions; establish structured failure without partial success. |
| PHOT-09 | S2 / open / C | Intrinsic-scatter zero boundary cannot bracket; broad catch leaves total scatter. Test statistically explained residuals and correct weights. |
| PHOT-10 | S2 / open / C | Brightness trimming retains saturated stars and treats zero ref magnitude as false; test realistic selection and zero explicitly. |
| PHOT-11 | S3 / recheck / H | Adaptive aperture inputs lose required FWHM columns; reproduce auto mode through field calibration. |
| PHOT-12 | S2 / recheck / H | Growth-curve neighbor guard may be dead; use controlled neighboring-source flux and aperture correction. |
| PHOT-13 | S4 / open / C | SNR conversions/fit weights differ; quantify against chosen scientific SNR definition before changing thresholds. |
| PHOT-14 | S2 / open / C | Gain=1 is overridden by FITS header; preservation tests pin behavior. Define explicit electrons/header/default gain semantics. |
| PHOT-15 | S1 / open / C | Arithmetic eval permits extreme exponentiation; band regex interpolation is unescaped. Bound AST/node/depth/exponent work and escape substitutions. Arbitrary-code exploitability is not established by this review. |
| PHOT-16 | S5 / recheck / H | Reference-driver swallowed exceptions/parity settings need reassessment against current recorded replay tests. |
| PHOT-17 | S4 / partial / C | Global deps module removed; sources/reference magnitudes/Header still mutate. Define caller ownership and test copy/reuse semantics. |
| PHOT-18 | S4 / recheck / H | Test RA-wrap matching and clarify arcsec/pixel tolerances independently. |
| PHOT-19 | S5 / recheck / H | Tentative stale third-edge point needs a pinned authoritative SEP C comparison. Do not conflate with fatal ALG-01 recursion. |

### 5.3 Catalogs / query — all 32 IDs

| ID | Stream / status / evidence | Current problem, correction or next evidence |
| --- | --- | --- |
| CAT-01 | S1 / open / R+C | Johnson V resolves to SkyMapper violet `v`; fix/test both catalog selection and reference-magnitude candidate paths. |
| CAT-02 | S1 / open / C | SDSS payload still has no TOP and ignores limits; test bounded SQL construction and provider limit semantics. |
| CAT-03 | S2 / open / C+H | B/R direct-band declarations outrank transforms; verify CDS photographic column provenance before scientific remapping. |
| CAT-04 | S2 / open / C+H | Tycho BT/VT declared as Johnson B/V; derive authoritative color transform and quantify before/after. |
| CAT-05 | S2 / open / C | UCAC wildcard maps every filter to Open; define relative-versus-absolute calibration policy and stop-on-success implications. |
| CAT-06 | S3 / open / C | APASS U transform references unavailable uprime; surface catalog/filter-specific failure or scientifically valid fallback. |
| CAT-07 | S3 / recheck / H | Test CRPIX at/outside array boundaries through current WCS box geometry. |
| CAT-08 | S2 / open / C | SkyMapper mutates caller constraints with flags; use independent per-catalog constraints and correct stale docstring. |
| CAT-09 | S2 / recheck / H | Non-square binning/rotation must establish swapped pixel-scale footprint error. |
| CAT-10 | S2 / open / C+H | J−K polynomial lacks valid-range guard; verify primary published range, then refuse/warn extrapolation. |
| CAT-11 | S2 / open / C | Polar footprint arcsin domain can drop sources/emit NaN SQL; test geometry without live requests. |
| CAT-12 | S2 / open / C+H | APASS I transform provenance/substitution needs primary reference and a quantified validity envelope. |
| CAT-13 | S2 / open / C | Halpha values differ between intentionally distinct selection/resolution registries; explicit scientific decision, not registry merging. |
| CAT-14 | S2 / open / C+P | Registry/plugin names and transform-resolution source differ; fixing keys alone does not enable transforms. Define the complete resolution contract. |
| CAT-15 | S2 / open / C+H | SkyMapper constant offsets omit color terms; verify coefficients/primary references and supported stellar range. |
| CAT-16 | S2 / recheck / H | Narrowband/broadband relative and absolute zero points need distinguishable validity semantics. |
| CAT-17 | S4 / recheck / H | Cache-center quantization can shrink coverage; establish minimum footprint and fix no-shrink documentation/geometry. |
| CAT-18 | S3 / open / C+H | SDSS backend calls singular `query_object`; check pinned installed API, then test supported binding/error. |
| CAT-19 | S2 / open / C+H | Brightness-sorted truncation may bias fitting; inspect provider truncation metadata and expose completeness. |
| CAT-20 | S3 / recheck / H | Renamed/missing columns can make populated responses appear empty; record mapping failures without dropping entire usable rows. |
| CAT-21 | S4 / partial / C | Empty otype fallback is now documented; validate current star/galaxy codes and raw-code preservation policy. |
| CAT-22 | S3 / open / C | First SIMBAD failure disables resolution for process lifetime; retry/expiry with deterministic transient-failure tests. |
| CAT-23 | S2 / recheck / H | Inventory remaining truthiness-based zero magnitude/error readers; some direct ref-mag paths already use `is not None`. |
| CAT-24 | S5 / recheck / H | Derived Landolt/Stetson columns may include built-in names; use recorded provider columns and expression parsing tests. |
| CAT-25 | S4 / open / C | NaN→None removes invalid-versus-absent provenance; decide metadata/error contract before serialization changes. |
| CAT-26 | S5 / recheck / H | Profile cache pruning and test bounded directory IO/failures; avoid unsupported performance claims. |
| CAT-27 | S1→S5 / recheck / C+H | SQL interpolation exists; shipped column names are trusted. Establish custom/untrusted reachability and identifier validation before assigning injection severity. |
| CAT-28 | S5 / open / C | Token normalization strips whitespace and typographic quotes separately; test combined padded spellings. |
| CAT-29 | S5 / partial / C | Current query uses bound CATALOGS; historical extraction-provenance correction needs a current documentation crosscheck. |
| CAT-30 | S2 / recheck / H | First nonempty catalog may stop a scientifically insufficient calibration; define minimum source/fit-quality contract. |
| CAT-31 | S5 / protected / C | Private one-time mutating catalog classes are deliberate parity; reassess only if exposure/lifetime changes. |
| CAT-32 | S4 / open / C+H | APASS uses recno identifiers; confirm CDS ingest stability and define cache/dedup identity policy. |

### 5.4 Retired TypeScript findings / current Python paths — all 31 IDs

| ID | Stream / status / evidence | Current problem, correction or next evidence |
| --- | --- | --- |
| TS-01 | S1 / open / R+C | `hrdiagram_py/legacy.py` atan quotient loses Galactic longitude quadrant; M67 probe differs by ~180°. Distinguish legacy helpers from fitter output. |
| TS-02 | S1 / partial / P+C | Variable wrapper validates/caps fold work; pulsar nonpositive modulo returns unchanged values. Repeated subtraction and non-finite/tiny-period work still need bounds (PUL-02). |
| TS-03 | S1 / recheck / P+R | Old silent-NaN blocker superseded by carried-error validation and stage-1 error merge; direct bad lengths/zero errors now raise. Prove incomplete rows follow the intended contract before closure. |
| TS-04 | S3 / open / C | Variable fold missing-error alignment failure remains pinned; wrapper catches it but helper contract needs intentional correction. |
| TS-05 | S2 / open / R+C | Legacy MWSC age distribution compares Myr to 13.8 and drops ordinary old clusters; use explicit units and population fixtures. |
| TS-06 | S2 / open / R+C | Numeric sort/lexical FSR join skips source ID 10 when ordered with 2; test both sorting domains and unmatched policy. |
| TS-07 | S2 / open / C | Exact-zero proper motion is excluded by truthiness; test finite zero/None/non-finite membership separately. |
| TS-08 | S4 / recheck / P+H | Former fold-by-index helper not exported in Python; establish standard/prefolded file x-axis meaning and surviving caller before fixing. |
| TS-09 | S2 / open / C | Variable weighted LS mixes weighted numerator and unweighted denominator/variance; compare an independent weighted spectral reference. |
| TS-10 | S2 / partial / R+C | Legacy W1 extinction returns zero; active hrfit rejects wavelengths outside CCM coverage. Decide retained-helper behavior and supported filter contract. |
| TS-11 | S2 / open / C | Pulsar significance uses grid point count as independent trials; calibrate resolution-independent statistical meaning and confidence labels. |
| TS-12 | S4 / open / C | Variable period step quantizes valid small steps to zero; slider path retired, helper remains. Test precision/domain contract. |
| TS-13 | S2 / open / C | Pulsar Nyquist bound uses mean baseline spacing; actual median cadence is only metadata. Define irregular-sampling search limits with gapped cases. |
| TS-14 | S2 / open / C | Differential error MSE still divides by two; establish quadrature convention and propagated spectrum effects in shared Python helper. |
| TS-15 | S2 / open / R+C | Legacy negative DMS loses sign; test negative/zero/positive boundaries and downstream formatting. |
| TS-16 | S3 / partial / P+C | Empty global maxima now return None; NaN argmax poisoning needs current tool/algorithm reproduction. |
| TS-17 | S3 / partial / P+C | Browser alert retired, Python failure differs; constant variable inputs still yield NaN. Test wrapper finite-output contract and empty/constant cases. |
| TS-18 | S3 / open / R+C | Legacy singleton/tied histogram bin count is non-finite; define bounded degenerate histogram behavior. |
| TS-19 | S2 / partial / C | Active fitter honors rv; legacy extinction still hardcodes 3.1. Decide current public reachability and legacy divergence. |
| TS-20 | S2 / open / C | Coupled dispersion statistic requires whole-routine replacement; no isolated percentile endpoint edit. Reference distribution and mass fixture required. |
| TS-21 | protected | Explicitly no assembled defect; cancelling unit factors cannot be fixed independently. Whole-routine dimensional redesign only with a reference fixture. |
| TS-22 | S5 / open / C | Legacy luminosity-axis padding uses the red filter's faint framing limit; establish intended framing before changing pinned output. |
| TS-23 | S4 / open / C | Legacy isochrone splice drops a model point; fitter assembly differs. Test legacy and active consumers separately. |
| TS-24 | S4 / recheck / H | Reproduce maximum-x sample loss in current pulsar binning with a tiny boundary case. |
| TS-25 | S4 / open / C | Exact multiples map to phase one; define periodic/display convention and test phase-zero edges. |
| TS-26 | S4 / recheck / H | Difference/sum pairing may align by index rather than phase; test differently occupied profile bins. |
| TS-27 | S5 / recheck / P | ArrMath class retired; confirm no surviving scalar-first reverse arithmetic path, then close as removed dead code. |
| TS-28 | S3 / open / P+C | Legacy singleton histogram extrema now raise IndexError rather than JS undefined; define singleton bounds. |
| TS-29 | S2 / partial / C | Legacy V wavelength is 0.540, fitter uses 0.55; validate chosen bandpass/normalization and public helper usage. |
| TS-30 | S5 / open / C | Legacy edge-on projection uses unequal display scales; change only after deciding equal-scale intent. |
| TS-31 | S3 / partial / P+C | Variable all-null JD raises ValueError now; wrapper catches. Define empty/all-null helper result and diagnostics. |

## 6. Evidence acquisition and validation ledger

All seven original review uncertainties have a destination. Acquire only the
data/source needed for the active finding; do not commit downloaded catalogs,
remote dumps, user FITS, credentials or caches as fixtures.

| Original uncertainty | Current evidence and remaining gate |
| --- | --- |
| End-to-end solver/catalog/algorithm runs | Later optical tracks added real-frame, bounded solver and local-grid evidence. Remaining configured-test/ATLAS convergence work is VAL-03/04; M0 verifies the integrated installed wheel. Historical “none ever ran” is obsolete. |
| Live provider response/column/vocabulary | APASS/VSX recorded rows are exercised; other paths require VAL-01/02/05 and CAT-18/20/21. Network tests remain explicit opt-in. |
| UCAC on-disk layout | WCS-19 needs a real zone and pinned format specification. Record filename/layout/signed-coordinate facts and a permitted tiny synthetic contract fixture. |
| CDS B/R photometric provenance | CAT-03/04/32 require primary catalog documentation, not inferred band labels or secondary summaries. |
| SkyMapper coefficients | CAT-15 requires a pinned primary transformation/validity reference; absent color terms are observed, exact claimed offsets remain uncertain. |
| SEP overlap provenance | PHOT-19 requires source-version diff; ALG-01 separately requires bounded crash/area reproduction. |
| Standard/prefolded time versus index | TS-08 requires actual format/ingest evidence; mark timestamp/frame semantics explicitly in returned models. |

Bounded current probes from the parallel review reproduced: M67 legacy Galactic
longitude 35.6973° versus Astropy 215.6960°; SkyMapper Johnson-V support true;
MWSC age=9 producing an empty distribution; FSR IDs 10/2 leaving 10 unmatched;
negative DMS losing its sign; legacy W1 extinction zero; singleton histogram
bins NaN. Weighted-LS bad length/zero errors raised ValueError/ZeroDivisionError,
which contradicts the old universal silent-NaN claim. These probes establish
the named helper behavior, not all public-tool reachability or fitting impacts.

| Checkpoint | Actual evidence | Outstanding |
| --- | --- | --- |
| Pre-rebase rc3 remediation | 2,765 non-slow tests passed; installed no-checkout wheel self-test exercised both verified bundles, 55 tools, six skill resources, five pulsar scans, 42 optical frames and a 597-row isochrone track. | Historical evidence only for the rc3 tree; not a claim about latest rc4. |
| Integrated rc4 tests, 2026-10-01 | Focused paths: 186 passed. Non-slow MCP-enabled suite: **2,779 passed, 10 skipped, 92 deselected**, 182 warnings. Local runtime is Python 3.14.7/Linux aarch64; supported CI target is Python 3.13. Lock, syntax, skill-rendering and diff checks passed. | The 92 slow tests were not run. Skips include absent solver/model/provider resources and unavailable saved benchmark directories. Python 3.13 and other platforms remain separate evidence gates; do not treat this as the full default suite. |
| M0 `main` baseline and reconciliation, 2026-10-01–02, from `81017e6` | Full default suite, including slow tests: **2,833 passed, 48 skipped**, 188 warnings before the M0 edits; the post-edit suite repeated the same counts in 7m27s on Python 3.14.7/Linux aarch64. | Skips cover 38 opt-in live catalog cases, four absent saved benchmark directories, one live model, one additional live query, unavailable ATLAS/astrometry resources and one uncovered local solver fixture. Python 3.13 and other platforms remain separate evidence gates. |
| Integrated rc4 wheel/data, 2026-10-01 | Built rc4 wheel passes expanded distribution/licence check. Installed into a pre-existing dependency environment without checkout, it passes `self-test --with-data`: both bundle digests, 597-row track, 55 tools, six skill resources, five pulsar scans, detection/audio and 42 optical frames. All 93 installed packages satisfy dependency constraints. | This was wheel replacement with existing dependencies, not a clean Python 3.13 dependency installation. Release/INS-01 must supply that target/platform evidence. |
| M0 release-target closure, 2026-10-02, after merging `main` at `eacb1a7` | `uv lock --check`, syntax compilation and the rebuilt optical-manifest check passed. The 221-test packaging/MCP focus passed on Python 3.14.7/Linux aarch64. A fresh rc4 wheel and sdist passed strict Twine metadata and the distribution/licence checker. From outside the checkout, the wheel installed with its MCP extra and no pre-existing packages into Python **3.13.15**; `pip check` passed with urllib3 2.8.0 and MCP 2.2.0. Both published, manifest-pinned bundles downloaded and verified, then `self-test --with-data` passed: 597-row isochrone, 55 tools, six skill resources, five scans, detection/audio and 42 optical frames. | Linux aarch64 only. The previously recorded full default suite supplies the slow-test gate because M0 changed only documentation/comments and then merged the urllib3 lock-only update. Opt-in live providers/models, unavailable solver/catalog resources, publishing, Windows/macOS and actual desktop hosts remain assigned to VAL/INS/M4 rather than inferred here. |
| M1 ALG-01 containment, 2026-10-02 | Initial subprocess characterization reached the fatal recursion through fixed and default-auto `run_photometry`; the pre-fix full locked suite passed **2,835 tests with 48 skipped and 188 warnings**. A deliberate guard validates source ellipses inside `aperture_photometry`, then validates every effective ellipse and annulus axis before Numba parallel dispatch and again at direct-call kernel initialization. Subprocess tests retain the helper crash evidence, establish representative rotated/elongated safety at the conservative 0.5 px floor, and prove clean rejection for non-finite, direct, optimizer-derived, annulus, fixed/default-auto, and registered HR/radio FITS paths; a small fixed-circle control remains valid. The final four-file focused surface passed **154 tests** and the post-review full locked suite passed **2,849 tests with 48 skipped and 188 warnings** in 4m48s on Python 3.14.7/Linux aarch64. | ALG-01 is contained without changing overlap arithmetic. A future numerical correction remains separate and requires independent area evidence plus scientific-divergence review. |
| M1 ART-01 containment, 2026-10-02 | Test-first cases cover absolute and parent traversal, escaping and contained symlinks, a scope changed after entry, path-like extensions on every public extension-bearing writer, and an explicit absolute caller-selected root. The 11-file artifact/agent/benchmark/MCP/pulsar/HR/radio/variable-star surface passed **363 tests** in 4m38s on Python 3.14.7/Linux aarch64. | Artifact destinations are contained without removing supported explicit Python output roots. Full-suite evidence is recorded after the final locked run. |
| PR #98 CI, 2026-10-01, merged as `81017e6` | Initial runs at `3a8b228`: Python 3.13 tests, syntax, package, repository shape and secret scan passed; zizmor 1.30.1 rejected 25 mutable action references. Verified upstream commits replaced those references without suppressing the audit. Final head `3a602bc`: CI run `36914768038`, secret scan `36914768075` and workflow-safety run `36914767931` all passed, including actionlint, zizmor and both required aggregate checks. | PR #98's required online checks are closed. Release publishing, platform and actual host gates remain separate. |
| Master completeness, 2026-10-01 | Automated comparison confirms every original algorithm ID occurs exactly once: 110/110. Pulsar/validation/external rows and local master/index links/anchors checked. | Refresh inventory when code or source reviews change; source review completeness does not prove absence of undiscovered bugs. |
| Platforms/hosts/workflows | Source/DAG inspection, parsed workflow YAML, assertions that data gates both GitHub/TestPyPI and transitively PyPI, SDK-level tests and documented host configuration; final passing PR #98 check evidence is recorded above. | No claim of current Windows/macOS or actual Claude/Cursor validation; INS-01. Publishing workflow execution remains a separate evidence gate. |

Update this ledger as checks run. A skipped test is not a successful solver or
provider verification. Each closed finding gets its PR/commit, test locator,
date and provenance note. A retained limitation gets warning/documentation and
the reason a numerical change was declined. Refresh the baseline after each
new `dev` integration and inspect changed assumptions before carrying results
forward.

## 7. External Skynet findings — upstream evidence gate

[The 2026-09-24 observation snapshot](../analysis/obs-report.md) reviews a
different repository. Its relative source links leave this checkout; the
upstream monorepo and production API are unavailable here, and the snapshot
does not pin a commit. The rows below are **historical/unverified upstream
claims**, not reproduced MARS bugs. Each belongs to M6: first obtain a pinned
upstream revision/durable source locator, confirm current behavior and assign
an upstream owner. Then choose upstream correction, a MARS integration guard,
or explicit deferral. This task does not authorize telescope operations or
production observation creation.

| ID | Snapshot finding | Required disposition / acceptance |
| --- | --- | --- |
| EXT-SKY-01 | Exactly-one exposure sizing allegedly unenforced; docs claim conflicting modes rejected. | Current schema/database/API test for zero/one/multiple modes; align docs with intended precedence or exclusivity. |
| EXT-SKY-02 | Fixed-duration requests allegedly ignore allow_coadding. | Confirm execution depth/coadd behavior and expose the actual supported policy. |
| EXT-SKY-03 | Waxing/waning lunar direction lacks an identified enforcing consumer. | Trace scheduler constraints; test direction across dates or explicitly describe storage-only behavior. |
| EXT-SKY-04 | Frame cohesion is treated as sample cohesion. | Define scheduling unit and verify window splitting against policy. |
| EXT-SKY-05 | Cadence finer than epoch not established as enforced. | Pin each advertised cadence level to an actual scheduling test and docs. |
| EXT-SKY-06 | Synchronized copies/start tolerance appear model-only. | Establish supported synchronization contract; test planner/executor timing or label unsupported. |
| EXT-SKY-07 | Fine-grained affinity/migration/handoff enforcement is incomplete. | Trace assignment/reassignment and interrupted units with owner-approved integration tests. |
| EXT-SKY-08 | Saturation safety threshold exists in ORM but is absent from create schema. | Decide configurability/default policy; round-trip create/read/exposure safety tests. |
| EXT-SKY-09 | Request-level instrument ID list absent despite mode field. | Resolve create API contract and validate request/observation instrument constraints. |
| EXT-SKY-10 | Image-normalization settings ID lacks a found ORM field. | Determine retirement/mapping; reject unsupported input or persist it coherently. |
| EXT-SKY-11 | Docs/schema drift in brightness location, request discriminator, exposure validation and cadence wording. | Validate examples against current OpenAPI/SDK and runtime; correct upstream documentation. |
| EXT-SKY-12 | Target-position readback, idempotency, bare ephemeral creation and configured-versus-live telescope status remain uncertain. | Establish API tests/source evidence before MARS observation integration. Separate submitted target from returned payload, creation retry semantics and authenticated observing access from live hardware status. |

Do not reuse the snapshot's telescope counts as current deployment status.
Record the source scope/date and obtain current authorized evidence only when
an integration needs it.

## 8. Deliberate deferrals, exclusions and maintenance

| Decision / ID | Disposition and revisit condition |
| --- | --- |
| CAP-01 — local PostGIS catalog backend | Historical unextracted capability noted in `extraction.md` (Skynet commits a8241c83e, 9a6a5a6ad, fb643309f). M6 decision: accept only with a concrete local-catalog need, licence/provenance review, optional dependency and query-binding tests; otherwise retain deferral. |
| CAP-02 — period uncertainty/barycentric timing | Optional science extension, not promised upstream functionality. Require timing requirements, time-frame metadata and validation against a trustworthy timing reference before adoption. |
| CAP-03 — artifact MCP resources | MCP archive records an available extension for hosts without filesystem tools. Revisit for a concrete supported-host need; define resource authorization/size/lifetime and compare with existing inline media/artifact tools. |
| CAP-04 — CLI-agent/MCP model backend | Model archive defers an external agent as a ModelBackend. Revisit only with a needed provider/harness use case and explicit protocol/trajectory contracts. Existing MCP serving is a different implemented feature. |
| CAP-05 — streaming other model adapters | OpenAI/Gemini/Ollama adapters currently use completed-text fallback. Revisit for a concrete latency/UI requirement; test cancellation, text/tool assembly and usage accounting before marking capability true. |
| CAP-06 — shared services/richer result envelopes | `tool-architecture.md` §§4/6 sketches provenance/pagination and internal services. Introduce only when multiple actual tools need the contract; scope a caller migration/serialization test and measured benefit. These sketches do not create unconditional implementation commitments. |
| HTTP MCP/shared service | Excluded by the completed stdio scope; PR #97 expressly parks browser support. Reopen only for a sponsored hosted/classroom need, not a personal tunnel. Requires authentication/OAuth, per-user isolation, cost ceilings, operator-held key/compute policy, uploads and remote artifact/input contracts (AUD-03, CAP-03); reconsider cloud-call timeouts/result limits with current vendor evidence. |
| Dedispersion/browser AudioContext | Current inputs are single-band continuum; browser audio graph intentionally not ported. Revisit only with suitable data/product requirements. |
| Provider base classes, replacing database tools, wholesale orchestration | Applied-designs deliberately rejects these changes. Revisit only if the recorded architectural constraints change. |
| Benchmark price table | Explicitly declined in the model archive; no unscheduled implementation commitment. |
| Manifest-description TODO / abstract catalog methods | Generated build template asks operator to replace its description; catalog methods deliberately reject unbound querying. They are not forgotten TODOs. |

The master stays current as implementation lands; historical reviews keep their
dated claims and link here for dispositions. There must be one indexed row for
each newly discovered actionable issue or explicit capability decision. Avoid
anonymous catch-all promises such as “test all tools”: add named paths and
acceptance evidence. Keep completed rows and their closure locators; archive
the master only when every accepted item is closed and every remaining item has
an explicit deferral/revisit condition, with durable outcomes folded into
reference docs.

## 9. Desktop-host rollout (D0–D4)

**Status:** proposed, 2026-10-01; no phase started. This M4 substream preserves
PR #97's sequencing: each phase is a separately reviewed PR; the preceding
phase must land first. Owner role: packaging/MCP maintainer with actual
macOS/Windows desktop testers. INS-01 owns overlapping host-validation work;
record evidence once and link it from both IDs.

**Prerequisites:** installed stdio MCP surface, per-host instructions in
[`installing.md`](../installing.md), current vendor facts and available host
machines. The [dated proposal](../analysis/mcp-desktop-hosts.md) keeps the
rationale and sources, not a second active plan. Claims about application
support, MCPB 0.4 `uv` support, wheel availability, startup timing and desktop
versus ordinary ChatGPT chats require D0/D2 verification. Historical 640 MB
dependency and 4.5 s import measurements are not current target measurements
(INS-03).

**Unblocks:** non-terminal researchers using Claude Desktop or the ChatGPT
desktop app's Codex without hand-editing paths/configuration. No HTTP server,
browser service or algorithm/model-backend change is included.

| Phase / priority | Ordered work and decision | Exit evidence |
| --- | --- | --- |
| D0 / P2 | Recheck vendor facts and install from PyPI on Claude Desktop/macOS (Windows if available) and the ChatGPT desktop app's Codex. Follow the current registration docs. Run the self-test's five-step pulsar detection on B0329+54 and B1133+16 and one explicitly enabled live SIMBAD search. Record OS/app/package versions, correct period provenance, whether instructions/skill resources reach the model, inline image/audio behavior, approval prompts, cold-start time and startup/call timeout behavior. | Both apps complete detection; retain transcripts/measurements and correct installation docs. Unavailable Windows evidence stays an open INS-01 gate, not an inferred pass. Live checks stay opt-in, outside the default suite. |
| D1 / P2, after D0 | Fold measured findings and caveats into installation docs, including the app settings route. Validate and document `uv tool install "skynet-mars[mcp]" --python 3.13` as the simplest manual route; measure stable entry-point path and first-launch behavior. Decide whether an optional registration helper is warranted or an MCPB extension would make it redundant. | A docs-only reader reproduces D0. A helper, if accepted, uses the running environment's entry point, parses existing host config, preserves unrelated entries and refuses a different `mars` entry without explicit replacement consent. Test preservation/malformed files and report writes outside MARS home. Prefer existing `codex mcp add` where sufficient. |
| D2 / P3, after D1 | Spike a throwaway `uv`-type MCPB 0.4 extension against an exact published release, pinning managed Python 3.13. On macOS and Windows establish actual host support, first-install dependency/startup timeout or retry behavior, a non-terminal data-fetch route, and release/version/distribution feasibility. Do not infer host support from the manifest spec. | Recorded build/no-build decision with measurements and all four questions answered. If unsupported, retain managed-uv documentation, not a roughly 640 MB per-platform bundled-Python extension. If a data-fetch tool is necessary, review its effect classification and `tools/bench/plane.py` registration together; do not add one solely on speculation. |
| D3 / P3, only after accepted D2 build decision | Add manifest source and release build asset, exact `skynet-mars[mcp]` release/Python pins, sensitive ADS key configuration and tool-group/MARS_HOME options (evaluate ANET_INDEX_PATH where needed). Verify manifest/version against the release tag, then attach MCPB to GitHub releases. Recheck connectors-directory distribution policy rather than assuming submission is possible. | Automated release gate installs/inspects built manifest and pinned version; a fresh macOS user installs by double-click and completes detection. Actual Windows Desktop installation stays a documented manual/platform gate. Dependency installation and data-fetch security remain subject to AUD-02/03 and INS-01. |
| D4 / P2, after D3 or recorded no-build branch | Fold the chosen outcome into installation docs, `tool-architecture.md` §10.3 and `CLAUDE.md` MCP rules. For a no-build decision, document the validated manual route and rejected extension with its revisit condition. | D0–D4 closed or explicitly deferred with PR/test/evidence locators here; no orphan active desktop plan. The dated proposal remains provenance. |

Browser hosts remain parked (§8), including remote local-path/result contract
changes, OAuth, cloud-call limits and hosted-service operations. Reopening them
requires a separate sponsor/requirements decision; desktop friction does not
authorize an HTTP transport or production service.
