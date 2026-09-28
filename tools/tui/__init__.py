"""MARS's Textual research-console interface."""

from __future__ import annotations

import sys


def launch() -> int:
    """The ``mars`` console script: load ``.env``, then start the console.

    ``tools.config`` fixes its settings at import (``MARS_ARTIFACT_DIR``,
    ``MARS_DATA_DIR``, ``MARS_ISOCHRONE_DIR``, ...), and the console's own
    module imports it. Pointing the script at ``tools.tui.__main__:main`` meant
    that import ran first and a setting kept in ``.env`` was read, then
    ignored. ``tools.dotenv`` resolves nothing at import, so it goes first.
    """

    from tools.dotenv import load_dotenv
    from tools.paths import pin_numba_cache

    load_dotenv()
    # Printed before the console takes the screen, and so seen on exit.
    from tools.compat import adopt_legacy_environment, legacy_home_notice

    for legacy in adopt_legacy_environment():
        print(f"mars: {legacy.message()}", file=sys.stderr)
    notice = legacy_home_notice()
    if notice:
        print(f"mars: {notice}", file=sys.stderr)
    pin_numba_cache()
    from tools.tui.__main__ import main

    return main()
