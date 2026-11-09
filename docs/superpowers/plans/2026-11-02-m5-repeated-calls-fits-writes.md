# M5 repeated calls and FITS writes investigation plan

**Goal:** Establish which reports in the third M5 square are reachable at
`a4d429a`, their observed consequences, and the remaining release decisions.

**Spec:** [Master continuation plan](../../working/master-continuation-plan.md#m5-resolve-the-specific-older-reports-that-remain-unverified).

**Approach:** Trace maintained callers, run deterministic repeated-call and
write/read probes, and compare with fresh-input controls and independent WCS
transforms. Record confirmed defects separately from intentional output
mutation, already corrected reports and unverified native behavior. This pass
adds evidence and characterization tests; it does not change production code.

**Constraints:** Use the existing `feature/m5-geometry` branch, no worktrees.
Keep tests offline and native numerical calls bounded. External binaries and
catalogs are optional evidence, not a requirement for deterministic controls.
Retain the existing M4 scope and the first two M5 squares' completed state.

## Work

- [x] Input reuse: inspect `algorithms/wcs/wcs.py`,
  `algorithms/fieldcal/field_cal.py`, and
  `algorithms/skylib_lite/photometry/aperture.py`. Compare reused settings,
  catalog rows, source arrays and headers against deep/fresh copies, including
  invalid-to-valid measurements and failure-to-success calls. Add
  `tests/test_m5_reuse_investigation.py` with real numerical controls.
- [x] FITS writes: inspect `_write_wcs_to_header` and maintained tool writers.
  Probe obsolete frame/equinox and distortion keywords, alternate WCS,
  observation metadata and repeated write/read cycles. Compare reopened WCS
  against the accepted solution; add `tests/test_m5_fits_write_investigation.py`.
- [x] Solver controls: trace automatic/explicit parity through both backends
  and acceptance, and source caps with absent/partial/nonfinite flux. Exercise
  actual xylist generation and inspect backend requests/commands using bounded
  solver seams. Add `tests/test_m5_solver_controls_investigation.py`.
- [x] Consolidate findings in
  `docs/analysis/m5-repeated-calls-fits-writes.md`, with reachability, numerical
  consequences, smallest reproductions, references and disposition per report.
  Update the master plan and test map without marking unresolved defects fixed.
- [x] Run focused and related suites, compilation, guidance and whitespace
  checks; obtain independent review; run full locked offline validation with
  source/tests/guidance frozen. Commit and push the investigation, then attempt
  the shared-memory transaction workflow.

Validation: 79 default offline probes plus four opt-in native cases; 786
related passes and a separate 51-pass native-enabled solver-control run.
Independent review repeated the default group with no actionable findings.
Final locked suite: 4,620 passed, 94 skipped, 214 FITS notices (425.22 seconds).
Compilation, guidance consistency and whitespace pass. The M5 square remains
open for the findings' remediation; this checkpoint changes no production code.

## Review focus

- Deliberate output mutation versus inputs whose reuse silently affects a later call.
- Failure flags and metadata surviving a successful second measurement.
- A clean new WCS interpreted differently after old frame/distortion cards survive.
- Automatic parity compared with both explicit values and hinted/header-free cases.
- Source budgets with omitted or unusable brightness, without fabricating flux.
