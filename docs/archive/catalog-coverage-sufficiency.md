# Catalog coverage and sufficiency implementation plan

> [!NOTE] Archived 2026-10-28
> This M2 checkpoint is complete on `feature/m2`. The original implementation
> plan and validation record below are historical. Current gate status and
> subsequent review fixes are maintained in the
> [master continuation plan](../working/master-continuation-plan.md).
> See the [acceptance record](../analysis/catalog-coverage-sufficiency.md)
> for technical evidence and retained limits.

**Goal:** Close the M2 coverage/sufficiency gate on the existing `feature/m2`
branch while preserving reference magnitudes, transforms and solver arithmetic.

**Design:** Query WCS footprints with enclosing spherical cones, then clip to
the actual detectors. A cone encloses an undistorted TAN detector's rectangular
projection, including off-detector CRPIX, rotation, anisotropic scales, RA seams
and poles. Other projections/distortions receive an explicit coverage warning;
sampled boundaries cannot establish completeness. Keep historical box helpers
available, but remove the polar NaN failure from explicit box clipping and SQL.

Keep priority-ordered first-nonempty fallback and disclose which alternatives
were not queried. Automatically pooling catalogs would change reference systems;
a raw-row minimum cannot establish how many usable stars survive photometry.
Every successful fit reports actual survivor counts and states that sample
sufficiency is unverified. A finite empirical fit uncertainty is not a completeness,
spatial/colour coverage or systematic-error test. Degenerate fits retain M3's
existing refusal. No arbitrary star-count threshold establishes reliability.

Report a possibly capped provider response before mapping or detector clipping
can hide the cap. Retain row limits and ordering; name brightness bias when the
request sorts by magnitude. Collect notices per operation, without storing
mutable last-query state on shared catalog instances. Carry notices into both
photometry tool results, including calibration failures. Copy SkyMapper
constraints before adding the existing flags default.

**Constraints:** Python 3.13; no new dependencies; no transform, H-alpha,
uncertainty propagation or solver arithmetic changes; network tests stay opt-in;
do not edit executable files while pytest runs. No vault writes requested.

**Review focus:** raw rows discarded during mapping/clipping; cache-centre
rounding at detector edges; failures after a capped query; nested/concurrent
notice collectors; rejected stars inflating the reported calibration sample.

## Tasks

- [x] Geometry and constraint isolation: regression tests for polar clipping,
  SQL, a detector grid across seams/poles/off-detector CRPIX, and caller-owned
  constraints; implement enclosing-cone WCS queries and copy constraints.
- [x] Coverage notices: tests for at-limit VizieR/SDSS responses before mapping,
  first-nonempty fallback, failed catalogs and isolated collectors; implement
  operation-scoped notices with no changes to list-returning query APIs.
- [x] Public calibration disclosures: test actual tool runs, solver survivors,
  offline supplied references and failures; propagate coverage notices and
  report unverified sample sufficiency with actual surviving-star counts.
- [x] Review and validate: focused M2/M3 checks, complete offline suite, opt-in
  live catalog checks, compilation, schema/guidance and whitespace checks;
  document acceptance and commit on `feature/m2`.

## Progress

Baseline: `4eaa725`, clean `feature/m2`; the immediately preceding full suite
passed 3,934 tests with 85 skipped. Vault lookup used linked-note/text fallback
because the retrieval index is absent; the older catalog note is stale relative
to verified M2/M3 changes.

Review reproduced a TPV footprint silently treated as undistorted TAN; two
regressions failed before the effective-header detection fix and pass after it.
Review also identified registered measurement/replay fits outside the original
two photometry wrappers. They now share sample disclosures and survivor counts.
Direct one-star/zero-uncertainty fits follow M3's existing no-solution policy;
four new public-fit tests reproduced those omissions before the fixes.
Survivor counts use an independent private integer from the exact fit mask,
without depending on reference-provenance dictionary keys. Solver arithmetic
and transforms are unchanged. Concluding validation passed 613 focused tests,
3,979 whole-suite tests (88 skipped) and 15 live tests. All review findings
are fixed. Full evidence and retained limits are in
[the acceptance record](../analysis/catalog-coverage-sufficiency.md).
