# Pulsar candidates, sampling and false-alarm bounds

Validated 2026-10-21 for the second M2 checkpoint. This replaces the public
driver's independent-grid-point confidence interpretation; it does not
calibrate pulsar detection on radio data.

## Coordinates and sampling

Every `top_peaks` entry has `period_s`, `frequency_hz` and `power`, regardless
of search mode. `peak_period_s` and `peak_frequency_hz` have the same invariant
units. `search_unit` identifies the requested `search_start` and `search_stop`;
the ECSV column and its unit identify the actual tested coordinates. The
historical float-accumulation loop can produce an extra row, so the result
also reports `evaluated_trials`.

Defaults use twice the median positive spacing of sorted distinct times
through 3 s, or the reciprocal band in frequency mode. Sampling is rederived
from the samples at every load, including old ECSV artifacts. Only uniformly
spaced distinct epochs, within relative tolerance 1e-7, receive a
`nyquist_period_s`. Otherwise it is null: `suggested_min_period_s` and
`sampling_policy=median_spacing_heuristic` describe the heuristic, accompanied
by `sampling_limit_heuristic`. Explicit uniform searches beyond Nyquist warn
about aliases. An unrepresentable reciprocal coordinate is invalid input.

There is no universal irregular-sampling cutoff derived from average, median
or minimum spacing. Cadence, integration time and the sampling window matter;
the default can miss shorter signals and does not remove aliases.
[VanderPlas, §IV](https://arxiv.org/html/1703.09824).

## Conditional finite-grid bound

Let `N` be the sample count, `K` the number of actually evaluated frequencies,
and `z` the largest reported spectral power. The port divides by twice the
observed population variance, so `q = 2z/N` is standard-normalized power for
a sine/cosine fit to mean-centered flux without a fitted intercept. This
normalization agrees with an independent Astropy calculation using
`fit_mean=False`, `center_data=True`, `normalization="standard"`.
[Astropy normalization documentation](https://docs.astropy.org/en/stable/timeseries/lombscargle.html#periodogram-normalizations).

Consider instead the nested model with a floating intercept. Its residual
sum of squares cannot exceed that of the centered fixed-intercept fit: its
model space contains the latter fit plus the sample mean. Thus its normalized
improvement is at least `q`. Under independent equal-variance Gaussian errors
around a constant mean, the full-rank floating-mean improvement has tail
`(1-q)^((N-3)/2)` for `N>3`. Lower-rank trials are stochastically dominated by
this reference. This is a finite-sample variance estimate, rather than an
assumed known population noise variance.
[Baluev, Table 1 and model definitions](https://arxiv.org/html/0711.0330).

Applying the union inequality to the tested frequencies gives the conservative
bound

```text
FAP <= min(1, K * (1 - 2z/N)^((N-3)/2)).
```

This step requires no independence between trial frequencies.
[NIST, Bonferroni inequality](https://www.itl.nist.gov/div898/handbook/prc/section4/prc473.htm).
The implementation evaluates the expression in log space, with a positive
floating-point floor for otherwise underflowing probabilities. For a requested
bound `alpha`, the sufficient power threshold is

```text
z_alpha = -N/2 * expm1(2 * (log(alpha) - log(K)) / (N-3)).
```

Results identify `false_alarm_method="gaussian_bonferroni"`, report the bound
and thresholds keyed by `0.1`, `0.01`, `0.001`, and include explicit assumptions
and a warning. With only three samples there is no nontrivial bound of this
form: probability/method are null, thresholds empty, and
`false_alarm_unavailable` explains why. Legacy `peak_confidence` is null and
`confidence_thresholds` is empty. Old artifacts' thresholds remain drawable
as **Legacy threshold N (uncalibrated)** with a warning. New plots say
**Gaussian noise FAP <= …**.

The proof requires an actual least-squares projection. At exact or nearly
uniform Nyquist frequencies, roundoff can make the port's nominally orthogonal
trigonometric columns nonorthogonal. The historical sum of quotients can then
exceed `N/2`, or distort powers below that cap. Such trials now use a thin SVD
projection of the same raw columns, retaining singular values above
`eps * max(design.shape) * largest_singular_value`. Tiny/zero columns or a
normalized cross-dot above 1e-10 trigger this fallback. Ordinary trials retain
the port's arithmetic; no artificial column rescaling or power clipping is
used. This is a deliberate numerical correction needed for the bound.

## Acceptance evidence and limits

`tests/test_pulsar_candidates_confidence.py` compares powers with Astropy and
tails/thresholds with SciPy's Beta distribution, exercises both coordinate
modes and artifact handoffs, and checks gaps, stale metadata, exact/near
Nyquist, small samples and finite reciprocal coordinates. Fixed-seed ensembles
of 256 iid Gaussian realizations each cover regular, gapped and irregular
times at a 10% nominal bound, with a binomial sampling tolerance. These are
empirical checks alongside the analytic argument, not a noise model for real
radio observations. Existing rendered-content tests inspect the actual
threshold lines in both modes.

A separate probe using seed 47291, `N=32`, a 0.15–3 Hz grid with 60 steps
(61 evaluated rows), found maximum absolute standard-power differences from
Astropy of 1.34e-15, 2.53e-15 and 2.16e-15 for regular, gapped and irregular
times. A nominal 10% threshold was 5.7191678216462165; the subsequent 256-draw
ensembles exceeded it 7, 11 and 17 times respectively. These recorded probe
counts depend on the random draws; regression tests do not pin the counts.

The real B0329 scan has 13,054 retained samples, mean gap 0.00430018 s and
median gap 0.00419400 s, with gaps up to 0.100664 s. Calling twice the mean
gap a hard Nyquist period was unjustified. With the new median defaults,
all five bundled scans complete; only B0329 matches the curated reference:

| Scan | Peak period (s) | Fold concentration | Conditional Gaussian FAP bound |
| --- | ---: | ---: | ---: |
| B0329+54 | 0.7146219 | 231.15 | 2.69e-177 |
| B1133+16 | 2.1839076 | 2.78 | 1.04e-16 |
| B1933+16 | 2.1839076 | 6.18 | 1.59e-8 |
| B2021+51 | 2.1331452 | 1.69 | 3.73e-16 |
| B2045−16 | 1.9761750 | 1.49 | 6.04e-23 |

These small bounds on unsupported candidates illustrate the model's limits.
Baseline subtraction creates correlations; radio noise and interference do
not satisfy the stated iid Gaussian null. The bound covers only a finite grid
chosen independently of flux values, not peaks between grid points or a
workflow that tries channels, filtering windows and search bands after seeing
the data. It is neither a posterior probability of a pulsar nor a probability
that the chosen period is correct. Fold SNR is an empirical concentration
diagnostic, with an inherited warning cutoff of 8; coherent interference may
fold too. No detection-probability, period-uncertainty or general sensitivity
claim follows from this checkpoint.
[VanderPlas, §VII](https://arxiv.org/html/1703.09824).
