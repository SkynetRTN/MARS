# Archived Track Documents

Completed plans, kept as records. Each one states the problem it was written
to solve, the architecture that answered it, and the phased rollout that got
there — and each now carries an `Archived` block at the top saying when the
track finished, what a completion audit re-verified, and which of its own
statements were corrected at archive.

They are **not** current-state documents. `docs/`'s top level describes the
system as it is, and is what to read first:
[`../tool-architecture.md`](../tool-architecture.md) for the architecture,
[`../extraction.md`](../extraction.md) for per-domain provenance,
[`../repository-folders.md`](../repository-folders.md) for what each folder
does. Read an archived plan when you want the *why* — the alternatives that
were rejected, the constraint that forced a shape, the measurement that
overturned a guess.

Remaining findings and deferred decisions from these records are reconciled in
the [master continuation plan](../working/master-continuation-plan.md). An
archive completion date applies to its original implementation track.

| Document | Track | Finished | Durable outcome |
| --- | --- | --- | --- |
| [mars-rebrand.md](mars-rebrand.md) | Kepler renamed MARS (MCP Astronomy Research Suite): the `skynet-mars` distribution, commands, server and skill; `MARS_*` variables and the `mars` home; code and prose with a guard test; the logo, banner, server icon and console palette; the repository and the `v0.1.0rc3` release. Phases R1–R6. | 2026-09-28 | `../installing.md`'s *Upgrading from Kepler*; `tests/test_rebrand_guard.py`; `../assets/make_brand.py`; `tools/tui/theme.py` |
| [mcp-tool-surface.md](mcp-tool-surface.md) | MARS's tools served over MCP to a coding agent's own console on a machine with no checkout: the agent skill, the stdio server, inline media, tool groups and annotations, packaging with checksum-pinned data bundles, and the GitHub release track. Phases C0–C9. | 2026-09-25 | `../tool-architecture.md` section 10.3; `../installing.md`; `../releasing.md`; `CLAUDE.md`'s `tools/mcp/` rules |
| [optical-tools.md](optical-tools.md) | Thirteen broken links between the tool surface and the bundled data, and the stateless architecture underneath them. Baseline 1–4, stateless S0–S6, closure P1–P9. | 2026-09-16 | `../tool-architecture.md`; `../extraction.md`; `CLAUDE.md`'s *Python domain boundaries* |
| [model-backends.md](model-backends.md) | The provider-neutral model port: `tools/llm/`, the four adapters, schema translation, argument validation, and the headless engine in `tools/agent/`. Phases −1–3. | 2026-09-09 | `../tool-architecture.md` section 10 |

Two completed tracks are not filed here.

**The benchmark track** — phases 4–5 of the model port, not a track of its own
— is in [`../benchmarking/`](../benchmarking/README.md) with its results,
report and figures, because a harness document belongs beside the evidence it
produced.

**The TUI track** was folded into `../tool-architecture.md` section 10.2 and
its working document deleted before this folder existed, under the lifecycle
rule as it then stood. Git history has it. The narrower
[artifact-rendering implementation recipe](../superpowers/plans/2026-09-14-tui-artifact-rendering.md)
remains as a completed record with a completion annotation.

## Why archived rather than deleted

`docs/README.md`'s lifecycle used to say to delete a plan once its work landed,
on the grounds that git history preserves it. It does, but only for someone who
already knows the document existed and what it was called. These three carry a
lot of reasoning that no reference document has room for — measured findings
that overturned a design guess, the reason a quirk is deliberate, the
alternatives that were rejected and why — and that reasoning is what gets
re-litigated when it is not findable. Keeping them costs one folder and an
`Archived` block that stops anyone mistaking a record for a plan.
