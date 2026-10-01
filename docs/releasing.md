# Releasing MARS

How a MARS (MCP Astronomy Research Suite) release is cut, what its version means, and how the optional data
bundles are published and matched to it. The workflow is
`.github/workflows/release.yml`. Installing a release is `installing.md`.

## Versions and tags

- **`pyproject.toml`'s `version` is the version.** A release is the tag
  `v<version>`, exactly: `v0.1.0rc1` for `0.1.0rc1`. The workflow refuses a
  tag that does not match, so a wheel never carries a version its tag
  contradicts.
- **A pre-release** is a [PEP 440](https://peps.python.org/pep-0440/)
  pre-release version: `aN`, `bN`, `rcN` or `.devN`. It is published as a
  GitHub pre-release, for testing — no compatibility promise between one and
  the next. Anything else is published as a release and marked latest.
- **Bump the version, relock, merge, then tag.** Change `version`, run
  `uv lock` (the lockfile records the project's own version), merge that
  change, and push the tag at the merged commit.

**Build from a checkout with symlinks.** The core data reaches the wheel
through the committed `tools/_data` symlink. A clone made with
`core.symlinks=false` (Git for Windows' default) builds a wheel with no data,
and the workflow refuses to publish one.

## What the workflow does

On a `v*` tag push (or `workflow_dispatch`, which runs everything except
the publishing jobs, as a dry run):

1. **build**:
   - checks the tag against the version;
   - rebuilds `data/optical/` and fails unless it matches `tools/mcp/bundles.json`;
   - builds the wheel and the sdist, and writes `SHA256SUMS`;
   - fails unless the wheel carries the scans, periods, zero-point reference,
     variable-star sample, Afterglow fixtures, skill and bundle manifest;
   - classifies the version with `packaging.version`, so every PEP 440
     pre-release spelling publishes as a pre-release.
2. **verify** runs on a clean runner **with no checkout**, on Python 3.13 --
   MARS's version, and the newest Python every dependency ships wheels for. It
   installs the wheel with `[mcp]` and runs
   `mars-mcp self-test`. That launches the installed server over stdio and
   detects B0329+54 from a measured period through the protocol.
3. **data** checks that the `data` release holds every archive
   `bundles.json` pins, at the pinned size and SHA-256. It reads GitHub's own
   asset digest.
4. **verify-data** installs the wheel without a checkout, fetches both
   optional bundles, rehashes their extracted trees, and runs
   `mars-mcp self-test --with-data` through stdio and the local grid loader.
5. **publish** creates the GitHub release with the wheel, the sdist and
   `SHA256SUMS`, only after **verify**, **data** and **verify-data** pass. It is the only job
   with write permission to the repository, and only on a tag.
6. **publish to TestPyPI** uploads the wheel and the sdist to TestPyPI, after
   the same build and verification jobs pass.
7. **verify the TestPyPI upload** downloads the wheel TestPyPI serves,
   requires it to be byte-identical to the one **build** made, installs it
   with its dependencies from PyPI -- never from TestPyPI, where anyone can
   register a dependency's name -- and runs `mars-mcp self-test`.
8. **publish to PyPI** refuses a wheel that declares no licence, then
   uploads. It runs in the `pypi` environment, so it waits for a reviewer.

The build job and CI's `package` job, which runs on every pull request, both
run `twine check --strict` and `.github/scripts/check_dist.py`: the core data,
the package data the server reads, and nothing that must not ship.

`secret-scan.yml` and `workflow-safety.yml` (actionlint, zizmor) run on the
pull request that changes any workflow, this one included.

## Publishing to PyPI

The distribution is `skynet-mars` on [PyPI](https://pypi.org/project/skynet-mars/)
and [TestPyPI](https://test.pypi.org/project/skynet-mars/). Uploads use
[trusted publishing](https://docs.pypi.org/trusted-publishers/): PyPI trusts
this repository's release workflow directly, so no API token is stored in the
repository or its secrets.

**A PyPI version is permanent.** A file, once uploaded, can never be replaced,
even after deletion; a mistake is fixed only by a new version. That is why
every release goes through TestPyPI first, and why PyPI waits for a reviewer.
A tag that has already been published to GitHub cannot be reused either:
`v0.1.0rc3` predates this workflow, so the first index upload is the next
version.

### One-time setup (the maintainer, on the web)

The licence the upload gate asks for is in place: `GPL-3.0-only`, declared in
`pyproject.toml` with the `LICENSE` file (README, *License*). Two more steps,
both mirroring Skycat's (`SkynetRTN/skycat`):

1. **Pending trusted publishers**, one on each index, added from the account
   that holds the projects -- the package author's -- on
   [pypi.org](https://pypi.org/manage/account/publishing/) and
   [test.pypi.org](https://test.pypi.org/manage/account/publishing/)
   (separate accounts, separate registrations):

   | Field | PyPI | TestPyPI |
   | --- | --- | --- |
   | PyPI project name | `skynet-mars` | `skynet-mars` |
   | Owner | `SkynetRTN` | `SkynetRTN` |
   | Repository name | `MARS` | `MARS` |
   | Workflow name | `release.yml` | `release.yml` |
   | Environment name | `pypi` | `testpypi` |

   A pending publisher reserves the name until the first upload creates the
   project. The owner and repository are the ones the workflow runs under,
   `SkynetRTN/MARS` since the transfer; a publisher registered under an
   earlier owner or name (`archon774/...`) would never match.
2. **Two GitHub environments** (Settings → Environments on `SkynetRTN/MARS`),
   named exactly as the workflow names them:

   | Setting | `testpypi` | `pypi` |
   | --- | --- | --- |
   | Required reviewers | none: a tag's rehearsal upload runs unattended | the maintainers who may release; **at least one** |
   | Prevent self-review | -- | optional; on means the person who pushed the tag cannot approve |
   | Wait timer | none | none |
   | Allow administrators to bypass | -- | **off**, so an admin cannot skip the review |
   | Deployment branches and tags | **Selected branches and tags**, one tag rule `v*` | the same, tag rule `v*` |
   | Environment secrets | none (trusted publishing needs none) | none |

   The `v*` tag rule means only a release tag can deploy to either index; the
   reviewers are what makes PyPI wait for a person.

### Cutting a release to the indexes

The same as any release (*Versions and tags*): bump `version`, `uv lock`,
merge, tag the merged commit. The workflow then publishes to GitHub and
TestPyPI, verifies the TestPyPI upload, and waits for approval of the `pypi`
environment. Approve it from the run's page once the TestPyPI job is green.
The first release published this way was `0.1.0rc4`, on 2026-09-28.

## The data release

The two optional bundles are too large for a wheel. They are assets of one
standing GitHub release tagged **`data`**:

| Bundle | Source | Archive |
| --- | --- | --- |
| `optical` | `data/optical/` in this repository (Git LFS pulled) | `kepler-optical-<sha12>.tar` |
| `isochrones` | the operator's Girardi grid, `.npy` files only | `kepler-isochrones-<sha12>.tar` |

**A bundle's version is its content.** Archives are deterministic plain
`.tar` (sorted members, fixed mode, owner and mtime), named by the first 12
hex digits of their SHA-256. The same tree always builds the same file and the
same name.

**A wheel pins its bundles.** `tools/mcp/bundles.json` ships inside the wheel
and records each archive's name, size and SHA-256. `mars-mcp fetch-data`
downloads that exact archive from the `data` release and rejects any other
bytes. That is how an installed MARS resolves "which bundle matches me",
with no version negotiation. Old archives stay on the `data` release, so an
older wheel keeps fetching the bundle it was built with.

**Changing a bundle:**

```bash
python -m tools.mcp.bundles optical data/optical dist/bundles
python -m tools.mcp.bundles isochrones /path/to/girardi dist/bundles --include '*.npy'
```

Each prints its manifest entry. Then:

1. Paste the entry into `bundles.json`, with `url` set to
   `https://github.com/SkynetRTN/MARS/releases/download/data/<archive>`.
2. Upload the archive: `gh release upload data dist/bundles/<archive>`.
3. Ship the manifest change in the next release.

Never replace an existing asset: a published name always means the same
bytes. `--check` on the build command fails unless the build is exactly the
shipped entry. The workflow runs it for `optical`; `isochrones` is built from
outside the repository, so run it by hand.

## Testing a release

On a machine with no checkout (and a C compiler unless it is Python 3.13 on
x86_64 Linux, macOS or Windows; see `installing.md`):

```bash
python3.13 -m venv mars-env
mars-env/bin/pip install "skynet-mars[mcp]==<version>"
mars-env/bin/mars-mcp self-test
mars-env/bin/mars-mcp fetch-data optical      # optional
```

Then register `mars-env/bin/mars-mcp` with a host (`installing.md`) and
run a pulsar task through it.
