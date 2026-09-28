"""The Kepler command names, kept as deprecated aliases of the MARS ones.

Kepler was renamed MARS in ``0.1.0rc3`` (``docs/working/mars-rebrand.md``
§6.3). A host entry or a script written for ``kepler-mcp`` keeps working for
that one pre-release: each old command says its new name on stderr -- never
stdout, which is ``mars-mcp``'s protocol -- and then runs the new one
unchanged. All three are removed in the release after ``0.1.0rc3``.
"""

from __future__ import annotations

import sys

__all__ = ["kepler", "kepler_bench", "kepler_mcp"]

#: The last version that ships these aliases.
REMOVED_AFTER = "0.1.0rc3"


def _say(old: str, new: str) -> None:
    print(
        f"{old}: renamed to `{new}`; the `{old}` alias is removed in the release "
        f"after {REMOVED_AFTER}.",
        file=sys.stderr,
        flush=True,
    )


def kepler() -> int:
    """``kepler`` -> ``mars``."""
    _say("kepler", "mars")
    from tools.tui import launch

    return launch()


def kepler_mcp() -> int:
    """``kepler-mcp`` -> ``mars-mcp``."""
    _say("kepler-mcp", "mars-mcp")
    from tools.mcp.__main__ import main

    return main()


def kepler_bench() -> int:
    """``kepler-bench`` -> ``mars-bench``."""
    _say("kepler-bench", "mars-bench")
    from tools.bench.cli import main

    return main()
