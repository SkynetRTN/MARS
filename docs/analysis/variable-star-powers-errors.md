# Variable-star powers and differential uncertainties

M2 correction recorded 2026-10-21 on `feature/m2`. The public pipeline no longer
preserves the Astromancer weighted-power and halved-error formulas. Source
merging, differential-magnitude signs, the accumulating logarithmic period
grid, fold ordering and duplication, and work limits remain in place.

## Reproduced defects

Eight equally weighted samples of an exact sinusoid at a trial period of one
day returned power `0.0625`. Duplicating every observation reduced that to
`0.03125`. A correctly normalized, exact sinusoidal fit explains all of the
weighted variation and has standard power one in either case. The old code
mixed normalized weighted cross-products with unweighted trigonometric sums
and an unweighted variance. Multiplying its answer by a sample-count factor
would not repair unequal weights or the missing fitted offset.

Source standard errors `0.3` and `0.4` magnitudes returned combined error `0.25`.
The target-minus-comparison operation requires `0.5` when these errors are
independent. It is a difference, so the factor of one half appropriate to an
average has no place in its propagated uncertainty.

## Supported power definition

Each trial fits `c + a*cos(2*pi*t/P) + b*sin(2*pi*t/P)` with inverse-variance
weights from the supplied differential standard errors. The constant `c` is
fitted at each trial. The reported standard normalization is

```text
power = (chi2_constant - chi2_periodic) / chi2_constant
chi2 = sum((observed - fitted)**2 / sigma**2)
```

Power is dimensionless, between zero and one: fractional improvement over a
constant fit. This is the standard floating-mean Lomb–Scargle definition
described by [Astropy](https://docs.astropy.org/en/stable/timeseries/lombscargle.html#periodogram-normalizations).
It is not a probability of variability, a probability that a period is correct,
or a calibrated false-alarm probability. No new significance or uncertainty
estimate is supplied for the period.

The implementation normalizes inverse-variance weights, centers the response
and both sinusoidal columns with those weights, whitens them, and projects
through a thin SVD. Centering the columns eliminates the fitted intercept.
Value offsets are formed relative to an observed value before weighted
averaging, so an exactly constant series cannot gain artificial variance from
rounding its absolute mean. Times are likewise measured from an observed
epoch for the fit, avoiding unnecessary large-MJD trigonometric arguments.

At collapsed or nearly collapsed phases, rank is estimated with cutoff
`eps * (max(N, 3) + max(abs(angles)))`. The unit-norm intercept anchors the
solver scale; the angle term accounts for phase-formation roundoff. Discarded
directions contribute no fitted power. A trial with no resolved harmonic
direction has power zero; this does not establish an absence of variability.
This is an estimated numerical resolution policy, not certified interval
arithmetic or a resolution guarantee for arbitrarily close aliases. High power
and very large fitted amplitudes near aliases do not resolve period ambiguity.

The original logarithmic-period grid and float accumulation are retained,
including its normal 2,001 rows for 2,000 public steps. The direct API still
enforces 2,000 samples, 200,000 steps and 20,000,000 sample-grid work units.
Unrepresentable weights, variation or coordinates are rejected. Stable
centering no longer overflows merely when an exactly constant value is large;
the direct constant-series result remains nonfinite. The public stage rejects
constant series with `invalid_input` and no spectrum artifact. Broader direct
helper failure contracts remain M3 work.

## Differential standard errors and artifacts

For `target - comparison + fixed_reference_magnitude`, linear uncertainty
propagation gives

```text
variance = sigma_target**2 + sigma_comparison**2 - 2*covariance
sigma_difference = hypot(sigma_target, sigma_comparison)  # covariance = 0
```

This follows the linear-combination rule in
[NIST's uncertainty guidance](https://physics.nist.gov/cuu/Uncertainty/combination.html).
Both target selections have the same uncertainty. The comparison's supplied
measurement error contributes; uncertainty in the fixed reference magnitude,
source covariance and shared calibration systematics are not included.
Duplicating a point for a two-period display does not reduce its error bar.

The historical column name `error_mse` is retained for compatibility; its value
is a standard deviation in magnitudes, not a mean squared error. `hypot` avoids
overflow/underflow from unnecessarily squaring the component errors.
If the combined uncertainty itself exceeds the finite range, ingestion fails
with `invalid_input`. Public folding likewise rejects unrepresentable full
error bounds instead of writing an artifact containing infinities.

New light-curve/fold artifacts and results identify
`uncertainty_method=independent_quadrature`. New spectra identify
`power_normalization=standard`, `fit_mean=true` and `period_unit=d` in both
results and ECSV metadata. Coordinate columns carry days and photometric
columns carry magnitudes. Folded `phase` coordinates are elapsed days within
the displayed period; the input `phase` setting remains a fractional offset.

Public artifact loading validates the old fields and rederives nonmissing
cached combined errors from `error1` and `error2`. Thus older half-error
light-curve artifacts do not silently retain narrow error bars. Paired data
with a cached combined error but missing source-error components must be
re-ingested; the old cache has no independently established convention.
Missing or invalid combined errors retain the existing failure contract.
Already saved spectra/folds are not rewritten: recompute them from source
light curves to obtain corrected powers/error bars and explicit metadata.

## Independent acceptance evidence

`tests/test_variable_star_science.py` checks an exact sinusoid and duplicated
samples, unequal-error comparisons with Astropy for regular/gapped/irregular
epochs, units/offset/order invariance, collapsed aliases and resolved Nyquist
columns, quadrature at ordinary and extreme scales, both fold selections,
actual ECSV handoffs, legacy caches and constant-series rejection.
Two additional public regressions cover overflowing combined uncertainties and
unrepresentable full error bars; both were observed failing before the guards.

The initial 15 regressions failed against the old implementation. Review
identified the constant-series rounding regression; additional failing tests
were recorded before correcting it and the near-alias rank policy.
Independent review compared 120 randomized heteroscedastic cases against
SciPy full intercept/cosine/sine QR fits, with maximum power difference
`3.59e-14` after those final stability corrections. The review also verified
invariance after adding a representable `1e15` value offset.

The public grid and bundled-fixture checks use separate full-model QR fits.
Astropy's analytic slow formula loses precision near almost collapsed aliases:
one trial with condition number about `2.39e6` differed from the SVD by
`2.22e-6`, while QR agreed to about `3.1e-13`. This is why tests do not retain
incorrect historical power literals or treat that analytic formula as exact
in ill-conditioned cases. Existing tests continue to pin grid coordinates,
fold ordering and other retained behavior. No real-source detection claim or
historical model benchmark regrading follows from this checkpoint.

## Validation

Initial checkpoint validation (2026-10-21):

Python 3.13.15 with locked dependencies and `[mcp]`: **3,476 passed, 49 skipped**
in the full offline suite, with the same 198 existing warnings. The focused
variable/scientific, schema, skill and registry run passed 189 tests, including
all 21 new scientific regressions. Compileall, generated-skill consistency,
schema goldens, repository shape and `git diff --check` pass. Independent final
review has no outstanding findings. This is the third closed M2 checkpoint
on `feature/m2`; the remaining gates are open, and the changes are unmerged
and unpublished.

## Review follow-up: response amplitude (2026-10-22)

A fresh review found that squaring tiny residuals and projections could lose
their energy to underflow. Six irregular samples scaled by `1e-161` produced
power zero instead of `0.0383141338914464`; the public CSV pipeline reproduced
the failure. Large finite amplitudes could likewise overflow those energies.

The fit now divides response offsets by their maximum absolute value before
forming a weighted mean or squared energies. This common scale cancels from
standard power. Constants keep their existing rejection, and unrepresentable
offsets or weights still fail explicitly. Three direct amplitude regressions
(`1e-200`, `1e-161`, `1e200`) and a public tiny-amplitude CSV/ECSV handoff failed
before the change and pass afterward, bringing the scientific file to 25 tests.

All 116 focused variable-star tests pass. Independent follow-up review compared
1,500 amplitude cases spanning `1e-300` through `1e300` with full-model QR fits;
the maximum power difference was `1.08e-13`. It also checked subnormal values,
negative scales, extreme uncertainties, offsets and constants, and reported no
outstanding findings. Combined branch validation, including the subsequent
cluster checkpoint: Python 3.13.15 with locked dependencies and `[mcp]`,
**3,503 passed, 49 skipped**, with 198 existing warnings. Compileall, schema
goldens, generated-skill consistency, repository shape and `git diff --check`
pass.
