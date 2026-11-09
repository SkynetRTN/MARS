# M5 current-main integration and whole-branch review

The original review below is a dated snapshot of `afff753` against main
`193d117`. Its blockers are followed by the integration corrections and new
validation evidence; old review verdicts are not current status claims.

**Current result:** all reported integration blockers are resolved. Independent
review is clear; the real merged checkout passes 5,174 tests with 100 skips.
Main `193d117` was refreshed again after validation and has not advanced.

## Original review (before integration corrections)

Reviewed feature head `afff75392d2e91f8f9571b96844b8989f39b095b` against
M5's original base `fb097749cb78574df723bf651c5199c11eae8c2e` and freshly
fetched main `193d117`. The feature branch is 12 commits ahead and 40 behind
main. The M5 delta changes 103 files, including 31 production Python files.
No feature-branch files or commits were changed by this review.

### Verdict

**Not ready to merge as-is.** Independent reviews found no actionable new
numerical implementation defect in M5's documented correction scope, but
integration with current main is incomplete. Three documentation files
conflict and combined-source plotting tests fail.

### Required integration corrections

1. **Resolve current-main documentation conflicts.** A non-destructive
   `git merge-tree --write-tree origin/main HEAD` exits 1 for `CLAUDE.md`,
   `docs/working/README.md` and `docs/working/master-continuation-plan.md`.
   Preserve M4's catalog-folder/native/release evidence and added questions
   while retaining M5 correction/disposition evidence. In particular, M4's
   unquantified track-resampling impact is a fitting-policy question, not
   answered merely by the old M5 plot-polyline controls.
2. **Update the WCS configuration test seam for M4's signature.**
   `tests/test_m5_fits_write_investigation.py:275` replaces
   `_configured_backend_warnings` with a one-argument lambda. M4 now calls it
   with settings and catalog-directory diagnostics. The combined public-write
   test raises TypeError before reaching its solver/write assertion. Match
   the current configuration seam while retaining real staged FITS validation.
3. **Update two M5 HR plot controls for M4's intentional scatter renderer.**
   `tests/test_m5_hr_boundary_investigation.py:137` and `:238` index
   `ax.lines[0]`. Main's `plot_cmd` now draws model points using scatter, so
   both tests raise IndexError on the automatic merge output. Preserve the
   independent no-lost-model-point/NaN contracts through actual scatter
   offsets; reverting M4's renderer would reintroduce its misleading joined
   evolutionary tracks.
4. **Replace M4's stale missing-error fixture expectation.**
   Main's `tests/test_plot_content.py:182` assumes 29 kept stars and six
   unfitted zero-error stars on NGC 5128. M5 intentionally repairs that noise
   path; the combined measured-pixel run has 33 kept and one rejected outlier.
   Use a controlled missing-error case to preserve M4's distinction between
   unfitted inputs and true rejected outliers, and check actual fit masks in
   the real-frame integration instead of restoring the old uncertainty bug.

The three plotting failures were reproduced together: 57 passed, 3 failed.
The WCS seam failure was also repeated individually. None requires restoring
the old measurement or rendering behavior.

### Fidelity and retained scope

The six M5 squares are implemented as documented fixes and explicit retained
dispositions. Reviews covered geometry, catalog binary fields/motion, source
caps, time/header replacement, flux/variance/masks, matching/SNR, exact ellipse
overlap, repeated input ownership, full-cycle pulsar folding and artifact
handoffs, cache and expression parsing, labels, errors, IDs and instructions.
Recorded historical science outputs remain evidence rather than forced targets
for intentionally corrected results. No new dependencies/workflows/data were
introduced by M5.

Documented UCAC4, explicit legacy parity, format/display, Landolt U-error,
null-wire/pruning/APASS identity and error-systematics limits still apply.
One additional preexisting extraction limit was confirmed: with centroid
refinement disabled, downsampling omits `(d-1)/2` block-center offsets. A
Gaussian at FITS pixel 41 measures approximately 41, 40.5 and 40 for d=1/2/3.
The scaling lines are unchanged by M5; default public settings use d=1 and
centroid refinement. This is not an introduced M5 regression or a reason to
undo its saturation-count correction.

### Verification

- WCS/geometry independent review: 235 focused passes/4 native skips; 800
  related passes/4 configuration skips; 56 native-enabled controls. Native
  UCAC5 fields match independently decoded bytes for 356 rows. A 1,600-case
  independent Cartesian motion oracle differs by at most ~1.6e-6 arcsec.
- Photometry/fieldcal independent review: 217 focused passes. Independent
  100-case ellipse comparison to SEP has relative flux/error discrepancy
  below 1.8e-8.
- Catalog/pulsar independent review: 362 focused passes. No actionable new
  findings in the scoped implementation or its retained limits.
- Parent's automatic-merge snapshot: 56 native-enabled solver controls pass;
  compilation and generated-guidance consistency pass.
- Parent's actual-checkout branding/shape checks: 5 pass. The snapshot's full
  integration excludes `test_rebrand_guard.py`, which needs checkout metadata;
  its code is unchanged by either side.
- Full automatic-merge snapshot integration: **5,164 passed, 100 skipped,
  four failed**, 230 warnings, in 741.04 seconds. All four failures are the
  integration cases above. Source is the exact
  `c507b60a6cfef0720ffdc7cbee13613dd2c5e2d7` merge-tree output in a disposable
  archive, including unresolved documentation markers. This is not a resolved
  merge commit, and no branch/worktree was checked out or created. After the
  run, all 475 present source/test/guidance/CI metadata files matched their
  merge-tree blob hashes. Compilation and generated-guidance checks pass.

Reproduce the automatic merge and its test run without modifying the feature
branch by archiving the merge-tree object to a temporary directory. The parent
run used:

```bash
/home/codex/mars/.venv/bin/python -m pytest -q \
  --ignore=tests/test_rebrand_guard.py \
  --junitxml=/tmp/m5-merge-review-full.xml
```

The checkout-only branding file passed separately on the actual feature
checkout (five tests). The combined-source failures are real integration
failures; the archive's lack of Git metadata is not their cause.

Counts above are per invocation, not a total of distinct tests. The prior
feature-head full run passed 4,974 tests/94 skips; that alone cannot validate
integration with main's subsequent M4 commits. This review does not merge,
rebase, resolve conflicts, or silently fix the findings.


## Integration corrections (2026-11-09)

Current main `193d117` is integrated into `feature/m5-geometry`. No worktrees
or rebases are used. The three conflict
resolutions retain M4's catalog-folder/native/publication evidence and M5's
fixes/dispositions. M4's unmeasured HR fitting-gap effect remains explicit as
a release question; changing the renderer does not resolve that question.

The WCS test seam accepts the current settings/diagnostics arguments while
keeping the real staged FITS writer. HR tests inspect actual scatter offsets:
both coordinates of a gap are masked and all 337 finite model vertices remain.
The real-frame zero-point plot is checked against the independent numerical fit
oracle and actual measured calibration rows, including positive uncertainties,
kept/rejected markers and residuals. A deterministic plot control covers both
None and zero instrumental errors, distinguishing an unfitted star from a real
outlier. No replacement hard-coded 33/1 result is required.

All four prior failures reproduced on this real checkout before correction
(4 failed in 4.14 seconds). Focused corrected checks: 62 passed in 9.04 seconds.
A trailing blank line inherited from main's catalog-directory test was removed
for staged whitespace validation. Algorithms/tools remain byte-identical to
the reviewed automatic-merge output; no formula or renderer was changed.

Independent integration review is clear: 99 tests passed in 9.60 seconds across
the three affected test files. Broader checks pass 192 cases with four expected
result-status skips (11.38 seconds); native-enabled controls pass 56 with two
synthetic-header FITS notices (2.80 seconds). Compilation, generated guidance,
touched Markdown links and whitespace checks pass.

Final locked validation on the resolved real checkout (Python 3.13.15):

```bash
uv run --locked --extra mcp pytest -q --junitxml=/tmp/m5-main-integration-full.xml
```

**5,174 passed, 100 skipped, 230 FITS notices**, no failures or errors, in
454.22 seconds. All 475 snapshotted source/test/guidance/CI metadata files
remained unchanged through the run. The checkout-specific branding checks are
included this time. Algorithms/tools remain identical to the reviewed
automatic merge; all manual integration changes are tests, documentation and
the one trailing-blank-line cleanup. No numerical or renderer behavior was
changed to accommodate old expectations.

The reported blockers against main `193d117` are cleared. Required PR/platform
CI and M6 release evidence remain separate; the unmeasured HR fitting-gap
question is preserved rather than declared repaired.
