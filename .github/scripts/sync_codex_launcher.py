#!/usr/bin/env python3
"""Copy the MARS launcher into the Codex plugin's ``.mcp.json``.

The Claude Desktop extension runs ``installers/claude-desktop/src/server.py``
as a file. The Codex plugin cannot run a file from its own directory -- Codex
replaces that directory while a server starts -- so its ``.mcp.json`` runs the
same code with ``uv run python -c``. This writes that argument: the file's
code, with its module docstring replaced by a one-line pointer, which keeps a
command line short. ``tests/test_codex_plugin.py`` fails when the two differ.

Usage: sync_codex_launcher.py [--check]
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "installers" / "claude-desktop" / "src" / "server.py"
MCP_JSON = ROOT / "installers" / "codex" / ".mcp.json"
POINTER = (
    "# The MARS launcher, copied from installers/claude-desktop/src/server.py "
    "by .github/scripts/sync_codex_launcher.py.\n"
)


def launcher_code(source: str) -> str:
    """The source with its module docstring replaced by :data:`POINTER`."""
    docstring = ast.parse(source).body[0]
    lines = source.splitlines(keepends=True)
    return POINTER + "".join(lines[docstring.end_lineno:]).lstrip("\n")


def rendered() -> str:
    config = json.loads(MCP_JSON.read_text(encoding="utf-8"))
    args = config["mcpServers"]["mars"]["args"]
    args[args.index("-c") + 1] = launcher_code(SOURCE.read_text(encoding="utf-8"))
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    text = rendered()
    if argv == ["--check"]:
        return 0 if MCP_JSON.read_text(encoding="utf-8") == text else 1
    MCP_JSON.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
