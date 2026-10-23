# M2 catalog magnitudes and filters

Recorded 2026-10-23 on `feature/m2`. The maintainer requested production Skynet
filter selection with all existing numerical transforms, especially H-alpha,
preserved. This is a routing and band-identity correction, not a replacement
photometric transformation model. Catalog coverage/sufficiency remains a separate
checkpoint.

## Production comparison and preserved arithmetic

The reference checkouts are `/home/codex/skynet` at
`a0dbbc5ce65c4880ff22f8ce83d7f17e1d079903` and
`/home/codex/afterglow-core` at `92aaf61`. Skynet's
`runners/common/catalog_bands.py`, `runners/utils.py` and optical
`catalog_query.py` supply the current consumer policy. Afterglow's
`resources/job_plugins/field_cal_job.py` establishes direct-band-before-mapping
precedence; its catalog plugins supply the retained survey expressions.
Neither reference checkout is modified. A standalone probe extracted the
actual production helpers without importing Skynet's service infrastructure:
**135 strict magnitude/error pairs and 45 selection lists** agree for APASS,
Landolt and Stetson. A source-AST comparison against the pre-checkpoint commit
confirmed all **65 numerical catalog expression literals** are unchanged.

MARS retains its eleven adapters. Production Skynet currently has four Skycat
providers (APASS, Landolt, Stetson and positional-only VSX); matching its filter
policy does not mean importing its database transport or deleting MARS's remote
adapters. Selection, numeric resolution and `resolve_reference_band` now share
one effective `CATALOGS` map. Historical `CATALOG_OPTIONS` remains exported for
compatibility and provenance, and no longer overrides runtime photometry.

An exact band takes priority, then an explicit mapping, then compatible label
case variants and a caller's wildcard. As in the earlier M1 V/v safeguard,
single-letter case distinguishes physical passbands: Johnson U/R/I must not
match native survey u/r/i. Typographic primes, whitespace and underscores
compose; literal colour-index names such as `B_V` win before normalization.
Standard prime spellings (`gprime`, `g'`, `gp`) reach the same existing formula.
The numeric resolver and selection both bound alias traversal and detect cycles.
Registry keys and row-stamped names (`StetsonGlobs`, `Tycho2`, `UCAC5`, `USNOB1`)
resolve through the same metadata. Caller overrides are copied and applied after base metadata, with explicit
source-name overrides taking priority over registry-key overrides independently
of dictionary insertion order. Mixed-case multi-letter aliases share that map;
underscores cannot bypass the single-letter case safeguard.

APASS `Halpha` keeps **`rprime - 0.2936*(rprime - iprime) - 0.1439`**,
the production/current pipeline Lupton R expression. `H_alpha` now follows this
same route instead of the historical secondary registry's bare rprime alias.
SDSS and Pan-STARRS keep their own existing narrowband references. No numerical
expression or coefficient was changed. USNO epoch averaging, Landolt colour
arithmetic and numeric-derivative uncertainty propagation are retained.

## Band identities and supported routes

| Catalog | Reported/native bands and retained routes |
| --- | --- |
| APASS | B, V, gprime, rprime, iprime; retained R/I expressions, colour/curriculum aliases and broadband narrowband proxies. U is unavailable because its unchanged expression needs absent uprime. |
| Landolt | V and published colour indices, with the unchanged reconstruction of U/B/R/I; Open/Clear/Lum map to V. |
| Stetson | Johnson-Cousins U/B/V/R/I; Open/Clear/Lum map to V, including row name StetsonGlobs. |
| Pan-STARRS | Native g/r/i/z/y and retained prime-band conversions; the historical narrowband aliases use those prime conversions. No Johnson R is inferred from lowercase r. |
| SDSS | Native u/g/r/i/z, retained prime-band conversions and UBVRI expressions; an explicit standard-band conversion precedes a case-only native match. |
| SkyMapper | Native u/v/g/r/i/z and retained F5V prime-band offsets; no Johnson U/V/R/I substitution. |
| 2MASS | Native J/H/K (K denotes 2MASS Ks) and retained optical J-K polynomials. Associated optical columns are Bopt/Ropt, which cannot shadow B/R transforms; these counterparts may be USNO or Tycho, not native 2MASS photometry. |
| Tycho | BT and VT, preserving the provider values and errors. No new Johnson conversion is introduced; Open/Clear/Lum no longer imply a nonexistent Johnson V. |
| UCAC | Open (native UCAC model magnitude), Gaia G, photographic NOMAD Rphot and 2MASS J/H/K. The any-filter-to-Open wildcard is removed. |
| USNO | Survey epochs B1/B2/R1/R2 and unchanged averages/single-epoch fallbacks Bphot/Rphot. These are not relabeled Johnson-Cousins B/R. |
| VSX | Variable-star positions/passband metadata, used for variable-star rejection; no standard-star calibration claim. |

The live provider metadata explicitly identifies UCAC Rmag as photographic NOMAD
R and f.mag as the UCAC model magnitude. 2MASS Bmag is the associated optical
blue magnitude; Rmag can be visual **or** red. The live `opt` flag describes the
counterpart origin. Naming them Bopt/Ropt preserves that distinction. Native
Tycho BT/VT are a separate photometric system; see the
[ESA Hipparcos/Tycho documentation, section 1.3](https://www.cosmos.esa.int/documents/532822/552851/vol1_all.pdf).
MARS adds no Tycho transformation under this checkpoint.

Finite magnitude and uncertainty zero survive VizieR mapping. This also retains
zero Landolt colour indices needed to reconstruct the other bands. Missing,
masked and nonfinite values remain unusable; the legacy >=99 magnitude sentinel
is retained. Known unsupported passbands cannot enter the preferred-band
compatibility fallback. The advisory selector still logs and returns the
configured list on a total mismatch, as production does; calibration's
preflight rejects a wholly unsupported pairing before a query.

## Retained scientific limitations

The maintainer explicitly requested preservation of the transformations.
Live numerical agreement establishes that the requested provider values and
existing formulas are used; it does not establish the accuracy of a conversion
for an arbitrary source spectrum.

- The 2MASS optical J-K polynomials remain stellar estimates with no range
  clipping or validated source classification. The earlier audit's stated
  colour range is not promoted here to a newly verified primary-source claim.
  Tool results disclose that validity for the source is unestablished and that
  propagated measurement errors exclude transformation scatter.
- APASS I retains its r'-i' stellar-locus approximation. It is not measured I,
  and is not the published i-z Lupton relation. The
  [SDSS transformation reference](https://www.sdss4.org/dr12/algorithms/sdssUBVRITransform/)
  distinguishes the available relations and their inherent uncertainties.
- SkyMapper prime-band offsets remain the original F5V constants. The
  [survey transformation guidance](https://skymapper.anu.edu.au/filter-transformations/)
  makes their dependence on source type, metallicity and reddening explicit.
- Narrowband mappings provide a broadband stellar **relative** zero point.
  They do not establish an absolute narrowband magnitude or an emission-line
  flux calibration. Results warn with `broadband_reference`; verified image
  photometry using these references is labeled
  `relative magnitude (broadband reference)`.
- UCAC Open retains the model bandpass (approximately 579–642 nm), not a
  universal instrument-clear response; results disclose this as
  `nonstandard_passband`. Landolt's historical U-error formula
  remains unchanged and belongs to the retained-defect warnings gate.

These limitations are retained under the explicit transform-preservation scope.
No catalog completeness, color-based quality selection, adequate calibration
sample, general absolute narrowband scale or live ADS validation is claimed.

## Verification record

Offline regressions exercise real query mappers, each public resolution entry,
case/prime/underscore precedence, exact standard-band values, native band
identities, zero values, invalid values and alias overrides. A replay of real B-band pixels with FILTER explicitly overridden to Halpha
uses the recorded full APASS response to exercise the warning path; this is
routing/disclosure validation, not an observed H-alpha calibration accuracy test.
The live tests observe the raw response entering the real row mapper, then
compare native magnitudes and independently evaluated transforms against the
same rows. Missing/empty responses fail, and each catalog must exercise a
mandatory set of filter conversions. Network checks remain opt-in and no
downloaded catalog data is committed.

Initial offline regressions reproduced 33 failures. The corrected catalog,
calibration and M3 regression group passed **396 tests**. Follow-up safety and
override tests passed **180 tests**, and the concluding catalog/artifact/replay/
M3/schema/shape group passed **329 tests**. Independent concluding review found
no outstanding actionable findings; 2,288 complete-row combinations agreed
between selection, reporting and strict numeric resolution. Initial live checks
passed six providers before a test-coordinate assumption was corrected for
Stetson; a subsequent run passed nine providers but SDSS timed out at its
60-second connection boundary after an earlier 529-value SDSS pass.
The concluding fresh VizieR run passed **11 tests** (nine calibration catalogs
plus two M3 identifier checks), with SDSS explicitly deselected after its
connection timeouts. It checked **2,688 native/transformed values across 294
mapped rows**. APASS Halpha/H_alpha and its colour/curriculum aliases,
Pan-STARRS narrowband aliases and each provider's mandatory transforms passed.
The earlier successful SDSS response supplied 23 rows and **529 matching
native/transformed values**; subsequent SDSS-only retries and a bounded HTTP
connectivity probe timed out. No failed live check was converted into a skip.
The first complete offline run passed 3,915 tests and failed the warning-code
vocabulary check. Registering the three new warning codes corrected that
integration omission; the focused code/catalog/schema/shape group then passed
**113 tests**. The concluding Python 3.13.15 offline run passed **3,916 tests, 85 skipped,
216 warnings in 367.31 seconds**. Compileall, schema goldens, generated-guidance
consistency, repository shape and whitespace checks pass. The added live tests
remain default-skipped; their separately executed outcomes are reported above.
After the full suite, the concluding fresh SDSS retry passed: **667 value
comparisons over 23 stars**, including every mandatory standard/prime transform
and the unchanged narrowband aliases. Across the concluding VizieR and SDSS
runs, all **ten calibration catalogs** passed **3,355 native/transformed value
checks over 317 mapped stars**, plus the two M3 identifier checks. The earlier
connection timeouts remain recorded above; none was hidden as a skipped test.
The catalog-magnitudes-and-filters checkpoint is closed. Coverage/sufficiency,
remaining warning/benchmark work and live ADS grouping validation stay open.


## Review of the committed checkpoint

A fresh review of `c8bd0de` identified a remaining source-name override mismatch:
selection under `Stetson` could discard a custom mapping keyed `StetsonGlobs`
that numeric resolution of returned rows accepted. Every entry point now merges
the registry-key map followed by the declared plugin/source-name map, within
each base/custom layer. This priority is independent of the input alias and
mapping insertion order, including when both maps define conflicting targets.

Warning and scale-label inference also needed actual provenance. A caller's
pre-resolved `ref_mag`, or a directly supplied native Halpha band, must not be
reported as an unperformed broadband transformation. The internal resolver now
records the used terminal band/expression and route kind, while the public
resolver retains its magnitude/error pair and every calculation. Internal
provenance follows the exact solver survivor mask: an outlier or zero-error
pre-filtered proxy cannot determine the scale of an otherwise native-reference
fit. Candidate rows remain in the public diagnostic result. Provenance stays
private and absent from serialized results and schemas. Photographic epochs
and Landolt colour expressions are recognized as continuum references when
used by explicit narrowband mappings.

`tests/test_catalog_filter_review.py` adds 18 cases covering source-name-only
selection through the real query runner, direct/provided references, actual
public photometry warnings/labels, custom targets, and rejected proxies in
both input orders and both rejection paths. A 586-test focused group passes.
Independent review repeated 14,663 production magnitude/error comparisons over
every nonempty APASS/Landolt/Stetson band subset with zero differences, and
confirmed no remaining actionable findings after the fixes. Source checks
again preserve all numerical transforms. The live catalog and M3 identifier
checks passed all 12 tests during this follow-up: 3,355 value comparisons over
317 stars in ten calibration catalogs, plus two M3 identifier checks. The
concluding Python 3.13.15 offline suite passed **3,934 tests, 85 skipped,
216 warnings in 525.64 seconds**. Compilation, generated-guidance consistency,
schema goldens, repository shape and whitespace checks pass. No actionable
review findings remain.
