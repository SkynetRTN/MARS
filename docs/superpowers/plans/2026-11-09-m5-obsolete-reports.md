# M5 obsolete reports and instructions implementation plan

> **For agentic workers:** Use superpowers:executing-plans for inline work;
> obtain a fresh review before closure. Use the existing feature/m5-geometry
> branch; no worktrees or branch switches.

**Goal:** Resolve the sixth M5 square using current callers, replay behavior,
and executable/package metadata rather than treating old reports as current bugs.

**Architecture:** Preserve dated reviews and recorded scientific outputs. Add
current dispositions and correct active contributor instructions. Change an
executable path only if a failure is reproduced through its maintained caller.

**Tech Stack:** Python 3.12/3.13, locked pytest, existing offline FITS/catalog
fixtures, AST/source inspection and generated-guidance checks.

**Spec:** [M5 obsolete reports and instructions](../../working/master-continuation-plan.md#m5-resolve-the-specific-older-reports-that-remain-unverified).

## Constraints and review focus

- Keep dated historical reports, recorded fixtures and TS-21's cancelling unit
  factors intact; distinguish removed implementations from surviving ports.
- Verify PHOT-16 against the deleted exporter and current public replay,
  including ordinary exceptions, no convergence and preserved warnings.
- Check real default centroid settings; a provided-photometry replay does not
  exercise a pixel centroid pass.
- Derive Python/CI guidance from pyproject/workflows; retain deliberate 3.13
  host-installer choices. Do not edit dependencies, workflows or release state.
- Correct active instructions without changing unrelated domain behavior or
  claiming current native/live checks that were not executed.

## Tasks

- [x] Inspect relevant vault context, current callers and deletion history;
  record report-by-report dispositions in a new analysis note.
- [x] Add offline public replay controls for frame/WCS errors, solver errors,
  nonconvergence, warning preservation and recovery on a subsequent call.
  Run existing real replay, parity/centroid, routing and shape checks too.
- [x] Reconcile AGENTS.md, CLAUDE.md, CONTRIBUTING.md and tests/README.md with
  verified package/CI metadata, maintained routing and remediation contracts.
  Remove active obsolete execution guidance; preserve dated history.
- [x] Independently review the combined changes: no actionable findings;
  all ten new replay controls repeated successfully.
- [x] Freeze source/tests/guidance and run required validation. Close the sixth
  master-plan box only after all questions have evidence/dispositions.

Delivery: commit/push the existing feature branch under standing authorization
and attempt the shared-vault Save transaction; record any existing vault block.

## Evidence ledger

- Vault retrieval used index/text fallback; current metadata/CI and caller
  behavior override stale September preservation/version claims.
- `01177ec` deleted optical state/deps and the PHOT-16 exporter; `b5d1b0a`
  retired TypeScript. No retired-symbol definitions/calls in 227 inspected
  algorithm/tool Python modules. The maintained image-query API stays live.
- Ten new public replay controls pass on existing behavior; no executable fix
  is claimed. Only the replay docstring changes in production Python; its
  executable AST is unchanged from `783abbf` after stripping docstrings.
- Targeted group: 404 passed (8.69 seconds). Existing pixel-centroid controls:
  2 passed, 27 deselected (1.46 seconds). Compilation, generated-guidance and
  whitespace checks pass. Independent review is clear; all ten controls also
  pass in the reviewer's run.
- Final locked suite with MCP on Python 3.13.15: 4,974 passed, 94 skipped, 214
  FITS notices, no failures (409.08 seconds). All 466 frozen source/test/
  guidance/CI metadata files unchanged. Sixth square closed; M5 complete.
