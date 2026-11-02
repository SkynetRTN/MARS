# M5 measured flux and source position implementation plan

**Goal:** Correct every confirmed finding in
[the investigation](../../analysis/m5-measured-flux-source-position.md), on the
existing `feature/m5-geometry` branch without worktrees.

**Approach:** Repair the existing numerical layers and convert their probes
to independent correctness checks. Keep source/reference magnitude units,
calibration's annular flux convention, and its disabled aperture correction.
Retain the M1 axis guard while correcting the exact-overlap arithmetic.

**Noise contract:** Background RMS represents per-pixel sky/read noise in input
counts. Add source shot variance from positive net source flux divided by gain,
after sky subtraction, rather than from raw sky-inclusive aperture sums. With
annular sky, include the variance of its mean; estimate local residual noise
when an RMS map is absent. An empty/unusable annulus invalidates measurement.
These marginal errors do not reconstruct covariance or original detector noise
from reduced images. Calibration forwards extracted RMS while retaining local
annular sky. Nonpositive net flux has no finite magnitude; constrained SNR
selection requires usable uncertainty. Existing M2 magnitude-variance fit
weights remain unchanged.

**Matching contract:** With WCS, associate in detector pixels using origin 1,
including anisotropic/rotated images. Without WCS, supplied sky positions use
an explicitly angular tolerance and spherical distance; never reinterpret an
undocumented pixel tolerance silently. Flux SNR is flux/error when present;
legacy magnitude-only inputs invert the retained logarithmic error relation.

## Work and verification

- [x] PHOT-19: convert bounded crash/cap/triangle probes to correct geometry;
  fix the discarded third-edge intersection; test SEP/analytic agreement and
  retained M1 guards. Files: `util/overlap.py`, overlap/geometry tests.
- [x] PHOT-06 and image admission: exact per-source detector saturation counts
  at every downsample and FITS pixel-center admission. Files:
  `extraction/main.py`, `photometry/photometry.py`, position tests.
- [x] PHOT-18/13: WCS pixel association, spherical angular fallback with an
  explicit contract, valid-measurement and flux-SNR gates; forward RMS only to
  preserve annular flux. Files: `fieldcal/field_cal.py`, matching/SNR tests.
- [x] PHOT-01/02 and M5-FLUX-01/02: missing magnitudes and reliable failure
  flags for unusable measurements; sky/source variance contract, valid annulus
  areas/flags, correct RMS squaring in optimizer. Files: `photometry/aperture.py`,
  `aperture_numba.py`, flux/uncertainty tests.
- [x] PHOT-07 and M5-POS-01: use zero-based analysis centers and covariance
  `atan2` orientation, including equal diagonal moments. Files:
  `photometry/aperture.py`, position tests.
- [x] PHOT-12: reject a reaccelerating growth curve as a correction reference,
  try the next suitable source, and disclose when none is usable. Preserve
  calibration's `apcorr_tol=0`. Files: `photometry/aperture.py`, growth tests.
- [x] Retire repaired-defect warnings, update extraction/provenance and master
  status; retain historical data and document intended numerical changes.
- [x] For each change: run the corrected test first, record expected failures,
  implement, and rerun. Then run related suites, the full offline suite outside
  the socket-restricted sandbox, compilation, guidance/schema/shape checks,
  independent review and the shared-memory transaction workflow.

Review focus: fully masked versus edge annuli; background-only/RMS-only inputs;
gain and negative reduced-image offsets; zero/partial errors in provided
photometry; seam/polar/anisotropic matching; growth curves with no clean stars;
bounded native execution and no retained stale magnitudes on reused tables.

Completed 2026-11-02. Final locked offline validation: 4,514 passed, 90 skipped;
independent review and compilation/guidance/whitespace checks passed. Evidence,
failed intermediate checks and model limitations are in the linked report.
