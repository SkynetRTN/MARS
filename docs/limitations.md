# Known limitations

What MARS (MCP Astronomy Research Suite) does not do, or does only under a
condition. Each entry links to its details. A science limit that applies to
one result is also returned with that result, as a warning whose code
carries its meaning. The agent skill teaches models to read those warnings.

Compiled 2026-11-04 from the release gates M2–M4 and M6 in the
[master plan](working/master-continuation-plan.md). The open M5 checks may
add to it before the next release.

## What the results are

- **Extractions, not independent validations.** The algorithms reproduce
  Skynet and Astromancer, including their documented quirks and known bugs.
  The test suite pins parity with recorded upstream output; it does not
  establish scientific correctness. Each deliberate correction since is
  recorded per package. [Extraction record](extraction.md),
  [what the tests prove](../tests/README.md)

## Installation and platforms

- **Platforms.** Python 3.12 and 3.13 on Linux (x86_64 and ARM), Apple
  Silicon macOS and Windows on ARM. On Windows on ARM, MARS runs on the x64
  build of Python 3.13 under Windows' emulation, because `sep` and `pyerfa`
  publish no ARM64 wheels. x64 Windows is no longer tested. Intel Macs are
  not supported, because `numba` and `llvmlite` publish no wheels for them.
  Python 3.14 is not supported either, because `sep` has no wheel for it.
  [Install](installing.md#install), [macOS](installing/macos.md)
- **Size and first start.** The install is about 700 MB, nearly all of it
  dependencies. A first start from an empty cache took 47 s on Linux ARM,
  and 86 s and 1.7 GB on Windows on ARM, which needs two Pythons. Later
  starts take seconds. [Install](installing.md#install)
- **Desktop apps.** Claude Desktop has no Linux build. Codex in the ChatGPT
  app has not been tested on a Mac; it uses the same route verified on
  Linux. The guides name no OS or app versions, because none were recorded.
  [Desktop acceptance](archive/desktop-acceptance.md)
- **`mars-bench` needs a checkout.** The package does not ship the benchmark
  suites. [Install](installing.md#install)
- **The Codex plugin's copy of the skill can lag the server** until the
  plugin is upgraded. The server always sends its current guide.
  [Updates](installing.md#updates-offline-use-and-rollback)

## Plate solving

- **A machine dependency.** Plate solving needs astrometry.net, and index
  files covering your images' field of view, installed on your machine. No
  MARS install route provides them. astrometry.net has no native Windows
  build, and MARS has not been run against WSL or Cygwin.
  [Plate solving](installing.md#plate-solving)
- **ATLAS does not search blind.** Without the frame's scale or pointing it
  refuses, so astrometry.net is the only blind route. An all-sky
  astrometry.net solve against several index series is slow; give it the
  frame's scale. [Plate solving](installing.md#plate-solving)

## The `mars` console

- **Stopping.** Esc stops the turn after the running step finishes. Ctrl+C
  stops the step itself, a tool or a model reply, and keeps the console
  open. Ctrl+Q quits at once. [Console keys](tool-architecture.md#102-the-mars-console)
- **Terminals.** On macOS the supported terminal is Terminal.app; iTerm2 is
  not supported. The console was also checked on Windows on ARM over SSH,
  and is developed on Fedora Linux.
- **Approvals.** "Allow always" lasts for the current question only.
- **Resumed sessions** show the questions and answers, not the tool calls
  or artifacts.
- **Only the Anthropic backend streams.** OpenAI-compatible, Gemini and
  Ollama answers appear when they are complete.
- **Ollama** needs a context window of at least 32,768 tokens
  (`OLLAMA_CONTEXT_LENGTH=32768 ollama serve`). The default model is an MLX
  build for Apple Silicon; on Linux and Windows, name another.
  [The console](installing.md#the-mars-console)

## The MCP server

- **Local and single-user.** `mars-mcp` is a trusted stdio interface, not a
  shared service: no HTTP transport, no authentication and no browser
  hosting. Do not expose it to untrusted users.
  [Runtime limits](installing.md#mcp-runtime-limits-and-cleanup)
- **Per-call budgets.** A call has 600 s by default (an operator can allow
  up to 1800 s), 4 GiB of memory on Linux, and download, disk and reply
  budgets. Aggregate checks are sampled and can briefly overshoot; they are
  not filesystem quotas. [Runtime limits](installing.md#mcp-runtime-limits-and-cleanup)
- **Tool groups narrow what is served, not what is loaded.** Every
  `--tools` group imports every domain, about 1.6 s and 280 MB warm.
  [Scope decisions](analysis/m6-scope-decisions.md#1-eager-domain-imports-arc-01)
- **No output schemas.** Results arrive as structured content and as the
  same JSON in text, with no declared `outputSchema`.

## Calling the tools from Python

- **Package names.** MARS installs two top-level packages, `tools` and
  `algorithms`. In a project that has its own package or module by either
  name, Python imports yours instead and MARS fails to import. Rename yours,
  or run from another directory. The `mars`, `mars-mcp` and `mars-bench`
  commands are not affected.
  [Scope decisions](analysis/m6-scope-decisions.md#2-generic-top-level-package-names-arc-02)
- **Settings are read at import.** MARS reads its `MARS_*` settings once,
  when first imported. These include the data, artifact and download
  folders, `MARS_ISOCHRONE_DIR` and the preview and listing caps. Set them
  before importing MARS, or restart the kernel.
  [Scope decisions](analysis/m6-scope-decisions.md#4-hr-code-reads-application-configuration)
- **Some pulsar controls are Python-only:** plot labels and sizes, `cal`,
  the sonification `phase`, `max_input_seconds` and `sample_rate`.
  [Pulsar controls](pulsar-tool-pipeline.md#6b-public-and-python-only-controls-m3-2026-10-22)

## Remote services

- **Outages are reported, not hidden.** During October 2026 checks, SIMBAD,
  VizieR mirrors, Pan-STARRS, SkyMapper and UCAC queries failed or timed out.
  MARS reports such failures as `provider_unavailable` or
  `unusable_response`, never as an empty match. The full set of live checks
  could not be repeated cleanly. [M2 validation](working/master-continuation-plan.md#m2-validation-and-remaining-checks)
- **ADS becomes Science Explorer (SciX) on 2026-11-16.** The API and tokens
  are stated to carry over, and a token answered on `api.scixplorer.org` on
  2026-10-22. MARS's live ADS checks have not been rerun since the move, and
  the documented token link still names ADS. [Keys](installing.md#register-the-server-with-a-host)

## Science results

Each of these is also returned, as a warning, with the result it applies to.

- **Pulsar periods.** The false-alarm bound assumes Gaussian noise. Neither
  the bound nor the fold signal-to-noise is a pulsar probability.
  Correlated noise, periodic interference and repeated retuning fall outside
  the bound. A blind search finds the period in one of the five bundled
  scans. A fold at a catalogued period is not an independent detection.
  Spectra saved by 0.1.0rc6 or earlier show their thresholds as
  uncalibrated, with a warning; recompute them from the light curve. [Candidates and confidence](analysis/pulsar-candidates-confidence.md),
  [the pipeline](pulsar-tool-pipeline.md)
- **Photometric calibration.** A finite zero point and error do not
  establish enough stars or enough coverage. The sky coverage of a distorted
  footprint is estimated, not guaranteed complete. A narrowband image is
  calibrated against a broadband reference: the result is a relative zero
  point, not an absolute narrowband magnitude. A one-star solve is refused,
  where Skynet returns it with no error estimate.
  [Calibration](analysis/photometric-calibration.md),
  [coverage](analysis/catalog-coverage-sufficiency.md),
  [magnitudes and filters](analysis/catalog-magnitudes-filters.md)
- **HR diagrams.** Members are selected; no membership probability is
  claimed. The fitted isochrone is drawn as points, because the local
  Girardi tracks mark no phase breaks. The fit needs the Girardi grid
  (`MARS_ISOCHRONE_DIR`, or the `isochrones` bundle).
  [Ages and membership](analysis/cluster-ages-membership.md),
  [optional data](installing.md#optional-data)
- **Legacy radius and mass outputs are labelled proxies.**
  [Coordinates, extinction and mass](analysis/legacy-coordinates-extinction-mass.md)

## The benchmark

- **The scores cover 16 hand-picked probes** of documented failure modes,
  not general astronomy work. The schema dialect is confounded with the
  provider, and the corpus was written while watching the models it
  compares. The historical scores were not checked for author attribution.
  [Benchmark limits](benchmarking/results.md#limits)

## Still being checked

The M5 gate is rechecking older reports about coordinates and image
geometry, measured flux and source positions, repeated calls and FITS
writes, light-curve and HR boundaries, and catalog parsing and caches. Its
outcomes are added here before the release. One limit is already recorded:
the HR fit joins track rows no more than 0.5 mag apart, and the effect on the
fitted parameters has not been measured.
