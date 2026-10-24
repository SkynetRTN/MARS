# Warnings and benchmark claims implementation plan

**Goal:** Complete the final M2 checkpoint on the single `feature/m2` branch.
Keep numerical transforms, H-alpha, error propagation and fitting arithmetic
unchanged. Make retained limits visible and stop treating sourced numbers as
proof of author attribution.

**Design:** Use operation-scoped numerical notices, following the query-notice
pattern, with explicit conversion to tool warning codes. Emit notices at the
affected algorithm branch, and collect them at public result boundaries,
including structured failure returns. Keep this separate from query coverage.
Audit the existing findings against current public paths; retired/unreachable
helpers and previously fixed defects do not get blanket warnings.

Numerical disclosure targets: PHOT-01 nonpositive aperture flux placeholders;
PHOT-02 empty background annuli; PHOT-06 downsampled saturation counts;
PHOT-07 adaptive isophotal coordinate origin; PHOT-12 aperture-correction
crowding; PHOT-13 magnitude-error SNR cuts; PHOT-18 angular matching across the
RA seam; unvalidated limiting-magnitude extrapolation (including near-flat
SNR fits); and Landolt's retained U-error colour-index defect. Existing
2MASS/APASS/SkyMapper approximation warnings remain, without clipping values.

For benchmarks, add a deterministic, evidence-aware author/year attribution
check. Bibliographic identifiers alone do not establish author names. Author
metadata must come from returned bibliography records and match the cited
year and explicit bibcode association. Treat explicit background/disclaimed
claims separately. Cover normal prose and Markdown citation/table forms;
document the supported grammar and its limits. Record attribution-check
coverage in generated reports. A passing set of enabled checks is not a
claim that every fact in the prose has been verified.

Keep the historical report's numerical scores and corpus provenance intact.
Label them attribution-unchecked; no new model run or invented regrade. Update
the two relevant core task keys and their lock digests for future grading.

**Approach choices:** Correcting every retained kernel would change the
preservation contract and exceeds this warning gate. A model judge would add
an external, nondeterministic dependency and contradict the existing harness.
Use conditional disclosures and a bounded deterministic check, with explicit
reporting limits. Implementation stays inline; request one fresh code review.

**Review focus:** notices emitted before an exception; positive controls with
no affected algorithm path; invented authors paired with sourced values;
author metadata belonging to a different paper; nearby unrelated background
labels; historical reports with no attribution metrics; fixture/key digests.

## Tasks

- [x] Numerical disclosures: write failing branch and public-boundary tests,
  add notices and propagate them through photometry, calibration, replay and
  FITS-driven HR tools. Verify arithmetic and public input schemas stay stable.
- [x] Attribution grading: write adversarial failures and positive controls,
  implement metadata-grounded author/year checks, validate the task language,
  update relevant keys, and label report coverage and historical limits.
- [x] Review and validation: run focused M2/M3/grader checks, independent code
  review, complete offline suite, compilation, generated guidance, schema and
  whitespace checks; record evidence and commit on `feature/m2`.

## Progress

Baseline `437513c`: clean `feature/m2`; latest full suite 3,979 passed,
88 skipped. Narrow vault lookup used linked notes/text fallback because the
retrieval index is absent. Benchmark notes confirm the known author-attribution
hole; verified repository state supersedes older notes about corrected algorithms.

The numerical paths retain their values while emitting conditional notices.
Focused checks passed **287 tests**, including actual frame photometry and HR
extraction, direct/degenerate fits, explicit route controls, and failure returns.
Independent review's three findings were reproduced and fixed: trailing unrelated
disclosures, focus negation and warnings lost after photometry exceptions.
The key-lock correction preserves all unaffected task digests. A final MCP
boundary check exposed a lost error flag on structured photometry failures;
three failing status regressions pass with the computed status field. The
complete suite then passed 4,035 tests and found one registry-classification
omission: the new shared warning helper must be listed as infrastructure.
That classification is corrected; its three checks pass. Final validation:
**4,036 passed, 88 skipped, 218 warnings in 508.64 seconds**, Python 3.13.15
with locked dependencies and MCP. The skips retain live-service, missing paid
transcript, native Windows and external solver-data gates. The warnings include
retained FITS/kernel warnings; none is a new suite failure. Compilation,
generated guidance, schema goldens, repository shape and whitespace checks pass.
The checkpoint and all ten M2 checkboxes are complete locally on `feature/m2`;
other release gates remain open. No model sweep, publication or vault update.
