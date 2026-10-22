"""SIMBAD identifier resolution.

Turns a free-text identifier — ``"M31"``, ``"NGC 5286"``, ``"HD 209458"`` —
into sky coordinates plus a human-readable object type. This is name lookup,
not photometry: SIMBAD is a bibliographic database of objects, and the answer is
an identity and a position, not catalog rows. Callers wanting magnitudes go to
the photometric catalogs instead.

The object-type vocabulary lives in ``catalogs/simbad.py``; only the resolution
logic is here.

EXTRACTED FROM:
``skynet/apps/public-api/public_api/services/target_search.py`` (394 lines), the
SIMBAD branch of ``search_targets`` (lines 260-297) plus the module-level
availability probe (lines 236-242).

SEVERED: upstream's ``search_targets`` also queried four *local database*
catalogs through SQLAlchemy — NORAD satellites, major solar-system bodies, MPC
comets and MPC orbits — merging them into the same result list. Those are ORM
queries against Skynet's own tables, not remote catalog access, and they carry
the whole ``skynet_db.models`` dependency. They are not part of this extraction.
The merge-and-sort shape is preserved in ``resolve_targets``, which accepts
additional result lists so a caller with its own object database can restore the
combined behaviour without this module knowing about it.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional, Sequence

from astropy import units as u
from astropy.coordinates import Angle

from algorithms.catalogs.simbad import SIMBAD_OBJECT_TYPES

__all__ = [
    "ResolvedTarget",
    "SimbadResponseError",
    "SimbadUnavailableError",
    "resolve_simbad",
    "resolve_targets",
    "simbad_available",
]

logger = logging.getLogger(__name__)

#: J2000.0 as upstream wrote it — noon TT on 2000-01-01.
J2000 = datetime(2000, 1, 1, 12, 0, 0)

#: Seconds a failed probe is remembered before the next lookup retries it.
RETRY_AFTER_S = 30.0

#: The probed client; ``None`` until a probe succeeds.
_simbad = None
#: The last probe failure, and the ``time.monotonic()`` before which it stands.
_simbad_init_error: Optional[BaseException] = None
_simbad_retry_at = 0.0


class SimbadUnavailableError(RuntimeError):
    """SIMBAD could not be asked: it failed to initialize or the query failed.

    Raised only by ``resolve_simbad(..., strict=True)``, so a caller can tell
    an unreachable service from a name SIMBAD does not know. ``retryable`` is
    ``False`` only when astroquery itself cannot be imported -- a local
    installation problem that waiting will not fix.
    """

    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class SimbadResponseError(SimbadUnavailableError):
    """SIMBAD answered, but without the columns resolution reads (M3).

    Not retryable: the same query gets the same response shape.
    """

    def __init__(self, message: str):
        super().__init__(message, retryable=False)


#: The columns resolution reads, as astroquery >= 0.4.8 names them; older
#: releases returned them upper-case (MAIN_ID, RA, DEC, OTYPE).
_SIMBAD_COLUMNS = ("main_id", "ra", "dec", "otype")


@dataclass
class ResolvedTarget:
    """One candidate match for a free-text identifier.

    ``object_type`` is the prose label from ``SIMBAD_OBJECT_TYPES``. It is the
    empty string when SIMBAD reports a code MARS's table does not carry, which
    happens as SIMBAD's vocabulary evolves — treat it as "unknown", not as an
    error.
    """

    object_name: str
    ra_deg: float
    dec_deg: float
    object_type: str = ""
    source: str = "SIMBAD"
    epoch: datetime = J2000


def simbad_available() -> bool:
    """Return whether SIMBAD lookups can run.

    Resolution needs the ``otype`` VOTable field, which older astroquery
    versions and some SIMBAD mirrors do not offer. Upstream ran the probe at
    import time, which made importing the module do network-adjacent work, so
    it runs on first use instead.

    Success is cached for the process. A failure is remembered for only
    ``RETRY_AFTER_S`` seconds, after which the next lookup probes again, so a
    transient failure no longer disables resolution for the rest of the
    process (CAT-22), and a lasting one is not re-probed and re-logged on
    every call. An astroquery that cannot be imported is remembered for good.
    The failure is kept for ``resolve_simbad(..., strict=True)`` to report.
    """
    global _simbad, _simbad_init_error, _simbad_retry_at
    if _simbad is not None:
        return True
    if _simbad_init_error is not None and time.monotonic() < _simbad_retry_at:
        return False

    try:
        from astroquery.simbad import Simbad

        simbad = Simbad()
        simbad.add_votable_fields("otype")
    except ImportError as exc:
        logger.warning("astroquery.simbad cannot be imported; SIMBAD resolution disabled",
                       exc_info=True)
        _simbad_init_error, _simbad_retry_at = exc, math.inf
        return False
    except Exception as exc:
        logger.warning("SIMBAD object-type field unavailable; retrying in %.0f s",
                       RETRY_AFTER_S, exc_info=True)
        _simbad_init_error, _simbad_retry_at = exc, time.monotonic() + RETRY_AFTER_S
        return False

    _simbad = simbad
    _simbad_init_error = None
    return True


def resolve_simbad(name: str, *, strict: bool = False) -> list[ResolvedTarget]:
    """Resolve ``name`` against SIMBAD.

    Returns every row SIMBAD matched, which for an ambiguous identifier is more
    than one. Rows with no coordinates, or coordinates astropy cannot parse, are
    skipped rather than failing the lookup — a partial answer beats none.

    By default returns an empty list, never raises, when SIMBAD is unavailable
    or the query fails. Upstream printed such failures to stdout; MARS logs
    them. That makes an outage look like an unknown name, so ``strict=True``
    raises :class:`SimbadUnavailableError` for either failure instead, leaving
    an empty list to mean only that SIMBAD answered with no usable match.

    PRESERVED BEHAVIOUR: the identifier is lower-cased before the query.
    SIMBAD's matching is case-insensitive so this is normally invisible, and it
    is kept because upstream's downstream matching assumed it.
    """
    results: list[ResolvedTarget] = []

    name = (name or "").strip().lower()
    if name == "":
        return results

    if not simbad_available():
        if strict:
            raise SimbadUnavailableError(
                f"SIMBAD could not be initialized: {_simbad_init_error}",
                retryable=not isinstance(_simbad_init_error, ImportError),
            ) from _simbad_init_error
        return results

    try:
        rows = _simbad.query_object(name, wildcard=False)
    except Exception as exc:
        logger.warning("SIMBAD query failed for %r", name, exc_info=True)
        if strict:
            raise SimbadUnavailableError(f"SIMBAD query failed: {exc}") from exc
        return results

    if not rows:
        return results

    # M3: read the columns whichever case this astroquery uses, and fail by
    # name -- not with a KeyError -- when the response lacks one.
    colnames = getattr(rows, "colnames", None) or list(getattr(rows[0], "keys", lambda: [])())
    by_lower = {str(name).lower(): name for name in colnames}
    missing = [name for name in _SIMBAD_COLUMNS if name not in by_lower]
    if missing:
        message = (f"SIMBAD's response has no {', '.join(missing)} column; it returned "
                   f"{', '.join(map(str, colnames))}")
        if strict:
            raise SimbadResponseError(message)
        logger.warning("%s", message)
        return results
    column = {name: by_lower[name] for name in _SIMBAD_COLUMNS}

    for row in rows:
        ra = row[column["ra"]]
        dec = row[column["dec"]]
        # Was `if not ra or not dec`, which also skipped a real 0.0.
        if _missing_value(ra) or _missing_value(dec):
            continue
        try:
            # SIMBAD serves these in degrees already; Angle is used for its
            # parsing of the sexagesimal forms older releases returned.
            ra = Angle(ra, unit=u.degree)
            dec = Angle(dec, unit=u.degree)
        except Exception:
            logger.debug("Skipping SIMBAD row with unparseable position", exc_info=True)
            continue

        results.append(
            ResolvedTarget(
                object_name=row[column["main_id"]],
                ra_deg=ra.degree,
                dec_deg=dec.degree,
                object_type=SIMBAD_OBJECT_TYPES.get(row[column["otype"]], ""),
                source="SIMBAD",
            )
        )

    return results


def _missing_value(value) -> bool:
    """A cell SIMBAD left empty: None, masked, blank or non-finite."""
    if value is None or type(value).__name__ == "MaskedConstant":
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return not math.isfinite(float(value))
    except (TypeError, ValueError):
        return False  # a sexagesimal string; Angle parses it below


def resolve_targets(
    name: str,
    *,
    extra: Optional[Iterable[Sequence[ResolvedTarget]]] = None,
) -> list[ResolvedTarget]:
    """Resolve ``name`` and merge in any caller-supplied matches.

    ``extra`` is where the severed local-catalog branches plug back in: a caller
    with a satellite or minor-planet database passes its own result lists and
    gets upstream's combined, name-sorted output.

    Sorting is by lower-cased object name, so results from different sources
    interleave alphabetically rather than clustering by provider.
    """
    results = resolve_simbad(name)
    for group in extra or ():
        results.extend(group)
    results.sort(key=lambda t: (t.object_name or "").lower())
    return results
