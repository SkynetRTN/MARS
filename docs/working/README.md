# Working Documents

The [master continuation plan](master-continuation-plan.md) is the closure
checklist for the next release. It describes concrete failures, required
outcomes and questions that still need evidence. All manual step gates,
review-fix status and closure evidence are maintained there. Dated reviews
retain original findings and technical analysis. Do not create separate working
documents for individual gates.

## Index

| Plan | Status |
| --- | --- |
| [master-continuation-plan.md](master-continuation-plan.md) | Refreshed 2026-10-30 against `main` at `e1ad8b0` (M2, PR #124). M2 and M3 are closed on main, unpublished. Remaining gates describe missing evidence and release checks. |

## Landed

The earlier implementation tracks listed below have landed; their deferred
decisions and remaining findings are reconciled in the master plan. The MCP tool
surface's completion audit (2026-09-25) is in its own `Archived` block. For the others,
a completion audit on 2026-09-18 re-verified each one against `dev`: the default suite is green
(2575 passed, 44 skipped), and the asset-gated evidence — the NGC 5286 B
frames from pixels, the bounded M15 plate solve, the ATLAS backend against the
operator UCAC5 tree, the local Girardi grid — was re-run rather than taken
from the record.

| Track | Where it went | Finished |
| --- | --- | --- |
| MCP tool surface | [`../archive/mcp-tool-surface.md`](../archive/mcp-tool-surface.md); `v0.1.0rc1` published | 2026-09-25 (C9, the last phase) |
| Optical | [`../archive/optical-tools.md`](../archive/optical-tools.md) | 2026-09-16 (P8, the last phase) |
| Model | [`../archive/model-backends.md`](../archive/model-backends.md) | 2026-09-09 (phases −1–3) |
| Desktop acceptance (M4) | [`../archive/desktop-acceptance.md`](../archive/desktop-acceptance.md); install steps in [`../installing/`](../installing/) | 2026-10-23 |
| Benchmark | [`../benchmarking/`](../benchmarking/README.md) — phases 4–5 of the model port, with its results, report and figures | 2026-09-14 (calibration gate) |
| TUI | `../tool-architecture.md` section 10.2; working document deleted, git history has it | 2026-09-18 (phase G) |

## Lifecycle

When a work stream lands:

1. Fold the durable outcome into a reference document at the top level of
   `docs/` — that is the document that stays current against the code.
2. Update the relevant release checklist item with its outcome and evidence.
   Keep original finding IDs in the linked review records.
3. Archive the master only after every accepted item is closed and the others
   have explicit deferral/revisit decisions. Add an `Archived` block recording
   what was verified, move it to [`../archive/`](../archive/README.md), and add
   its row there. Do not delete dated source reviews to erase open findings.

A plan whose subject has its own folder — as the benchmark harness has
[`../benchmarking/`](../benchmarking/README.md) — is archived beside its
evidence instead, and `../archive/README.md` says so.

**Archiving is not the same as deleting**, which is what this rule used to say.
Git history preserves a deleted file, but only for someone who already knows it
existed and what it was called; these documents carry reasoning that no
reference document has room for. See `../archive/README.md`.

See [`../README.md`](../README.md) for how `docs/` is organized.
