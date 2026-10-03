<p align="center">
  <img src="https://raw.githubusercontent.com/SkynetRTN/MARS/dev/docs/assets/mars-banner.png" alt="MARS — MCP Astronomy Research Suite" width="880">
</p>

<p align="center">
  <a href="https://github.com/SkynetRTN/MARS/actions/workflows/ci.yml"><img src="https://github.com/SkynetRTN/MARS/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.13-blue" alt="Python 3.13">
</p>

MARS (MCP Astronomy Research Suite) is an agentic, tool-enabled system for
automated astronomy: a registry of purpose-built tools — SIMBAD, NED, VizieR,
ATNF, MAST, MPC, CASDA and ADS queries, plus local pulsar, variable-star,
optical photometry, plate-solving, HR-diagram and radio-source pipelines —
that an LLM agent plans and executes research tasks with. Serve them over MCP
to your own coding agent, or drive them from the `mars` console.

The algorithms behind the tools come from two production systems built around
the [Skynet Robotic Telescope Network](https://skynet.unc.edu/) at the
University of North Carolina at Chapel Hill: Skynet itself, extracted
directly into Python, and [Astromancer](https://astromancer.skynet.unc.edu/home),
its light-curve, periodogram and star-cluster web application, ported from
TypeScript. They are **extractions, not rewrites** — algorithms, constants,
comments and known bugs are preserved, and the test suite checks bit-for-bit
parity with recorded Skynet output rather than "fixing" it in transit.

## Quick Start

**From an MCP host** (Claude Code, Claude Desktop, Codex, Cursor, …), with no
checkout — install [`skynet-mars`](https://pypi.org/project/skynet-mars/) on
Python 3.13 and register its server:

```bash
uv tool install --python 3.13 "skynet-mars[mcp]"
mars-mcp self-test                                   # runs a pulsar detection end to end
claude mcp add --scope user mars -- /full/path/to/mars-mcp
```

Other hosts, the optional data bundles (`mars-mcp fetch-data`), credentials
and where files go are in [`docs/installing.md`](https://github.com/SkynetRTN/MARS/blob/dev/docs/installing.md).

**From a checkout**, run the console. It needs a model backend — Anthropic by
default (`ANTHROPIC_API_KEY`), or OpenAI-compatible, Gemini, or a local Ollama
daemon, switchable in the session with `/backend`:

```bash
uv sync
uv run mars
```

The console's commands, keys and flags are in
[`docs/tool-architecture.md` §10.2](https://github.com/SkynetRTN/MARS/blob/dev/docs/tool-architecture.md#102-the-mars-console);
backend settings are in [§10](https://github.com/SkynetRTN/MARS/blob/dev/docs/tool-architecture.md#10-the-agent-loop-and-model-port).
Every tool is also a plain Python function (`from tools.simbad import
search_simbad`), listed in
[§2](https://github.com/SkynetRTN/MARS/blob/dev/docs/tool-architecture.md#2-public-tool-layer).
Three optional optical frames are Git LFS objects (`git lfs pull`); see
[`data/README.md`](https://github.com/SkynetRTN/MARS/blob/dev/data/README.md).

## What's Here

| Path | What it holds |
| --- | --- |
| `tools/` | The public tool surface: plain Python wrappers, the tool registry, the agent loop (`agent/`), the model port (`llm/`), the `mars` console (`tui/`), the MCP server (`mcp/`), and the benchmark harness (`bench/`). |
| `algorithms/` | The extracted Skynet packages (`wcs/`, `photometry/`, `fieldcal/`, `catalogs/`, `query/`, shared `skylib_lite/`), the Astromancer ports (`pulsar/`, `variable_star/`, `hrdiagram_py/`), and the new `radio/`. |
| `skills/mars-tools/` | The agent skill for using the tools, generated from `tools/skill/source/`. |
| `tests/` | Algorithm-preservation and tool-smoke tests; no network by default. |
| `data/` | Fixture frames, pulsar scans and recorded reference solves. |
| `benchmarks/`, `docs/` | The model benchmark corpus; the documentation. |

## Documentation

- [`docs/README.md`](https://github.com/SkynetRTN/MARS/blob/dev/docs/README.md) — the documentation map.
- [`docs/installing.md`](https://github.com/SkynetRTN/MARS/blob/dev/docs/installing.md) — installing with no checkout, registering `mars-mcp`, data bundles.
- [`docs/tool-architecture.md`](https://github.com/SkynetRTN/MARS/blob/dev/docs/tool-architecture.md) — the architecture: public tools, algorithm ownership, the agent loop, console, benchmark and MCP server.
- [`docs/repository-folders.md`](https://github.com/SkynetRTN/MARS/blob/dev/docs/repository-folders.md) — every folder, its important files, and its configuration (WCS solver and ATLAS catalog setup, VizieR settings).
- [`docs/extraction.md`](https://github.com/SkynetRTN/MARS/blob/dev/docs/extraction.md) — upstream provenance, severed dependencies and preserved parity quirks, per package.
- [`docs/pulsar-tool-pipeline.md`](https://github.com/SkynetRTN/MARS/blob/dev/docs/pulsar-tool-pipeline.md) — the four-stage pulsar chain.
- [`docs/benchmarking/README.md`](https://github.com/SkynetRTN/MARS/blob/dev/docs/benchmarking/README.md) — the model benchmark and its results.
- [`docs/releasing.md`](https://github.com/SkynetRTN/MARS/blob/dev/docs/releasing.md) — how releases and data bundles are cut.
- [`tests/README.md`](https://github.com/SkynetRTN/MARS/blob/dev/tests/README.md) — what the test suite proves and what it does not cover.

## Contributing

Target `dev`, keep changes narrow, and run the checks CI enforces
(`uv run pytest`, `python3 -m compileall tools algorithms tests`,
`git diff --check`). See
[`CONTRIBUTING.md`](https://github.com/SkynetRTN/MARS/blob/dev/CONTRIBUTING.md),
and [`AGENTS.md`](https://github.com/SkynetRTN/MARS/blob/dev/AGENTS.md) for
agentic contributors.

## License

Copyright (C) 2026 Skynet Robotic Telescope Network.

MARS is licensed under the **GNU General Public License v3.0 only**
(`GPL-3.0-only`); the full text is [`LICENSE`](https://github.com/SkynetRTN/MARS/blob/dev/LICENSE). It is the licence of
the Skynet projects it grew from: Astromancer and Skycat carry the same text.

The code under `algorithms/` comes from three places (provenance per file in
[`docs/extraction.md`](https://github.com/SkynetRTN/MARS/blob/dev/docs/extraction.md)):

- **Skynet**, by the same group as MARS: `skylib` and the optical processing
  in `skynet-db`, extracted into `algorithms/skylib_lite/`, `wcs/`,
  `photometry/`, `fieldcal/` and `catalogs/`.
- **[Astromancer](https://github.com/SkynetRTN/astromancer)**, by the same
  group, GPL-3.0: ported to Python in `algorithms/pulsar/`,
  `algorithms/variable_star/` and `algorithms/hrdiagram_py/`.
- **Afterglow Core**, Apache-2.0: parts of the query layer in
  `algorithms/query/`. Apache-2.0 code may be combined into a GPL-3.0 work.

Files that carry their own third-party notice — for example the BSD-3-Clause
header in `algorithms/skylib_lite/util/overlap.py` — keep it, and those terms
apply to those files as well.
