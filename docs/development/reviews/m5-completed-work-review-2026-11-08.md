# Completed M5 work: code review, 2026-11-08

Reviewed the combined changes from `fb09774` through `a1b57fa` on
`feature/m5-geometry`: 26 algorithm/tool/guidance source paths, covering the
first four checked M5 squares. The review used three independent passes and
current source/tests rather than treating the dated finding registers or vault
notes as live state. Reviewers made no repository changes.

**Result: no confirmed actionable findings in the completed-work scope.**
No production correction was needed before beginning the fifth M5 square.

| Review pass | Main interactions checked | Fresh verification |
|---|---|---|
| Coordinates, geometry and FITS writes | Alternate-WCS units, polar/RA-wrap enclosure, motion transport, UCAC5 metadata alignment/full-turn queries, triangles, PC metadata, copied settings, reopened distortion cleanup and time origins | 482 passed, six expected skips; 1,080 independent cap-enclosure witnesses and 60 forward/backward motion round trips |
| Photometry, calibration and repeated measurements | Mask/annulus/RMS consistency, net-source shot variance, native overlap, pixel origins, angular matching, crowding references, retained isophotal weights, caller ownership and current flag replacement | 221 passed, no skips; 60 separate randomized circle/ellipse/custom-annulus checks against native SEP flux and analytic variance/area, maximum relative delta 5.65e-8 |
| Light-curve and HR boundaries | Endpoint retention, full-cycle bins, calibrated aligned channels, finite derived profiles, display-independent diagnostics, saved display settings, real PNG/PCM handoffs and served guidance | 105 M5 tests and 112 related tests passed; 900 independent rational-bin/channel/calibration/phase/display controls |

The counts are per review pass, not a claim of 920 distinct tests. The WCS
skips comprise four opt-in native parity cases and two unconfigured solver-data
cases; this review did not repeat blind native solves. The second WCS group
reported 23 existing FITS date-normalization notices. Generated guidance and
whitespace checks pass.

The last full locked suite for the reviewed code remains the 2026-11-06 run:
**4,769 passed, 94 skipped, 214 FITS notices**, no failures, Python 3.13.15.
That is prior integration evidence, not a new full-suite run performed by the
reviewers. The subsequent catalog investigation adds its own validation record.
Its final locked integration, with 105 additional offline probes and no
production changes, passes **4,874 tests, 94 skips and 214 FITS notices**, no
failures (426.28 seconds). Source/tests/guidance remained fixed during that run.

## Scope and dispositions

The review does not reopen documented limitations as new regressions:

- Explicit latent parity behavior, inert ancillary metadata and unverified
  UCAC4 product layout keep their recorded WCS/FITS dispositions.
- Detector history, resampling covariance and sky/correction systematics are
  outside the implemented photometric noise model.
- Legacy subtraction drift/work limits, unused period-slider/HR helpers,
  the original standard/prefolded coordinate contract, independently supported
  value-only channel pairing and qualitative sparse audio remain explicit.

The review's evidence supports continuing with **catalog parsing, caches and
identity**. It does not close that square or the separate obsolete-reports
square, approve a release, or assert that every external/native configuration
has been exercised.

Related correction records:
[coordinates and geometry](m5-coordinates-image-geometry.md),
[measured flux and position](m5-measured-flux-source-position.md),
[repeated calls and FITS writes](m5-repeated-calls-fits-writes.md), and
[light-curve/HR boundaries](m5-lightcurve-hr-boundaries.md).
