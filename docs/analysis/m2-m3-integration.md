# M2 integration of M3 PR #122

Recorded 2026-10-22 on `feature/m2`, before starting M2 accepted sky positions
and reference stars. Pre-integration M2 head: `1e9d14c`. Incoming main:
`9544782`, the merge of [PR #122](https://github.com/SkynetRTN/MARS/pull/122)
(PR head `351e46d`). The PR closes five M3 items; provider-response closure
still requires live ADS grouping verification with an operator-supplied key.
No live provider or native-solver validation is inferred from this integration.

## Reconciled behavior

- Variable-star spectra keep M2's weighted floating-mean standard powers,
  numerical rank policy, amplitude normalization and period grid. M3 constants
  now raise `ValueError`; nonfinite powers are rejected before clipping.
- M3 folds keep every paired observation with its own bounds, using missing
  bounds when uncertainty is absent. The M2 wrapper's finite-value check now
  permits those missing bounds while rejecting nonfinite calculated values.
  ECSV bounds are masked and warn; valid bounds retain independent quadrature,
  cached half-error migration, days/magnitudes and uncertainty metadata.
- Pulsar candidates retain `period_s`, `frequency_hz` and `power`. M3 skips
  nonfinite powers without restoring the old ambiguous candidate shape. M2
  channel/axis labels, sampling and residual-based conditional Gaussian bounds
  remain in place.
- Background controls belong at stage 1. Artifact reuse preserves the recorded
  baseline and warns about incompatible requests. The ineffective background
  arguments are removed from registered sonification, as intended by M3;
  guidance retains M2's empirical-SNR, interference and retuning limitations.
- M3 histogram guards coexist with the M2 cluster/legacy science corrections.
  AST checks found no changes to M2's age, ID-join, motion selection, coordinate,
  extinction, RMS, radius or mass functions during this merge.

## Conflict and regression checks

The three-way merge had conflicts in shared algorithms/wrappers, instructions,
documentation and generated skill/schema copies. Generated copies were rebuilt
from the reconciled registry and skill source, rather than selecting a parent.
All four schema dialects retain M2 semantics and incorporate the intended M3
stage-1 guidance and sonification-argument removal. The served brief keeps both
milestones' guidance within its 1,100-character content budget.

The initial combined run reproduced the masked-bound `TypeError`, outdated
constant-series/power/candidate assertions and a removed test import. These
were reconciled to the combined contracts. A joint ECSV test failed before the
wrapper correction and passes afterward: one missing error remains masked,
older halved cached errors are rederived, finite bounds use the full
`0.0223606797749979` mag uncertainty, and metadata/units remain present.
Undefined constant-series results are not treated as powers or detections.

Independent integration review checked both parents and found no executable
M2/M3 incompatibility after the corrections. Nine nonconstant weighted spectra
across 4, 13 and 37 samples, with ordinary, `1e-200` and `1e200` amplitudes,
matched pre-merge M2 bit-for-bit. M3 constant rejection and masked-fold probes
passed. Stale extraction and repository guidance about direct NaNs or folds as
proof of detection were also corrected.

## Validation

Generated schema/skill consistency: **74 passed**. Full offline suite:
**3,779 passed, 75 skipped**, with 219 warnings. Compilation, repository shape,
generated-skill consistency and staged whitespace checks passed. Final
integration review has no outstanding findings. This integration was validated
before starting accepted sky-position work; live provider and native-solver
checks remain separately gated.
