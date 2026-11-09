# M5 catalog fixes implementation plan

> **For agentic workers:** Use test-driven implementation with independent file
> ownership and a fresh combined review. The user authorized closing this box
> on the existing `feature/m5-geometry` branch; no worktrees or branch switches.

**Goal:** Correct the current catalog findings, validate their maintained paths,
and close M5's fifth square with explicit remaining policy/product limits.

**Architecture:** Extend existing query/parser/cache seams rather than add a
new backend. Cached boxes must enclose the original region; column analysis
must distinguish callable names from real columns; cache I/O may fall back
without hiding provider failures or duplicating network requests.

**Tech stack:** Existing locked Python, Astropy/astroquery, NumPy, Pydantic and
offline pytest fixtures.

**Spec:** [Catalog investigation](../../analysis/m5-catalog-parsing-cache-identity.md)
and [master M5 requirements](../../working/master-continuation-plan.md#m5-resolve-the-specific-older-reports-that-remain-unverified).

## Constraints and review focus

- Preserve cone enclosure, row/work caps, provider error distinctions, aliases,
  single-letter passband case and already-correct zero-value mapping.
- Preserve real literal columns named `int`, `float`, NumPy exports or string
  methods while excluding only actual callable references/attribute names.
- Test cached/uncached box edges, RA wrap, both poles and different dimensions.
- Cache directory/eviction faults must not suppress network, parser, save-file
  or cancellation errors, retry indefinitely, or replay mutating requests.
- Preserve known zero errors without assigning zero to missing uncertainty.
  Keep the separately disclosed legacy U-error formula outside this correction.
- Keep intentional empty SIMBAD labels; preserve unknown raw codes and map
  known machine star/galaxy codes without querying metadata on every request.
- Treat masked optional identifiers as absent, without inventing persistent
  APASS identifiers or changing exact-row/catalog dedup policy.
- Wire-null behavior, pruning frequency and conditional ordinal identity retain
  their dispositions. This deployment uses UCAC5; UCAC4 remains unverified legacy.

## Implementation

- [x] Query coverage/dependencies: own `algorithms/query/vizier.py` and new
  `tests/test_m5_catalog_query_fixes.py`. Write failing controls for box
  enclosure through both backends, real SDK request columns, missing literal
  builtin coordinate columns and masked optional IDs. Implement minimal fixes;
  retain `_round_for_cache`/cone call compatibility with SDSS.
- [x] Cache resilience: own `algorithms/query/cache.py`,
  `algorithms/query/sdss.py` and new `tests/test_m5_catalog_cache_fixes.py`.
  Prove directory-fault fallback and direct-SDSS error-entry recovery, with
  working cached controls and provider errors that still surface normally.
- [x] Landolt errors: own `algorithms/catalogs/landolt_catalog.py` and new
  `tests/test_m5_landolt_errors.py`. Prove known-zero versus absent uncertainty
  across U/B/R/I without altering magnitude values or the retained nonzero
  formula. Verify real mapper and numeric-reference handoffs.
- [x] SIMBAD labels: primary agent owns `algorithms/catalogs/simbad.py`,
  `algorithms/query/simbad.py` and new `tests/test_m5_simbad_types.py`.
  Convert common/unknown-code behavior to public correctness controls.
- [x] Primary agent converts original investigation bug pins after the owned
  changes land, preserving policy/conditional controls. Reconcile current
  provenance, guidance and master/test-map status with the implementation.
- [x] Independently review combined changes and resolve verified findings.
  Lambda/comprehension scope and default-cache discovery permissions gained
  failing controls before correction; final independent group: 195 passed.
- [x] Freeze code/tests/guidance, run focused and full locked validation.

Delivery after validation: commit/push this feature branch and attempt the
shared-vault checkpoint under the existing standing authorization.

## Verification evidence

- Initial SIMBAD correction: 8 failures/5 passes before implementation, then
  13 passes. SDK cache faults: 20 failures/5 passes before implementation,
  then all controls pass; discovery faults added two independently reproduced
  failures. Original investigation assertions converted to correction checks
  reproduced 20 failures before the remaining query/Landolt changes.
- Landolt positive partial-error arithmetic remains the literal upstream
  `sqrt(sum / 2)` for I; the initial test expectation was corrected before
  production changes. The retained wrong-colour U formula remains disclosed.
- New scope controls reproduced five failures. A seeded wide-box probe found
  decreasing longitude extent above 180 degrees, gained two public-backend
  regression cases and now passes all 20,000 enclosure probes.
- Final focused integration: 890 passed, 1 expected network skip, 6 FITS notices
  (5.56 seconds). Compilation, generated-guidance and whitespace checks pass.
- Full locked validation completed 2026-11-09: 4,964 passed, 94 skipped, 214
  FITS notices, no failures (407.55 seconds, Python 3.13.15). All 453 frozen
  code/test/guidance files are unchanged. Fifth square closed; M5 now 5/6.
