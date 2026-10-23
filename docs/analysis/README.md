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
| [pulsar-candidates-confidence.md](pulsar-candidates-confidence.md) | M2 acceptance (2026-10-21, numerical follow-ups 2026-10-22): explicit candidate/search units, sampling heuristics, finite-sample Gaussian bounds, endpoint/host-context corrections, exact-constant rejection and scope limits. |
| [variable-star-powers-errors.md](variable-star-powers-errors.md) | M2 acceptance (2026-10-21, amplitude follow-up 2026-10-22): weighted floating-mean standard powers, independent quadrature uncertainties, numerical rank policy, artifact migration and scientific references. |
| [cluster-ages-membership.md](cluster-ages-membership.md) | M2 acceptance (2026-10-22): legacy MWSC age units, exact source-ID joins, measured zero proper motion and degenerate selection geometry; registered-tool scope and ECSV checks. |
| [legacy-coordinates-extinction-mass.md](legacy-coordinates-extinction-mass.md) | M2 acceptance (2026-10-22): signed sexagesimal coordinates, supported CCM extinction, observed one-dimensional motion RMS and explicitly labeled radius/mass proxies. |
| [m2-m3-integration.md](m2-m3-integration.md) | Integration (2026-10-22): M3 PR #122 reconciled with M2 powers, uncertainties, candidates and guidance before the accepted-sky-position checkpoint. |
| [accepted-sky-positions.md](accepted-sky-positions.md) | M2 acceptance (2026-10-22): solved-footprint position checks and ATLAS reference queries, finite WCS validation and signed southern fallback coordinates. |
| [photometric-calibration.md](photometric-calibration.md) | M2 calibration correction (2026-10-23): small-sample rejection, nonnegative extra variance, exact diagnostic masks, known saturation selection, magnitude zero, explicit unit gain and honest historical comparisons. |
| [obs-report.md](obs-report.md) | External Skynet observation/scheduler/API snapshot (2026-09-24), moved from `working/`. Source paths leave this standalone repository; EXT-SKY-01–12 require pinned upstream revalidation before implementation. |
| [mcp-desktop-hosts.md](mcp-desktop-hosts.md) | PR #97 desktop-host proposal and vendor-source snapshot (2026-10-01), reconciled into master §9 as D0–D4. MCPB/config-helper decisions require actual macOS/Windows/app evidence; browser support remains parked. |

## Related

- [../extraction.md](../extraction.md) — the master extraction record; the analysis here leans on it heavily for extraction boundaries and preserved quirks.
- [../tool-architecture.md](../tool-architecture.md) — the tool and algorithm-package boundaries these documents operate within.
