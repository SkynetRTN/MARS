# M5 pulsar boundary fixes

Repair the maintained defects from
[the light-curve/HR investigation](../../analysis/m5-lightcurve-hr-boundaries.md)
on `feature/m5-geometry`, without a worktree. The legacy/helper-only findings
keep their recorded dispositions; the standard-file coordinate contract remains
an explicit unknown, not a reason to invent a unit conversion.

1. Add failing independent controls for canonical `[0, P)` phases, full-cycle
   equal-width bins, endpoint/tied-maximum retention and degenerate support.
   Preserve synchronized channels, calibration, post-bin phase shifts and
   display duplication. Keep empty bins absent rather than fabricating flux.
2. Convert public artifact/PCM/PNG bug pins to correctness regressions. Save
   display extent with folded artifacts, and warn when a fold concentration
   cannot be evaluated as well as when it is weak. Exercise the periodogram,
   fold and sonification callers, including flat and insufficient profiles.
3. Disclose that sparse folded audio plays occupied bins by index; a global
   playback stretch cannot reconstruct missing relative phase gaps. Retain
   qualitative sonification rather than adding a timing capability.
4. Review numerical changes against literal oracles and the existing real-scan
   controls. Update provenance, served guidance and the investigation/plan
   status. Obtain an independent code review and address verified findings.
5. Freeze source, tests and generated guidance, run the full locked suite plus
   compilation/guidance/whitespace checks, then commit and push this feature
   branch. Preserve a concise validated vault checkpoint through its transaction
   workflow, recording any pre-existing permission blocker.

Parallel ownership: the folding task owns only `algorithms/pulsar/folding.py`
and its new focused tests. The primary task owns the tool handoff, diagnostics,
public regression conversions, documentation and final integration.

Completed 2026-11-04. Forty boundary cases pass (13 converted, 20 numerical,
seven handoff), with 360 related passes and 73 final boundary/limit passes.
Independent review's two extreme-scale findings are fixed and covered; final
review is clear. The locked suite passed 4,759 tests, 94 skips and 214 FITS
notices in 416.07 seconds on Python 3.13.15. All 434 snapshotted algorithm,
tool, test and guidance files remained unchanged during that run; compilation,
guidance and whitespace checks pass. The fourth M5 square closes with explicit
legacy/helper, source-format and qualitative-audio limits. Commit/push and the
vault checkpoint follow validation; no other M5 square starts in this task.
