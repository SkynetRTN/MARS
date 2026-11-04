# M5 light-curve and HR boundary investigation

**Goal:** Resolve the fourth M5 square's reports against `7375f82`, using
maintained callers and reproducible numerical controls before proposing fixes.

**Spec:** [Master continuation plan](../../working/master-continuation-plan.md#m5-resolve-the-specific-older-reports-that-remain-unverified).

**Method:** Trace each old report through Python ports, legacy helpers and
current tools. Distinguish current defects, bounded/latent helpers, deliberate
display conventions and reports already corrected by M1–M3 or the Python port.
Add explicitly labeled characterization tests and independent expectations;
this investigation changes no production behavior.

**Constraints:** Existing `feature/m5-geometry`, no worktrees. Offline fixtures
and temporary artifacts only; native numerical calls and possible loops remain
bounded. Do not add remote catalog or isochrone downloads. Keep the first three
M5 squares complete and other active work separate.

## Work

- [x] Period/grid and variable-star boundaries: trace `get_period_step`, actual
  periodogram grids, variable folding at exact multiples, and retained sampling
  defaults. Compare finite-progress public controls against old helper output.
  Add `tests/test_m5_lightcurve_boundary_investigation.py`.
- [x] Pulsar folding and axes: trace maximum-bin endpoint retention, independently
  binned channel alignment, prefolded/index-fold axes and seconds/phase metadata.
  Add `tests/test_m5_pulsar_boundary_investigation.py`, including current-tool
  artifact boundaries where reachable.
- [x] HR boundaries: trace TS-22/23/30 luminosity framing, isochrone break splice
  and edge-on projection through current callers and local-grid/Python paths.
  Establish intended coordinate units or identify an unresolved display choice.
  Add `tests/test_m5_hr_boundary_investigation.py`.
- [x] Consolidate evidence in `docs/analysis/m5-lightcurve-hr-boundaries.md` with
  reachability, actual numerical impact, smallest reproduction and disposition
  per report; update master/test map without claiming unresolved bugs repaired.
- [x] Run focused/related suites, compilation, guidance/whitespace checks and
  independent review; freeze source/tests/guidance for full locked validation.
  Commit/push the investigation and attempt the shared-memory transaction.

Completed investigation validation: 68 new offline cases; related variable
group 167, HR 127 and pulsar 187 passes, plus 13 new pulsar passes. Independent
review repeated all 68, with only illustrative HR precision rounding corrected.
The first full run had one MCP readiness timeout (4,731 passes, 94 skips);
69-case recheck passed, followed by the unchanged full suite: 4,732 passed,
94 skipped, 214 FITS notices, no failures (428.55 s). Compilation/guidance/
whitespace pass. Production behavior is unchanged; the M5 box remains open.

## Review focus

- Exact endpoints and multiples compared with neighboring representable values.
- Different channel support, missing bins and unequal lengths versus equal-phase controls.
- Header/file type and stage metadata deciding time versus phase/index axes.
- Main-sequence gaps, first/last splice positions and data/model alignment.
- Magnitude/filter-dependent framing versus physically meaningful coordinate scale.
