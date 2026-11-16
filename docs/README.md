# MARS Documentation

Start with the guide for your task. Current guides and architecture references
track the code; dated reviews and completed plans live under `development/`.

| I want to… | Start here |
| --- | --- |
| Install MARS and connect a desktop host | [Installation](guides/installation/README.md), then [Linux](guides/installation/linux.md), [macOS](guides/installation/macos.md) or [Windows](guides/installation/windows.md) |
| Understand the supported scope | [Known limitations](guides/limitations.md) |
| Follow the pulsar workflow | [Pulsar tool pipeline](guides/pulsar-tool-pipeline.md) |
| Get a technical overview | [Technical summary](architecture/technical-summary.md) |
| Understand ownership and dependencies | [Tool architecture](architecture/tool-architecture.md), [layer map](architecture/architecture-layers.md) and [repository folders](architecture/repository-folders.md) |
| Check algorithm provenance and retained behavior | [Extraction record](architecture/extraction.md) |
| Read benchmark results and their limits | [Benchmarks](benchmarks/README.md) |
| Contribute or prepare a release | [Contributing](../CONTRIBUTING.md) and [development](development/README.md) |
| See what changed in a release | [0.1.0 release notes](releases/0.1.0.md) |

The agent guide is generated from [tools/skill/source/](../tools/skill/source/SKILL.md)
into [skills/mars-tools/](../skills/mars-tools/SKILL.md). Edit the source and run
`uv run python -m tools.skill` to update its distributed copies.

## Directory map

| Directory | Purpose |
| --- | --- |
| `guides/` | Installation, host setup, practical workflows and user-visible limitations. |
| `architecture/` | Current technical overview, system boundaries, source layout and algorithm provenance. |
| [development/](development/README.md) | Maintainer procedures, active plans, dated reviews and archived implementation records. |
| [benchmarks/](benchmarks/README.md) | Benchmark design, historical results, generated reports and figures, kept together. |
| `releases/` | Versioned release notes; the release workflow requires `<version>.md` here. |
| `assets/` | Brand and architecture figures, with generation scripts. |
| [examples/](examples/README.md) | Deliberately committed sample plots and audio. |

## Document lifecycle

- **Guides and architecture references** describe supported behavior. Update
  them with the change that alters that behavior. Label proposed extensions.
- **Active plans** live in `development/plans/`. The [master continuation
  plan](development/plans/master-continuation-plan.md) owns release gates,
  current dispositions and closure evidence. Keep it active through publication;
  avoid competing gate checklists.
- **Reviews** in `development/reviews/` are dated evidence. Preserve original
  findings and measurements; link current dispositions from the master plan.
- **Archived tracks and task plans** live in `development/archive/`. Add a
  dated completion annotation and preserve their reasoning. Historical unchecked
  recipes do not schedule new work. Fold durable outcomes into current references.
- **Benchmark reports, figures and examples** are evidence or deliberate
  generated output. Update navigation without silently changing measurements
  or scores. Regenerate them only as a separate, explicit operation.
- **Release notes** describe a version. Keep their location stable for the
  publishing workflow and use links that resolve at that version's tag.
