# M2 accepted sky positions and reference stars

Recorded 2026-10-22 on `feature/m2`, after integrating M3 PR #122 in
`160b3e4`. Scope: WCS-03, WCS-14 and WCS-27 from the algorithm review.

## Acceptance and reference geometry

The pointing tolerance retains the existing one-degree floor and allowance of
three image diagonals. A finite positive scale hint still defines that
allowance. Without one, the candidate's transformed footprint supplies the
size; the search's broad 60 arcsec/pixel ceiling no longer substitutes for a
measurement. This is a pointing sanity check, not an independent validation of
the solver's star matches. A blind solve has no pointing prior to compare.

Both backends validate stored WCS parameters and the transformed centre and
boundary before acceptance. Rejected/nonfinite solutions leave the header
unchanged. Header-WCS pointing hints, candidate centres and result metadata
are expressed in ICRS, consistently with the catalog query. Review found that
transforming only the candidate could reject a valid FK4/B1900 or FK5/J1800
frame against its own untransformed hint; four regressions reproduced this
before the header-hint conversion was corrected.

The ATLAS follow-up now uses the solved image centre and angular footprint,
including rotation, shear, displaced CRPIX and SIP distortions. Outer pixel
edges are sampled at 64 intervals per side, with the existing configurable
catalog padding. Sampling estimates a footprint; it does not certify arbitrary
pathological distortion functions between samples. The padded radius must fit
the existing catalog budget before catalog initialization; it is never clipped.

A spherical-cap bounding box covers the estimated footprint across the RA seam
and at high declinations. Pole-crossing caps query both half-turn RA intervals,
avoiding UCAC4's retained full-turn modulo bug, and remove duplicate meridian
positions before the existing source cap. The two queries share the returned-row
budget, and each retains its existing candidate/zone/index limits. These
corrections apply to the follow-up query. General query geometry, catalog
completeness, brightness/thinning selection,
proper-motion epoch correction and native UCAC layout validation remain in
their separate gates. Reference lists can include the padded surrounding field;
they are not a claim of a complete or sufficient calibration sample.

The no-WCS MaxIm fallback retains southern signs, including `-00` degrees.
Its six-value shape and RA-hours/Dec-degrees units remain unchanged.

## Evidence and limits

The new offline pipeline tests replace native backend execution and catalog
I/O, while using real Astropy transformations, acceptance, reference-query
filtering and header write-back. They cover distant and nearby candidates,
no-scale/no-pointing inputs, both backends, NaN coordinates, an oversized
footprint, a curved SIP edge, offset CRPIX, shear, the RA seam and both poles.
The first run reproduced distant acceptance, nonfinite acceptance/crash,
incorrect reference footprints and all three southern fallback failures.
Preservation assertions that formerly accepted a singular solution or pinned
the southern zero bug now assert the intended correction.

Fresh code review has no remaining findings after the frame correction.
Reviewer validation passed **410 tests**, with two native-data skips. Thirty
random TAN fields with rotation, shear and displaced CRPIX agreed with
independent analytical tangent-plane centre/radius calculations within
`4.5e-14` degrees. All **6,480** independently generated spherical-cap edge
positions were covered across nine ordinary, seam, high-declination and polar
cases. The root's post-frame-fix regression run passed **506 tests**, with two
native-data skips. Final Python 3.13.15 full offline validation passed
**3,798 tests, with 75 skips and 219 warnings** (the warning count is unchanged
from the M3 integration baseline). Compilation, generated-skill consistency,
schema goldens, repository shape and whitespace checks passed. Live provider,
native Windows and external solver-data checks retain their separate gates.

Review scope decisions retain per-reader-call candidate limits (at most two
calls in a polar follow-up) and a combined returned-row limit. Public inspection
of arbitrary native-frame WCS retains existing behavior outside this checkpoint;
these frame regressions validate the algorithm/result and reference-query
interfaces, rather than the separate public inspection helpers. General catalog geometry,
thinning/completeness and epoch corrections remain in their own gates. Native
solver convergence, real UCAC layout/completeness and guaranteed containment
of arbitrary distortions between samples were not established. The imported
M3 live ADS grouping check remains open.

Astropy references: [frame-aware WCS interface](https://docs.astropy.org/en/stable/wcs/wcsapi.html)
and [great-circle coordinate separation](https://docs.astropy.org/en/stable/coordinates/matchsep.html).
