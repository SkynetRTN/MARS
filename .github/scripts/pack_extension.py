#!/usr/bin/env python3
"""Pack the Claude Desktop extension into a ``.mcpb`` with the standard library.

Run by the release workflow (docs/releasing.md). A ``.mcpb`` is a zip of the
extension folder; ``mcpb pack`` makes the same thing, but would run npm's
unlocked dependency tree on the bytes users install, so the release packs here
and runs ``mcpb validate`` only in a job whose output nothing uses.

Packs every file under the folder except what ``mcpb pack`` always leaves
out (:data:`DEFAULT_EXCLUDES`: ``.env*``, ``.git``, ``.DS_Store``, older
``.mcpb`` files and the like), ``.mcpbignore`` itself, and what it lists, one
pattern per line; blank lines and ``#`` comments are skipped. Both lists
are matched as one ``.gitignore`` (see :func:`_rule`), as mcpb's ``ignore``
package matches them, so a name without a slash excludes a file or a whole
directory at any depth. ``!`` negations are refused rather than ignored,
since packing what ``mcpb pack`` would leave out (or the reverse) changes
the bytes users install. The archive is deterministic on every host:
sorted entries, a fixed timestamp, mode and creating system.

Usage: pack_extension.py SOURCE_DIR OUTPUT.mcpb
"""

from __future__ import annotations

import os
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

IGNORE_FILE = ".mcpbignore"
TIMESTAMP = (1980, 1, 1, 0, 0, 0)

#: ``mcpb pack``'s own excludes, applied before ``.mcpbignore`` as it does:
#: ``EXCLUDE_PATTERNS`` in ``@anthropic-ai/mcpb`` 2.1.2's
#: ``dist/node/files.js``. As in a ``.gitignore``, a pattern with no slash
#: matches a file or directory of that name at any depth.
DEFAULT_EXCLUDES = (
    ".DS_Store", "Thumbs.db", ".gitignore", ".git", ".mcpbignore", "*.log",
    ".env*", ".npm", ".npmrc", ".yarnrc", ".yarn", ".eslintrc",
    ".editorconfig", ".prettierrc", ".prettierignore", ".eslintignore",
    ".nycrc", ".babelrc", ".pnp.*", "node_modules/.cache",
    "node_modules/.bin", "*.map", ".env.local", ".env.*.local",
    "npm-debug.log*", "yarn-debug.log*", "yarn-error.log*",
    "package-lock.json", "yarn.lock", "*.mcpb", "*.d.ts", "*.tsbuildinfo",
    "tsconfig.json",
)


def read_patterns(source: Path) -> list[str]:
    """The folder's ``.mcpbignore`` patterns; none when it has no file, as
    ``mcpb pack`` allows."""
    ignore = source / IGNORE_FILE
    if not ignore.is_file():
        return []
    patterns = []
    for line in ignore.read_text(encoding="utf-8").splitlines():
        pattern = line.strip()
        if not pattern or pattern.startswith("#"):
            continue
        if pattern.startswith("!"):
            raise ValueError(f"{IGNORE_FILE}: negation is not supported: {pattern}")
        patterns.append(pattern)
    return patterns


def _rule(pattern: str) -> tuple["re.Pattern[str]", bool]:
    """One pattern, with ``.gitignore``'s meaning, as mcpb's ``ignore``
    package gives it: a trailing ``/`` matches directories only; a slash at
    the start or in the middle anchors the pattern to the folder root, and
    without one it matches a name at any depth; ``*`` and ``?`` never match
    ``/``; ``**`` matches across directories; matching is case-sensitive on
    every host. Returns the compiled pattern and whether it is directory-only.
    """
    directory_only = pattern.endswith("/")
    body = pattern.strip("/")
    anchored = pattern.startswith("/") or "/" in body
    out, i = [], 0
    while i < len(body):
        if body.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif body.startswith("**", i):
            out.append(".*")
            i += 2
        elif body[i] == "*":
            out.append("[^/]*")
            i += 1
        elif body[i] == "?":
            out.append("[^/]")
            i += 1
        elif body[i] == "[" and "]" in body[i + 2:]:
            end = body.index("]", i + 2)
            inner = body[i + 1:end]
            out.append("[" + ("^" + inner[1:] if inner.startswith("!") else inner) + "]")
            i = end + 1
        else:
            out.append(re.escape(body[i]))
            i += 1
    return re.compile(("" if anchored else "(?:.*/)?") + "".join(out) + r"\Z"), directory_only


def _excluded(relative: PurePosixPath, rules, *, is_dir: bool) -> bool:
    """Whether a path, or a directory above it, matches a rule. A matched
    directory excludes everything under it."""
    parts = relative.parts
    directories = ["/".join(parts[:depth]) for depth in range(1, len(parts))]
    if is_dir:
        directories.append("/".join(parts))
    for regex, directory_only in rules:
        if any(regex.match(path) for path in directories):
            return True
        if not is_dir and not directory_only and regex.match("/".join(parts)):
            return True
    return False


def packed_files(source: Path) -> list[Path]:
    """The files ``mcpb pack`` packs: everything but its own excludes and
    the folder's ``.mcpbignore``, matched as one ``.gitignore``. Excluded
    directories are not walked."""
    rules = [_rule(pattern) for pattern in (*DEFAULT_EXCLUDES, *read_patterns(source))]
    files = []
    for directory, subdirectories, names in os.walk(source):
        here = PurePosixPath(Path(directory).relative_to(source).as_posix())
        subdirectories[:] = [
            name for name in subdirectories if not _excluded(here / name, rules, is_dir=True)
        ]
        for name in names:
            relative = here / name
            if (Path(directory) / name).is_file() and not _excluded(relative, rules, is_dir=False):
                files.append(Path(relative))
    return sorted(files)


def pack(source: Path, output: Path) -> list[Path]:
    files = packed_files(source)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in files:
            info = zipfile.ZipInfo(relative.as_posix(), date_time=TIMESTAMP)
            info.create_system = 3  # Unix, whichever host packs: the same bytes everywhere
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
