# MARS Master Continuation Plan

**Status:** M0 closed; M1 **partial, not complete**, refreshed 2026-10-06.
This is the single execution index for known continuing work. Items are
sequenced below; implementation
owners and calendar dates are unassigned until a phase starts.
**Current baseline:** fetched `origin/main` at `6d966de` (PR #116 / rc6) and
`origin/dev` at `38bf06a` on 2026-10-05. Current-main CI, security and release
runs passed (§6). The working branch is `feature/m1-status-continuation`,
which merges that main into the earlier M1 photometry branch. ALG-01 at
`0be6f8c` and ART-01 at `dcea645` are **branch-only**, not fixes in main or
the published rc6 wheel. PUL-02/03/06 are at `ca9fb4f`, PUL-05 at `9ea0002`;
TS-02 is at `712c0a4`; ALG-02/TS-03 and the TS-17 public weighted-spectrum
containment are at `1042f70`; PHOT-15 is at `a3e152a`; CAT-02/27 and the
newly reproduced ALG-03 SDSS transport repair are at `f8a0af3`, recorded below.
WCS-02's finite attempt/owned-group cleanup is at `1dddb41`, with provider-schema
snapshots at `dfdfc7b`.
All are branch-only;
their local acceptance evidence is not a claim of merged/released protection.

**Historical baseline:** fetched `origin/dev` at `38bf06a`, plus the remediation on
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
`bd8b88e`. M1 started from that merged `main` baseline. Subsequent main PRs
#102–116 added the desktop extension/plugin, bundle-upgrade compatibility,
HR-fit corrections, Python 3.12/3.13 CI and rc5/rc6. These changes do not close
M1's resource/containment gate; their current dispositions appear below.
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
| [Desktop-host proposal from PR #97](../analysis/mcp-desktop-hosts.md), [installation docs](../installing.md), [Claude extension](../../installers/claude-desktop/README.md) and [Codex plugin](../../installers/codex/README.md) | PRs #102/#108/#109/#110 implemented installers and changed them to latest-release launchers. Codex Fedora app-server evidence is recorded upstream; full real desktop/platform acceptance is still incomplete. | INS-01/03/04, D0–D4 in §9; parked transport in §8 |
| Current `tools/`, `algorithms/`, packaging and workflows | Approval/effect drift, resource budgets, artifact destinations, supply-chain pins, upgrade/retention behavior; fatal overlap preservation test, direct weighted-grid stall and pinned-SDK SDSS transport mismatch. | AUD-01–05, MCP-01–02, INS-01–03, ALG-01–03 (new findings outside the 110 historical IDs) |
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
Every closure also states its delivery scope: **branch-only**, **merged** or
**released**. A branch-only fix is not protection for users of main/PyPI, and
merging one PR does not complete a phase containing other open findings.

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
| M0 — integrated baseline — **closed 2026-10-02** | Historical rc4/Python 3.13 wheel/data gate; DOC-01. Current main is rc6 and now supports/tests Python 3.12 and 3.13; retain its bounded dependencies and locked CI. | Repository/release maintainer | Historical closure remains valid for its stated baseline. The newer rc6 CI/release evidence is in §6; platform, actual-host and live-service gaps remain later-phase gates. |
| M1 — resource and containment — **partial** | ALG-01/02; S1 algorithm rows; ALG-03 as CAT-02 prerequisite; PUL-02/03/05/06; ART-01; AUD-01/02/03; MCP-01. First reproduce with bounded tests, then guard, isolate or intentionally correct. | Tool/runtime maintainer plus domain reviewer for numerical changes | Not met: branch-only ALG-01/02/03, ART-01, PUL-02/03/05/06, TS-02/03, PHOT-15, CAT-02/27 and WCS-02 do not close remaining S1, effects, retention and cancellation work. Dangerous inputs must fail with bounded structured results; crashing geometry is tested in a subprocess; destination containment and approval classifications are covered; valid fixtures preserve the declared contract. |
| M2 — scientific meaning | PUL-01/04/08; S2 algorithm rows; SCI-01; BEN-01. Start with channel labels and confirmed HR coordinate/unit/join bugs; CAT-01 band-selection safeguards are already assigned to M1. | Astronomy reviewer and tool/algorithm owner; preservation decision per finding | Independent scientific reference tests, explicit units/modes, before/after numeric effects, updated preservation assertions/provenance; saved benchmark transcripts regraded. |
| M3 — recoverable failures | S3 algorithm rows; ALG-03 (implemented as CAT-02 prerequisite); PUL-07 after ART-01; VAL-01/02/05. | Provider/tool maintainer | Malformed/empty/provider inputs cannot escape the result contract; retries and missing-data distinctions are deterministic; schemas expose intended bounded arguments. |
| M4 — install and architecture — **partial desktop implementation** | ARC-01–04; AUD-02 follow-through; INS-01–04; MCP-02; VAL-03/04; PUL-09; desktop D0–D4 in §9. Installers already exist; validate their actual behavior before further refactoring or extension work. | Packaging/MCP maintainer, platform and domain reviewers | Import/dependency isolation, installed resource/entry-point parity, actual host/platform matrix evidence, solver convergence when correctly configured, safe skill upgrades; explicit installer/update policy and recorded desktop outcome. |
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

### 2.1 M1 checkpoint and next execution queue

As of 2026-10-06, **do not mark M1 complete**. Main does not contain the
ALG-01/ART-01 fixes, and inspection still finds missing bounds and policy
coverage in solver/catalog paths, `tools/agent/policy.py` and
`tools/mcp/server.py`. Pulsar computation bounds
and scan recovery, direct/tool variable-fold and weighted-spectrum bounds, and
the paired-row weighted-error contract, bounded custom reference-magnitude
arithmetic, bounded SDSS region SQL/transport and finite solver attempts with
owned-group cleanup are now implemented on this branch
(§4/§6), not in rc6.
The continuation order is:

1. Deliver the branch-only ALG-01/02/03/ART-01/PUL-02/03/05/06/TS-02/03/PHOT-15/CAT-02/27/WCS-02 fixes: local
   regression evidence is in §6; continuation PR CI, review/merge and release
   remain. Preserve the conservative ellipse contract and valid numerical
   fixtures. The new first-party pulsar/variable limits deliberately reject
   unsafe inputs without replacing the accepted-input arithmetic.
   ALG-02/TS-03 now have shared grid guards, explicit aligned paired weights,
   numeric-mask/null handoffs and bounded regressions at `1042f70`. The public
   variable-spectrum TS-17 containment is implemented; direct constant NaN and
   TS-09/14 scientific arithmetic remain separately preserved.
   PHOT-15 at `a3e152a` removes Python evaluation from custom magnitude
   expressions, bounds arithmetic/namespace/alias work and uses literal band
   substitutions. Invalid mappings stay unresolved; accepted registry transforms
   and uncertainty propagation are unchanged. Custom settings are a Python API
   path, not an exposed registered-tool argument.
   CAT-02/27 and ALG-03 at `f8a0af3` bound SDSS region SQL/results and literal
   projection fields and use the pinned SDK's SQL endpoint/parser. Constraints,
   geometry and row mapping remain preserved. Whole-call/download budgets,
   catalog completeness and broken named-object lookup remain separate;
   future CAT-18 repair must reuse the bounded region contract.
   WCS-02 at `1dddb41` uses a finite 300-second attempt default and validated
   1–900-second overrides; native POSIX probes show SIGTERM-resistant children
   are killed even when the owned group leader has exited. Provider snapshots
   at `dfdfc7b` and both generated skill copies reflect the changed contract.
   Retry allowances remain per-attempt; ATLAS preprocessing/oriented work,
   whole-call/cancellation and solver output-byte limits remain WCS-21/MCP-01.
2. Next code work — remaining S1 rows: WCS-01/04/21/25,
   CAT-01 and TS-01.
   Prove public reachability, finite solver/query/expression limits and a
   documented decision on any legacy numerical divergence.
3. AUD-01/02/03 and MCP-01: complete writer/approval coverage, remaining supply
   pins/update policy, trusted-local retention/cleanup boundary, and measured
   cancellation/resource/download limits. Longer host timeouts are not server
   cancellation or disk/work budgets.
4. Close M1 only after every listed row has its acceptance evidence or an
   explicitly reviewed deferral, then merge and record the delivery/release
   scope. Do not silently move unfinished M1 work to M2/M4 to claim completion.

## 3. Already implemented or superseded

These are not queued for implementation again. rc6 is released; later
branch-only changes still need a merge and release before installed users get them.

| Item | Current disposition / evidence |
| --- | --- |
| Rebrand and compatibility-shim removal | Completed upstream; PR #105 removed the old-name record and links. Current namespace rationale lives in `repository-folders.md`; migration remains ARC-02. |
| Distribution/licence/index publishing | rc6 / PR #116 is published; GPL-3.0-only metadata, trusted publishing, served-wheel comparison and distribution checks remain. PR #112 sets locked CI/install tests on Python **3.12 and 3.13**, with security-only dependency automation; PR #113 updates the lock. Runtime dependencies remain bounded and pytest/packaging remain development-only. This supersedes the earlier 3.13-only policy, not the historical evidence. |
| Warning/error shape, optional MCP, session manifests and resume | Applied-designs §§3/5/6 shipped through `tools/codes.py`, `tools/models.py`, `tools/mcp/`, `tools/agent/`, `tools/sessions.py` and related tests. The old `tools.runner` locator is historical. |
| Solver unavailable versus genuine no solution | `tools/wcs.py` probes configuration and returns distinct structured diagnostics. Recheck individual low-level exception taxonomy under WCS-23 rather than reschedule the whole feature. |
| Remediation approval/annotations | Headless default denies **classified** risky calls; FITS `write_header` is argument-sensitive; allow-always is scoped by tool/risk class; MCP defaults conservatively classify writes. AUD-01 covers remaining inventory differences. |
| Remediation artifact privacy | Default POSIX artifact root is 0700, new files 0600, including FITS replacement. This does not close ART-01 containment or add per-client authorization. |
| Remediation bundle integrity/recovery | Extracted contents are rehashed against the wheel manifest; POSIX/Windows install locks and backup recovery exist; `fetch-data --verify` and `self-test --with-data` exist. PR #104 / `6a9108c` preserves an older release's bundle when its content still matches current pins and expands fixture-tree guarding. Platform/recovery evidence remains INS-01. |
| Remediation install/skill/release | Native skill installer and host registration guidance exist. Expanded core-asset checks are integrated into `.github/scripts/check_dist.py`; both GitHub and TestPyPI publication depend on installed-data verification. Host validation/upgrade gaps remain INS-01/02. |
| Desktop installers | Claude Desktop MCPB and Codex marketplace/plugin exist, with generated skill parity and launcher/config tests (PRs #102/#108/#109/#110). Both intentionally follow the latest PyPI release; Claude has a cached offline fallback, Codex requires a startup lookup. This supersedes the proposed exact-MARS-version launcher in §9, not its outstanding actual-host/security evidence gates. |
| First-party HR fitting | PR #106 corrects grid-aligned age windows and revises the active fitter's cost with dense track resampling, a systematic error floor, capped per-star cost and a coarse optimizer seed; it removes faint sentinel rows. Offline M67 reference/age-window tests and numeric effects are in `docs/extraction.md`, HR Diagram (Python). These are not fixes to retained `legacy.py` findings or proof of all-cluster accuracy. |
| Original WCS-13/WCS-15 | Stateless result fields use arcseconds explicitly and eliminate stale mutable solution state. §5 retains their closure rows. |
| TUI artifact rendering | Render capability, image/waveform and browser/app code and tests exist; M0 annotated the historical implementation record. This needs no new renderer build. General stale documentation remains DOC-01. |

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
| ALG-01 / P0 / M1 | **Implemented/verified on branch only / R+C**, `0be6f8c`; not in main/rc6. Fatal recursive ellipse clipping remains in `algorithms/skylib_lite/util/overlap.py`, distinct from tentative PHOT-19. `aperture_photometry` rejects non-finite or sub-0.5 px source ellipses before the automatic-radius search and after final axis derivation. Numba dispatchers validate effective ellipse/annulus axes before `prange`, with initializer checks for direct calls; fixed circles use the independent kernel. `tests/test_skylib_geometry.py` retains subprocess crash evidence and direct/optimizer/annulus/fixed/default-auto/registered HR/radio rejection cases. | Merge/release the guard and retain ordinary photometry regression evidence (§6). Overlap arithmetic remains preserved. A future clipping correction requires an independent area reference and explicit scientific-divergence review. |
| ALG-02 / P1 / M1 | **Implemented/verified branch-only / R+C**, `1042f70`, 2026-10-05; not in main/rc6. Two five-second kill/reap-bounded grid probes stalled before the fix. Direct weighted LS now validates finite ordered/progressing grids, integer steps (1–200,000), at most 2,000 samples and 20,000,000 conservative sample-grid units before preparation. The tool shares `validate_periodogram_grid`; runtime progress/steps+1 counters remain independent. Weights/normalization and trial coordinates must be representable. | `tests/test_variable_star_periodogram_limits.py` proves both direct stalls terminate, pre-allocation/work rejection and runtime protection when preflight is bypassed; weighted and 2,001-row fixture parity stays unchanged (§6). Direct constant-series NaN remains preserved; the public finite-output rejection is separate TS-17 containment. Provenance: `extraction.md`, Python M1 weighted-periodogram acceptance contract. Merge/release outstanding; no newly proven MCP grid-stall exploit. |
| ALG-03 / P1 / M3 (CAT-02 prerequisite) | **Implemented/verified branch-only / R+C**, `f8a0af3`, discovered 2026-10-06; not in main/rc6. Pinned astroquery 0.4.11's cone path passes a coordinate list into MARS's scalar payload seam and expects cross-ID instead of SQL; its box interface also differs. MARS regions now build their quality-filtered SQL explicitly and use the supported `query_sql` endpoint/parser. | Offline native SDK tests prove SQL GET construction, CSV mapping and service-error propagation for circle/box; runner/limits/cache controls pass (`tests/test_sdss_query_limits.py`; Query extraction §5.11). Inherited native `MARSSDSS.query_region` remains unsupported and is characterized to prevent backend reuse. Named-object CAT-18 remains open. Merge/release and actual live-service evidence outstanding; no live query or newly proven security exploit is claimed. |
| ART-01 / P1 / M1 | **Implemented on branch only / R+C**, `dcea645`; not in main/rc6. The shared artifact writer rejects absolute, parent-traversing and cross-platform path-like subdirectories, escaping existing symlinks, unsafe session scopes and non-alphanumeric filename extensions before creating files. Explicit Python `output_dir` roots remain supported. `tests/test_artifact_writers.py` covers rejection and valid controls. | Merge/release after current-main regression gates (§6). Keep validation centralized before PUL-07 exposes destination controls. This assumes a trusted local user and does not defeat concurrent filesystem mutation; shared-service sandboxing and cleanup remain AUD-03. |
| AUD-01 / P1 / M1 | `tools/agent/policy.py` and MCP effect annotations differ: many table/time-series/HR calls write private artifacts but have no agent write tag. | Define whether routine private artifacts require consent and document deliberate exemptions. Use a shared effect inventory where practical; test every registered writer plus download/header flags. Retain per-risk approvals. Do not claim current headless policy blocks every filesystem write. |
| AUD-02 / P2 / M1→M4 | **Partial.** PR #98 pins actions to verified SHAs and CI/release uv consistently. rc6 main CI/security/release passed (§6); gitleaks still uses mutable `v8.30.1` container tags and Twine is major-pinned. New desktop launchers deliberately resolve `@latest`, not the tested project lock. | Pin reviewed container digests and remaining CI tool versions; document the security-only update policy from PR #112. Review installer freshness/reproducibility, rollback and skill drift under INS-04 without silently reverting the upstream latest-release decision. Passing workflow audits do not close these residuals. |
| AUD-03 / P2 / M1 | Local artifacts/downloads accumulate; trusted stdio calls can read caller-selected paths. Private permissions do not provide a server sandbox. | Document supported local single-user trust and intentional absolute-path access. Define retention/disk budgets and safe cleanup boundaries. Any shared-service proposal requires a separate auth/containment design; test cleanup never removes operator datasets. |
| AUD-04 / P3 / M0 | Closed 2026-10-02: GitHub and TestPyPI publication intentionally run in parallel after the same build/install/data gates; `verify-testpypi` then byte-compares and self-tests the served wheel before PyPI. | Workflow comments and `docs/releasing.md` now describe the actual DAG. Parsed `needs` edges confirm both parallel jobs depend on `build`, `verify`, `data` and `verify-data`, while `publish-pypi` depends on `verify-testpypi`. |
| AUD-05 / P3 / M4 | `mars-bench` entry point ships, while benchmark assets are documented as checkout-only. | Exercise installed invocation with no checkout. Provide an actionable diagnostic or intentionally package the required assets; document the chosen scope. |
| ARC-01 / P2 / M4 | `tools/registry.py` imports all domains eagerly; filtering MCP groups does not isolate heavy imports or mandatory base dependencies. | Separate import-light definitions from callable loading; choose domain extras after measuring startup/size. A selected group avoids unrelated heavy domains and missing optional dependencies return structured errors; registry/schema/group identity stays compatible. |
| ARC-02 / P2 / M4 | Generic top-level `tools`/`algorithms` packages collide with other distributions; [`repository-folders.md`](../repository-folders.md#names-and-the-package-namespace) defers migration. | Choose a namespace and compatibility/version policy after checking conflicts, including that note's warning about another project's `mars` import. Migrate imports, package data, entry points, extraction markers and distribution checks together; installed coexistence tests pass. |
| ARC-03 / P2 / M4 | Heavy optional console/provider dependencies remain in the base install even for Python/MCP-only use. | Coordinate domain, console and model-adapter extras with ARC-01, measuring minimal supported installations. Selected features work without unrelated UI/provider packages; missing-feature diagnostics and installation docs are tested. |
| ARC-04 / P2 / M4 | `algorithms/hrdiagram_py/local_grid.py` and `isochrones.py` import `tools.config`, coupling algorithm loading to process-global application roots and bundle resolution. | Pass validated grid/settings from the tool layer through a documented seam. Test standalone algorithm imports and two independently configured calls without global monkeypatching; retain exact-track selection and missing-grid semantics. |
| MCP-01 / P1 / M1 | Sequential dispatch lock can be held by a long-running tool; no general deadline/cancellation or archive download byte/product budget. WCS-02 bounds solver attempts/owned-group timeout cleanup, not server cancellation, preprocessing or solver stdout/stderr bytes. | Define per-call/resource/download/solver-output budgets and cancellation semantics, coordinated with WCS/PUL limits. Stalled/cancelled work releases capacity; partial artifacts are not advertised as valid; prove bounded memory/disk/work without live bulk downloads. |
| MCP-02 / P3 / M4 | MCP output-schema declarations are deliberately deferred while structured results normalize non-finite numbers/bytes/errors. | Decide whether host benefit justifies exposing schemas. If accepted, validate every normalized success/error result class and actual host handling; otherwise retain an explicit deferral/revisit trigger. |
| INS-01 / P2 / M4 | **Partial.** rc6 CI and clean installed-wheel release jobs cover Linux/Python 3.12 and 3.13. Claude MCPB/Codex installers are merged. The Codex README records clean Fedora 44 x86_64/aarch64 app-server validation; that is upstream recorded evidence, not an actual desktop GUI test repeated here. Full macOS/Windows/Claude Code/Cursor and desktop detection/approval/media evidence remains incomplete. | Clean wheel fetch/verify/self-test and concurrent/interrupted install tests on each supported OS; permission checks; actual host registration, calls, skill/resources, approval/media and icon behavior. Record versions/transcripts. Use existing installers and §9 rather than rescheduling their implementation. |
| INS-02 / P3 / M4 | Native skill installer refuses an older pristine generated copy as well as a modified copy. | Document a safe upgrade or implement provenance/version-aware atomic replacement. Test pristine-old, modified-old, identical-current and interrupted updates; preserve user modifications. |
| INS-03 / P3 / M4 | **Partial.** Historical C7/Python 3.14 measurements are not rc6 measurements. Installer READMEs record roughly 640–700 MB dependencies and a 43 s Codex first start, with scope limits. Current CI targets are Python 3.12/3.13; desktop launchers choose 3.13 and latest-release dependencies. | Remeasure current OS/architecture, locked versus launcher-resolved environment, cold/warm imports and host startup during INS-01/ARC-01. Keep dated README figures as recorded measurements, not a fresh cross-platform guarantee. |
| INS-04 / P2 / M4 | **Open, discovered in 2026-10-05 refresh.** Claude/Codex launch the newest MARS release; only the Claude path has a cached offline fallback. The plugin's skill is a separately updated generated snapshot, so a server update need not update its skill. | Preserve the accepted latest-release design while documenting/testing resolver/offline/startup-failure behavior, version provenance, reproducible manual pin/rollback and server/skill compatibility. Bound the network refresh/startup path and record real-host behavior with INS-01 and AUD-02. A host timeout alone does not terminate all work. |
| PUL-01 / P1 / M2 | Periodogram artifact omits selected channel; static chart says Polarization XX even when searching Sum or YY (`tools/pulsar.py`). | Persist channel and render Sum/XX/YY correctly. Round-trip each channel and use an explicit unknown label for old artifacts. |
| PUL-02 / P0 / M1 | **Implemented/verified on continuation branch only, 2026-10-05 / R+C**, `ca9fb4f`; not in main/rc6. First-party guards cap input bytes/samples, background/fold/grid work, bins, audio rate/frames/duration and interpolation points before expensive paths; tiny/non-finite/non-progressing requests are rejected. Accepted-input arithmetic is unchanged. | `tests/test_pulsar_limits.py` uses six kill/reap-bounded direct/public subprocess cases and pre-allocation/work sentinels; ordinary five-scan parity/diagnostic folds remain valid (§6). Public stages return `invalid_input` with no artifact. Limits/provenance: `../pulsar-tool-pipeline.md` §6a and `../extraction.md`, Pulsar Sonification §6. TS-02 is also closed branch-only below; TS-24/25/26 quirks remain preserved. Merge/release outstanding; general plot/archive/server deadlines remain PUL-07/MCP-01. |
| PUL-03 / P1 / M1 | **Implemented/verified on continuation branch only, 2026-10-05 / R+C**; not in main/rc6. Spectra require finite vectors, three distinct times, finite positive variance and progressing finite grids/products; singular trials and overflowed/quantized-zero derived Nyquist intervals raise declared validation errors rather than escaping arithmetic or NaN successes. | `tests/test_pulsar_limits.py::test_degenerate_periodograms_raise_a_declared_validation_error`, `test_constant_periodogram_is_a_structured_failure` and `test_nyquist_derived_overflow_is_a_validation_error`; existing real-scan peaks unchanged (§6). Direct helpers reject with `ValueError`; public results carry `invalid_input` and no artifact. No change to variable weighted LS, confidence/trial science or mean-spacing Nyquist formula. TS-16/17 therefore remain partial. Merge/release outstanding. |
| PUL-04 / P1 / M2 | Frequency artifacts inherit Period (s)/log-axis chart semantics. | Render Frequency (Hz) on the intended frequency scale and return matching metadata; retain period-mode behavior. |
| PUL-05 / P1 / M1 | **Implemented/verified on continuation branch only, 2026-10-05 / R+C**, `9ea0002`; not in main/rc6. Five new regressions first reproduced escaping exceptions for empty/truncated/invalid ECSV and injected permission/disappearing-file failures; the ECSV read now translates parser/IO exceptions to the existing `parse_error` result contract. No computation changes. | The five regressions and full locked suite pass (§6); merge/release remains. Test locators: `tests/test_pulsar_plots.py::test_unreadable_ecsv_plot_returns_parse_error` and `test_ecsv_plot_read_failure_is_structured`; no plot artifact is advertised or created on failure. |
| PUL-06 / P1 / M1 | **Implemented/verified on continuation branch only, 2026-10-05 / R+C**; not in main/rc6. Per-file read/stat failures retain readable scans with declared `scan_unreadable` warnings; root/direct-path I/O returns declared `read_failed`, oversized headers return `parse_error`. Header reads are bounded to 256 comment lines/65,536 decoded characters. | `tests/test_pulsar_registry_failures.py`: eleven cases cover permission/disappearance, post-header stat failure, readable-neighbor/name resolution, root inspection/read and header size/line boundaries. Explicit stat/iteration avoids Python-version-dependent silent `is_file()`/`glob()` omissions. Focused/full regression gates passed (§6); merge/release outstanding. This is recovery for trusted-local scans, not a general directory/curation-cache quota or OS sandbox (AUD-03/MCP-01). |
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
| DOC-01 / P3 / M0→M5 | M0 portion closed: the master update fixed indexes/source crosslinks, moved the external snapshot, annotated TUI completion and replaced SIMBAD's obsolete deferred-ADS wording with current `tools.ads` locators. This refresh updates rc6/installer status. `AGENTS.md` still calls Python 3.13 the floor/CI target, whereas current `pyproject.toml`, CI and CLAUDE support 3.12/3.13; general stale-statement follow-through remains M5. | Reconcile the named agent-guide policy discrepancy with maintainer guidance; do not change runtime support simply to match stale prose. Keep planning sources routed here and replace stale statements with current code/evidence locators. Preserve dated history with corrections. Working contains this plan and its index; full closure records final checks and retained documentation debt. |

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
| WCS-01 | S1 / implemented branch-only / R+C | ATLAS rejects padded footprints above a constructible default 2-degree radius before initialization; explicit limits must be finite in (0, 5]. Chunked UCAC queries reject candidate/row/zone/index budgets rather than truncating. Synthetic bounded tests pass with existing WCS controls; provenance is extraction §5.8. No operator catalog compatibility claim; merge/release and full-call isolation remain outstanding. |
| WCS-02 | S1 / closed branch-only / R+C | `1dddb41` (provider snapshots `dfdfc7b`): omitted/None attempt limits select 300 s; configs/builders/public arguments validate finite 1–900 s, mutable backend inputs are revalidated, and malformed settings cannot silently remove a deadline. Astrometry.net receives CPU allowance plus the existing 30 s outer grace; owned POSIX group cleanup sends SIGKILL even after its leader exits. Two bounded native probes reproduced surviving children before the fix; final tests prove child termination, leader reaping, closed pipes, diagnostics and finite retry budgets. ATLAS still bounds only its blind matcher. Full-call/preprocessing/cancellation/output-byte work stays WCS-21/MCP-01; no Windows process-tree or configured astronomy solve evidence is claimed. Search/scale/parity formulas and retry policy are preserved. Merge/release outstanding; WCS extraction §5.7 and §6 ledger. |
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
| WCS-21 | S1 / partial branch-only / R+C | WCS-02 at `1dddb41` supplies finite attempt defaults and robust owned-group timeout cleanup; retry allowance propagation is tested. Source/catalog preprocessing, ATLAS oriented work, aggregate retry/full-call deadlines, server cancellation and solver-output byte budgets remain unbounded. Coordinate MCP-01 and WCS-01/25; per-attempt limits and longer host timeouts do not close this row. |
| WCS-22 | S3 / recheck / H | Synthetic `EQUINOX='J2000'` must exercise current hint path and return an actionable diagnostic. |
| WCS-23 | S3 / partial / C | Broad exception now records detail; wrapper distinguishes unavailable solver. Test missing binary/bad root/full disk taxonomy before further changes. |
| WCS-24 | S5 / recheck / H | Recheck FOV estimate on stripped temporary FITS and whether missing-FOV guard is reachable. |
| WCS-25 | S1 / implemented branch-only / R+C | Radius/padding are annotated constructible dataclass fields with finite bounds; dataclass-copy and invalid-setting tests pass. WCS-01 records their enforced pre-load contract. Merge/release outstanding. |
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
| PHOT-15 | S1 / closed **branch-only** / R+C | `a3e152a` replaces custom reference-expression `eval` with bounded numeric AST arithmetic: 2,048 characters, 256 nodes, 32 levels, literal exponent magnitude ≤16, 1,024-bit integers, 64 bands/128-character names and 32 alias hops. Namespace flattening/error propagation are band-count bounded; substitutions escape regex literals and reject ambiguous sanitized names. Safe pre-evaluator sentinels, wrong-arithmetic and escaped-regex failures reproduce the old mechanism without executing huge powers; a kill/reap-bounded post-fix child terminates normally. Invalid transforms return unresolved None/(None, None), preserving explicit-failure/no-preferred-fallback and source-skip semantics. Shipped reference polynomials keep exact arithmetic and numeric uncertainty propagation (§6); provenance: `extraction.md`, Field Calibration §5a. The Python settings/collection path is tested; registered tools do not expose custom expressions. No arbitrary-code/MCP exploit is claimed. Merge/release outstanding; this is not a global calibration-call/MCP budget. |
| PHOT-16 | S5 / recheck / H | Reference-driver swallowed exceptions/parity settings need reassessment against current recorded replay tests. |
| PHOT-17 | S4 / partial / C | Global deps module removed; sources/reference magnitudes/Header still mutate. Define caller ownership and test copy/reuse semantics. |
| PHOT-18 | S4 / recheck / H | Test RA-wrap matching and clarify arcsec/pixel tolerances independently. |
| PHOT-19 | S5 / recheck / H | Tentative stale third-edge point needs a pinned authoritative SEP C comparison. Do not conflate with fatal ALG-01 recursion. |

### 5.3 Catalogs / query — all 32 IDs

| ID | Stream / status / evidence | Current problem, correction or next evidence |
| --- | --- | --- |
| CAT-01 | S1 / implemented branch-only / R+C | Shared token candidates keep Johnson V distinct from SkyMapper violet v in selection and reference resolution; padded inputs and preferred fallback cannot reintroduce the pairing. Native v and explicit transforms remain valid. Deliberate divergence documented in extraction Catalogs §5.6; independent safeguards and preserved controls pass. Merge/release outstanding. |
| CAT-02 | S1 / closed branch-only / R+C | `f8a0af3`: functioning circle/box regions emit `SELECT DISTINCT TOP N`, default to declaration limit 5,000, validate integer 1–5,000 and cap rows before mapping even if the provider ignores TOP. Payload/input failures cannot invoke unbounded SDK fallback. Offline native SDK request/CSV/error parsing and runner/default/explicit limit tests pass (§6; Query extraction §5.11). Named-object lookup remains broken under CAT-18 and must reuse these bounds when repaired; HTTP-byte/parsing-memory/deadline budgets remain MCP-01, completeness CAT-19. Merge/release outstanding. |
| CAT-03 | S2 / open / C+H | B/R direct-band declarations outrank transforms; verify CDS photographic column provenance before scientific remapping. |
| CAT-04 | S2 / open / C+H | Tycho BT/VT declared as Johnson B/V; derive authoritative color transform and quantify before/after. |
| CAT-05 | S2 / open / C | UCAC wildcard maps every filter to Open; define relative-versus-absolute calibration policy and stop-on-success implications. |
| CAT-06 | S3 / open / C | APASS U transform references unavailable uprime; surface catalog/filter-specific failure or scientifically valid fallback. |
| CAT-07 | S3 / recheck / H | Test CRPIX at/outside array boundaries through current WCS box geometry. |
| CAT-08 | S2 / open / C | SkyMapper mutates caller constraints with flags; use independent per-catalog constraints and correct stale docstring. |
| CAT-09 | S2 / recheck / H | Non-square binning/rotation must establish swapped pixel-scale footprint error. |
| CAT-10 | S2 / open / C+H | J−K polynomial lacks valid-range guard; verify primary published range, then refuse/warn extrapolation. |
| CAT-11 | S2 / partial branch-only / R+C | `f8a0af3` rejects an unrepresentable SDSS polar RA span before emitting NaN SQL; offline regression pins the rejection. This is input containment, not a correction to preserved spherical footprint geometry or proof that sources cannot be dropped. Other footprint/scientific behavior still needs bounded reproduction and an explicit numerical-divergence decision in M2. |
| CAT-12 | S2 / open / C+H | APASS I transform provenance/substitution needs primary reference and a quantified validity envelope. |
| CAT-13 | S2 / open / C | Halpha values differ between intentionally distinct selection/resolution registries; explicit scientific decision, not registry merging. |
| CAT-14 | S2 / open / C+P | Registry/plugin names and transform-resolution source differ; fixing keys alone does not enable transforms. Define the complete resolution contract. |
| CAT-15 | S2 / open / C+H | SkyMapper constant offsets omit color terms; verify coefficients/primary references and supported stellar range. |
| CAT-16 | S2 / recheck / H | Narrowband/broadband relative and absolute zero points need distinguishable validity semantics. |
| CAT-17 | S4 / recheck / H | Cache-center quantization can shrink coverage; establish minimum footprint and fix no-shrink documentation/geometry. |
| CAT-18 | S3 / open / C+H | SDSS backend still calls singular `query_object`; check pinned installed API, then test supported binding/error. ALG-03 repairs only regions. Any named-object repair must use CAT-02/27's bounded SQL/input contract, avoid the incompatible native region/cross-ID seam, and distinguish empty/service-error results; do not count region tests as named-object evidence. |
| CAT-19 | S2 / open / C+H | Brightness-sorted truncation may bias fitting; inspect provider truncation metadata and expose completeness. |
| CAT-20 | S3 / recheck / H | Renamed/missing columns can make populated responses appear empty; record mapping failures without dropping entire usable rows. |
| CAT-21 | S4 / partial / C | Empty otype fallback is now documented; validate current star/galaxy codes and raw-code preservation policy. |
| CAT-22 | S3 / open / C | First SIMBAD failure disables resolution for process lifetime; retry/expiry with deterministic transient-failure tests. |
| CAT-23 | S2 / recheck / H | Inventory remaining truthiness-based zero magnitude/error readers; some direct ref-mag paths already use `is not None`. |
| CAT-24 | S5 / recheck / H | Derived Landolt/Stetson columns may include built-in names; use recorded provider columns and expression parsing tests. |
| CAT-25 | S4 / open / C | NaN→None removes invalid-versus-absent provenance; decide metadata/error contract before serialization changes. |
| CAT-26 | S5 / recheck / H | Profile cache pruning and test bounded directory IO/failures; avoid unsupported performance claims. |
| CAT-27 | S1→S5 / closed branch-only / R+C | `f8a0af3`: MARS SQL payload projections require 1–64 literal ASCII identifiers of at most 64 characters; SQL expressions/comments/qualified names and missing fields are rejected before transport. Shipped fields remain trusted; custom metadata/native Python payload input is the guarded boundary, not an arbitrary-field registered-tool argument. Tests exercise malformed projections and accepted quality-filtered requests. This closes the defense-in-depth identifier finding, not a proven MCP injection exploit or a sandbox for arbitrary native SDK `query_sql` calls. Merge/release outstanding. |
| CAT-28 | S5 / open / C | Token normalization strips whitespace and typographic quotes separately; test combined padded spellings. |
| CAT-29 | S5 / partial / C | Current query uses bound CATALOGS; historical extraction-provenance correction needs a current documentation crosscheck. |
| CAT-30 | S2 / recheck / H | First nonempty catalog may stop a scientifically insufficient calibration; define minimum source/fit-quality contract. |
| CAT-31 | S5 / protected / C | Private one-time mutating catalog classes are deliberate parity; reassess only if exposure/lifetime changes. |
| CAT-32 | S4 / open / C+H | APASS uses recno identifiers; confirm CDS ingest stability and define cache/dedup identity policy. |

### 5.4 Retired TypeScript findings / current Python paths — all 31 IDs

| ID | Stream / status / evidence | Current problem, correction or next evidence |
| --- | --- | --- |
| TS-01 | S1 / implemented branch-only / R+C | Legacy Galactic longitude uses atan2 and [0,360) wrapping; invalid coordinates reject. Deliberate 180-degree correction is confined to legacy helper/summary callers, not the new fitter. Nine independent Astropy quadrant/pole checks use a 0.002-degree allowance for unchanged legacy frame constants; unaffected summary/mass fixtures pass. TS-20/21 remain protected; merge/release outstanding. |
| TS-02 | S1 / closed **branch-only** / P+R+C | Both pulsar (PUL-02, `ca9fb4f`) and direct/tool variable folding (`712c0a4`) now have finite/sample/iteration/aggregate-work guards. Variable `validate_fold_work` is shared by the tool/algorithm; at most 2,000 rows, 100,000 iterations per sample and 10,000,000 conservative sample-iterations. Six direct calls stalled before guards; all 18 new cases pass with preserved default/zero-period, exact-multiple and TS-04 alignment/empty behavior (§6). Provenance: `extraction.md`, Light Curve §12b. Merge/release outstanding; the separate direct weighted-spectrum loop is ALG-02, not unfinished modulo work. |
| TS-03 | S1 / closed **branch-only** / P+R+C | `1042f70` uses one paired-row selection for both values and weights; paired rows missing combined uncertainty fail explicitly, and direct arrays require aligned finite positive representable weights. Unpaired rows remain excluded as upstream with public `unpaired_rows_skipped` counts. Object/null ingest artifacts already round-tripped; the reproduced numeric masked-cell NaN conversion is corrected to `None`. Tests cover both ECSV representations, raw partial-source stage-1→2 handoff, unchanged paired spectrum and invalid/nonscalar input failures without artifacts (§6). TS-09/14 weighted/error arithmetic and TS-04 fold alignment stay preserved. Provenance: `extraction.md`, Python M1 weighted-periodogram acceptance contract; merge/release outstanding. |
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
| TS-16 | S3 / partial / P+R+C | Empty global maxima return None. PUL-03 rejects non-finite/degenerate pulsar spectra before peak selection **on this branch**. `1042f70` rejects empty/non-finite public variable spectra but does not change peak helpers; direct peak contracts and surviving caller reachability still need focused evidence, so this shared finding is not closed. |
| TS-17 | S3 / partial / P+R+C | Browser alert retired. PUL-03 and `1042f70` return structured public failures for degenerate pulsar/variable spectra **on this branch**. Variable empty/all-unpaired, constant and non-finite/invalid-weight cases return `invalid_input` and no artifact; accepted fixture powers are unchanged. Direct weighted constant-series NaN stays intentionally pinned, not silently corrected. Decide and test remaining direct-helper degenerate-input contracts with scientific-divergence review before closure; public containment still needs merge/release. |
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
| M1 ART-01 containment, 2026-10-02 | Test-first cases cover absolute and parent traversal, escaping and contained symlinks, a scope changed after entry, path-like extensions on every public extension-bearing writer, and an explicit absolute caller-selected root. The 11-file artifact/agent/benchmark/MCP/pulsar/HR/radio/variable-star surface passed **363 tests** in 4m38s on Python 3.14.7/Linux aarch64. | Artifact destinations are contained without removing supported explicit Python output roots. The 2026-10-05 continuation supplies current-main full-suite evidence below; merge/release is still outstanding. |
| PR #98 CI, 2026-10-01, merged as `81017e6` | Initial runs at `3a8b228`: Python 3.13 tests, syntax, package, repository shape and secret scan passed; zizmor 1.30.1 rejected 25 mutable action references. Verified upstream commits replaced those references without suppressing the audit. Final head `3a602bc`: CI run `36914768038`, secret scan `36914768075` and workflow-safety run `36914767931` all passed, including actionlint, zizmor and both required aggregate checks. | PR #98's required online checks are closed. Release publishing, platform and actual host gates remain separate. |
| Master completeness, 2026-10-01 | Automated comparison confirms every original algorithm ID occurs exactly once: 110/110. Pulsar/validation/external rows and local master/index links/anchors checked. | Refresh inventory when code or source reviews change; source review completeness does not prove absence of undiscovered bugs. |
| rc6 main and release, inspected 2026-10-05 | At `6d966de`, [CI run 37102344320](https://github.com/SkynetRTN/MARS/actions/runs/37102344320), [secret scan 37102344331](https://github.com/SkynetRTN/MARS/actions/runs/37102344331) and [workflow safety 37102344423](https://github.com/SkynetRTN/MARS/actions/runs/37102344423) completed successfully. [Release run 37102347501](https://github.com/SkynetRTN/MARS/actions/runs/37102347501) passed build, clean installs/self-tests on Python 3.12 and 3.13, pinned-data availability, installed-data verification, GitHub/TestPyPI publication, served-wheel comparison/self-test and PyPI publication. [rc6](https://github.com/SkynetRTN/MARS/releases/tag/v0.1.0rc6) carries wheel, sdist and SHA256SUMS, published 2026-10-03 UTC. | This closes the formerly unexecuted release-workflow gate for that main revision, not the branch-only M1 fixes. No MCPB asset is attached. macOS/Windows/actual desktop acceptance and configured solver/live-service evidence remain separate. |
| Continuation focus, 2026-10-05, after merging rc6 main | Before the merge, artifact/benchmark focus passed **72 tests**. After the merge, artifact/benchmark/photometry/installer/HR/bundle focus passed **210 tests**, five warnings, in 85.31 s on Python 3.14.7/Linux aarch64. PUL-05's five new malformed/read-failure cases each failed before the fix and all **five passed** after it. `uv lock --check --offline` passed. | Full-suite evidence follows. Local Python 3.14 evidence is not supported-target CI or desktop-host validation. |
| Continuation full regression gate, 2026-10-05, `9ea0002` | `uv run --locked --extra mcp pytest -q`: **2,906 passed, 48 skipped, 188 warnings** in 329.11 s on Python 3.14.7/Linux aarch64. This includes slow tests, ALG-01 subprocess crash/guard characterization, artifact/agent/MCP coverage, five new PUL-05 regressions and upstream HR/installer/bundle tests. Syntax compilation, generated skill parity, lock consistency and whitespace checks passed. The updated master retains **110/110 unique historical IDs**; its/index/installing local links resolve. | Branch-only evidence. Skips remain 40 opt-in live catalog/query/model cases, four unavailable saved benchmark runs and four solver/catalog-resource cases (including the legacy no-solution skip tracked by VAL-03). Run continuation PR CI on supported Python 3.12/3.13 before merge; real host/platform and live-service gates stay open. No broad scientific-correctness claim follows from the preservation suite. |
| M1 PUL-02/03/06 continuation, 2026-10-05, `ca9fb4f` | Before the guards, three direct subprocess probes hit the 8 s kill/reap deadline and 17 other rejection/error-boundary cases failed; six initial scan recovery cases also failed. The final focused pulsar/artifact/MCP run passed **308 tests** in 50.39 s, including **42 new regressions** across the two new test files. Error-code and skill/plugin invariants passed **65 tests**; skill-creator validation, generated-copy parity, syntax, lock and whitespace checks passed. | Branch-only on `feature/m1-status-continuation`; preservation/parity fixtures pass, but no supported Python 3.12/3.13 CI, release, real-host or new live-service evidence is claimed. The first in-progress full run caught undeclared codes (corrected) and skill-copy snapshot drift during regeneration; it was not an acceptance pass. TS-02 closes in the following checkpoint; TS-03, ALG-02, other S1 rows and AUD/MCP policies remain open. |
| M1 pulsar full regression and wheel gate, 2026-10-05 | Stable final snapshot: `uv run --locked --extra mcp pytest -q` passed **2,948 tests, 48 skipped, 188 warnings** in 265.13 s on Python 3.14.7/Linux aarch64, including slow tests and all 42 new regressions. A temporary locally built wheel passed the distribution/licence check and contains `algorithms/pulsar/limits.py` and the updated skill source. Master/index/pipeline local links resolve and all **110/110 historical IDs** remain unique. | This is a local branch build with the existing rc6 version string, **not** a new published rc6 artifact or clean supported-target installation. The 48 skipped live/saved-run/solver cases retain their prior dispositions. Supported Python 3.12/3.13 PR CI, merge/release and real-host/platform gates remain outstanding. |
| M1 TS-02 variable continuation, 2026-10-05, `712c0a4` | Six direct fold/modulo cases stalled at the 5 s kill/reap deadline before the guards; five settings cases also failed to reject, while two accepted-input controls passed. The final focused variable-star/preservation/MCP run passed **139 tests** in 13.57 s, including **18 new regressions**. Sample and aggregate work sentinels prove pre-allocation/pre-loop rejection; the public tool translates the shared guard to `invalid_input` with no artifact. Syntax and whitespace checks passed. | TS-02 is contained **branch-only** without replacing subtraction or changing ordinary photometric arithmetic. The first focused run caught a work-budget probe with 2,001 rows; it now uses the supported 2,000 rows to reach the intended work check. TS-04 remains preserved, and TS-03/09/17 remain separate. |
| M1 variable continuation full regression gate, 2026-10-05, `712c0a4` | `uv run --locked --extra mcp pytest -q`: **2,966 passed, 48 skipped, 188 warnings** in 274.90 s on Python 3.14.7/Linux aarch64, including slow tests, all 18 new TS-02 cases, all 42 new pulsar cases, existing preservation assertions and MCP integration. Lock, syntax, skill parity, whitespace and master/index/pipeline local-link checks passed; **110/110 historical IDs** remain unique. | Local branch-only evidence, not supported Python 3.12/3.13 PR CI or a merged/released installation. The 48 live/saved-run/solver skips retain their prior dispositions. ALG-02, TS-03, other S1 rows and AUD/MCP policies remain the next M1 scope; do not mark M1 complete. |
| ALG-02 direct weighted-loop probe, 2026-10-05 | A subprocess importing `lomb_scargle_with_error` emitted `READY` then stalled for three finite varying samples, positive errors, start=1, stop=`math.nextafter(1,2)`, steps=1000. It was killed/reaped after **5 s**, exit -9, with no stderr. Existing public range validation rejects the same non-progressing grid under the fixed-2,000-step tool contract. | New direct-library finding scheduled in M1/ALG-02. This probe does not establish served-tool reachability or authorize a weighted-formula change; retain TS-09/17 parity until separately reviewed. |
| M1 ALG-02 / TS-03 weighted continuation, 2026-10-05, `1042f70` | Initial test-first run: **23 failed, 10 passed**, including two direct grid stalls killed/reaped after 5 s each. Separate adapter characterization: object/null missing cells passed both controls; **two numeric masked-cell cases failed** by conversion to NaN. Post-fix variable/preservation/error-code/MCP focus passed **195 tests** in 17.91 s, including **52 new regressions** across the two new files. Shared and runtime grid guards, pre-allocation/work sentinels, weights, numeric-mask/null handoffs, raw partial-source ingest, warnings and degenerate public failures are covered. Skill source regenerated both copies; skill-creator, renderer parity, lock, syntax and whitespace checks passed. | Branch-only on `feature/m1-status-continuation`; TS-03 and ALG-02 acceptance paths are contained without changing the weighted/error formulas, 2,001-row fixture grid or direct constant-series NaN. The full-suite gate follows; supported Python 3.12/3.13 PR CI, merge/release and real-host/platform gates remain outstanding. Remaining S1 and AUD/MCP policies are next; M1 remains partial. |
| M1 weighted continuation full regression and wheel gate, 2026-10-05, `1042f70` | `uv run --locked --extra mcp pytest -q`: **3,018 passed, 48 skipped, 188 warnings** in 268.23 s on Python 3.14.7/Linux aarch64, including slow tests, all 52 new weighted-contract cases and existing numeric/parity/MCP coverage. A temporary offline wheel passed the distribution/licence check; its weighted algorithm, public adapter, code vocabulary and skill source match this checkout byte-for-byte. Master has **110/110 unique historical IDs**, with its 17 local file-link destinations resolving; lock, syntax, skill validation/render parity and whitespace checks passed. | Local branch-only evidence with the existing rc6 version string, **not** a new published rc6 wheel or clean supported-target install. The 48 live/saved-run/solver skips retain prior dispositions. Supported Python 3.12/3.13 PR CI, review/merge, release and actual-host/platform gates remain outstanding. M1 stays partial; next are remaining S1 solver/catalog/legacy rows and AUD-01/02/03/MCP-01. |
| M1 PHOT-15 expression continuation, 2026-10-05–06, `a3e152a` | Safe test-first probes: **22 failed, 14 passed, two deselected**, with dangerous expressions intercepted before execution; the two deselections excluded an uncapped direct-power call and the parser sentinel while its patch scope was corrected. Earlier parser interception interfered with pytest reporting, not an acceptance run. Post-fix final calibration/reference/query/MCP focus passed **342 tests**, two existing warnings, in 13.51 s, including **48 new regressions**. Covers pre-parser/evaluator limits, literal/invalid regex keys, namespace/alias/integer budgets, calibration collection, exact reference-registry polynomial arithmetic, error propagation and a 5 s kill/reap-bounded child (with 64 MiB incremental mapped-memory cap on Linux). Lock, syntax, generated-skill parity and whitespace checks passed. | Branch-only on `feature/m1-status-continuation`. The initial 22 failing new acceptance cases are not 22 independently proven vulnerabilities. No giant power was executed in the old implementation and no arbitrary-code/MCP exploit is claimed. New custom-input acceptance bounds are explicit in Field Calibration §5a; known catalog scientific mappings and preserved zero-point math are unchanged. Full-suite evidence follows; remaining solver/catalog/legacy S1 and AUD/MCP work stays scheduled in §2.1. |
| M1 PHOT-15 full regression and wheel gate, 2026-10-06, `a3e152a` | `uv run --locked --extra mcp pytest -q`: **3,066 passed, 48 skipped, 188 warnings** in 265.61 s on Python 3.14.7/Linux aarch64, including slow tests and all 48 new expression cases. Temporary offline wheel passes the distribution/licence check and its expression implementation matches the checkout byte-for-byte. Syntax, lock, generated-skill parity and whitespace checks passed. | Local branch-only evidence at the existing rc6 version, not a published rc6 replacement or supported Python 3.12/3.13 clean install/CI. The 48 live/saved-run/solver skips retain prior dispositions; PR CI, review/merge, release and actual host/platform gates remain outstanding. PHOT-15 is closed branch-only; M1 remains partial. |
| M1 CAT-02/27 and ALG-03 SDSS continuation, 2026-10-06, `f8a0af3` | Test-first 49-case probe returned **43 failed, six passed**; one failure was a test assumption about SDK SQL whitespace, subsequently corrected rather than an implementation defect. Post-fix final query/geometry/selection/fieldcal/MCP focus passed **423 tests, one skipped, six warnings** in 14.22 s on Python 3.14.7/Linux aarch64, including **62 new regressions**. Native SDK endpoint construction and CSV/error parsing use offline HTTP stubs; sentinels prove response slicing precedes mapping and malformed input cannot reach transport/cache work. Temporary offline wheel passes the distribution/licence checker and its SDSS module matches the checkout byte-for-byte; lock, syntax, generated-skill parity and whitespace checks passed. | Branch-only, not main/rc6. Intermediate focused failures exposed test assumptions about upstream numeric IDs, SDK whitespace and floating coordinate text; tests were corrected without changing those preserved behaviors. No live provider call, named-object validation, full catalog completeness, arbitrary SDK SQL sandbox or HTTP-byte/whole-call budget is claimed. Full-suite gate follows; CAT-11 remains partial, CAT-18/19 and MCP-01 remain open. |
| M1 SDSS full regression and wheel gate, 2026-10-06, `f8a0af3` | `uv run --locked --extra mcp pytest -q`: **3,128 passed, 48 skipped, 188 warnings** in 284.88 s on Python 3.14.7/Linux aarch64, including slow tests, all 62 new SDSS regressions and existing scientific/preservation/MCP coverage. Temporary offline wheel passes the distribution/licence checker and contains the checkout's SDSS implementation byte-for-byte. Lock, syntax, generated-skill parity and whitespace checks pass; master retains **110/110 unique historical IDs** and all 17 local file-link destinations resolve. | Local branch-only evidence with the existing rc6 version string, not a new published rc6 artifact or clean supported Python 3.12/3.13 install/CI. The 48 live/saved-run/solver skips retain prior dispositions. CAT-02/27 and ALG-03 are closed branch-only; CAT-11 remains partial and named-object CAT-18, scientific completeness CAT-19, remaining S1 and AUD/MCP work remain open. Supported-target PR CI, review/merge, release and actual host/platform gates remain outstanding; M1 is not complete. |
| M1 WCS-02 finite attempts/cleanup, 2026-10-06, `1dddb41` + `dfdfc7b` | Initial 48-case test-first run: **40 failed, eight passed**, including two native owned-group probes with a SIGTERM-resistant child and a live/already-exited leader; every failure path killed/reaped only test-owned processes. Final WCS/MCP/skill/provider-schema focus passed **442 tests, four skipped, 43 warnings** in 14.24 s on Python 3.14.7/Linux aarch64, including **73 new regressions**. Direct/builders/mutable/public/environment budgets, CPU/backstop/retry propagation, actual timeout diagnostics, leader reaping/pipe closure and stubborn-child termination are covered. Temporary offline wheel passes the distribution/licence check; limits, backend, config, schema and skill source match the checkout byte-for-byte. Skill-creator validation, both rendered copies, syntax, lock and whitespace checks pass. | Branch-only. First full run had **four schema-snapshot failures, 3,197 passed, 48 skipped, 198 warnings** in 299.95 s, not an acceptance pass. The documented generator refreshed only the intended timeout description/900 s maximum in all four provider dialects; final focus above ran without regeneration mode. No operator-index/catalog solve, Windows tree termination, full-call/server cancellation or stdout-byte cap is claimed. Full-suite gate follows; remaining S1/AUD/MCP work stays scheduled in §2.1. |
| M1 WCS-02 full regression and wheel gate, 2026-10-06, `1dddb41` + `dfdfc7b` | Stable final snapshot: `uv run --locked --extra mcp pytest -q`: **3,201 passed, 48 skipped, 198 warnings** in 272.66 s on Python 3.14.7/Linux aarch64, including slow tests, all 73 new WCS regressions, the four regenerated provider-schema checks and existing scientific/preservation/MCP/skill coverage. The ten additional warnings are the existing FITS date-fix warning emitted by new public/environment tests. Temporary offline wheel passes distribution/licence checks; limits, backend, config, schema and skill source match this checkout byte-for-byte. Lock, syntax, skill-creator validation, generated-copy parity and whitespace checks pass; **110/110 historical IDs** remain unique and all 17 master local file-link destinations resolve. | Local branch-only evidence at the existing rc6 version, not a newly published rc6 artifact or supported Python 3.12/3.13 clean install/CI. The 48 live/saved-run/solver skips retain their prior dispositions. WCS-02 is closed branch-only; WCS-01/04/21/25, CAT-01, TS-01 and AUD/MCP work remain scheduled. Supported-target PR CI, review/merge, release and actual host/platform gates remain outstanding. M1 stays partial; next is WCS-01/25's pre-load catalog bound. |
| Platforms/hosts/workflows | Source/DAG inspection, SDK tests, documented host configuration and the current-main CI/release outcomes above. Codex installer README records Fedora 44 app-server/container evidence and its scope; Claude launcher tests establish configuration/refresh/fallback behavior, not a GUI installation. | Actual macOS/Windows/Claude/Cursor validation remains INS-01/D0; do not infer it from config, app-server or package tests. Repeat online checks for any continuation PR before merge. |

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

**Status:** partially implemented on main/rc6, refreshed 2026-10-05.
PR #102 built the Claude Desktop MCPB; #108/#109 revised it to follow the latest
release, and #110 added the Codex plugin. Implementation landed ahead of the
original D0/D1 evidence order; that is not retroactive proof those gates passed.
Keep the existing installers and finish the missing validation/distribution
work below. Owner role: packaging/MCP maintainer with actual macOS/Windows
desktop testers. INS-01 owns overlapping host-validation work; INS-04 owns
latest-release/offline/skill compatibility. Record shared evidence once.

**Prerequisites:** installed stdio MCP surface, per-host instructions in
[`installing.md`](../installing.md), current vendor facts and available host
machines. The [dated proposal](../analysis/mcp-desktop-hosts.md) keeps the
rationale and sources, not a second active plan. Claims about application
support, wheel availability, startup timing and desktop versus ordinary
ChatGPT chats still require actual host/platform evidence. The manifest uses
MCPB 0.4 `uv` and the launcher selects Python 3.13, but its MARS requirement is
now `@latest`, not an exact release. Recorded installer measurements and
Fedora app-server tests do not close D0 or establish current macOS/Windows
startup/GUI behavior (INS-01/03).

**Unblocks:** non-terminal researchers using Claude Desktop or the ChatGPT
desktop app's Codex without hand-editing paths/configuration. No HTTP server,
browser service or algorithm/model-backend change is included.

| Phase / priority | Ordered work and decision | Exit evidence |
| --- | --- | --- |
| D0 / P2 — **partial, actual desktop gate open** | Use the existing installers on Claude Desktop/macOS and the ChatGPT desktop app's Codex; Windows where available. Retain the recorded Fedora app-server evidence without labelling it a GUI run. Complete the five-step detection on B0329+54/B1133+16 and an explicitly enabled live SIMBAD search. | App/package/OS versions and transcripts demonstrate period provenance, instructions/skill delivery, inline media, approval prompts, cold starts and timeout behavior in both actual apps. Missing Windows evidence stays INS-01; live checks stay opt-in. |
| D1 / P2 — **docs implemented, reproduction gate open** | PR #103's compact install guide and installer READMEs provide managed-uv/manual/plugin routes and configuration. Refine them from D0 measurements; no generic config-writing helper was added. | A docs-only reader reproduces D0. Preserve unrelated host config if any helper is later accepted, refuse conflicting entries without consent and test malformed/preservation behavior. Existing plugin/native registration routes are preferred while sufficient. |
| D2 / P3 — **build implemented, spike questions partial** | PR #102 provides the MCPB 0.4 `uv` launcher; #110 provides the plugin and generated skill. Both fetch latest MARS, intentionally superseding the proposed exact-MARS pin. Build/config/launcher tests exist; manual data-fetch commands are documented. | Finish actual macOS/Windows host/startup/retry/distribution and non-terminal data-fetch evidence. INS-04 tracks offline/update/rollback/skill compatibility; INS-03 tracks measured environments. Do not rebuild an already implemented spike or add a speculative data-fetch tool. |
| D3 / P3 — **partial, release asset absent** | Manifest, launcher, Python 3.13 selection and ADS-secret/tool-group/MARS_HOME controls exist. Current `release.yml` and rc6 assets do not distribute an MCPB; users build it manually. The latest-release policy decouples extension version from MARS tag. | Decide/document manual-build versus published-asset distribution. If accepted, add a manifest/packed-file validation gate and release asset with its own version/provenance; do not require a MARS version pin contrary to #109. Complete fresh macOS double-click detection and Windows evidence; recheck distribution policy before proposing directory submission. |
| D4 / P2 — **partial documentation, closure open** | Installation, architecture, CLAUDE rules and installer READMEs now describe actual installers; this refresh reconciles their status here. Historical D2 measurements stay in the dated proposal. | Close or explicitly defer outstanding D0–D3 acceptance with PR/test/transcript locators, fold validated outcome/caveats into references, and retain one master plan. Missing real-host evidence or unpublished MCPB assets cannot be hidden by an archive annotation. |

Browser hosts remain parked (§8), including remote local-path/result contract
changes, OAuth, cloud-call limits and hosted-service operations. Reopening them
requires a separate sponsor/requirements decision; desktop friction does not
authorize an HTTP transport or production service.
