"""``mars-mcp``: serve MARS's tools to a host over stdio.

The order in :func:`main` is the point of this module. A checkout's ``.env``
is loaded first, then the roots are pinned into the environment, and only then
is anything imported that reads ``tools.config`` -- whose settings are fixed at
import, so a ``.env`` loaded any later is read and ignored. Logging goes to
stderr, because stdout is the protocol.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from tools.mcp.roots import pin_roots
from tools.paths import pin_numba_cache

log = logging.getLogger("mars-mcp")


def _missing_sdk_message() -> str:
    """How to add the SDK: this interpreter's pip, and this exact version.

    ``skynet-mars`` is on PyPI, so the extra can be installed by name -- but
    a bare ``pip install`` may be a different environment's pip, and an
    unpinned requirement may upgrade or downgrade the install it is meant to
    complete. So the advice names ``sys.executable`` and the installed
    version. (Before the rename the bare command was a trap: the PyPI project
    called ``kepler`` is unrelated, and ``-U`` replaced this install with it.)
    """

    from importlib.metadata import PackageNotFoundError, version

    try:
        requirement = f"skynet-mars[mcp]=={version('skynet-mars')}"
    except PackageNotFoundError:
        requirement = "skynet-mars[mcp]"
    return (
        "mars-mcp needs its optional [mcp] dependencies. From a checkout, run "
        "`uv sync --extra mcp`. From an install, add them with this environment's "
        f"pip: `{sys.executable} -m pip install \"{requirement}\"` "
        "(see docs/installing.md)."
    )


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    # First, for every subcommand. fetch-data and self-test import
    # tools.config too, and a checkout's .env can move the MARS home or name
    # a bundle mirror: loaded only for the server, the fetch installed into
    # one home and the server read another. The real environment still wins
    # over the file.
    from tools.dotenv import DOTENV_PATH, load_dotenv

    loaded = load_dotenv()
    pin_numba_cache()

    if argv[:1] == ["fetch-data"]:
        # Installs optional data bundles; serves nothing, needs no SDK.
        from tools.mcp.bundles import fetch_main

        return fetch_main(argv[1:])
    if argv[:1] == ["self-test"]:
        # Launches this install's own server over stdio and checks it end to end.
        from tools.mcp.selftest import main as self_test

        return self_test(argv[1:])
    if argv[:1] == ["install-skill"]:
        from pathlib import Path

        from tools.skill import install_native_skill

        skill_parser = argparse.ArgumentParser(prog="mars-mcp install-skill")
        skill_parser.add_argument("target", type=Path, help="Explicit path to the mars-tools skill directory.")
        skill_args = skill_parser.parse_args(argv[1:])
        try:
            installed = install_native_skill(skill_args.target)
        except (FileExistsError, OSError) as exc:
            skill_parser.error(str(exc))
        print(f"mars-tools skill {'installed at' if installed else 'already current at'} {skill_args.target.expanduser()}")
        return 0

    parser = argparse.ArgumentParser(
        prog="mars-mcp",
        description=(
            "Serve MARS's astronomy tools over MCP on stdio. A host launches "
            "this; it is not run by hand. Artifacts go to MARS_ARTIFACT_DIR, "
            "default a per-user directory, and the resolved roots are logged to "
            "stderr at startup. `mars-mcp fetch-data` installs the optional "
            "data bundles; `mars-mcp self-test` checks this install."
        ),
    )
    parser.add_argument(
        "--tools",
        metavar="GROUPS",
        help=(
            "Serve only these comma-separated tool groups (default: all 55 tools; "
            "also MARS_MCP_TOOLS). Groups: databases, optical, timeseries, hr, "
            "radio."
        ),
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        stream=sys.stderr, level=logging.INFO, format="mars-mcp: %(message)s"
    )

    # Every tool call runs on a worker thread, and on macOS matplotlib's
    # automatic backend refuses to create a figure off the main thread. The
    # server draws only to files, so it never needs a GUI backend. A user's own
    # MPLBACKEND still wins.
    os.environ.setdefault("MPLBACKEND", "Agg")

    if "tools.config" in sys.modules:
        raise RuntimeError("tools.config was imported before the roots were pinned")
    roots = pin_roots()

    # The group filter is checked before the SDK is imported, so a typo in a
    # host's configuration is reported as itself wherever it happens.
    from tools.mcp import groups

    try:
        selected = (
            groups.parse_groups(args.tools)
            if args.tools is not None
            else groups.groups_from_environment()
        )
    except ValueError as exc:
        parser.error(str(exc))
    schemas = groups.tools_in_groups(selected)

    try:
        import anyio

        from tools.mcp.server import build_server, serve_stdio
    except ImportError as exc:
        if exc.name in {"mcp", "mcp_types", "jsonschema"}:
            print(_missing_sdk_message(), file=sys.stderr)
            return 2
        raise

    from tools import config
    from tools.mcp import surface

    log.info("artifact root: %s (%s)", config.ARTIFACT_DIR, roots.artifact_source)
    log.info("data root: %s (%s)", config.DATA_DIR, roots.data_source)
    log.info("download root: %s", config.FITS_DOWNLOAD_DIR)
    log.info(
        "isochrone grid: %s",
        config.ISOCHRONE_DIR or "not set (MARS_ISOCHRONE_DIR); the isochrone fit is unavailable",
    )
    if loaded:
        log.info("read from %s: %s", DOTENV_PATH, ", ".join(loaded))
    for group in groups.GROUPS:
        if selected is None or group.name in selected:
            log.info("group %s: %s", group.name, group.description)
    server = build_server(schemas)
    log.info(
        "serving %d tools and %d skill resources over stdio; instructions %d characters",
        len(schemas),
        len(surface.served_resources()),
        len(server.instructions or ""),
    )

    anyio.run(serve_stdio, server)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
