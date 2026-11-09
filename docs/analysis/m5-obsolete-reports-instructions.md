# M5: obsolete reports and instructions

Investigated 2026-11-09 against `783abbf` on `feature/m5-geometry`.
The [master plan](../working/master-continuation-plan.md#m5-resolve-the-specific-older-reports-that-remain-unverified)
defines this sixth square. The [execution plan](../superpowers/plans/2026-11-09-m5-obsolete-reports.md)
records the bounded work. This is a current disposition of older reports, not
a rewrite of their original observations or a new release decision.

## Current findings

The reachable issues are stale instructions. No new numerical or replay-error
defect was reproduced. Ten new controls verify the current public replay;
the only production-module edit changes its outdated selection-count docstring.
An AST comparison excluding docstrings confirms executable replay logic is
unchanged from `783abbf`; no algorithm, dependency or workflow was changed.

| Instruction | Verified current state | Correction |
|---|---|---|
| AGENTS says Python 3.13 is the package floor and CI version | `pyproject.toml` requires >=3.12 and advertises 3.12/3.13; CI compiles on 3.12 and runs tests/packages on both | Describe both supported versions; keep the deliberate 3.13 host-installer choice |
| AGENTS/CLAUDE describe tests as preservation only and tell readers to keep bugs | M1–M5 contain independent correction regressions alongside historical preservation tests | Preserve evidence and convert affected bug pins when making an authorized correction; parity alone does not establish correctness |
| CLAUDE describes competing production catalog registries | `catalogs.filters` supplies one production map from `CATALOGS`; `CATALOG_OPTIONS` is an unchanged historical compatibility export | Remove the instruction to maintain divergent runtime reference routing |
| CLAUDE describes a staging repository, no inter-domain imports, environment-reading `SolverSettings`, and unvalidated ATLAS | Package metadata, current fieldcal composition, per-call config and prior opt-in native evidence contradict those descriptions | State current package/ownership/configuration boundaries and link current solver evidence without claiming fresh native checks |
| Active contributor guides target dev | Origin HEAD and the GitHub repository API identify main; the vault records maintainer guidance to target main | Align AGENTS, CLAUDE and CONTRIBUTING with main; no merge/PR is performed |
| tests/README says nothing has been fixed and its old defect table describes live bugs | Some rows already document M2/M5 corrections; others mention deleted processing-run state | Mark that table as extraction-time history and point to current dispositions |
| Replay documentation says it chooses 35 stars | The record contains 35; the maintained selection keeps 29 with usable uncertainty/SNR | Describe both counts without editing any recorded data |

The CI description also names packaging/native-containment checks and the
MCP-extra suite. Live service/model opt-in is distinguished from local MCP IPC.
The unrelated MCPB packaging command using `npx` is valid host-install tooling;
it is not a surviving astronomy TypeScript runtime and is retained.

## Older report dispositions

| Report | Current caller/implementation evidence | Disposition |
|---|---|---|
| WCS-15: stale fields on a processing-run object | `wcs/state.py` and `_clear_wcs_solution_fields` were deleted in `01177ec`; current solves return immutable results, with forbidden-API guards | Retired object-state defect. Modern FITS-header replacement is a separate reachable path, corrected and tested in M5's repeated-call/FITS square |
| PHOT-17: dependency globals | `fieldcal/deps.py` was deleted in `01177ec`; calibration accepts explicit inputs | Retired shim claim. Input-mutation half was separately corrected and checked in the earlier M5 work |
| PHOT-16: blank CSV failures and centroid_radius=5 | `01177ec` deleted the exporter; pre-deletion source confirms its blanket except/blank row and literal 5. No maintained batch entry point remains | Retired driver. Current replay returns structured errors; current pixel photometry defaults to centroid radius 0. Recorded-magnitude replay never runs a centroid pass |
| TS-27: scalar-first ArrMath.sub/div reversed | The private object lived in `periodogram/core/lomb-scargle.ts`, retired in `b5d1b0a`; live Python periodograms use direct NumPy operations, not these branches | Retired implementation; do not resurrect it to repair an unreachable scalar branch |
| TS-08: index/count folding | Old foldSingleSourceByIndex is absent; Python ingest/folding uses time coordinates | Retired divide-by-count implementation. Original standard-format coordinate intent remains explicitly unverified, as recorded in the lightcurve square |
| CAT-29: image-query registry change | `query_catalogs_for_image` still exists and has tests; it uses the bound CATALOGS query registry, while selection/resolution share canonical routing | Historical extraction documentation issue, not a retired callable or a reason to revert routing |
| TS-15/16/18/28/31 and other surviving helper ports | Python d2_dms, maximum/baseline/histogram helpers survive; M2/M3 and the earlier M5 controls establish their current behavior | Not closed merely because TypeScript retired; retain the actual correction evidence and any explicit helper-only limits |
| TS-21 protected radius/mass unit factors | Live legacy summary still contains the deliberately cancelling factors; this work does not change them | Retained protected behavior, not an actionable defect |

AST inspection of 227 maintained algorithm/tool modules finds no definitions
or calls for the retired optical state/batch/index/ArrMath symbols. Source/import
search and `test_repository_shape.py` independently confirm the optical run API
and TypeScript trees/toolchain stay absent. The checked symbol set is bounded;
this is not a claim that every historical helper in the register was deleted.
Surviving `query_catalogs_for_image` is deliberately excluded from that set.

## PHOT-16 replay evidence

`tools.fieldcal_reference.replay_field_calibration` is registered as a public
tool and runs the recorded NGC 5128 detections, APASS/VSX responses, detector
clipping, reference mapping and maintained fit offline. Its result reports
selection counts, the actual solution and deltas against historical references.
The current selection has 29 matches from 45 detector candidates/132 cone rows,
against 298 detections; the historical selection of 35 remains unchanged.

`test_m5_obsolete_report_controls.py` replaces only each failed operation and
calls the public registry entry. It establishes:

- unreadable/invalid frames and missing WCS produce `field_calibration_failed`
  with the original diagnostic message, no solution and no match rows;
- degenerate fits produce `no_solution`; other fit exceptions produce
  `field_calibration_failed`; both retain the already collected variable-star
  and numerical warnings;
- None/empty-solution convergence results produce an explicit `no_solution`;
- after an injected failure, the next real call succeeds with 29 matches and
  does not inherit the injected diagnostic;
- recorded replay succeeds while pixel photometry is disabled by a sentinel,
  proving this path does not exercise the retired driver's centroid setting.

These are passing current-behavior controls, not claimed RED→GREEN bug fixes.
The existing pixel-photometry/default-centroid and Afterglow-settings tests
establish the separate measurement settings. Real selection replay retains its
independent fit oracle, exact recorded magnitude checks and socket guard.

## Validation and status

Initial targeted integration: **404 passed** in 8.69 seconds, including all ten
new replay controls, real replay/Afterglow references, repository shape,
packaging metadata, canonical routing and surviving lightcurve/HR helpers.
No live astronomy services, native solver run, dependency update, fixture
regeneration or TypeScript runtime was needed for this disposition.

Independent combined review found no actionable issue. It repeated all ten
new controls, checked deletion history and surviving callers, confirmed the
227-module scan and unchanged executable replay AST, and verified metadata/CI
versus installer choices. Existing pixel-centroid controls also pass: two
tests, 27 deselected (1.46 seconds). Compilation, generated guidance, touched
Markdown links and whitespace checks pass.

The sixth square is **closed on 2026-11-09; M5 is 6/6 complete**. Final locked
validation on Python 3.13.15:

```bash
uv run --locked --extra mcp pytest -q --junitxml=/tmp/m5-obsolete-full-results.xml
```

**4,974 passed, 94 skipped, 214 FITS notices**, no failures, in 409.08 seconds.
All 466 snapshotted source/test/guidance/CI metadata files remained unchanged
through the run. No new Python 3.12, native-solver or live-provider execution
is implied by these results. M6 publication/host decisions remain separate.

## Shared context

The vault query used its index/text fallback because BM25/chunks are absent.
September findings notes are historical. The project note still says Python
3.13 only, while the newer hot cache says 3.12/3.13; repository metadata and CI
are authoritative. Prior Save attempts were blocked by an unrelated unreadable
transaction. A scoped post-validation Save will be attempted without bypassing
the transaction workflow or repairing that unrelated state.
