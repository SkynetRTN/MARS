"""Entry point Claude Desktop runs: the newest ``mars-mcp`` on PyPI, over stdio.

The extension pins no MARS release. This file has no dependencies, so the
environment Claude Desktop builds for it is empty and instant; it then runs
``mars-mcp`` through ``uv tool run`` (``uvx``), in uv's own cache:

1. **Refresh**: ``--from "skynet-mars[mcp]@latest"`` asks PyPI for the newest
   release and installs it into uv's cache if it is not there yet. Its output
   goes to stderr, never to stdout, which is the MCP stream.
2. **Serve**: ``--offline --from "skynet-mars[mcp]"`` starts the newest
   release in the cache. After step 1 that is the latest; with no network,
   step 1 fails and the last release that was fetched still starts.

uv is whichever binary ran this file: ``uv run`` names it in ``UV``.

The manifest maps each optional ``user_config`` field to an environment
variable. A field the user left empty can arrive as an empty string, or as
the unexpanded ``${user_config...}`` placeholder; which one is undocumented.
Both are removed here, before ``mars-mcp`` reads anything. Two of them
matter: an unexpanded ``MARS_MCP_TOOLS`` stops ``mars-mcp`` at startup
("unknown tool group(s)"), and an empty ``ADS_DEV_KEY`` stops astroquery
from reading ``~/.ads/dev_key``. ``mars-mcp`` already treats an empty
``MARS_HOME`` or ``MARS_MCP_TOOLS`` as unset; removing them too keeps one rule.
"""

import os
import shutil
import subprocess
import sys

OPTIONAL_SETTINGS = ("ADS_DEV_KEY", "MARS_MCP_TOOLS", "MARS_HOME")

#: The one Python every MARS dependency ships wheels for (docs/installing.md).
PYTHON = "3.13"
REQUIREMENT = "skynet-mars[mcp]"


def drop_unset(environ):
    for name in OPTIONAL_SETTINGS:
        value = environ.get(name)
        if value is not None and (not value.strip() or value.startswith("${")):
            del environ[name]


def uv_binary(environ):
    return environ.get("UV") or shutil.which("uv") or "uv"


def refresh_command(uv):
    """Fetch the newest release into uv's cache; runs nothing of MARS's."""
    return [uv, "tool", "run", "--python", PYTHON, "--from", f"{REQUIREMENT}@latest", "python", "-c", "pass"]


def serve_command(uv, args):
    return [uv, "tool", "run", "--offline", "--python", PYTHON, "--from", REQUIREMENT, "mars-mcp", *args]


def main(args, environ=os.environ, run=subprocess.run, execv=os.execv):
    drop_unset(environ)
    uv = uv_binary(environ)
    refreshed = run(refresh_command(uv), stdin=subprocess.DEVNULL, stdout=sys.stderr, env=environ)
    if refreshed.returncode != 0:
        print("mars: could not reach PyPI for the newest release; starting the last one fetched.", file=sys.stderr)
    command = serve_command(uv, args)
    if os.name == "posix":
        # Replace this process, so the host's signals reach mars-mcp directly.
        execv(command[0] if os.path.isabs(command[0]) else shutil.which(command[0]) or command[0], command)
    return run(command, env=environ).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
