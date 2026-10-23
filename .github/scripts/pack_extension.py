#!/usr/bin/env python3
"""Pack the Claude Desktop extension into a ``.mcpb`` with the standard library.

Run by the release workflow (docs/releasing.md). A ``.mcpb`` is a zip of the
extension folder; ``mcpb pack`` makes the same thing, but would run npm's
unlocked dependency tree on the bytes users install, so the release packs here
and runs ``mcpb validate`` only in a job whose output nothing uses.

Packs every file under the folder except ``.mcpbignore`` itself and what it
lists, as ``mcpb pack`` does: a pattern ending in ``/`` excludes a directory
anywhere in the tree, any other pattern is matched against each name. The
archive is deterministic: sorted entries, a fixed timestamp and mode.

Usage: pack_extension.py SOURCE_DIR OUTPUT.mcpb
"""

from __future__ import annotations

import fnmatch
import sys
import zipfile
from pathlib import Path

IGNORE_FILE = ".mcpbignore"
TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def packed_files(source: Path) -> list[Path]:
    patterns = (source / IGNORE_FILE).read_text(encoding="utf-8").split()
    directories = [p.rstrip("/") for p in patterns if p.endswith("/")]
    names = [p for p in patterns if not p.endswith("/")]
    files = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if relative.as_posix() == IGNORE_FILE:
            continue
        if any(fnmatch.fnmatch(part, d) for part in relative.parts[:-1] for d in directories):
            continue
        if any(fnmatch.fnmatch(relative.name, n) or fnmatch.fnmatch(relative.as_posix(), n) for n in names):
            continue
        files.append(relative)
    return files


def pack(source: Path, output: Path) -> list[Path]:
    files = packed_files(source)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in files:
            info = zipfile.ZipInfo(relative.as_posix(), date_time=TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (source / relative).read_bytes())
    return files


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    for relative in pack(Path(argv[0]), Path(argv[1])):
        print(relative.as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
