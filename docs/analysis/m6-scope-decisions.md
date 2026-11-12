# M6: scope decisions

Investigated 2026-11-04 against `main` at `193d117` (M4 merged), on
`docs/m6-release-decision`. The [master plan](../working/master-continuation-plan.md#m6-record-the-release-decision-and-its-limits)
asks whether four architectural limits have a failing supported use case
before any of them becomes a release requirement. It also asks for the
remaining capability questions to be recorded as separate decisions.
**No production behavior changes in this investigation.** The maintainer
decided every disposition on 2026-11-04: all four limits are retained, none
is a release requirement, and the deferrals in §5 stand as recorded.

Host: Fedora 44, Linux aarch64, 8 cores, Python 3.13.14. "Wheel install"
means a wheel built from `193d117` in a fresh clone, installed with
`uv pip install --offline` into a new virtual environment. That resolves
dependencies from the local uv cache, not from `uv.lock`, so the sizes are
for this resolution. The checkout's own `.venv` is an editable install, and
for the package-name question that difference decides the result (§2).

## Summary

| Limit | Failing supported use case? | Decision (maintainer, 2026-11-04) |
|---|---|---|
| Eager domain imports (ARC-01) | **None found.** Every `--tools` group loads every domain: 1.6 s and 280 MB warm. M4's hosts all started within their limits. | **Retained.** Not a release requirement. |
| Generic package names (ARC-02) | **Yes, loud.** Under a wheel install, a Python caller whose project has its own `tools` or `algorithms` package, or a `tools.py`, cannot import MARS. The console commands are unaffected. | **Retained** (maintainer, 2026-11-04). MARS is run over MCP or in its own virtual environment. No namespace move is scheduled. |
| Heavy base dependencies (ARC-03) | **None found.** The console and provider packages are 14 MB of a 664 MB install. Neither the server nor the registry imports them. | **Retained.** Not a release requirement. |
| HR reads application configuration | **No wrong result.** One misleading error when a Python session sets `MARS_ISOCHRONE_DIR` after importing MARS. | **Retained.** Tell Python callers that settings are read at import. Correct two false sentences in `repository-folders.md`. |

## 1. Eager domain imports (ARC-01)

`tools/registry.py` imports 21 tool modules at load. `tools/mcp/server.py:49`
imports the registry before the `--tools` filter is applied. So the filter
narrows what is listed and callable, as `tool-architecture.md` §10.3 says,
but not what is imported. Every group loads every domain.

| Import (checkout `.venv`, warm, three runs) | Wall time | Peak RSS |
|---|---|---|
| `import tools.registry` | 1.29–1.30 s (2.26 s first) | 250 MB |
| `import tools.mcp.server` | 1.62 s | 280 MB |
| `import mcp.server, jsonschema, anyio` (SDK alone) | 0.42 s | 70 MB |

`python -X importtime` puts most of the registry's cost in `tools.ads`
(astroquery, astropy tables), `tools.astrometry` (the `skylib_lite`
extraction stack, numba, scipy) and `tools.photometry` (matplotlib).

No supported use case fails because of it:

- **Startup:** M4 measured `uvx … mars-mcp self-test` at 47 s cold (empty uv
  cache, including environment creation) and 8.2 s warm. The Codex plugin
  allows 600 s. The maintainer verified Claude Desktop and Codex in the
  ChatGPT app on real hosts ([desktop acceptance](../archive/desktop-acceptance.md)).
- **Missing dependencies:** every domain dependency is a base dependency, so
  no supported install lacks one. A lazy loader would have nothing to contain.
- **Read-only home:** with `HOME` unwritable, `import tools.mcp.server`
  succeeds. matplotlib writes a warning to stderr, which the stdio protocol
  does not read, and uses a temporary directory.
- **Documentation:** `installing.md:164` ("To serve fewer tools") and
  `tool-architecture.md:832` describe what a group serves. Neither claims a
  group starts faster or uses less memory.

**Decided 2026-11-04 (maintainer):** retained. Revisit if a supported
host's startup limit is exceeded, or if domain extras (ARC-03) make a
dependency optional.

## 2. Generic top-level package names (ARC-02)

The wheel installs top-level `tools` and `algorithms` packages
(`pyproject.toml:89`). The README (line 56) and `tool-architecture.md` (line
6) document calling tools from Python: "Python callers, scripts, notebooks",
`from tools.simbad import …`. So that route is supported.

Each case below ran `from tools.pulsar import list_pulsar_scans` as a script
in the named project directory, with a wheel install:

| Caller's project directory | Result |
|---|---|
| nothing named `tools` or `algorithms` | works |
| `tools/__init__.py` (a regular package) | `ModuleNotFoundError: No module named 'tools.pulsar'` |
| `tools.py` | `ModuleNotFoundError: No module named 'tools.pulsar'; 'tools' is not a package` |
| `algorithms/__init__.py` | `ModuleNotFoundError: No module named 'algorithms.pulsar'`, raised from MARS's own `tools.pulsar` |
| `tools/` with no `__init__.py` | works: a namespace portion yields to MARS's regular package |

The same happens to `python -c` and to notebook kernels, which put the
working directory first on `sys.path`. `mars-mcp --help` started inside the
`tools/__init__.py` project works, because a console script puts its own
`bin` directory first, not the working directory. The `mars`, `mars-mcp` and
`mars-bench` commands are therefore unaffected.

**The checkout cannot show this.** In the editable `.venv`, setuptools'
editable finder resolves `tools` before `sys.path` is searched. There, only
`tools.py` shadowed MARS, and the package and `algorithms/` cases passed. A
test run from a checkout will not catch a regression here.

**A second distribution in the same environment.** A demonstration wheel
(`collider-demo`) ships its own top-level `tools/__init__.py`. Installed
next to MARS, `uv pip install` reported no conflict and overwrote MARS's
`tools/__init__.py`. MARS still worked, but the other package's `__init__`
now ran on every MARS import. Uninstalling it deleted the file both had
installed, leaving `tools` a namespace package; MARS still imported. A
colliding *submodule* name, such as `tools/config.py`, would replace MARS's
module the same way. That is inferred from the overwrite, not tried. None of
the 71 distributions in MARS's own dependency closure ships either name.
Whether any published distribution does was not checked.

The failure is loud: an import error, never a wrong result. The durable fix
is the namespace move, which `repository-folders.md` ("Names and the package
namespace") already defers. It touches every import, test, extraction marker,
entry point and package-data path, and the namespace must not be `mars`.

**Decided 2026-11-04 (maintainer):** retained as is. MARS is normally run
over MCP or in its own virtual environment, and no namespace move is
scheduled. The caveat below is now in the README, `installing.md` and
[Known limitations](../limitations.md). A later move is cheapest before the first final release, because
`releasing.md` gives pre-releases no compatibility promise.
It would put both packages under one parent and use relative imports inside
it, so the code works wherever the parent sits. The scope measured at
`193d117` was 491 import lines in 106 package files, 983 in 129 test files,
117 module-name strings in 24 files, no `importlib.import_module` calls, and
18 path-scoped `.gitleaks.toml` entries that must move with their files.

The caveat, as written for users:

> MARS installs two top-level packages, `tools` and `algorithms`. If your
> project has its own package or module by either name, Python imports yours
> instead and MARS fails to import. Rename yours, or run from another
> directory. The `mars`, `mars-mcp` and `mars-bench` commands are not
> affected.

## 3. Heavy base dependencies (ARC-03)

Base install, wheel environment, by installed file size:

| Set | Distributions | Size |
|---|---|---|
| MARS's base dependency closure | 71 | 664 MB |
| without `textual`, `textual-image`, `anthropic`, `rich`, `keyring` as roots | 58 | 650 MB |
| exclusive to those roots | 13 | **14.3 MB** |

The 13 exclusive packages are pygments 4.6 MB, anthropic 3.7, textual 2.8,
rich 1.2 and jiter 0.8, plus eight under 0.3 MB each (distro,
docstring-parser, markdown-it-py, mdit-py-plugins, mdurl, platformdirs,
sniffio, textual-image). `keyring` stays in either case, because astroquery
requires it. The weight is in the domain dependencies: llvmlite 176 MB,
scipy 121, numpy 54, pandas 46, astropy 40, photutils 39, matplotlib 27 and
fonttools 24. numba (and through it llvmlite) and sep are hard import-time
requirements of `algorithms/skylib_lite`. The rest arrive through the
algorithms or through modules the registry imports eagerly.

Neither `import tools.registry` nor `import tools.mcp.server` imports
textual, anthropic or rich, so Python and MCP callers pay disk, not startup.
M4's release dry run (run 40611174066) installed the full base set on Linux,
macOS and `windows-11-arm`, so none of these packages blocks a supported
platform.

**Decided 2026-11-04 (maintainer):** retained. A console/provider extra
would save about 2%. Only a lazy registry (ARC-01) plus domain extras could
shrink a minimal install substantially. That is a design change, not a release fix. Revisit if a
supported platform loses wheels for one of these packages, or if a minimal
install becomes a supported use case.

## 4. HR code reads application configuration

`algorithms/hrdiagram_py/isochrones.py:18` and `local_grid.py:16` do
`from tools import config` to read `ISOCHRONE_DIR`. They are the only
`algorithms → tools` imports. `tools.config` reads its environment once,
when first imported (`tools/config.py:261`). The fitting functions take no
grid-directory argument.

With the Girardi grid at `/srv/agents/isochrones`, wheel environment, loading
one exact track with `local_grid.load_isochrone(age=10.00, metallicity=0.0,
…)`:

| `MARS_ISOCHRONE_DIR` set | Result |
|---|---|
| before any MARS import | the track loads |
| after `import tools.hr_diagram` | `GridUnavailableError: Girardi grid directory is unavailable; set MARS_ISOCHRONE_DIR to an unpacked grid directory` |
| after import, then `tools.config.ISOCHRONE_DIR = Path(…)` | the track loads |

The error names the variable the caller has just set. Hosts, the console and
`mars-mcp` set their environment before launch and are unaffected. No user
document says settings are read at import. Only `CLAUDE.md` and the comment
in `tools/config.py` do, so a notebook user has no way to learn it.

Two sentences in `repository-folders.md` (`algorithms/hrdiagram_py/`) are
false against current code, and this change corrects them. One said
`isochrones.py` fetches PARSEC isochrones from stev.oapd.inaf.it; its
docstring says "This module does not download isochrones", and no module in
the folder imports a network library. The other said the folder "never
imports `tools.*`", which `architecture-layers.md` §1 already records as an
exception.

**Decided 2026-11-04 (maintainer):** retained; the layering exception
produces no wrong result. The error message is unchanged. Python callers are
told that MARS reads its environment settings when first imported, so they
must set them before importing or restart the kernel (the README,
`installing.md` and [Known limitations](../limitations.md)). The durable fix,
passing the grid directory in from `tools/hr_diagram.py`, is deferred.

## 5. Separate decisions

The plan names these as needing decisions of their own, not release work.
The maintainer kept every row below as recorded (2026-11-04).
Their earlier IDs and revisit conditions were in the pre-rewrite master's
§§4, 7 and 8 ([`a6785aa`](https://github.com/SkynetRTN/MARS/blob/a6785aa/docs/working/master-continuation-plan.md)).
The rewrite dropped those IDs, so this table is now their only current
record. Each was rechecked against `193d117`.

| Scope | Earlier record | Current state | Revisit condition (as recorded) |
|---|---|---|---|
| MCP output schemas | MCP-02 | Not declared. Structured results normalize non-finite numbers, bytes and errors. | A host benefit justifies them. Then validate every normalized success and error class against actual host handling. |
| New transports: HTTP MCP, shared service | §8 | stdio only. | A sponsored hosted or classroom need, not a personal tunnel. Needs authentication, per-user isolation, cost ceilings, key and compute policy, and remote artifact and input contracts. |
| Browser hosting | §8, PR #97, [mcp-desktop-hosts.md](mcp-desktop-hosts.md) | Parked. | As for HTTP MCP. |
| Local catalog backend | CAP-01 | Unextracted. `extraction.md` records Skynet's PostGIS backend commits. M4's `MARS_CATALOG_DIR` is plate-solving index and catalog data, not this. | A concrete local-catalog need, licence and provenance review, an optional dependency, and query-binding tests. |
| New timing capabilities | CAP-02 | Absent: no period uncertainty or barycentric correction. | Timing requirements, time-frame metadata, and validation against a trustworthy timing reference. |
| External Skynet review | §7, EXT-SKY-01–12, [obs-report.md](obs-report.md) | Excluded; `obs-report.md` carries the cross-reference. | A pinned upstream revision and an upstream owner, before any claim is treated as a bug. |

The pre-rewrite §8 also deferred the following. The current plan no longer
names them, so they are retained here with their conditions:

| Earlier record | Current state | Revisit condition |
|---|---|---|
| CAP-03: artifacts as MCP resources | The server serves only `mars://skill/…` documents. | A supported host without filesystem tools needs them. Define authorization, size and lifetime first. |
| CAP-04: an external agent as a model backend | Four adapters plus replay; none is an agent. | A needed provider or harness use case, with protocol and trajectory contracts. |
| CAP-05: streaming in the other adapters | Only Anthropic streams; OpenAI, Gemini and Ollama declare `streaming=False`. | A concrete latency or UI requirement. Test cancellation, text and tool assembly, and usage accounting. |
| CAP-06: richer result envelopes, shared services | `tool-architecture.md` §4 still presents the richer `ToolResult` as a future shape. | Several actual tools need the contract, with a caller migration and a measured benefit. |
| Dedispersion, browser audio | Inputs are single-band continuum; the browser audio graph was never ported. | Suitable data and product requirements. |
| Provider base classes, replacing database tools, wholesale orchestration | Rejected in [applicable-designs.md](applicable-designs.md). | The recorded architectural constraints change. |
| Benchmark price table | Declined in the model-backend archive. | None scheduled. |

## Reproducing

The shadowing and HR probes need only a wheel install and a scratch
directory:

```bash
uv build --wheel -o dist && uv venv /tmp/w && uv pip install --python /tmp/w/bin/python dist/*.whl
mkdir -p /tmp/p/tools && touch /tmp/p/tools/__init__.py
cd /tmp/p && /tmp/w/bin/python -c 'from tools.pulsar import list_pulsar_scans'
```

Build the wheel from a fresh clone (`releasing.md`): a stale `build/lib`
can carry retired modules.
