#!/usr/bin/env python3
"""Check a built skynet-mars wheel before anything installs or uploads it.

Run by CI on every pull request and by the release workflow before each
publish (docs/releasing.md). ``twine check`` covers what an index would reject;
this covers what it would accept and then ship broken:

- the core data that reaches the wheel only through the ``tools/_data``
  symlink -- a clone without symlinks builds a wheel with none, silently;
- the package data the installed server reads: the bundle manifest, the
  skill source, the server icons;
- nothing that must never ship: tests, the fetched optical frame library,
  a ``.env``, compiled caches, or a top-level package other than ``tools`` and
  ``algorithms`` (a generic top-level name collides with other projects);
- with ``--require-license``, a declared licence. PyPI is permanent: a
  version uploaded without one cannot be replaced, only superseded.

Exits 1 and prints every problem, not just the first.
"""

from __future__ import annotations

import argparse
import email.parser
import re
import sys
import zipfile
from pathlib import Path

#: Files the installed package reads at run time, by exact path.
REQUIRED = (
    "tools/mcp/bundles.json",
    "tools/mcp/icons/mars-64.png",
    "tools/mcp/icons/mars-128.png",
    "tools/skill/source/SKILL.md",
    "tools/skill/source/BRIEF.md",
    "algorithms/skylib_lite/astrometry/anet/ngc2000.dat",
)

#: The five bundled pulsar scans the self-test detects from.
PULSAR_SCANS = re.compile(r"tools/_data/pulsar/[^/]+\.cal\.txt")
MIN_PULSAR_SCANS = 5

#: Never in a wheel.
FORBIDDEN = (
    re.compile(r"(^|/)__pycache__/"),
    re.compile(r"\.pyc$"),
    re.compile(r"(^|/)\.env$"),
    re.compile(r"^tests/"),
    re.compile(r"^tools/_data/optical/"),
    re.compile(r"^tools/_data/fits_downloads/"),
)

TOP_LEVEL = {"tools", "algorithms"}


def _metadata(archive: zipfile.ZipFile) -> email.message.Message | None:
    names = [n for n in archive.namelist() if re.fullmatch(r"[^/]+\.dist-info/METADATA", n)]
    if len(names) != 1:
        return None
    return email.parser.Parser().parsestr(archive.read(names[0]).decode("utf-8"))


def check_wheel(path: Path, *, require_license: bool = False) -> list[str]:
    """Every problem with the wheel at ``path``; empty when it is fit to ship."""

    problems: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        metadata = _metadata(archive)

    present = set(names)
    problems += [f"missing {name}" for name in REQUIRED if name not in present]

    scans = sum(1 for n in names if PULSAR_SCANS.fullmatch(n))
    if scans < MIN_PULSAR_SCANS:
        problems.append(
            f"{scans} bundled pulsar scans, want {MIN_PULSAR_SCANS}: build from a "
            "checkout with symlinks (tools/_data)"
        )

    problems += [f"must not ship {n}" for n in names if any(p.search(n) for p in FORBIDDEN)]

    top = {n.split("/", 1)[0] for n in names if "/" in n}
    stray = sorted(t for t in top - TOP_LEVEL if not t.endswith(".dist-info"))
    problems += [f"unexpected top-level directory {t}/" for t in stray]

    if metadata is None:
        problems.append("no single *.dist-info/METADATA")
    else:
        if metadata["Name"] != "skynet-mars":
            problems.append(f"distribution is {metadata['Name']!r}, not 'skynet-mars'")
        if require_license and not (
            metadata.get("License-Expression")
            or metadata.get("License-File")
            or metadata.get("License")
        ):
            problems.append(
                "no licence declared (License-Expression, License-File or License); "
                "PyPI uploads are permanent, so publishing waits for one"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("wheels", nargs="+", type=Path)
    parser.add_argument("--require-license", action="store_true")
    args = parser.parse_args(argv)

    status = 0
    for wheel in args.wheels:
        problems = check_wheel(wheel, require_license=args.require_license)
        for problem in problems:
            print(f"::error::{wheel.name}: {problem}")
        print(f"{wheel.name}: {'FAILED' if problems else 'ok'}")
        status |= bool(problems)
    return status


if __name__ == "__main__":
    sys.exit(main())
