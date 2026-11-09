# M5: catalog parsing, caches and identity

Investigated 2026-11-08 against `a1b57fa` on `feature/m5-geometry`, after
[reviewing the four completed M5 squares](m5-completed-work-review-2026-11-08.md).
The [master plan](../working/master-continuation-plan.md#m5-resolve-the-specific-older-reports-that-remain-unverified)
defines the questions; the [investigation plan](../superpowers/plans/2026-11-08-m5-review-and-catalog-investigation.md)
records the original investigation. The dated repair section below supersedes
its defect descriptions. Original confirmed bug pins now require corrected
behavior; retained policy and conditional controls keep their explicit scope.

The vault's September catalog note predates M2/M3/M5. Retrieval used its
index/text fallback because BM25/chunks are unconfigured. Current repository
code, installed SDK behavior and executed probes are authoritative.

## Repair and closure (2026-11-08–09)

The [repair plan](../superpowers/plans/2026-11-08-m5-catalog-fixes.md) corrects
all seven confirmed findings and the masked-optional-ID handoff:

- Cached rectangular queries grow height for latitude displacement and invert
  their spherical longitude extent at the snapped latitude, including RA
  center displacement. Pole/full-RA and widths at least 180 degrees use full
  longitude. Both backends preserve independently specified original bounds;
  default square height, unequal dimensions, both poles and the RA seam are
  covered. Cone enclosure and row/work caps remain intact. A provider cap may
  still truncate the expanded region; no claim of live provider completeness
  follows from these offline bounds.
- The shared SDK patch tolerates filesystem `OSError` during default-directory
  discovery and creation, as well as its existing read/write/eviction hooks.
  A discovery failure returns the platform null-device path as a non-directory
  cache sentinel; protected hooks miss without relocating the cache. A later
  call retries discovery and normal cache hits resume. The original HTTP
  request is never replayed; provider/network/cancellation and requested
  file-save errors still surface.
- SDSS tolerates direct eviction failure. Successful eviction keeps caching
  enabled on its single HTML-recovery retry and repairs the entry; an
  undeletable entry makes only that retry uncached. Persistent HTML and
  parser/service/network failures remain distinct and bounded.
- SIMBAD maps `*`/`G` to Star/Galaxy, decodes byte codes, trims padding and
  preserves unknown raw codes. Missing/masked types and the deliberately empty
  `Possible_As*` label remain empty without discarding valid coordinates.
- A shared AST walk derives request and response dependencies. Calls and
  attribute names are excluded, literal columns named like builtins/NumPy/
  string methods stay usable and guarded, and lambda/comprehension locals do
  not become provider columns. NumPy expression constants retain their existing
  global meaning. Null-byte declarations now raise contextual validation errors.
- Landolt retains computed zero errors when every operand of the actual
  retained formula has a recorded finite error. Missing uncertainties remain
  distinct from zero. Magnitudes, positive partial-error quadrature and the
  separately disclosed wrong-colour U-error formula are unchanged.
- Masked optional identifiers stay unset before calibration normalization;
  integer zero remains valid. No persistent APASS identity is fabricated.

Review reproduced two further gaps before validation: lambda/comprehension
scope and Astropy's default-directory discovery permission failure. Both gained
failing regression controls before correction. A deterministic enclosure probe
also found the decreasing-asin width branch above 180 degrees; its new public
backend controls now require enclosure. **20,000** seeded independent rectangle
probes pass across centers, widths and heights.

The original 105 cases are converted where needed, with 90 additional offline
regressions in the four repair files. Cache tests use real SDK request/cache
paths, expression tests execute real mappings, and uncertainty tests reach
numeric reference resolution. No new live service traffic or catalog fixtures
are required. Independent follow-up review has no remaining findings; all
195 catalog cases pass. Related focused integration passes 890 tests with one
expected network skip and six FITS notices (5.56 seconds).

The fifth square is **closed on 2026-11-09**. The final locked Python 3.13.15
suite passes **4,964 tests, 94 skips, 214 FITS notices**, no failures, in
407.55 seconds:

```bash
uv run --locked pytest -q --junitxml=/tmp/m5-catalog-fixes-full-results.xml
```

All 453 snapshotted code/test/guidance files remained unchanged through that
run. Compilation, generated-guidance consistency and whitespace checks pass.
No new live provider or Windows execution was performed. M5 now has five of
six squares complete; obsolete reports/instructions remain separate.

Retained dispositions: CAT-25 wire-null policy, CAT-26 prune frequency and
distinct SDK freshness/file-retention policies, CAT-32 ordinal/exact-row identity
limits, and the unverified UCAC4 native product. This deployment uses UCAC5.

## Original investigation (before repair)

The remainder is the dated pre-repair evidence, including its then-current
open status and validation counts. Source line numbers refer to that baseline.

## Findings and dispositions

| Report | Current result | Reachability/disposition |
|---|---|---|
| CAT-17: cache rounding omits edge stars | Exact-grid rectangular dimensions do not grow when the center snaps. A witness 0.06 arcsec inside an original two-arcminute box becomes 4.62 arcsec outside its cached north edge. | Confirmed P2 in maintained Python box queries for APASS and SDSS. M2's WCS/image cone path is corrected and remains protected. |
| M5-CACHE-01: cache directory creation fails before suppression | The installed SDK calls `cache_location.mkdir` before the patched read hook. A permission failure prevents any provider request; explicit uncached mode succeeds. | Confirmed P2 cache-resilience gap, distinct from invalid configuration. |
| M5-CACHE-02: direct SDSS cache eviction can abort recovery | SDSS error-page recovery unlinks the request file directly, outside the patched SDK eviction method. An unlink permission failure prevents the intended refetch. | Confirmed P2 on the maintained SDSS recovery path; the ordinary protected SDK eviction control does not cover this helper. |
| CAT-21: SIMBAD loses common object types | Public resolution maps machine `*`, `G` and unknown codes to an empty type label while retaining the name and coordinates. | Confirmed P2 metadata loss. Coordinate consumers still work; dictionary/return-model fallback documentation disagrees. |
| CAT-24: expressions request nonexistent columns | Landolt/Stetson call targets `int`/`float` enter `_columns` twice each; the installed SDK emits each once in `-out`. Real offline VOTables still map coordinates/magnitudes correctly. | Confirmed P3 request defect. No live provider rejection or resulting magnitude error was established. |
| M5-PARSE-01: derived zero uncertainties become absent | Landolt raw errors explicitly equal to zero survive mapping, but computed U/B/R/I errors of zero become `None` under `if err`. | Confirmed P3 in maintained Landolt synthesis. Separate from the already disclosed wrong-colour U-error formula. |
| M5-PARSE-02: literal builtin-named coordinate dependency is ignored | Custom columns literally named `int`/`float` work when present, but a missing one bypasses the response-schema guard and maps to `[]`; ordinary missing `RAhours` raises. | Confirmed conditional P3 custom-catalog schema gap. Not a claim that shipped providers rename coordinates to these names. |
| CAT-23: zero magnitudes/errors disappear | Finite zero magnitudes, raw errors, colours and positions survive the sampled real mappers; unrelated usable bands survive missing/invalid columns. | Original base-mapper claim already corrected by M2/M3. The narrower Landolt synthesized-error case above remains. |
| CAT-28: padded/composed filter spellings fail | Shared tokens compose whitespace, typographic quotes and underscores across selection, numerical resolution and tool reporting; Johnson `V` and SkyMapper `v` stay distinct. | Already corrected by M2. Do not restore single-letter case folding as a supposed repair. |
| CAT-25: invalid values look absent on the wire | None/NaN/infinity serialize to null while finite errors remain; invalid values are equally unusable before and after round-trip, and a valid public solution is unchanged. | Retained documented wire policy. No new measurement/eligibility defect established. |
| CAT-26: pruning scans on writes | Every global SDK cache write scans VizieR's directory, including an SDSS write; cache hits do not scan. SDK hit freshness and file-pruning retention differ. | Confirmed policy/work observation, not demonstrated unacceptable latency or missing freshness expiry. |
| CAT-32: APASS record numbers imply unstable identity | Optional ordinal IDs affect exact-row dedup; absent/integer-zero IDs work. Current APASS metadata has no `recno`, and no live re-ingestion was observed. | Conditional identity caveat. No persistent astrophysical identifier or current live DR9 re-ingestion failure is established. |
| UCAC4 native layout | The configured operator tree contains UCAC5; the maintainer confirms this deployment uses UCAC5, not UCAC4. | UCAC4 remains an unverified legacy path, not a deployment blocker. No reader defect is asserted from synthetic records or a different catalog format. |

## Cache geometry and default behavior

`QuerySettings` defaults `VIZIER_CACHE_ENABLED` to true. The false class
attribute on `VizierCatalog` is overwritten by its constructor unless a caller
explicitly supplies `cache=False`. The environment flag is unset here; all
eleven bound registry instances have caching enabled. Disable it before
initialization or construct an uncached backend to opt out.

`vizier.py:433` and `sdss.py:411` pass rectangular requests through
`_round_for_cache` at `vizier.py:528`. Center coordinates snap to ten arcseconds
and dimensions round up to 0.2 arcmin, but center displacement is not added.
For Dec 20.0013 degrees and height 2 arcmin, the snapped center is 20 degrees
and height remains 2 arcmin. The independently placed north-edge witness is
lost. Public `query_catalogs` captures demonstrate both backend paths, with
uncached controls, both declination signs, poles and the RA seam.

This is not a regression in M2's WCS-footprint correction. Both WCS/image
runner paths use enclosing circular queries plus clipping. `_round_cone_for_cache`
adds spherical center displacement before rounding radius outward. Eight
cached-cone controls retain all 36 independently constructed edge witnesses
per control, including seam/polar centers. Raw `tools.vizier.search_vizier`
does not use catalog-region rounding.

## Cache failures, cleanup and freshness

The installed environment uses astroquery 0.4.11 and Astropy 8.0.1.
`BaseQuery._request` resolves the MARS replacements for `AstroQuery` and
`to_cache` dynamically, so they are active hooks rather than stale bindings.
Real SDK request/cache paths, with only HTTP/filesystem seams replaced, prove
that read permission errors, corrupt pickles, write disk-full errors and
pruning listing/stat/unlink faults are nonfatal. The patched SDK
`remove_cache_file` also suppresses eviction failure; that test leaves a valid
cached response in place and does not claim an undeletable error entry heals.

Two ordinary cache-I/O paths remain outside those protections:

- Cache-location creation occurs before the patched read hook. Injected
  `PermissionError` prevents a provider attempt; `cache=False` succeeds through
  the same real SDK request/parser path.
- `sdss.py:207` unlinks directly in `_evict_last_query`; its caller at line 169
  intends to evict the bad entry and retry with caching still enabled. When
  eviction succeeds the missing entry causes a provider refetch. An unlink
  permission failure prevents that retry. The normal bad-HTML-to-valid-response
  recovery control succeeds with two provider requests and repairs the cache;
  explicit `cache=False` remains a separate working control.

The pruning hook at `cache.py:118` is global. Four seeded live VizieR entries,
two VizieR writes and one SDSS write cause scans of 4, 5 and 6 entries: 15
stat calls, all under VizieR. A subsequent hit adds no scan. This bounds the
observed work frequency without inventing a latency failure.

SDK cache hits expire after the installed 604800-second/seven-day timeout;
expired reads refetch without removing files. MARS file cleanup defaults to
30 days. These are different policies. NaN/infinite configured retention raises
outside write suppression, but that is unsafe configuration, not evidence that
ordinary read/write errors escape the protected hooks.

## Parsing, schema dependencies and zero values

Landolt/Stetson `_derive_columns` reads Python `co_names` without distinguishing
call targets from data columns. Each coordinate expression contributes `int`
and `float`; the SDK deduplicates them but still sends both invalid names.
Transport-seam controls capture the real request payload and return real
VOTables. Literal 06 30 00 / -00 30 00 coordinates map to 6.5 hours / -0.5
degrees, and UBVRI values follow independent colour algebra. This verifies
mapping, not a claim about a live server's response to unknown columns.

The response checker has the opposite problem for a custom literal column:
`_expression_columns` at `vizier.py:489` excludes builtin names indiscriminately.
When a declared position column named `int` or `float` is missing, the response
becomes an empty source list instead of M3's `ProviderResponseError`. Present
literal builtin columns and ordinary missing-coordinate columns are controls.
A future correction must distinguish call targets from genuine column names.

Zero-value controls exercise bound Landolt, Stetson, APASS, 2MASS and PanSTARRS
mappers, Landolt zero colours and USNO epoch values. The base mapper retains
finite zeros. Missing/masked/nonfinite/sentinel magnitudes remain unusable,
while unrelated usable bands and finite magnitudes without errors survive.
Landolt's four `if err` assignments at lines 86/92/98/108 still erase a known
computed zero error. Preserving known zero uncertainty must not turn missing
input errors into an assertion of exact precision.

## Object types, null serialization and identity

SIMBAD `otype` is a machine code distinct from the human label. The official
[astroquery evolution documentation](https://docs.astropy.org/projects/astroquery/en/stable/simbad/simbad_evolution.html#object-types)
shows this distinction and its current hierarchy. `query/simbad.py:230` instead
looks up the machine code in a retained long-label vocabulary and defaults to
an empty string. Actual `resolve_target` controls return status ok/count1 and
correct zero coordinates but lose `*`/`G` labels. Long `Star`/`Galaxy` controls
still produce prose. Unknown codes are erased too: the vocabulary module
promises a raw fallback while `ResolvedTarget` documents the empty policy.
CASDA uses the resolved coordinates, so label loss is not an astrometric error.

The source schema's null conversion does not mutate the model. None, NaN and
both infinities lose their distinction on serialization while a finite error
can remain beside a null magnitude. Numerical resolution excludes each equally;
the public measurement-based zero-point tool rejects unusable references.
A finite three-star solution remains bit-identical through JSON round-trip.
Magnitude/error zero remains valid. This establishes current eligibility and
wire behavior, not a universal assertion that null carries a cause of invalidity.

APASS requests optional `recno`, but the current
[DR9 provider metadata](https://vizier.cfa.harvard.edu/viz-bin/VizieR-3?-source=II/336)
lists no such native column. VizieR describes its generated record counter as
unsuitable for identification in its
[catalog metadata](https://vizier.cds.unistra.fr/cgi-bin/VizieR-3?-source=I%2F285).
These facts do not prove a live APASS ID change or supply a substitute stable ID.
Absent IDs and numeric 0/42 reach field-calibration normalization correctly.

The real multi-image runner deduplicates only equal `(id,ra_hours,dec_degs)`
triples within each catalog. Unchanged or absent identities collapse; a changed
ordinal or absent-to-present ID leaves two rows; equal IDs at different positions
stay distinct. The standalone helper is catalog-blind, but the current runner
deduplicates separately per catalog. A conditional masked-integer `recno` probe
instead reaches a normalization `ValidationError`; current APASS provider
reachability is unverified. Do not turn this fixture into a claim of a live DR9
failure or fabricate persistent identities from field numbers/coordinates.

## UCAC layout evidence gate

Read-only inventory of `/srv/agents/catalogs/ATLAS` found only the UCAC5 tree;
the catalog inventory found no UCAC4 zone. The current UCAC4 reader expects
`Z000.UC4` through `Z179.UC4`, 80-byte records with its declared fields. Existing
synthetic logical-record tests establish interval arithmetic, not that product's
binary provenance. UCAC5's installed `u5z` product and independently packed
52-byte controls were already checked in the first M5 square.

[IRSA's UCAC4 field definitions](https://irsa.ipac.caltech.edu/data/USNO/UCAC4/ucac4.html)
describe RA and south-pole-distance fields, but do not establish the intended
layout of the reader's possibly converted product. The linked README for binary
files could not be decoded by the browser. An actual UCAC4 zone and matching product
specification are still required before claiming or repairing a native-layout
defect. The maintainer confirmed on 2026-11-08 that this deployment uses UCAC5,
not UCAC4. The unverified UCAC4 path is therefore a legacy limitation rather
than a blocker for this deployment or the independent catalog findings above.

## Validation and next work

Three new test files exercise real mappings, SDK request/cache code, public
resolution/calibration and multi-image dedup, replacing only service/filesystem
seams. Test names/comments distinguish BUGPINs from working controls and
conditional inputs. No production catalog source, real cache contents or
downloaded catalog fixtures were changed.

The new group passes **105 cases** (41 parsing, 35 cache, 29 identity),
0.85 seconds. Parsing plus its related routing/provider/selection files pass
307 tests; the cache/pruning selection passes 61 tests with 268 deselected.
Those are invocation counts, not an aggregate of distinct cases.

Independent review repeated all 105 cases and found no test-oracle defects.
It independently reproduced the direct SDSS eviction gap, which gained its
own bug pin and working recovery control. Report wording was narrowed to the
actual protected SDK hooks and cache-enabled refetch; a coordinate transcription
was corrected to match the literal 06 30 00 / 6.5-hour fixture.

Final locked integration on Python 3.13.15:

```bash
uv run --locked pytest -q --junitxml=/tmp/m5-catalog-investigation-full-results.xml
```

**4,874 passed, 94 skipped, 214 FITS normalization notices**, no failures,
in 426.28 seconds. All 438 snapshotted algorithm/tool/test/guidance files
remained unchanged through the run; production algorithm/tool files have no
diff from `a1b57fa`. Compilation, generated-guidance consistency and whitespace
checks pass. The existing external/asset/platform skip gates remain; no live
astronomy queries were run by these new tests.

Repair priorities are cached rectangular coverage, cache directory and direct
SDSS eviction fallback, SIMBAD type preservation, and the confirmed parsing
gaps. Convert their bug pins to independent correctness regressions during
remediation. Keep wire-null policy, ordinal identity limits, pruning policy and
UCAC4's unverified product contract explicit. Passing the investigation does
not close this fifth square; the obsolete-reports square also remains open.
