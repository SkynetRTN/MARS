# M2 review fixes implementation plan

**Goal:** Resolve all six reproducible findings from the 2026-10-25 M2 review
on the existing `feature/m2` branch, starting at `62da5cc`.

**Spec:** the six findings in that review: unstable pulsar centering, rank-one
WCS acceptance, method-word attribution exemptions, detached bibcode context,
lost memory-limit classification and lost HR warnings after artifact failure.

**Approach:** Execute inline with a failing regression before each fix and one
fresh review after implementation. Keep public inputs, grids, conditional
Gaussian interpretation and catalog/H-alpha transforms unchanged. Use the
locked Python 3.13 environment. Do not edit source or tests while pytest runs.
Keep every M2 change on this branch; no merge, push, publication or vault writes.

## Tasks

- [x] **Stable pulsar centering:** extend
  `tests/test_pulsar_probability_precision.py` with one-ULP translation
  invariance and independently known 1-Hz power/tail, including public ECSV
  output in both modes. Centralize observed-value offset centering/scaling in
  `algorithms/pulsar/periodogram.py`, shared by powers and residual fitting.
  Run the precision and pulsar science suites; retain exact-constant rejection.
- [x] **Invertible WCS:** add nonzero rank-one CD/PC cases to
  `tests/test_wcs_accepted_positions.py` for both native boundary substitutes,
  assert rejection and unchanged headers. Validate the effective celestial
  matrix in `algorithms/wcs/wcs.py` before forward-footprint acceptance. Keep
  valid rotated/anisotropic solutions accepted.
- [x] **Scoped attribution disclaimers:** add asserted interpolation/training
  data and unrelated/negated disclosure cases to `tests/test_bench_attribution.py`.
  Replace substring exemptions in `tools/bench/graders/attribution.py` with
  explicit citation-scoped qualifications; retain genuine background controls.
- [x] **Bibcode association:** add wrong-paper author cases with honorifics,
  wrapped prose and Markdown rows, plus legitimate adjacent citations.
  Preserve sentence/row association across abbreviations and soft line breaks
  without borrowing identifiers across independent sentences/rows/paragraphs.
- [x] **Memory errors:** add real public-dispatch compute/plot failure
  regressions to `tests/test_numerical_warnings.py`; preserve `resource_limit`
  through `tools/photometry.py` while ordinary failures retain their warnings.
- [x] **HR artifact failure:** add a real-frame extraction followed by a
  substituted failed artifact write. Extend `tools/hr_diagram.py`'s failure
  boundary so the served error retains already-collected numerical warnings.
- [x] **Review, verify, commit:** run focused regressions, fresh independent
  review, the complete offline suite, compileall, schema/guidance and whitespace
  checks. Document before/after evidence and limits in `docs/analysis/`, update
  the M2 acceptance record and commit the fixes on `feature/m2`.

## Review focus

- Fractional, subnormal and large finite flux baselines with representable
  variation; power and saved residual tails must use the same centered data.
- Tiny valid WCS scales versus finite rank-one matrices in CD and PC forms.
- Negated or unrelated provenance wording versus an explicit disclaimer of
  the cited author; ordinary scientific method words remain assertions.
- Author initials/abbreviations and wrapped prose versus real table-row and
  paragraph boundaries, with multiple returned papers from the same year.
- Allocation and artifact-write failures preserve the intended error code;
  ordinary failures preserve numerical notices without claiming success.

## Progress

Baseline clean at `62da5cc`; prior full audit: 4,036 passed, 88 skipped.
Vault orientation/index fallback used because the retrieval index is absent;
the linked project notes predate M2 and the checked repository is authoritative.
Ruling: use this repository's `docs/working/` plan convention and the existing
feature branch, following the user's standing branch and execution instructions.

Observed red cases: eight centering inputs, four rank-one native-result paths,
seven false disclaimer exemptions and six detached associations. Focused
green checks: 69 pulsar cases, then 136 cross-domain cases, then 278 benchmark
cases. WCS tests were corrected to supply ATLAS's required hint and assert
actual acceptance/header behavior rather than an unrelated failure-list policy.
Ruling: old M2 Gaussian artifacts need an observed-offset centering marker before
plotting as calibrated; their saved false bounds cannot be corrected without
the light curve. The old-marker regression failed before the new metadata guard.
Memory and HR artifact red tests reproduced four failures; a separate metadata
allocation failure also reproduced the nested broad-handler omission.

All six original fixes passed 460 focused tests. The fresh reviewer found
three attribution regressions: absolute-value prose mistaken for a table,
combined/cell-local qualifications rejected, and negated findings excused.
Eleven failing cases reproduced them before correction. The single fix pass
uses structural rows (including actual GFM header dividers), cell-local
qualification scope, combined parenthetical qualifications and narrowly scoped
unverified citations. Independent review checked 210 numerical QR cases;
maximum discrepancies were 2.67e-15 in power and 1.12e-15 in residual fraction.

The first complete run passed 4,091 tests and exposed one obsolete preservation
expectation: `[0, 1e-300, 0]` was labelled degenerate solely because its unscaled
variance underflowed. Ruling: retain this resolvable signal, consistently with
safe normalization and the original tiny-baseline regressions. Replace that
case with the independently derived three-sample Nyquist power `4/3`, at unit,
tiny and large amplitude. Constants, invalid times, nonfinite values and
insufficient samples retain their rejection tests. No production change was
needed after this complete run.

The obsolete case was
`test_degenerate_periodograms_raise_a_declared_validation_error[times5-values5]`;
the replacement scale-contract and precision group passed 76 checks. Final
complete suite: **4,094 passed, 88 skipped, 220 warnings in 918.18 seconds**,
Python 3.13.15 with locked dependencies and MCP. The 58 net added cases cover
the six original findings, review follow-ups and positive controls. Compilation,
schema goldens, generated-skill consistency, repository shape and whitespace
checks pass. Existing live-service, untracked paid-transcript, native Windows
and external solver-data checks retain their skips. Catalog/H-alpha transforms,
calibration equations, benchmark keys and historical score data are unchanged.
All reported findings are corrected locally on `feature/m2`; other release
gates remain open. No merge, push, publication or vault update.
