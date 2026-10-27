"""The MARS launcher: the newest ``mars-mcp`` on PyPI, over stdio.

Claude Desktop runs this file as the extension's entry point, and the Codex
plugin runs the same source with ``uv run python -c`` (its ``.mcp.json``
carries a copy, which a test keeps identical). Neither pins a MARS release.
This file has no dependencies, so it starts instantly; it then runs
``mars-mcp`` through ``uv tool run`` (``uvx``), in uv's own cache:

1. **Refresh**: ``--from "skynet-mars[mcp]@latest"`` asks PyPI for the newest
   release and installs it into uv's cache if it is not there yet, then
   prints that release's version. Its stdout is captured here and uv's
   output goes to stderr, so neither reaches stdout, the MCP stream.
2. **Serve**: ``--offline``, naming that version, starts exactly that
   release. It must name it: given the bare name, uv prefers a
   ``uv tool install`` of MARS, however old, over the cache. With no
   network, step 1 is repeated offline, which finds the newest release in
   the cache; only with none cached does the bare name start whatever is
   installed.

**Rollback.** ``MARS_VERSION`` (the extension's *MARS release* setting) pins
one release instead: both steps then name exactly that version, so a bad
release can be stepped back from without reinstalling anything. Empty means
the newest. A value that is not a version stops here with a message rather
than silently serving the newest.

uv is whichever binary ran this file: ``uv run`` names it in ``UV``. Every
uv call passes ``--no-config``: the host may start this in any folder, and a
``uv.toml`` there must not choose the index MARS is installed from. (uv's
``UV_*`` environment variables still apply.)

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
import re
import shutil
import subprocess
import sys

OPTIONAL_SETTINGS = ("ADS_DEV_KEY", "MARS_MCP_TOOLS", "MARS_HOME", "MARS_VERSION")

#: A release as PyPI names one (PEP 440's characters), never a specifier.
VERSION = re.compile(r"[0-9][0-9A-Za-z.!+-]*")

#: The one Python every MARS dependency ships wheels for (docs/installing.md).
PYTHON = "3.13"
REQUIREMENT = "skynet-mars[mcp]"

#: Step 1's program: print the release uv fetched, the only line on stdout.
PRINT_VERSION = "import importlib.metadata as m; print(m.version('skynet-mars'))"


def drop_unset(environ):
    for name in OPTIONAL_SETTINGS:
        value = environ.get(name)
        if value is not None and (not value.strip() or value.startswith("${")):
            del environ[name]


def uv_binary(environ):
    return environ.get("UV") or shutil.which("uv") or "uv"


def requirements(pin=None):
    """What step 1 fetches and step 2 serves: the newest, or the pinned one."""
    if pin:
        return f"{REQUIREMENT}=={pin}", f"{REQUIREMENT}=={pin}"
    return f"{REQUIREMENT}@latest", REQUIREMENT


def refresh_command(uv, pin=None, offline=False):
    """Fetch the release into uv's cache and print its version; runs nothing of MARS's.

    Offline it fetches nothing: ``@latest`` then names the newest release cached."""
    fetch, _ = requirements(pin)
    network = ["--offline"] if offline else []
    return [uv, "tool", "run", "--no-config", *network, "--python", PYTHON, "--from", fetch, "python", "-I", "-c", PRINT_VERSION]


def fetched_version(run, command, environ):
    """The version step 1 printed, or None when it failed."""
    done = run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True, env=environ)
    version = (done.stdout or "").strip()
    return version if done.returncode == 0 and VERSION.fullmatch(version) else None


def serve_command(uv, args, pin=None):
    _, serve = requirements(pin)
    return [uv, "tool", "run", "--no-config", "--offline", "--python", PYTHON, "--from", serve, "mars-mcp", *args]


def main(args, environ=os.environ, run=subprocess.run, execv=os.execv):
    drop_unset(environ)
    pin = environ.get("MARS_VERSION", "").strip() or None
    if pin is not None and not VERSION.fullmatch(pin):
        print(f"mars: MARS_VERSION={pin!r} is not an exact release number; leave it empty for the newest.", file=sys.stderr)
        return 2
    uv = uv_binary(environ)
    fetched = fetched_version(run, refresh_command(uv, pin), environ)
    if fetched:
        pin = fetched
    elif pin:
        print(f"mars: could not fetch release {pin}; starting it from uv's cache if it was fetched before.", file=sys.stderr)
    else:
        print("mars: could not reach PyPI for the newest release; starting the newest one on this machine.", file=sys.stderr)
        pin = fetched_version(run, refresh_command(uv, offline=True), environ)
    command = serve_command(uv, args, pin)
    if os.name == "posix":
        # Replace this process, so the host's signals reach mars-mcp directly.
        execv(command[0] if os.path.isabs(command[0]) else shutil.which(command[0]) or command[0], command)
    return run(command, env=environ).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
