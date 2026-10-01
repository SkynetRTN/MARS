# Analysis

Point-in-time review and external-research output. These documents are **dated**:
each captures what a review found on a given day, not the current state of the
code. Action items from them land as `working/` plans or as code changes — not as
edits here. See [`../README.md`](../README.md) for how `docs/` is organized.

Current disposition and scheduling for all known continuing work are in the
[master continuation plan](../working/master-continuation-plan.md), reconciled
2026-10-01. Original claims below remain dated evidence.

| Document | Description |
| --- | --- |
| [algorithm-remediation-plan.md](algorithm-remediation-plan.md) | Output of a four-part algorithm review (2026-08-10): 110 IDs (109 originally actionable plus protected TS-21), seven original blockers and a proposed rollout. The master plan maps every ID to current Python code, including completed/changed claims and evidence gates. |
| [applicable-designs.md](applicable-designs.md) | Reads MARS against external astrophysics-agent systems and benchmarks (2026-08-11). Structured warnings, optional MCP and session persistence have shipped; current implementations are `tools.agent`, `tools.sessions` and `tools.mcp`. Reachable preserved-defect warnings remain SCI-01 in the master. |
| [pulsar-pipeline-review.md](pulsar-pipeline-review.md) | Open tool-correctness bugs in `tools/pulsar.py` and a review of the pulsar plotting tools, split out of [`../pulsar-tool-pipeline.md`](../pulsar-tool-pipeline.md) so that architecture document stays architecture. |
| [obs-report.md](obs-report.md) | External Skynet observation/scheduler/API snapshot (2026-09-24), moved from `working/`. Source paths leave this standalone repository; EXT-SKY-01–12 require pinned upstream revalidation before implementation. |
| [mcp-desktop-hosts.md](mcp-desktop-hosts.md) | PR #97 desktop-host proposal and vendor-source snapshot (2026-10-01), reconciled into master §9 as D0–D4. MCPB/config-helper decisions require actual macOS/Windows/app evidence; browser support remains parked. |

## Related

- [../extraction.md](../extraction.md) — the master extraction record; the analysis here leans on it heavily for extraction boundaries and preserved quirks.
- [../tool-architecture.md](../tool-architecture.md) — the tool and algorithm-package boundaries these documents operate within.
