# Catalog coverage and sufficiency

This M2 checkpoint addresses CAT-07/08/09/11/17/19/30 on `feature/m2`.
It repairs detector coverage and constraint isolation, and makes remaining
selection and calibration-sample limitations explicit. Reference magnitude
formulas, H-alpha transforms, measurement-error propagation and fitting
arithmetic are unchanged.

## Detector coverage

Both WCS query entry points now request an enclosing spherical cone and clip
the returned sources to the actual detector. This handles rotation, unequal
pixel scales, the RA seam, pole-crossing fields and off-detector CRPIX without
the historical relocated-box reconstruction or swapped image-axis scales.
The cone encloses the accepted pixel domain `[0,width) × [0,height)`.

For undistorted TAN geometry, a cone smaller than a hemisphere containing the
four detector vertices contains their gnomonic rectangle: its boundary is a
set of great-circle segments inside a convex spherical cap. The radius is
rounded outward. Cached cones also grow by the spherical displacement caused
by rounding their centre, then round the enlarged radius upward. This fixes
the previous edge loss when a radius was already an exact cache-grid multiple.

Distortions and other projections use 65 samples along each boundary edge and
emit `catalog_coverage_unverified`. Sampling is best effort; it does not prove
complete coverage between samples or through arbitrary interior distortions.
TPV needs special detection: wcslib internally normalizes it to TAN while
`WCS.has_distortion` can be false. The effective serialized CTYPE preserves
TPV, so these fields take the sampled/disclosed path. Non-finite footprints,
nonpositive dimensions and cones reaching a hemisphere fail before querying.

Explicit polar box clipping and SDSS SQL now use a conservative full-RA
declination band when the tangent-meridian bound is undefined. They cannot
silently drop every star or emit NaN SQL. Historical `boxes_from_wcs` and
`image_boxes_from_wcs` remain available for extraction comparisons, including
their documented limitations; the live WCS runner uses neither helper.

## Query selection and isolation

SkyMapper copies constraints before adding its existing `flags=0` default.
Explicit flags remain intact, and caller dictionaries and later queries are
unaffected.

VizieR and SDSS record `catalog_rows_capped` when the **raw response** reaches
its effective limit, before row mapping, slicing or detector clipping can hide
the cap. This includes astroquery's 50-row default for a declaration without
an explicit VizieR limit. At-limit responses may be incomplete; reaching a cap
does not prove more stars exist. Magnitude ordering can favor bright and
possibly saturated stars. Returned rows remain bounded when a response exceeds
the requested limit. HTTP bytes/parsing allocations are separate runtime work.

The priority chain still stops at the first nonempty result. When alternatives
remain, `catalog_fallback_not_exhausted` names them and explains that a nonempty
response is no sufficiency test. Pooling catalogs or automatically retrying
using an arbitrary raw-row threshold would change selection without knowing
which stars survive matching, saturation/SNR checks and the fit. This gate
discloses the limitation rather than inventing a reliability threshold.
Skipped queries and failed live VSX cross-checks emit `catalog_query_incomplete`.
The latter means known variables may remain among reference candidates.

Notices are collected per operation with a `ContextVar` and reset on exit,
including exceptions. There is no mutable last-query report on shared catalog
instances. Nested operations aggregate into their parent; independent threads
collect only their own notices. Low-level list-returning APIs stay unchanged;
callers can use `collect_query_notices` or read the query logger.

## Calibration sufficiency

All registered fit paths—pixel calibration, photometry, direct measurements
and recorded selection replay—report `calibration_sufficiency_unverified`.
A finite zero point and empirical uncertainty establish a computed fit, not
enough reference stars, spatial/colour coverage, an unbiased sample or safe
extrapolation beyond the reference magnitude range. No star-count threshold
certifies those conditions. Degenerate direct fits now return `no_solution`,
matching M3's field-calibration policy for non-finite or nonpositive uncertainty.

Completed fits report exact solver survivors in `source_count`; candidate
rows remain available in replay matches and plots. A private integer records
the mask cardinality independently of reference-provenance keys. The recorded
NGC 5128 solve has 35 candidates and 29 survivors. Its reference measurement
fit and pixel remeasurement differ as documented in the preceding calibration
gate; this checkpoint does not alter either arithmetic path.

Coverage notices survive both successful calibration and failure fallbacks in
the two photometry tools. The photometry result and nested zero-point result
both carry them. Supplied offline references get sample disclosures without
inventing live coverage evidence. Numerical failures before fitting retain
the existing candidate-count diagnostic.

## Verification

The initial geometry/constraint regressions reproduced 15 failures; later
coverage and public-boundary tests reproduced missing disclosures and counts.
Independent review exposed the TPV omission and the direct/replay fit gaps;
each has a failing-then-passing regression. The concluding focused group passed
**613 tests, one network skip**. The new offline files add **45 cases** covering
both query entry points, detector grids, TPV curvature, raw caps, SDK defaults,
nested/concurrent collectors, real provider-table mapping through the public
tools, successful/failed solves, supplied references and exact fit counts.

Fresh live checks passed **15 tests in 21.10 seconds**, with no skips or
failures. They include a near-north-pole detector, an ordinary southern field,
a three-row brightness-sorted 2MASS cap, all ten magnitude/filter catalogs
(**3,355 value comparisons across 317 stars**) and both M3 identifier checks.
Live coverage checks demonstrate working transport and on-detector returned
sources; they are not an independent census of every star on the sky.

The final Python 3.13.15 offline suite passed **3,979 tests, 88 skipped,
216 warnings in 446.90 seconds**. Compileall, generated guidance, schema
goldens, repository shape and whitespace checks pass. Both review findings
are resolved and no actionable findings remain from this review. Existing
numerical defects and benchmark attribution remain in their separate gate.
This checkpoint is closed locally; M2 remains open for warnings/benchmark claims.

Review boundaries: existing arbitrary native-frame/epoch photometry handling,
the unused calibration-quality verdict helper and retained transform/solver
defects were not reassessed here. This checkpoint supplies no new acceptance
evidence for those behaviors; their existing limitations still apply.
