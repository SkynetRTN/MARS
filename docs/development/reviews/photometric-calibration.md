# M2 photometric calibration

Recorded 2026-10-23 on the single working branch `feature/m2`. Scope: PHOT-03,
PHOT-09, PHOT-10 and PHOT-14 (explicit unit gain in `run_photometry`).
This intentionally changes the extracted solver; recorded Skynet and Afterglow
fixtures remain unchanged historical evidence.

## Scientific model and rejection

For instrumental magnitude `m_i`, reference magnitude `r_i` and their supplied
errors, fit the offsets `b_i = r_i - m_i` with known variance
`v_i = error(m_i)^2 + error(r_i)^2` and nonnegative additional variance `s^2`.
At each trial variance, the offset is the weighted mean using
`w_i = 1 / (v_i + s^2)`. Minimize the profiled Gaussian negative log likelihood,
up to an additive constant and a factor of two:

```
sum(log(v_i + s^2) + (b_i - offset)^2 / (v_i + s^2)), s^2 >= 0
```

This is the fixed-slope offset specialization of the additive intrinsic-variance
likelihood in [Hogg, Bovy & Lang (2010), equation 35](https://arxiv.org/abs/1008.4686).
The logarithmic normalization penalizes excess variance. Zero additional
scatter is a valid optimum when measurement errors explain the residuals;
measurement-error weights still apply there. A nonpositive score at zero does
not exclude a lower positive-variance minimum with heterogeneous errors.
The implementation compares zero with positive minima found on a logarithmic
grid augmented by measurement-variance knots. The upper search bound is the
squared offset range, beyond which the score cannot favor increasing variance.
Centering offsets and scaling relative weights avoid avoidable cancellation.

Chauvenet rejection now runs below eleven stars and retains at least two
survivors. Weighted residuals use each star's own total standard deviation,
instead of a common empirical scale that can reject legitimately imprecise
measurements. Without supplied errors, the fit uses the mean and empirical
scatter; the rejection scale uses the sample standard deviation. Classical
Chauvenet has limited rejection power in very small unweighted samples. A
minimum of two permits fitting; it does not establish calibration sufficiency.
The subsequent [coverage/sufficiency gate](catalog-coverage-sufficiency.md)
discloses that limit and reports actual solver survivors for public fits.

The returned zero-point error remains the empirical weighted-mean sandwich
estimator, evaluated on residuals to remove a cancellation crash. It is not
`1/sqrt(sum(w_i))`, a catalog systematic uncertainty, or a calibrated confidence
interval. Additional scatter is the fitted residual component after accounting
for measurement errors. Missing reference errors retain the existing zero
contribution policy. Mixed zero/positive total variances without instrumental
errors remain unsupported; the old path already produced an unusable NaN fit.
The five-value public return is unchanged. The plotting helper now consumes
the solver's exact input-aligned survivor mask, including pre-fit drops.

## Selection, gain and integration

Calibration excludes measurements with a known positive saturation count
before the SNR window, reference-magnitude resolution and brightest-star cap.
The registered direct-measurement tool applies the same exclusion to both
measurement and paired catalog counts; an all-saturated input has no usable
sources. Unknown counts retain their existing policy.
Matching keeps the larger detection/catalog count, so a catalog's default zero
cannot erase image saturation. A finite reference magnitude of zero sorts as
a valid bright magnitude. Unknown saturation is not evidence of unsaturation;
the separate retained downsampling/counting defect PHOT-06 is not fixed by
this selection change and remains in the warnings gate.

An explicit gain of `1` is honored. Only an omitted gain falls back to the FITS
header. A real-frame regression compares explicit unit gain with an omitted
gain on an independently unit-gain header, and distinguishes both from the
original header gain and explicit gain four.

M3's finite-input handling, detected-shape handoff and rejection of singleton
or nonfinite/zero-error calibration before header write-back remain in place.
Calibration still forces aperture correction off as the retained Afterglow
measurement convention. This checkpoint does not change catalog transforms,
completeness, aperture/background kernels or the SNR definition. Retained
near-flat SNR regression can still produce an implausible finite limiting
magnitude; no improved limiting-magnitude model is claimed.
Insufficient or rank-deficient magnitude samples now return no limiting
magnitude with an explicit notice while preserving their zero-point fit.

## Evidence and historical differences

`tests/test_photometric_calibration_science.py` covers planted outliers with
five through ten stars, three/four-star weighted cases, zero and positive
analytic variance, heterogeneous measurement weights, a boundary-score trap,
an imprecise retained star, magnitude zero, saturated selection and matching.
An independent test reference optimizes offset and variance together with
SciPy Nelder-Mead and uses SciPy Gaussian tails, rather than importing the
production fitter or Chauvenet kernel. It checks all five outputs and exact
survivor masks on the four recorded calibration inputs.

For NGC 5128 B, six zero-instrumental-error rows are still pre-filtered.
The corrected weighted rejection retains the other 29, instead of the recorded
26, giving an offset of `21.149158002828372` rather than
`21.147659857998637`. The difference is about `0.001498` mag. The unchanged
historical comparison correctly reports that this exceeds its `0.0005` mag
tolerance. The remaining three recorded fields retain their survivor counts;
small numerical changes reflect the corrected likelihood convergence.
Historical Skynet/Afterglow agreement remains tested against historical
summaries; its tolerance was not widened to accommodate current output.

Independent source review found no actionable P1/P2/P3 issues. A seeded
6,000-case heterogeneous-error probe agreed with a separate 4,096-point
variance scan and local refinement to a worst likelihood difference of
`1.42e-14`. The finite grid is still a numerical search, not a proof of
global optimality for every possible input. No native or live-catalog
calibration validation is claimed, and M3's live ADS grouping gate remains open.

The combined calibration, real-frame, statistics and M3 regression run passed
**276 tests**. Schema, generated-guidance, registry and photometry-registry
checks passed **83 tests**. Review follow-ups corrected stale historical-parity
claims in documentation, wrapper tests, tool descriptions and generated
guidance. All four provider-schema snapshots changed only the two intended
descriptions; input schemas and public arguments did not change.

Final Python 3.13.15 offline validation passed **3,834 tests, with 75 skips and
216 warnings**. Compilation, schema goldens, generated-guidance consistency,
repository shape and whitespace checks passed. This was the seventh M2
checkpoint on `feature/m2`. Subsequent [magnitude/filter](catalog-magnitudes-filters.md)
and [coverage/sufficiency](catalog-coverage-sufficiency.md) checkpoints now
record their own acceptance; warnings/benchmark claims remain open in the master plan.
