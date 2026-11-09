# M5 completed-work review and catalog investigation plan

> **For agentic workers:** Use the requesting-code-review workflow for the
> completed work and execute the investigation below with independent,
> non-overlapping test-file ownership. The user has authorized this sequence
> on the existing feature branch; no worktrees or branch switches.

**Goal:** Review M5's four completed squares, then establish current behavior
and reachability for catalog parsing, cache and identity reports.

**Architecture:** Trace maintained entry points before classifying old reports.
Use real parsers/mappers and independently specified numerical controls, with
offline provider/SDK seams. Keep legacy quirks, already corrected behavior,
format uncertainty and newly confirmed defects distinguishable.

**Tech stack:** Existing locked Python environment, NumPy/Astropy/Pydantic,
pytest, installed astroquery, and read-only local catalog evidence.

**Spec:** [M5 in the master continuation plan](../../working/master-continuation-plan.md#m5-resolve-the-specific-older-reports-that-remain-unverified).

## Global constraints

- Work on `feature/m5-geometry`; review baseline `fb09774` through `a1b57fa`.
- Review agents do not edit files. Verify reported regressions before fixing.
- Complete the review before executing the catalog investigation tests.
- No live astronomy queries in default tests, committed downloaded catalogs,
  regenerated historical fixtures or fabricated source-format assumptions.
- Read official provider/format sources when a claim depends on their contract.
- Do not claim a UCAC4 reader defect from a self-generated dtype fixture: an
  actual zone and its relevant format specification are required.
- The first catalog pass is an investigation with dispositions and bug pins,
  not blanket acceptance of every historical finding or unreviewed fixes.

## Review focus

- Coupled changes in measurement masks, RMS/sky noise and caller-owned arrays.
- Reopened FITS coordinates, observation-time origins and retained distortions.
- Proper-motion, polar/RA-zero footprints and catalog candidate budgets.
- Folded sample retention, displayed support and finite derived channels.
- Current public reachability versus explicit legacy/helper limitations.

## Work

- [x] Review completed WCS/geometry/FITS, photometry/calibration/reuse and
  light-curve changes independently; reproduce actionable findings and report
  the review outcome before catalog remediation.
- [x] Trace CAT-23/24/28: padded/composed filter spelling, finite zero values,
  Landolt/Stetson requested columns and actual row mapping. Add narrowly owned
  `tests/test_m5_catalog_parsing_investigation.py` controls/characterizations.
- [x] Trace CAT-17/26: rectangular versus circular cache enclosure, actual
  installed SDK cache hooks, read/write/eviction failure behavior and pruning
  work. Add `tests/test_m5_catalog_cache_investigation.py` without real cache
  deletion or remote requests.
- [x] Trace CAT-21/25/32: SIMBAD common/unknown object types, non-finite versus
  absent serialization and optional APASS identifiers/deduplication. Add
  `tests/test_m5_catalog_identity_investigation.py`; establish provider identity
  semantics from primary sources without manufacturing stable identifiers.
- [x] Inventory actual local UCAC products and their provenance. Compare a
  reader only to its intended product's format; record missing evidence
  explicitly if no actual UCAC4 zone is available.
  Maintainer confirms this deployment uses UCAC5, not UCAC4; the latter remains
  an unverified legacy path, not a deployment blocker.
- [x] Consolidate the completed-work review and catalog findings in scoped
  analysis reports; update the master/test map without closing unresolved work.
- [x] Review the investigation's reachability/oracles, run relevant checks,
  freeze source/tests/guidance for full locked validation, then commit/push the
  investigation and attempt the authorized shared-vault checkpoint.

Completed investigation validation: 105 new cases, independent review clear
after adding the direct SDSS eviction-path probe and correcting a report
coordinate transcription. Full locked suite: 4,874 passed, 94 skipped and
214 FITS notices, no failures (426.28 seconds, Python 3.13.15). All 438
snapshotted algorithm/tool/test/guidance files stayed unchanged through the
run; compilation, guidance and whitespace pass. Production catalog behavior
is unchanged; the fifth square remains open. Final commit/push and vault
transaction outcomes are reported separately.
