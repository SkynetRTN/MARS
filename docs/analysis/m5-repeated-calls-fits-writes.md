# M5: repeated calls and FITS writes

Investigated 2026-11-02 against `a4d429a` on `feature/m5-geometry`, after the
first two M5 squares and their review fixes. The [master plan](../working/master-continuation-plan.md#m5-resolve-the-specific-older-reports-that-remain-unverified)
defines the questions; the [investigation plan](../superpowers/plans/2026-11-02-m5-repeated-calls-fits-writes.md)
records the probes. **No production behavior changes in this investigation.**
Passing characterization tests below deliberately preserve observed defects;
they are not acceptance tests for repairs. The M5 square remains open pending
fixes or an explicit disposition of its remaining contracts.

## Findings and reachability

| Finding | Current evidence | Reachability and priority |
|---|---|---|
| WCS-28: caller's saturation setting changes | `solve_wcs` sets supplied `extraction_settings.discard_saturated=0` in place, even when both solvers are disabled and the result is a miss. A later extraction reusing it admits a saturated star that a fresh setting rejects. | Confirmed algorithm-API reuse hazard, P2. Maintained tools build fresh extraction settings rather than share this object across calls. |
| M5-REUSE-01: adaptive aperture depends on prior measurement | The low-level driver overwrites isophotal `flux`, which a later call uses as the weight for fixed aperture/ellipse/orientation selection. Reusing either the original caller array or returned array changes the aperture and measured magnitudes. | Confirmed low-level API reuse hazard, P2. `run_photometry` builds a fresh table on each call and is stable in the native control. |
| M5-REUSE-02: failed measurement flags survive a valid one | Reusing a table from a nonpositive-flux or unusable-annulus measurement produces valid current flux/magnitude but retains the previous aperture failure bits. A fresh table has identical flux/magnitude and flag zero. | Confirmed low-level API reuse hazard, P2. Public measurement likewise avoids it by rebuilding its table. |
| M5-WRITE-01: old detector lookup distortion survives | Both FITS writers omit `D2IMDIS1/2` and `D2IM1/2` records from WCS cleanup. Reopening with the full HDU list reapplies the old map to a clean accepted WCS. Header-only readers conceal the map. | Confirmed maintained-tool write/read defect, P2. Forced public writes are reachable; solver execution is replaced only at the test seam. |
| M5-WRITE-02: time-reference metadata is overwritten | Both writers replace single-card `MJDREF=61041.75` with a clean WCS's default `MJDREF=0`. The raw writer's preservation list covers split `MJDREFI/MJDREFF`, but omits the single-card form. | Confirmed metadata defect at both write boundaries, P3. This does not establish an incorrect `DATE-OBS`, measured magnitude or current MARS time result. |
| WCS-26: direct no-flux source cap is ignored | Actual xylist output retains all four coordinates with `max_sources=2, flux=None`; a finite brightness vector selects two. | Confirmed direct-backend defect, P3. The maintained wrapper independently caps rows first, so its missing-flux frame-cap consequence from the old report is not reproduced. |

### Input reuse controls and numerical consequences

`algorithms/wcs/wcs.py:575–576` assigns the shared saturation setting before
extraction. In the 128×128 two-Gaussian fixture, the initial extraction with
`discard_saturated=1` returns one star. A no-backend solve returns no solution
and two extracted stars, leaves the header intact, but changes the setting to
zero. Reusing it returns both stars. The image has **13 saturated pixels**;
both later rows report zero `sat_pixels` because disabling discard also skips
construction of the saturation mask. The fresh-copy control still returns
only the unsaturated star. Including saturated stars for astrometry itself is
distinct from leaking that choice into the caller's next measurement.

In `algorithms/skylib_lite/photometry/aperture.py:350–368`, shape/flux columns
can alias the caller's extraction table; lines 409–413 use flux as the adaptive
weight, and line 624 replaces it with measured aperture flux. Two genuinely
SEP-extracted Gaussian stars have initial isophotal fluxes **15007.9580 and
15729.3711 counts**. With `k=2`, `fix_aper=True`, `fix_ell=True`,
`fix_rot=True` and correction disabled, the first common semi-major aperture
is **5.87879944 px**. Its measured fluxes favor the narrower star. Reusing
the input or output table selects **3.94784188 px**, shifting the two
magnitudes by **+0.13690663 and +0.28314708 mag**. A fresh extraction-table
copy repeats the first result exactly. This is measured-flux feedback into
isophotal weights, not random extraction or aperture-correction convergence.

At `aperture.py:634/646`, old and new flags are ORed. After a failed measurement,
a valid planted 300-count impulse returns **300 counts and −6.19280314 mag**
from both reused and fresh tables, but only the reused one retains rejecting
failure bits. That status is ambiguous without separating extraction flags
from the previous measurement's flags. Retaining fields in a returned table
is not by itself a bug; the probes demonstrate the consequential reuse behavior.

The public `run_photometry` control runs actual native adaptive photometry
twice and returns identical rows while preserving source models, settings,
image, background, RMS and header. PHOT-17's old catalog/global-state claim
is also narrowed: current `_normalize_catalog_sources` builds new models.
Model and mapping inputs retain their ids and values across two successful
provided-photometry calibrations and a failed pixel measurement. Calibration
generates call-local ids and deliberately writes `PHOT_M0`, `PHOT_M0E`, and
`PHOT_CAL` to the output header. A later failure preserves that header rather
than returning a new calibration; this is an explicit transactional control.
The removed process-global dependency shim is not a current finding.

### FITS round trips and stale keyword reports

The shared cleanup expression is `algorithms/wcs/wcs.py:86–117`; the raw writer
is at line 299 and the staged file writer at `tools/wcs.py:266`. A valid old
detector map with constant **(+3, −4) px** corrections survives replacement by
a clean acceptance-gated 1 arcsec/px TAN WCS. `WCS(header, hdul)` then differs
from the accepted center by **4.999999999 arcsec**. Three write/read cycles
retain the same error rather than accumulating it. Science pixels and lookup
HDUs are unchanged. CPDIS is a working cleanup control: its references are
removed, and retained unreferenced HDUs do not alter coordinates.

New lookup-bearing candidate solutions are rejected by distortion validation;
that does not remove lookup references in the old destination. A public
`solve_astrometry(force=True, write_header=True)` test exercises the real
staged writer with only the solver/configuration seam controlled. It reports
the clean accepted center while a full-HDU reopen sees the old distortion.
The next default call short-circuits through a header-only reader and again
reports the clean center. This proves the write/read mismatch, not native
solver success. An independent second reproduction uses **(+1, +2) px** at
2 arcsec/px and measures **4.472135954 arcsec**, agreeing with `2*sqrt(5)`;
its header-only offset is zero. It also confirms the `MJDREF` overwrite.

WCS-18's older frame/epoch claim needs narrower wording. `RADECSYS`, `EPOCH`,
old ICRS `EQUINOX`, and SIP `A/B/AP/BP_DMAX` cards do survive. Nevertheless,
accepted ICRS/FK5/FK4 replacements match independent inverse-TAN/frame controls
to **2e-7 arcsec**: ICRS writes explicit `RADESYS=ICRS`, while acceptance
resolves FK5/FK4 default equinoxes to 2000/1950 before serialization. Old
regular SIP coefficients are replaced correctly; valid SIP→SIP, SIP→no SIP,
and no SIP→SIP controls also match independent SIP-polynomial/TAN calculations.
Alternate celestial geometry is removed, although `EQUINOXA` and `CNAME1`
debris survives. These are metadata-cleanup gaps; the blanket coordinate-frame
error from stale epoch cards was not reproduced on the accepted path.

Two conditional boundary observations remain separate from native failures:
the staged writer can overwrite observation dates when a supplied solved WCS
carries conflicting dates, whereas the raw helper restores its protected
cards/comments. There is no evidence here that native solvers emit those
conflicts. A deliberately broken serialization object strips the raw helper's
in-memory header before raising; the staged writer preserves the original file
byte-for-byte and removes its temporary file. That injected object is not a
normal acceptance-gated solver result.

### Parity, source budgets and superseded consequences

WCS-20's automatic path is already correct. The wrapper constructs fresh
`WcsCalibrationSettings`, exposes no explicit parity/source-cap preference,
and automatically sends the header determinant's inverse to astrometry.net
and its sign to ATLAS. Independent reflected-pixel and oriented-sky-offset
controls validate handedness. Both backends' candidates remain subject to
header-derived acceptance: a matching determinant is accepted and a reflection
rejected; pointing-only hints impose no parity restriction. Without a pointing
hint, ATLAS is skipped rather than asked to search blindly.

Bounded native `/usr/bin/solve-field` controls use 35 exact index-derived stars
from local `ucac5-index-00-00.fits`, center (26°, 16.5°), 1024² pixels and
1 arcsec/px. Positive-determinant truth solves with request `False` / CLI
`neg`; its reflected negative-determinant truth solves with `True` / `pos`.
The recovered determinants are approximately **±7.715967934e-8 deg²/px²**.
Opposite flags return exit zero without a WCS. Each optional case has a
two-CPU-second and eight-wall-second process-group limit. Exact index-derived
inputs verify the convention; they do not demonstrate independent real-image
recovery or completeness. The owned suite's native-enabled run passes all
51 cases, with two expected synthetic-header NAXIS warnings.

The explicit Boolean contract still differs between direct backends, and ATLAS
blind search ignores parity while echoing it in its attempt. The maintained
wrapper always supplies `rotation_deg=None`; entering its explicit settings
branch requires test-only settings-factory replacement. Resolve that latent
contract before exposing a parity knob rather than describing it as a current
automatic-parity failure. ATLAS also uses its own configured extraction/matching
budgets rather than the blind request's echoed `max_sources`.

For WCS-26, the maintained wrapper caps 120 detections to 100 before constructing
the brightness vector. Actual written tables remain at 100 for finite,
all-missing, partially missing and nonfinite supplied flux. Missing or
nonconvertible values discard the brightness vector; NaN/Inf are not sanitized
and can take brightest-source slots in injected inputs. No real extraction
occurrence is established. A partial direct vector raises `ValueError` before
writing. Metadata `n_field` counts capped detections before unusable-position
filtering: one missing position gives 100 in metadata and 99 submitted rows.
That distinction and the unused blind-ATLAS request fields need explicit
semantics; they are not proof that the maintained wrapper bypasses its cap.

## Reproduction and remaining work

The three `tests/test_m5_{reuse,fits_write,solver_controls}_investigation.py`
files exercise actual SEP/Numba calculations, FITS writers/readers, independent
geometry and bounded deterministic solver seams. The native parity cases are
opt-in and require an installed solver and a supplied index; catalogs and
generated FITS products are not committed fixtures.

```bash
.venv/bin/python -m pytest -q tests/test_m5_reuse_investigation.py tests/test_m5_fits_write_investigation.py tests/test_m5_solver_controls_investigation.py
MARS_M5_NATIVE_PARITY_INDEX=/srv/agents/catalogs/astrometry/UCAC5/ucac5-index-00-00.fits .venv/bin/python -m pytest -q tests/test_m5_solver_controls_investigation.py
```

Priorities are the maintained FITS detector-map/time-reference write defects
and the demonstrated caller-input reuse hazards. Convert each bug-pinning
probe into an independent correctness regression when fixing it. Reconcile
the direct-backend cap, latent parity contract and ancillary metadata cleanup
with their documented scope. M4 acceptance and the remaining M5 squares are
separate work. Final integrated validation and review are recorded below.

Pre-integration verification: **786 passed, 8 skipped, 68 existing fixture
warnings** across the new probes and related WCS/photometry/calibration suites
(12.61 seconds). Independently repeated native-enabled solver-control suite:
**51 passed, two expected NAXIS warnings** (3.86 seconds). The three new files
contain **79 default offline cases and four opt-in native cases**. Compilation,
generated guidance consistency and whitespace checks pass; production source
remains unchanged.

Final independent review found no actionable claim, reachability or test-labeling
issues and repeated the default group: **79 passed, four expected native
skips** (1.93 seconds). The final locked offline suite passed **4,620 tests,
94 skips, 214 FITS normalization warnings**, no failures, in 425.22 seconds
on Python 3.13.15. The four additional skips are the opt-in native parity cases,
which passed separately as recorded above. Source, tests and guidance stayed
unchanged throughout the full run outside the socket-restricted sandbox.
Compilation, generated-copy consistency and whitespace checks pass.
