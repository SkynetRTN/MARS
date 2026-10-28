# Warnings and benchmark claims

2026-10-23, final M2 checkpoint on `feature/m2`, based on `437513c`.

The checkpoint adds disclosures to retained numerical behavior and a bounded
author/year attribution check. Magnitude transforms, H-alpha, uncertainty
propagation, fitting equations and solver decisions remain unchanged.

## Numerical disclosures

Notices originate in the affected branch and are collected per operation using
`ContextVar`, with reset in `finally`. Public tools translate them to closed
warning codes; no process-global last-result state is used. They accompany
successes and handled failures in pixel/direct calibration, reference replay,
photometry, FITS-driven HR extraction and WCS solving. Public photometry also
keeps notices when computation or later artifact generation raises.
Its result includes a computed `ok`/`error` status, so returning structured
failure details preserves MCP's and the agent loop's error flag.

| Retained behavior | Condition and disclosure |
| --- | --- |
| PHOT-01: nonpositive aperture flux leaves a zero magnitude placeholder | `nonpositive_aperture_flux` when any measured flux is nonpositive; zero remains a placeholder, not a valid magnitude. |
| PHOT-02: an empty background annulus can leave a misleading finite measurement | `empty_background_annulus`; undefined background means remain NaN without dividing by zero. |
| PHOT-06: downsampled saturation counts are unreliable | `saturation_count_unreliable` when downsampling with a saturation image; ordinary extraction is unaffected. |
| PHOT-07: adaptive isophotal analysis has an origin mismatch | `isophotal_origin_approximation` only when the missing-shape fallback actually runs. |
| PHOT-12: growth-curve neighbour rejection is ineffective | `aperture_correction_crowding` when aperture correction runs; it does not claim the particular field is crowded. |
| PHOT-13: SNR selection uses inverse magnitude error | `magnitude_error_snr_cut` when those selection thresholds are enabled; they are not exact flux-SNR cuts. |
| PHOT-18: angular matching uses unwrapped flat-sky RA | `ra_seam_matching_approximation` for a detected/catalog RA span over 12 hours; close stars across the seam can remain unmatched. |
| Limiting magnitude extrapolates log SNR | `limiting_magnitude_unvalidated` when the estimate is considered. Insufficient or rank-deficient samples also report `limiting_magnitude_unidentifiable` and return no limit. Full-rank extrapolations remain unvalidated for detection completeness. |
| Landolt U uncertainty uses the wrong colour error | `retained_catalog_uncertainty` for a U-dependent reference; V and externally supplied reference magnitudes do not acquire that warning. |

Landolt's warning concerns the existing synthesized uncertainty, including
catalogs queried earlier or supplied as raw U-band rows; the tool cannot infer
that an external producer corrected it. Direct fits track the actual reference
route and disclose only routes retained by the solver mask. Existing
2MASS/APASS/SkyMapper approximation warnings and catalog coverage/sufficiency
warnings remain separate. No values are clipped or substituted.

This audit follows current public callers. Defects fixed in earlier M2/M3
checkpoints do not get warnings asserting they still occur. Retired helpers and
unconfirmed findings in dated reviews are not newly certified as numerical
defects. A warning is disclosure, not a correction or an accuracy guarantee;
native solver and live-service limitations from earlier checkpoints remain.

## Attribution grading and benchmark interpretation

`must_source_attribution` is an optional hard answer check with a required
`because`. It is enabled on `ned-formal-designation` and
`abstract-before-attribution`. Unsupported citations are diagnostic metrics on
other tasks. Only these two answer-key digests change.

The deterministic grammar covers `Surname et al. 2017`, its parenthesized-year
form, `Surname (2017)` and paired `Surname & Surname (2017)`/`and` forms,
including Markdown table rows. Authors must match the leading returned author
name(s) and year. Where a sentence or table row contains bibcodes, the nearest
explicit identifier must belong to the same returned record. Metadata comes
from successful/partial bibliography-tool preview records; query echoes,
abstract mentions, arbitrary local files and failed calls do not establish
authorship. A bibcode or a sourced number alone establishes no author name.

Explicit background labels are scoped to their clause. Unrelated preceding or
trailing disclaimers, a negated scientific result, and “not … alone” cannot
excuse an asserted author. Direct denials and clearly disclaimed citations are
not affirmative attribution claims.

This is bounded pattern matching, not full prose verification. Object nicknames,
catalog names, titles, citations outside the grammar and whether a paper
supports the surrounding scientific conclusion still require review. Matching
author metadata does not establish that an abstract was read; the existing
conditional/value checks continue to enforce their separate requirements.

Generated reports show how many scored answers enabled the hard check and how
many unsupported claims were flagged. A perfect correctness score means all
enabled hard checks passed. It does not mean every fact was verified.

The September report, JSON and figures retain their historical scores and corpus
identities. The original 144 paid transcripts are absent from this checkout,
so no historical regrade or revised model ranking is claimed. Prominent caveats
mark those scores **attribution-unchecked**. Regrading requires all original
backends' events and answers together; synthetic regression answers demonstrate
the new rule, not a changed historical pass rate.

## Review and validation

Independent code review found three issues: unrelated trailing disclosures could
hide author claims, focus negation could hide “not … alone” citations, and
photometry exceptions could discard prior notices. Each was reproduced by a
failing regression and corrected. Key-digest integration tests also caught an
unintended empty-default change to unaffected tasks; only the two intended keys
now change. Public input signatures and numerical transforms remain unchanged.

A final boundary check reproduced an MCP error flag lost when the exception
became a structured photometry result. Three failing status regressions led to
the computed status field; success remains `ok`, and compute/plot failures
remain errors while carrying their prior warnings.

Final complete offline suite: **4,036 passed, 88 skipped, 218 warnings in
508.64 seconds**, Python 3.13.15 with locked dependencies and MCP. The 57 added
cases cover numerical warnings, attribution, corpus/report integration and task
validation. Compilation, schema goldens, generated guidance, repository shape
and whitespace checks pass. A full-run registry-classification omission was
corrected by declaring the shared warning helper as infrastructure. Live-service,
untracked paid-transcript, native Windows and external solver-data gates retain
their skips. No new paid model sweep or historical regrade was performed.

All ten M2 checkboxes are complete locally on `feature/m2`; these changes are
unmerged and unpublished. Other release gates remain open. The
[archived implementation plan](../archive/warnings-benchmark-claims.md) records the work.

## 2026-10-26 comprehensive-review corrections

The follow-up audit found the remaining method-word exemption and abbreviation/
line-wrap association gaps in author grading. Citation qualifications are now
explicitly anchored, and identifier context survives scholarly abbreviations and
wrapped prose while keeping independent blocks/table rows separate. It also
found MemoryError masked by photometry's broad catch and HR warnings lost on
artifact failure. Allocation errors retain `resource_limit`; ordinary HR write
errors retain their extraction notices. See the
[master plan's review corrections](../working/master-continuation-plan.md#m2-review-corrections).

The adversarial follow-up collects catalog notices at the outer photometry
boundary and preserves completed reference/sample disclosures before artifact
I/O. Directory and plotting failures retain those notices. WCS allocation
failures propagate through inner and public handlers to `resource_limit`.
Ordinary parenthesized temporal labels are excluded from single-author grading;
explicit author contexts and paired/et-al forms remain checked. The grammar
remains bounded and cannot disambiguate every author name from ordinary prose.
