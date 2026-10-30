"""Filter-aware catalog selection.

Before querying anything, narrow the configured catalog list to catalogs that
can actually produce a reference magnitude for the image's filter. Querying
2MASS for a prime-band image wastes a round trip and returns sources the
zero-point solve will discard.

"Can produce" is not just "has that band". A catalog supports a filter if the
filter names one of its bands directly, or if its ``filter_lookup`` maps the
filter to a band, or to an *expression* over bands it has — APASS answers an
R-band image through ``rprime - 0.2936*(rprime - iprime) - 0.1439`` without
carrying R at all. Aliases chain: ``g'`` -> ``gprime`` -> an expression over
``g`` and ``r``. Resolution follows the same bounded alias chains and effective filter map as
``fieldcal.ref_mag.resolve_ref_mag_for_filter`` (up to 32 visited targets).

This module reads declarations only. It imports ``catalogs``, not
``query.registry``, so filter matching costs no astroquery import.

EXTRACTED FROM:
``skynet/.../optical_data_processing/catalog_query.py`` (lines 20-191 of 436),
with intentional M2 shared-routing and band-identity corrections. The WCS and orchestration halves of
that file are now ``query/geometry.py`` and ``query/runner.py``.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from algorithms.catalogs import CATALOGS
from algorithms.catalogs.filters import (
    catalog_filter_lookup, catalog_key, filter_token_candidates, reference_routes,
)

__all__ = [
    "catalog_supports_filter",
    "select_catalogs_for_filter",
    "normalize_filter_token",
]

logger = logging.getLogger(__name__)


#: Names that appear in ``filter_lookup`` expressions but are functions, not
#: bands. Anything else an expression references must be a band the catalog has.
_MATH_BUILTINS: frozenset[str] = frozenset(("sqrt", "log10", "abs", "exp", "log"))


def _expression_deps(expr: str) -> set[str]:
    """Return the band names an expression references.

    Compiles the expression and reads ``co_names``, so ``'r - 0.2936*(r - i)'``
    yields ``{'r', 'i'}``. A plain band name yields ``{'B'}`` — indistinguishable
    from an expression, which is fine because both are checked the same way.

    Returns an empty set for anything that will not compile, which callers treat
    as "resolves nothing".
    """
    try:
        return {
            name
            for name in compile(expr, "<string>", "eval").co_names
            if name not in _MATH_BUILTINS
        }
    except (SyntaxError, ValueError):
        return set()


def _filter_token_candidates(image_filter: str) -> list[str]:
    """Return the spellings of a filter name worth trying, in priority order.

    FITS headers spell filters inconsistently — ``"V"``, ``" v "``, ``"g'"`` with
    a typographic apostrophe. Case variants are tried, but the original casing
    goes first: lower-casing ``Halpha`` to ``halpha`` or upper-casing ``g'`` to
    ``G'`` would match the wrong entry, and some catalogs distinguish ``v`` (a
    SkyMapper band) from ``V`` (Johnson V).
    """
    return filter_token_candidates(image_filter)


def normalize_filter_token(image_filter: Optional[str]) -> Optional[str]:
    """Return a stripped filter token, or ``None`` if blank."""
    if image_filter is None:
        return None
    return image_filter.strip() or None


def _lookup_resolves(
    target: str,
    catalog_mags: set[str],
    effective_lookup: dict[str, str],
) -> bool:
    """Return whether ``target`` bottoms out in bands the catalog has.

    ``target`` is the right-hand side of a ``filter_lookup`` entry: a band, an
    alias for another entry, or an expression. Alias traversal has the same
    cycle detection and 32-target bound as numeric resolution.
    """
    seen: set[str] = set()
    while target and target not in seen and len(seen) < 32:
        seen.add(target)
        if target in catalog_mags:
            return True
        deps = _expression_deps(target)
        if deps and deps <= catalog_mags:
            return True
        target = effective_lookup.get(target)
    return False


def catalog_supports_filter(
    catalog_name: str,
    image_filter: str,
    *,
    custom_filter_lookup: Optional[dict] = None,
) -> bool:
    """Return whether a catalog can supply a reference magnitude for a filter.

    ``custom_filter_lookup`` is ``{catalog_name: {filter: target}}`` and overlays
    the catalog's own lookup, letting a deployment teach a catalog about a filter
    MARS does not ship a transform for.

    Unknown catalog names return ``False`` rather than raising: selection is
    advisory, and the query runner validates names separately with a clear error.
    """
    catalog = CATALOGS.get(catalog_key(catalog_name))
    if catalog is None:
        return False

    catalog_mags: set[str] = set(getattr(catalog, "mags", {}) or {})
    if not catalog_mags:
        return False

    # Effective lookup: the instance's filter_lookup already merges the class
    # declaration with whatever the registry overlaid at construction.
    effective_lookup = catalog_filter_lookup(catalog_name, custom_filter_lookup)
    return any(_lookup_resolves(target, catalog_mags, effective_lookup)
               for target, _kind in reference_routes(image_filter, catalog_mags, effective_lookup))


def select_catalogs_for_filter(
    catalog_names: Sequence[str],
    image_filter: Optional[str],
    *,
    custom_filter_lookup: Optional[dict] = None,
) -> list[str]:
    """Narrow a catalog list to those that can resolve ``image_filter``.

    Configured priority order is preserved among the survivors.

    Two deliberate fallbacks, both returning the list unchanged: a blank filter
    means there is nothing to match on, and *no* compatible catalog means the
    caller's configuration disagrees with MARS's transform tables. Dropping
    every catalog would turn a recoverable situation into a failed calibration,
    so the full list is tried and the mismatch is logged as a warning.
    """
    norm = normalize_filter_token(image_filter)
    if not norm:
        return list(catalog_names)

    logger.debug(
        "Filter-aware catalog selection: raw=%r normalized=%r configured=%s",
        image_filter,
        norm,
        list(catalog_names),
    )

    compatible = [
        c
        for c in catalog_names
        if catalog_supports_filter(c, norm, custom_filter_lookup=custom_filter_lookup)
    ]

    logger.debug("Filter-compatible catalogs for %r: %s", norm, compatible)

    if not compatible:
        logger.warning(
            "No configured catalog supports filter %r (configured: %s); "
            "falling back to full configured list",
            norm,
            list(catalog_names),
        )
        return list(catalog_names)

    return compatible
