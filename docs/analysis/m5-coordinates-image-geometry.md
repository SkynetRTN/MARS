# M5 coordinates and image geometry: investigation and corrections

Recorded 2026-11-01 on `feature/m5-geometry`, based on merged main `fb09774`
(including M2 PR #124). Compared the affected source files with M4 branch
`docs/m4-desktop-acceptance` at `3e90733`. Its only change within WCS/query/
ATLAS/extraction is astrometry.net's index-loading policy; it does not repair
the baseline cases below. The investigation initially made no production
changes. The subsequent authorized corrections are described in
[Remediation](#remediation); the tables retain the evidence observed before
those corrections.

The vault's optical/finding-register notes predate M2. Retrieval had no
configured BM25 index, so context came from the hot/index pages and narrow
text search. Current source and fresh probes decide the dispositions here.

## Findings that still affect current calls

| Report | Reproduction and caller | Disposition |
| --- | --- | --- |
| WCS-06: decimal RA strings interpreted as hours | With no celestial WCS, `RA_PNT='185.6'`, `TARGRA='185.6'` or `OBJCTRA='185.6'` produces a search centre at **264 degrees**, rather than 185.6. `solve_wcs` falls through to `guess_icrs_radec_from_header`, which passes every RA string to `Angle(..., hourangle)`. | Confirmed reachable defect in the fallback. The earlier `RA`, `TELRA`, `OBJRA` parser correctly treats this string as degrees. Preserve sexagesimal-hour controls and establish the ambiguous numeric <=24 convention before changing it. |
| WCS-08: alternate-WCS scale units | A declared alternate celestial WCS with `CUNIT1A=CUNIT2A='deg'` and `abs(CDELT1A)=abs(CDELT2A)=1/3600` has a 1 arcsec/pixel scale by Astropy. The header helper returns **1/3600 arcsec/pixel**, and `solve_wcs` submits ATLAS a **0.1 to 0.00055556** window. | Confirmed reachable defect, 3,600 times too small. Respect the alternate WCS's axis types/units; do not assume arbitrary alternate linear axes are celestial or angular. Explicit tool scale bounds bypass this narrowing. |
| WCS-07: small-field triangles | A noncollinear triangle accepted in pixels is rejected after conversion to tangent-plane radians. An exact 16-source TAN catalog for a 300x300-pixel field at 1 arcsec/pixel yields **32 image triangles and zero catalog triangles**, returning `no_triangles` before matching. | Confirmed reachable defect. The absolute cross-product cutoff `1e-6` is dimensional and is reused for pixels squared and radians squared. The probe demonstrates premature rejection, not that changing the cutoff alone guarantees a solve. |
| WCS-10: polar catalog coverage | For a 512x512-pixel field at 1 arcsec/pixel, a star 0.05 degrees east of a centre at Dec +89 or -89 lies on the detector. Both ATLAS searches exclude it: the blind path's RA half-width is about 1.006 degrees, but the star is about 2.863 degrees away in RA. An equatorial control includes it. | Confirmed reachable defect in the general triangle search and direct oriented backend. Both clamp `abs(cos(dec))` to at least 0.2. Their boxes also lack pole-crossing spherical-cap handling. M2 repaired the **post-solve reference query**, not these pre-solve searches. The public pipeline currently selects the general search, since it supplies no rotation prior. |

The RA and scale probes exercise real `solve_wcs` parsing and request assembly,
replacing source extraction and native backend execution. The triangle probe
executes the real ATLAS general search with exact synthetic sky positions,
replacing extraction and catalog I/O. The polar probes capture each real
search's catalog request and independently place the witness with Astropy WCS.
They do not claim native end-to-end convergence or a real observed polar miss.
Additional cases at Dec +/-89.95 degrees independently verify that the pole
itself lies on the detector and reproduce the same omitted-star failure.

## Reports already superseded on maintained query paths

CAT-07 (CRPIX at/outside a detector edge), CAT-09 (swapped scales and rotation),
and CAT-11 (polar NaNs) were addressed by M2's enclosing-cone queries and
explicit-box/SQL polar handling. Both `query_catalogs(..., wcs=...)` and
`query_catalogs_for_image` use `cone_from_wcs` and detector clipping. Neither
calls the retained `boxes_from_wcs` / `image_boxes_from_wcs` implementations;
a source search found their definitions but no maintained callers.

The existing M2 detector-grid controls cover rotation, unequal pixel scales,
off-detector CRPIX, the RA seam and both poles, and passed again. This resolves
those original reports for the live query routes without claiming the old
helpers were repaired. Distorted/non-TAN footprints remain sampled and emit
`catalog_coverage_unverified`, as documented in M2's
[coverage record](catalog-coverage-sufficiency.md).

## Retained helper defects and bounded exposure

| Report | Current evidence | Reachability and implication |
| --- | --- | --- |
| WCS-09: far-side gnomonic projection | Both copies project (180, 0) almost onto a tangent point at (0, 0), while Astropy's TAN inverse rejects that sky position. The distance cap can consequently prefer an antipodal star. | The arithmetic defect persists. Valid current ATLAS search boxes have at most a 5-degree Dec half-span and 25-degree RA half-span under the pre-load guard; a valid catalog row in such a box cannot be on the far hemisphere. The solved reference query is also local. No supported valid-input false match was demonstrated. Corrupt/out-of-region catalog rows or direct private-helper calls remain unguarded. |
| WCS-11: UCAC4 spans of 360 degrees or more | Synthetic records at RA 0, 50, 180 and 350 return only RA 0 for `[0,360]`, and only RA 180 for `[-200,200]`. A seam-crossing `[350,10]` returns both ends. UCAC5's full-turn control retains all four. | Confirmed interval-arithmetic defect in `Ucac4Index.query_box`. Current pre-solve RA spans are under 360 degrees; M2's polar follow-up deliberately splits the full turn. This does not validate UCAC4's disputed native layout, which belongs to M5's catalog-reader item. |
| WCS-12: PC/CDELT multiplication order | With unequal CDELT values and rotation, `_wcs_matrix` disagrees with Astropy's `pixel_scale_matrix`: it multiplies `PC @ diag(CDELT)` instead of `diag(CDELT) @ PC`. The accepted-result metadata block repeats it. | Conditional on a PC-form backend result: ATLAS constructs CD and stock astrometry.net emits CD, but its reader does not enforce that representation. For an input PC header, the helper is currently used for determinant/parity, and the determinant is invariant to this product reversal. No current input-header coverage loss was established from this helper. |
| WCS-16: ellipse normalization writes to copies | Real SEP extraction already returns `a >= b`; a rotated-Gaussian control retains both axes. A negative angle is changed to an equivalent angle above pi/2 because the final masked write is a no-op. Both `sin(2 theta)` and `cos(2 theta)` agree before/after. | The range-normalization defect persists, but a half-turn represents the same ellipse. The alleged wrong-axis result was not reproduced with real SEP output. The separate swap would fail if fed `a < b`, but no current producer of that ordering was established. Do not report demonstrated flux bias from this code on that evidence. |
| WCS-24: impossible FOV from stripped headers | `_estimate_fov` returns `(4096,4096)` degrees for a stripped header and supplied 4096x4096 dimensions: Astropy's default non-celestial WCS increments are misread as angular scales. | The bad estimate is real, but current requests have positive scale bounds, and `_search_half_diag_deg` uses those instead. For 0.5-1 arcsec/pixel, its actual unpadded radius is 0.80453 degrees. No oversized catalog query was caused by the estimate in this probe. |

## Catalog depth and epoch (WCS-17)

The general ATLAS search's `_limit_catalog` and the post-solve
`_limit_catalog_sources` retain the nearest tangent-plane positions when the
catalog exceeds its cap. Query results carry positions only; they cannot
rank stars by brightness. The oriented backend instead uses a deterministic
uniform random subsample. Image matching uses bright image sources. A
distance-cap control confirms the selection policy, but this investigation
does **not** establish a particular real-frame failure caused by depth mismatch.

The UCAC5 reader uses Gaia positions at epoch 2015.0 and discards the rest of
each record from its public result, including proper motion. Neither catalog
query API accepts an observation epoch, and the general/oriented searches and
follow-up do not propagate those positions. This is a confirmed missing
capability. As an illustrative calculation, 100 mas/year over eleven years
is 1.1 arcsec; it is not a measurement of an audited star's residual or proof
that a fit fails. Reference source objects produced by the follow-up also
carry no motion/epoch metadata.

A read-only query of the operator's actual UCAC5 tree at
`/srv/agents/catalogs/ATLAS/UCAC5` returned 356 rows in
RA 169.5-170.5, Dec 13-14 degrees, 2,489 rows in RA 322-323, Dec 12-13,
and 458 rows in RA 179.5-180.5, Dec -0.5 to +0.5. Results contain only
`ra_deg` and `dec_deg`. A smaller initial query was empty. These are native
lookup checks, not completeness, brightness, epoch-propagation or native
solver acceptance tests.

Depth selection and epoch handling need a documented supported accuracy/epoch
contract and either remediation or an explicit maintainer decision with a
user-visible limitation. Do not silently expand this into a new catalog
backend or change star-selection policy based only on the old report.

## Verification and next work

The initial `tests/test_m5_geometry_investigation.py` had 29 offline
characterization/control cases. They recorded retained defects; their original
passing results established reproduction, not correctness. The remediation
converts them to correctness assertions. That converted group failed in 22
cases on the original code, before production corrections.

Baseline: 566 geometry/header/acceptance/catalog-budget tests passed on
Python 3.13.15, with 12 Astropy FITS date-normalization notices. Final focused
verification is recorded in the master plan. No live provider was queried,
no production algorithm changed during that investigation, and M4's manual
evidence was not rerun.

Recommended remediation order: header RA/scale contracts, scale-invariant
triangle rejection, then spherical pre-solve catalog coverage. Each needs
the smallest independent regression/control pair and the existing M2 acceptance
and query suites. Decide the remaining depth/epoch limitations separately.

## Remediation

The subsequent instruction to fix all findings authorizes the scientific
divergences below. Existing public argument shapes and finite runtime/catalog
budgets remain. No worktree or new dependency is introduced.

- **Header coordinates and scales (WCS-06/08):** decimal RA strings and numbers
  share the existing absolute-value <=24-hours heuristic; sexagesimal and
  explicit-unit strings retain their units. Alternate WCS A scales require
  celestial axes and finite nonsingular angular geometry, and use Astropy's
  full PC/CD transform and CUNIT conversion. Direct arcsec-keyword precedence
  is unchanged. The separate primary-WCS/optics hint paths remain disabled.
- **Triangles and ellipses (WCS-07/16):** collinearity uses dimensionless
  twice-area/longest-side-squared at the same `1e-6` tolerance, with robust
  finite side lengths. Ellipse normalization updates the actual structured
  fields, swaps reversed axes with a quarter-turn, and keeps angles in
  `(-pi/2, pi/2]` without changing the represented ellipse.
- **Catalog geometry (WCS-09/10/11):** both ATLAS searches and the follow-up
  use a shared spherical-cap enclosure, including the RA seam and poles.
  Polar queries use one full-turn reader call, preserving both candidate and
  returned-row budgets before clipping. UCAC4 now
  handles full/super-full-turn spans independently as well. Invisible
  hemispheres become NaN in projection and are excluded before matching/caps.
- **Matrices, field sizes and old query helpers (WCS-12/24, CAT-07/09):**
  PC-form matrices and result metadata use `diag(CDELT) @ PC`. FOV inference
  requires a celestial WCS; a stripped header uses explicit angular scale
  bounds. Both old box helpers now wrap the maintained enclosing cone and
  return conservative angular boxes instead of retaining off-CRPIX/rotation/
  anisotropic-scale defects. CAT-11's existing polar clipping/SQL fix remains.
- **Catalog depth and epoch (WCS-17):** the UCAC5 reader retains Gaia G and
  both signed proper-motion components, verified against the authors'
  52-byte binary layout. Capped matching catalogs prefer measured bright
  stars with deterministic distance ties, rather than nearest-only or random
  selection. Reference queries carry aligned brightness/motion metadata.
  Recorded exposure midpoints (including MJD-only observations) select the
  target epoch. The query cap grows by the maximum angular displacement
  permitted by the binary PM encoding before querying, then positions and
  tangent directions propagate along a great circle and clip to the original
  requested cap. Reference objects carry their new epoch and motion.

The proper-motion model assumes constant tangential angular motion; it does
not invent radial velocity, distance or perspective acceleration. The source
epoch is 2015.0. The encoding's vector bound is approximately 4,634.095 mas/year;
the enlarged query must fit the existing radius budget or fail explicitly.
Unknown observation dates or absent epoch/motion data emit
`astrometry_catalog_epoch_unverified`; incomplete brightness at a cap emits
`astrometry_catalog_brightness_unavailable`. These disclosures cover legacy
readers and incomplete user data, rather than pretending those inputs gained
missing measurements. They survive the public tool's handled failures.
Neither brightness ranking nor motion correction certifies catalog
completeness, bandpass-independent detectability or astrometric accuracy for
arbitrary epochs. UCAC4 native-layout validation remains the separate M5
catalog-reader item.

New tests in `test_m5_header_fixes.py`, `test_m5_shape_fixes.py`,
`test_m5_catalog_readers.py` and `test_m5_catalog_geometry.py` cover the fixes
and edge cases in addition to the converted original probes. Reader fixtures
use hand-packed binary bytes, not the production dtype to derive expectations.
Read-only native checks preserved the three lookup counts above and verified
metadata against independent byte decoding for all 356 first-field rows.
The bounded native ATLAS solve on the WCS-stripped NGC 3628 frame recovered
the recorded geometry within 0.17 arcsec at centre and 0.38 arcsec across the
detector, 0.026% in scale and 0.017 degrees in rotation. Its 67 reference
objects carried proper motion/epoch metadata. With all documented 2MASS 4200,
TYCHO2 and UCAC5 astrometry.net index directories configured, both existing
native checks passed, including blind known-solution recovery. An initial
2MASS-only blind run hit its 330-second outer timeout; it remains a failed
check of that subset, rather than evidence that every index selection solves.

Independent review reproduced and corrected naive/aware epoch incompatibility,
a split-query candidate-budget gap, duplicate first-bin UCAC5 spans, and
incomplete epoch/duration handling. Each has a correctness regression. The
reviewer confirmed no remaining findings after the corrections.

Final validation on 2026-11-02: **4,428 passed, 90 skipped, 214 Astropy FITS
notices**, with no failures on Python 3.13.15, plus all **145 M5 correctness
cases** and both configured algorithm-level native checks. The full suite ran
outside the sandbox after a restricted attempt failed the socket-restoration
guard and stalled in subprocess MCP calls. Those paths pass in the unrestricted
run. Compilation, generated guidance and whitespace checks pass. The master
continuation plan's first M5 checkbox is closed locally; the changes remain
unpublished, and other M5/M4 items remain separate.

Earlier failed checks remain part of the evidence: the first full integration
run failed `test_every_declared_code_is_constructed` and
`test_no_new_dynamic_code_site_appears` because the two new warning codes used
a dynamic constructor; literal registered constructors corrected both.
The restricted run failed `test_the_guard_actually_refuses` when restoring a
real socket and stalled in MCP subprocess calls, and was interrupted rather
than counted as passing. `test_blind_solve_recovers_the_known_plate_solution`
timed out with the 2MASS-only configuration and passed with the documented
complete configuration. All corresponding tests pass in the final applicable
runs above.

References checked during the investigation:

- [FITS Standard](https://science.data.nasa.gov/fits/documentation/standard): celestial WCS units, alternate representations and PC/CDELT transformations.
- [Astropy projected pixel scales](https://docs.astropy.org/en/stable/api/astropy.wcs.utils.proj_plane_pixel_scales.html): returned units and the requirement to select celestial axes for celestial scales.
- [CDS UCAC5 description](https://cdsarc.cds.unistra.fr/viz-bin/ReadMe/I/340?format=html&tex=true): Gaia positions at epoch 2015.0, proper-motion fields and native catalog provenance. It does not validate MARS's parser.
- [Authors' UCAC5 binary specification](https://vizier.cfa.harvard.edu/ftp/cats/I/340/readmeU5.txt), version 2.0, section 4c: verified 52-byte field offsets, 0.1 mas/year proper motions and millimagnitude Gaia G values. No PM/G missing sentinel is specified.
- [SEP extraction interface](https://sep.readthedocs.io/en/stable/api/sep.extract.html): source moments and ellipse parameters.
