# MARS Documentation

The top level of `docs/` holds the **reference documents** — the ones that
describe how MARS (MCP Astronomy Research Suite) is built and how it works. They track the code and are
updated when the code changes.

| Document | What it covers |
| --- | --- |
| [tool-architecture.md](tool-architecture.md) | The master package architecture: the public tool layer, algorithm-package ownership, shared models and artifacts, `skylib_lite` consolidation, runtime and validation policy, and the non-goals. |
| [extraction.md](extraction.md) | The master extraction record: one section per algorithm package, with exact upstream provenance (source path, line ranges, per-file diff fidelity), every severed dependency, the preserved parity quirks, and the verification actually performed. |
| [repository-folders.md](repository-folders.md) | A current-state guide to every source folder in the repository — responsibilities, important files, and caveats. |
| [technical-summary.md](technical-summary.md) | A concise current-state summary of what MARS is, the capability, agent, console, and benchmark work already delivered, and its validation boundaries. |
| [architecture-layers.md](architecture-layers.md) | The layer map over the architecture: which parts of the repository are tools, which are turn-taking, and which are harness — with the flowcharts for each, the eight gates the loop adds over a bare tool-use wrapper, and the three seams the console and the benchmark fill differently. |
| [installing.md](installing.md) | Installing MARS with no checkout: what a wheel contains, registering `mars-mcp` with a host, where artifacts and downloads go, fetching the optional data bundles, and which tools need which bundle. |
| [releasing.md](releasing.md) | How a release is cut: version and tag policy, what a pre-release means, the release workflow, and how the optional data bundles are published on the standing `data` release and pinned by each wheel. |
| [pulsar-tool-pipeline.md](pulsar-tool-pipeline.md) | The four-stage pulsar tool chain (light curve → periodogram → fold → sonify): why the stage order is a dependency, each stage's extracted Astromancer provenance, result contracts, and where output goes. |

## Subdirectories

| Directory | Contents |
| --- | --- |
| [`analysis/`](analysis/README.md) | Point-in-time review and external-research output. Dated. Kept for the "why"; the action items land elsewhere as plans or code. |
| [`benchmarking/`](benchmarking/README.md) | Measuring models on MARS's tool surface: the harness design, the 144-session sweep, the generated report, and the figures. |
| [`archive/`](archive/README.md) | Completed track documents, kept as records rather than deleted. Not current-state. |
| [`working/`](working/README.md) | The [master continuation plan](working/master-continuation-plan.md): current dispositions, execution order and acceptance checks for known continuing work. |
| [`examples/`](examples/README.md) | Committed sample output — the deliberate exception to the repository's "no generated files" rule. |

## Document lifecycle

- **Reference docs** (`docs/*.md`) describe the system as it is. Update them in
  the same change that alters the behaviour they describe.
- **`analysis/`** documents are snapshots. They are not kept current against the
  code; they record what a review found on a given date. Trim or delete one when
  it has been fully superseded.
- **`working/`** holds the single master continuation plan. New findings get a
  row there, linked to their evidence; completed work gets closure locators.
  Fold durable outcomes into reference docs as they land. Archive the master
  only after accepted work is closed and remaining scope has explicit
  deferral/revisit decisions; preserve its verification record.
- **`archive/`** documents are records. They are never updated to track the
  code; a correction to one is dated and marked inline.
- **`benchmarking/`** is the benchmark track's own folder — design, results,
  report and figures together, because the document and its evidence are one
  subject.
- **`examples/`** output is regenerated deliberately and rarely; see that
  directory's README before adding to it.
