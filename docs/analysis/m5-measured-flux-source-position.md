# M5 measured flux and source position investigation

**Current status:** all confirmed findings below are corrected and validated on
`feature/m5-geometry`. The original investigation remains as failure evidence;
the correction and final-validation record is at the end.

Recorded 2026-11-02 on `feature/m5-geometry`, against `fab8b21` after the
coordinates/image-geometry corrections were committed and pushed. Scope is
the second M5 square in the [master continuation plan](../working/master-continuation-plan.md):
PHOT-01/02/06/07/12/13/18/19, source origins, matching tolerances and uncertainty
handling. This record establishes failures; it does not repair their numerical
paths. The original observations below predate the corrections recorded at the
end of this document; those later results supersede the retained-defect status.

The shared-vault lookup used its index/text fallback because BM25 retrieval was
not configured. The shared optical/findings notes predate the merged M2/M3
changes; current source, recorded data and executed probes are authoritative.

## Disposition of the older reports

| Report | Current result and reachability |
| --- | --- |
| PHOT-01: nonpositive flux appears valid | **Confirmed, including a public false calibration.** Zero/negative net flux retains finite magnitude/error placeholders and zero flags. An entirely zero-valued FITS image can return a successful zero point. M2 emits a warning but does not reject the measurement. |
| PHOT-02: empty annulus omits sky subtraction | **Confirmed.** Annulus flags are discarded and zero usable area skips subtraction. An outside-frame annulus is disclosed; a fully masked annulus also produces biased flux and can evade that disclosure. Maintained field calibration uses annular measurement; the final photometry pipeline normally supplies maps. |
| PHOT-06: downsampling loses saturation counts | **Confirmed, with a stronger wrong-star case.** Already-downsampled indices are divided again. Saturation can be assigned to a healthy star, so filtering removes the healthy star and keeps the saturated one. Configurable Python API trigger; registered defaults use downsample 1. Existing M2 warning applies. |
| PHOT-07: isophotal origin mismatch | **Confirmed.** Origin-1 positions enter origin-0 analysis when shapes/flux must be remeasured. The resulting biased shape changes final aperture flux. Python adaptive-photometry trigger; ordinary fixed-aperture tools and valid supplied extraction shapes bypass it. Existing warning applies. |
| PHOT-12: growth-curve neighbor guard | **Confirmed.** `df_prev` is assigned but never read. Neighbor flux enters the correction and shifts distant sources. Public instrumental/header-zero-point paths enable correction; field-calibrated paths deliberately disable it. Existing warning applies. |
| PHOT-13: inconsistent SNR/weights | **Selection mismatch confirmed; old weight claim superseded.** Selection uses inverse magnitude error; the limiting-magnitude fit uses an inverse log-error relation. Current M2 zero-point weights use supplied magnitude/reference variances and fitted extra variance, rather than either SNR proxy. |
| PHOT-18: angular matching and tolerances | **Seam failure confirmed; stated mean-RA cause corrected.** Unwrapped RA differences are the cause. Variable-star filtering correctly uses spherical distance. Different tolerance units serve different operations, but missing-WCS conversion and anisotropic scale averaging make the source matcher change its effective contract. |
| PHOT-19: tentative ellipse clipping | **Confirmed against pinned SEP and independent geometry.** The third edge discards its second intersection and reuses a stale point. This causes finite flux corruption and a native crash through maintained photometry even when both axes pass the M1 floor. |

## Measurement validity and background

`aperture.py:584–596` fills magnitude/error only for positive flux. Otherwise
new columns remain zero. `photometry.py:216–224` accepts finite zero values
and the unset failure flags. A requested zero point of 20 turns the placeholder
into magnitude 20; it does not make it a detection.

The stronger public reproduction writes a 60×60 image containing only zeros,
with a valid TAN WCS, `FILTER=V`, and three supplied APASS references with
magnitudes 12.95, 13 and 13.05. Unmodified `calibrate_zeropoint` remeasures the
pixels and returns **zero point 13, no errors**. The underlying calibration
uncertainty is 0.0288675 mag. Default `min_snr=10` accepts zero errors through
the truthiness condition at `field_cal.py:725`. If all instrumental errors are
zero, `solution.py:114–124` skips its positive-error filter; a fit with all
reference errors also zero then takes the unweighted branch. Nonzero reference
errors can still supply weights. Zero instrumental errors are dropped in a
mixed sample containing positive instrumental errors. Public warnings
disclose nonpositive flux and sample sufficiency, but a success value remains.

For PHOT-02, a 300-count impulse on sky 10, aperture radius 2, and annulus
entirely outside the frame returns **425.663706 counts, flag 0**: +41.8879%
flux and −0.379863 mag. The internal circle/ellipse annular branches discard
the annulus flags and only subtract when both areas are positive
(`aperture_numba.py:728–741`, with the analogous ellipse branch below).

Masking every annulus pixel reproduces the same error **without** the
`empty_background_annulus` notice. The driver's separate annulus measurement
reports geometric area including masked pixels; the subtraction kernel uses
`ignore_mask=True` and finds zero usable area. The notice at `aperture.py:452`
therefore checks a different area from the one governing subtraction. This is
a current disclosure gap in addition to the known arithmetic defect.

## Uncertainty findings beyond the old register

**M5-FLUX-01: missing sky noise and raw-offset-dependent shot noise.** Field
calibration obtains background/RMS maps during extraction but explicitly passes
`None` for both to measurement (`field_cal.py:694–699`). The annular kernel does
not estimate a sample RMS, despite the driver's docstring. Without supplied
noise, only its raw-sum Poisson term remains; that term is omitted when the raw
sum is nonpositive (`aperture_numba.py:249–253`). Subtracting a negative sky can
then yield positive net flux with exactly zero error.

This explains M4's NGC 5128 B observation. Replaying `selected_rows` from the
actual frame through `calibrate_zeropoint` yields **35 measured candidates,
six with zero `flux_error` and `mag_error`**. All six have positive net flux
(3063–3985 electrons), but both their raw aperture and annulus sums are
negative. For example, one raw aperture is −1369.681060 counts, its annulus
mean is −49.843427 counts/pixel, and the net result after gain 1.20919 is
3077.403748 electrons with zero error. The mixed-error fitter excludes these
six. The full recorded cone produces 39 measurements, ten with the same
zero-error mechanism; those counts belong to different input selections.

A controlled constant-offset test isolates the mechanism: the same 300-count
impulse with sky offsets −50, 0 and +50 has identical net flux, but annular
errors **0, 17.320508 and 31.907340**. Even with a supplied, unchanged RMS map
of 4 and corresponding background maps, errors become **14.179631, 22.384413
and 33.606256**. The driver sums the raw sky-inclusive image with gain before
subtracting its background, so supplying an RMS map alone does not make the
source Poisson contribution consistent. For a planted source with known
variance, the independent constant-noise reference is
`sqrt(300 + 4**2 * pi * 2**2) = 22.384413`.

This is a noise-model defect, not permission to infer original detector noise
from reduced pixels. A correction needs an explicit source-plus-background
variance contract and treatment of missing variance, with independent noise
validation. SEP's [official tutorial](https://sep.readthedocs.io/en/stable/tutorial.html#aperture-photometry)
uses the background-subtracted image together with background RMS and gain;
its [API](https://sep.readthedocs.io/en/stable/api/sep.sum_circle.html) distinguishes
RMS/error from variance and defines the additional Poisson term.

**M5-FLUX-02: optimal-radius objective treats RMS as variance.**
`calc_flux_err` passes the supplied RMS map directly into `_sum_ellipse`'s
variance argument (`aperture.py:68`). The ordinary dispatcher squares `err`
first (`aperture_numba.py:626–638`). A Gaussian with RMS 4, axes 3×2 and
theta 0.3 radians produces relative error **0.158164156** in the optimizer
versus **0.248604886** from independent SEP exact summation, about 36.4% low.
This reaches the automatic-factor search when `k=0` and is separate from
growth-curve correction. No corrected optimal-radius policy is claimed here.

## Position, shape and matching evidence

In the two-star saturation test there are exactly 13 saturated detector pixels.
At downsample 1, counts are `[0, 13]`; at downsample 2 they become `[24, 0]`.
`discard_saturated=1` then keeps the saturated source. This proves wrong
association as well as lost counts (`extraction/main.py:235–238`). It does not
prove that every downsampled field loses every count, as the old wording implies.

For isophotal analysis, a circular Gaussian centered at zero-based (31,31)
has equal moment axes 2.227017607 in the correct radius-5 disk. The passed
FITS coordinate (32,32) instead gives axes 2.206318772×2.183553584 at −45°.
Independent weighted covariance agrees with each disk's moment arithmetic.
The scratch isophotal flux falls 4.904%; the **final** aperture flux changes
from 46344.908362 to 45807.946763, **1.1586% low / +0.012653 mag**. Those are
different quantities; the scratch flux is subsequently replaced.

**M5-POS-01: equal diagonal moments lose orientation.** The separate branch
`if x2 == y2: theta = 0` (`aperture.py:129`) also covers nonzero covariance.
A deterministic weighted image with covariance `[[1,7/9],[7/9,1]]` has major
axis 45° by eigendecomposition, while the current function returns zero.
This requires the same isophotal-analysis path as PHOT-07.

**M5-POS-02: image admission uses the wrong origin.**
`get_source_xy`, WCS and centroiding use FITS origin 1, but
`photometry.py:138` checks `0 <= x < width` and `0 <= y < height`. On a 20×20
image, a radius-0.4 circle centered at (20,10) or (10,20) is fully contained
and accepted by the underlying aperture kernel, with flag zero. The maintained
wrapper rejects it. It admits (0,10)/(10,0), which can survive as zero-flux
magnitude placeholders. This is independent of plot-overlay origins.

For PHOT-18, RA 23.99999 h and 0.00001 h at declination zero are **1.08 arcsec**
apart, but fail an angular 2-arcsec match; the equivalent pair near 12 h matches.
Subtracting a common arithmetic reference cancels in pairwise differences;
changing only the mean does not repair unwrapped longitudes
(`field_cal.py:354,414`). The variable-star filter handles the same seam pair.

`variable_check_tol` is an angular exclusion radius; `source_match_tol` is a
source-association pixel tolerance. Those distinct units are sensible. The
current conversion is not equivalent to the pixel contract on anisotropic
images: for a 2×1 arcsec/pixel WCS and tolerance 1 pixel, angular mode uses
1.5 arcsec, rejecting a 0.9-pixel x offset and accepting a 1.4-pixel y offset.
Pixel mode does the opposite. Omitting WCS also reinterprets the same numeric
tolerance as arcseconds. The anisotropic difference has no numerical notice.

At default `min_snr=10`, the retained magnitude-error formula and selection
imply a true flux-SNR threshold of **10.365036246**. Provided-photometry probes
reject SNR 10.1/10.3 and retain 10.4/10.5. The current two-measurement Gaussian
fit independently returns the expected 4:1 precision-weighted offset, proving
that the old SNR-derived fit-weight criticism should not be carried forward as
a current M2 solver defect. Incorrect supplied measurement errors can still
change both selection and weights.

## Growth correction and ellipse clipping

With a Gaussian primary and a neighbor 8.5 pixels away, the growth loop passes
eight reaccelerating steps rather than applying its stated nearby-source guard
(`aperture.py:505–543`). Its correction changes from −0.441240552 to
−0.552604815 mag. A distant secondary whose measured flux is unchanged shifts
**−0.111364263 mag**. M2's crowding warning is present; calibration's forced
`apcorr_tol=0` avoids this path, while other public zero-point routes enable it.

The PHOT-19 comparison used the installed SEP 1.4.1 tag's official
[`src/overlap.h`](https://github.com/sep-developers/sep/blob/v1.4.1/src/overlap.h#L475-L502).
The C implementation retains both third-edge intersections. The Python port
discards the second at `overlap.py:348` and averages the first with a stale
point at lines 350–351. The triangle (1.2,0), (1.2,2), (−3,0) contains exactly
the upper half unit disk, but the current function returns **0 instead of pi/2**.

Finite public reproduction: an 11×11 zero image with a unit impulse at
`image[5,4]`, source FITS (6,6), axes 1×0.5 and rotation zero returns flux
**0.769745547**, flag zero. An independent ellipse-cap integral and SEP give
**0.307092425**, so measured flux is **2.50656 times** the correct value.

Fatal public reproduction: an 11×11 image of ones, source FITS (5.5,6.2),
`a=0.8, b=0.5, theta=-45`, zero background, unit RMS and correction disabled
passes the existing guards and **SIGSEGVs**. SEP returns `pi*0.8*0.5`, flag
zero. Native questionable calls were isolated in bounded child processes with
core dumps disabled. An interpreter-only diagnosis reaches repeated recursive
clipping at line 352. An isolated temporary-copy control changing only the
discarded intersection assignment restores the triangle, the finite pixel
integral and the formerly fatal public case. Thus these PHOT-19 failures share
the stale-point cause; no production patch was applied during investigation.

M1's sub-0.5-pixel validation still handles its tested cases, but its floor
does **not** contain every fatal ellipse. The new >=0.5-pixel crash is an open
finding and must be resolved before claiming general overlap containment.

## Reproduction and remaining work

The four `tests/test_m5_{flux,positions,uncertainty,overlap}_investigation.py`
files are explicitly **characterization**, not numerical acceptance. They
exercise actual kernels, public calibration, independent covariance/area/SEP
references and the recorded real frame. The overlap file forces native JIT in
bounded child processes and skips its POSIX signal probes on Windows. Tests
need no network, downloaded data or compiled external source.

Validation: **33 new characterization cases**, included in a focused run of
**431 passed, 8 Astropy FITS notices** in 140.75 seconds. The run also covers
existing extraction, photometry, field calibration/reference, M2 calibration,
numerical-warning and Skylib geometry tests. Python compilation and whitespace
checks pass. Independent review found no remaining issues after correcting a
claim about zero instrumental errors: nonzero reference errors can still make
that fit weighted. No production source changed during this investigation;
the geometry commit's earlier full-suite result is recorded separately.

Fix priorities are the reachable PHOT-19 crash and corrupt overlaps, invalid
measurement/calibration success, unusable annuli and noise contracts, followed
by saturation/origin/matching and growth correction. Correctness regressions
must replace the corresponding bug-pinning assertions as each path is repaired.
M4 host/manual acceptance remains a separate activity and does not validate
these numerical paths.

## Corrections after investigation (2026-11-02)

The authorized remediation fixes PHOT-01/02/06/07/12/13/18/19 and
M5-FLUX-01/02, M5-POS-01/02. The original characterization assertions have
been converted to correctness regressions. The [implementation plan](../superpowers/plans/2026-11-02-m5-flux-position-fixes.md)
records the scope; [extraction provenance](../extraction.md#11-m5-measured-flux-and-source-position-corrections-2026-11-02)
records intentional numerical departures.

- Exact clipping retains the second third-edge intersection. The half-disk,
  individual ellipse-cap/pixel integrals, formerly fatal public 0.8×0.5 case
  and older small-axis low-level probes now complete with correct areas in
  bounded native subprocesses. The conservative public axis floor remains.
- Nonpositive flux clears even preexisting magnitudes to NaN and sets a failure
  flag. Public measurement excludes it; the zero-valued image cannot produce
  a calibration. Unusable annuli likewise invalidate measurements and retain
  flags, including masked annuli. Annulus truncation is now visible to the
  existing rejection policy.
- Detector saturation counts are exact before downsampling; masking, nonzero
  integer maps and incomplete edge blocks are covered. FITS pixel-center
  admission, isophotal origin and equal-diagonal covariance angles are fixed.
- Noise uses independent background and RMS inputs, supplied marginal sky
  variance or weighted annular residual variance, variance of the sky mean,
  and positive net source shot variance after subtraction. The optimal-radius
  objective squares RMS. Calibration forwards extracted RMS while retaining
  annular sky. The six negative-raw-sum candidates no longer generate zero
  measurement errors; an edge candidate is excluded by its annulus flag.
- WCS associations use detector distance, with no average-scale approximation
  or duplicate motion/projection of measured centroids. Sky-only association
  without WCS requires `source_match_tol_arcsec` and uses unit-vector chord
  distance. SNR gates use flux/error or the exact logarithmic error inverse for
  magnitude-only input. Missing/zero errors cannot bypass a constrained gate;
  M2's fit weights remain unchanged.
- Growth curves that reaccelerate beyond the fractional tolerance are rejected
  as references; a clean replacement supplies the correction. Without a usable
  curve, magnitudes stay on the measured aperture scale with
  `aperture_correction_unavailable`. `aperture_correction_crowding` now reports
  an actual rejected reference rather than an unconditional retained defect.
  Repaired saturation, origin, seam and SNR-proxy warnings are retired.

Independent review reproduced two additional edge cases before correction:
missing-RMS estimation discarded combined masks, and a separately requested
annulus could differ from the one used for subtraction. Both received failing
regressions first. Mask-aware estimation now gives identical flux/error when
only masked values change, agreeing with independently masked SEP estimation.
One annulus's actual shape, rotation, masks and outlier selection now govern
flux, variance and metadata. The custom ellipse excludes the planted sky
contaminant and returns the analytic 300-count source with its expected error.
The reviewer rechecked both probes and found no remaining actionable issue.

The full-suite integration also exercised an interpolated RMS map on NGC 5286
B with 120 negative pixels. Rejecting its entire frame was too broad. Invalid
RMS pixels are now excluded locally, with `background_noise_masked`, rather
than squared or assigned fabricated valid noise. A wholly invalid map produces
invalid measurements. An independent recheck found identical flux/variance/
metadata to explicit masking for bad pixels in the aperture, annulus and
elsewhere, in both sky modes; the real frame's calibration succeeds.

The error model follows SEP's fractional-area convention and assumes independent
marginal sky errors and a known gain. It does not reconstruct original detector
noise, covariance from resampling, sky-model systematics or aperture-correction
uncertainty from reduced pixels. Background RMS is an estimate, not a proof of
a calibrated confidence interval. These limits are separate from the corrected
arithmetic and invalid-row acceptance.

Historical fixtures remain unchanged: the provided-photometry replay selects
29 usable-error rows instead of 35; pixel measurement returns 34 of 35 because
one annulus is truncated. The default NGC 3628 annular path returns 33 of 35
detections for the same flag policy. Dedicated controls preserve the identity
and order of surviving measurements and compare annulus bounds independently.

Validation before final suite: 117 photometry/calibration/warning checks pass;
46 recorded-reference checks pass; the two review regressions and related
flux/uncertainty controls pass (26 cases). An earlier 13-failure integration
run identified stale historical counts, retired warning expectations and
inconsistent synthetic sky/pixel fixtures; these were corrected without
widening historical numerical tolerances. The first full-suite attempt was
interrupted after review changed the source; the final run checks those fixes.
The next full run exposed two stale coverage counts, the invalid-RMS real-frame
case, the same RMS policy on a radio map, and a prohibited earlier project name
in the report: 5 failed, 4,508 passed and 90 skipped. Those failures are retained
as evidence; the corrected cases pass separately before final validation.

Final validation on Python 3.13.15: `uv run --locked pytest` passed
**4,514 tests, with 90 skips and 214 FITS normalization warnings**, no failures
(428.26 seconds). The run used the final source and generated guidance outside
the socket-restricted sandbox. The preceding run had one served-guidance
invariant failure because a guidance file changed after pytest cached its old
contents; a fresh 50-case guidance check passed, and the final full run held
source/guidance unchanged. Compilation, generated-copy consistency and whitespace
checks pass. Independent review found no remaining actionable findings after
the mask, custom-annulus and local invalid-RMS rechecks. Asset/network/platform
skips remain gated; this does not claim live-catalog or additional host coverage.
The master's measured-flux/source-position square is closed on this branch.
