# M5 current-main integration plan

**Goal:** Remove the merge blockers found between M5 `afff753` and main
`193d117`, preserving both sets of intended behavior.

**Scope:** The three documentation conflicts and four failing integration
tests reproduced by the whole-branch review. No scientific formula, renderer,
dependency or recorded fixture is changed to satisfy an obsolete expectation.

## Constraints

- Use `feature/m5-geometry`; merge current main into it without rebasing,
  worktrees, force pushes or merging the feature into main.
- Preserve M4 catalog-folder/native/release evidence and its unquantified HR
  fitting-gap question alongside M5 corrections and retained limitations.
- Keep the actual staged FITS writer in its public regression; update only
  the obsolete configuration stub signature.
- Verify actual scatter offsets, including masked gap rows and all 337 model
  points, rather than reintroduce connected tracks.
- Test unfitted versus rejected stars with controlled inputs. For real-frame
  plots compare actual rows/masks and positive measured uncertainties; do not
  replace old hard-coded counts with new unexplained hard-coded counts.

## Work

- [x] Merge `origin/main` without committing; resolve the three docs conflicts
  while retaining both current evidence sets and remaining release questions.
- [x] Reproduce the four failed tests on the real feature checkout.
- [x] Correct the WCS seam and both HR plot assertions; run their focused tests.
- [x] Replace stale real-frame plot expectations with meaningful fit/measurement
  assertions and add a deterministic missing-error/outlier control.
- [x] Review the combined integration changes independently; address findings.
- [x] Freeze source/tests/guidance and run the full locked MCP suite, native
  controls, compilation, generated guidance, links and whitespace checks.

Delivery after validation: record the integration result, finish the merge
commit, push this feature branch and attempt the authorized shared-vault Save
checkpoint.

**Review evidence:** Whole-branch review at `afff753`: 5,164 passing, 100
skipped, four failing automatic-merge tests; three docs conflicts. Three
independent numerical reviews found no new scoped implementation defect.
The [durable review record](../../analysis/m5-main-integration-review.md) now
preserves that original verdict and subsequent corrections.

## Verification ledger

- RED: all four reviewed tests fail on the merged real checkout (4.14 seconds).
- GREEN: WCS write/HR/plot group passes 62 tests (9.04 seconds), including the
  additional missing-error control. No numerical or rendering changes.
- Production algorithms/tools match the prior automatic-merge tree byte for
  byte; main's trailing test-file EOF blank line is the only whitespace cleanup.
- Broader integration: 192 passed, 4 expected result-status skips (11.38s).
  Independent review: 99 passed (9.60s), no actionable findings. Native-enabled
  controls: 56 passed, 2 synthetic-header FITS notices (2.80s). Compilation,
  generated guidance, touched Markdown links and whitespace checks pass.
- Full locked MCP suite on the resolved real checkout: 5,174 passed, 100
  skipped, 230 FITS notices, no failures/errors (454.22s, Python 3.13.15).
  All 475 frozen files unchanged. Main refreshed afterward remains `193d117`.
