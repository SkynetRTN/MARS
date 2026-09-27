"""Kepler's environment variables and home, honoured for one pre-release.

Kepler was renamed MARS in ``0.1.0rc3`` (``docs/working/mars-rebrand.md``
§6.3). Every setting is now ``MARS_*`` and the per-user home is ``mars``. A
user who configured Kepler keeps a working install for that one pre-release:

- :func:`adopt_legacy_environment` copies each ``KEPLER_X`` into ``MARS_X``
  when ``MARS_X`` is unset, so every reader needs to know only the new name.
  A ``KEPLER_X`` whose twin is set is ignored, and reported as ignored.
- :func:`legacy_home_notice` points out a ``kepler`` home left beside a
  ``mars`` home that does not exist yet. Nothing is ever moved: a fetched
  bundle is hundreds of megabytes of the user's disk, and where it goes is
  the user's decision.

Adoption runs in each entry point right after ``.env`` is loaded -- so a
``.env`` still written with ``KEPLER_*`` works too -- and before anything
reads a setting; ``tools.config`` runs it again at import, silently, for code
that uses the tools as a library. It is idempotent. All of this is removed in
the release after ``0.1.0rc3``.

Nothing here is resolved at import, like :mod:`tools.paths`, which
:mod:`tools.mcp.roots` imports before the roots are pinned.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, MutableMapping

from tools.aliases import REMOVED_AFTER
from tools.paths import MARS_HOME_ENV, mars_home, user_data_base

__all__ = [
    "LEGACY_HOME_NAME",
    "LEGACY_PREFIX",
    "PREFIX",
    "LegacyVariable",
    "adopt_legacy_environment",
    "legacy_home_notice",
]

LEGACY_PREFIX = "KEPLER_"
PREFIX = "MARS_"
LEGACY_HOME_NAME = "kepler"


@dataclass(frozen=True)
class LegacyVariable:
    """One ``KEPLER_*`` variable found in the environment, and what became of it."""

    legacy: str
    current: str
    adopted: bool

    def message(self) -> str:
        if self.adopted:
            return (
                f"{self.legacy} is deprecated; read as {self.current}. Rename it: "
                f"the old name is ignored after {REMOVED_AFTER}."
            )
        return f"{self.legacy} is ignored because {self.current} is set; remove it."


def adopt_legacy_environment(
    environ: MutableMapping[str, str] | None = None,
) -> tuple[LegacyVariable, ...]:
    """Copy each non-empty ``KEPLER_X`` into an unset or empty ``MARS_X``.

    Returns every ``KEPLER_*`` variable found, adopted or not, in name order,
    for the caller to report. Values are never returned. The ``KEPLER_*``
    variables themselves are left in place.
    """

    environ = os.environ if environ is None else environ
    found: list[LegacyVariable] = []
    for legacy in sorted(name for name in environ if name.startswith(LEGACY_PREFIX)):
        value = environ[legacy]
        if not value:
            continue
        current = PREFIX + legacy[len(LEGACY_PREFIX) :]
        existing = environ.get(current)
        if existing and existing != value:
            found.append(LegacyVariable(legacy, current, adopted=False))
            continue
        environ[current] = value
        found.append(LegacyVariable(legacy, current, adopted=True))
    return tuple(found)


def legacy_home_notice(
    environ: Mapping[str, str] | None = None,
    *,
    platform: str | None = None,
    home: Path | None = None,
) -> str | None:
    """What to say about a leftover ``kepler`` home, or ``None``.

    Only for the default location: a ``MARS_HOME`` (or an adopted
    ``KEPLER_HOME``) is the user's own choice and is never second-guessed.
    Silent once the ``mars`` home exists, whatever it holds -- and the first
    ``mars-mcp`` start creates it, so the notice is given once. Call this
    before anything writes into the home.
    """

    environ = os.environ if environ is None else environ
    if environ.get(MARS_HOME_ENV, "").strip():
        return None
    base = user_data_base(environ, platform=platform, home=home)
    if base is None:
        return None
    legacy = base / LEGACY_HOME_NAME
    current = mars_home(environ, platform=platform, home=home)
    if not legacy.is_dir() or current.exists():
        return None
    return (
        f"found {legacy}, the home of an earlier Kepler install, and no {current}. "
        f"Nothing was moved. To keep its artifacts, downloads and fetched bundles, "
        f"rename that directory to {current}, or set {MARS_HOME_ENV} to it."
    )

