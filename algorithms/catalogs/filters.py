"""Shared filter spelling, catalog identity and reference-routing policy.

Metadata only: importing this module never imports a query backend. M2 follows
Skynet's exact-band -> explicit mapping -> case variant -> wildcard order.
The CAT-01 safeguard applies to all single-letter passbands: case distinguishes
Johnson U/R/I from native survey u/r/i as well as Johnson V from SkyMapper v.
"""


from collections.abc import Collection


def exact_filter_token_candidates(image_filter: str) -> list[str]:
    """Normalize transcription noise while retaining passband case and order."""
    stripped = image_filter.strip()
    prime = stripped.replace("′", "'").replace("’", "'")
    return list(dict.fromkeys((image_filter, stripped, prime, prime.replace("_", ""))))


def filter_token_candidates(image_filter: str) -> list[str]:
    """Try real spelling first; case variants only for multi-letter labels."""
    exact = exact_filter_token_candidates(image_filter)
    tokens = exact[:2]
    if len(exact[-1]) > 1:
        tokens.extend((image_filter.strip().lower(), image_filter.strip().upper()))
    tokens.extend(exact[2:])
    for token in list(tokens):
        normalized = token.strip().replace("′", "'").replace("’", "'").replace("_", "")
        tokens.append(normalized)
        if len(normalized) == 2 and normalized[0] in "ugriz" and normalized[1] in "'p":
            tokens.append(normalized[0] + "prime")
    return list(dict.fromkeys(tokens))


def catalog_key(name: str | None) -> str | None:
    """Accept registry keys and the plugin names stamped onto returned rows."""
    from . import CATALOGS

    if name in CATALOGS:
        return name
    return next((key for key, catalog in CATALOGS.items() if catalog.name == name), None)


def catalog_filter_lookup(
    name: str | None, custom_filter_lookup: dict[str, dict[str, str]] | None = None,
    *, base_filter_lookup: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    """One effective map for selection, calculation and tool descriptions.

    The historical CATALOG_OPTIONS export remains available for provenance; it
    no longer supplies a competing APASS H-alpha expression at runtime.
    """
    from . import CATALOGS

    key = catalog_key(name)
    lookup = dict(getattr(CATALOGS.get(key), "filter_lookup", {}) or {})
    for mapping in (base_filter_lookup, custom_filter_lookup):
        if not mapping:
            continue
        # Registry-key overrides also work for sources stamped StetsonGlobs,
        # Tycho2, UCAC5 or USNOB1; a literal source-name override takes priority.
        for candidate in dict.fromkeys((key, name)):
            lookup.update(mapping.get(candidate, {}))
    return lookup


def _matching_keys(image_filter: str, keys: Collection[str]) -> list[str]:
    """Try literal variants first, then case-insensitive multi-letter labels."""
    tokens = filter_token_candidates(image_filter)
    matches = [token for token in tokens if token in keys]
    if matches:
        return matches
    if len(exact_filter_token_candidates(image_filter)[-1]) > 1:
        folded = {token.casefold() for token in tokens}
        return [key for key in keys if key.casefold() in folded]
    return []


def reference_routes(
    image_filter: str, bands: set[str], lookup: dict[str, str],
) -> list[tuple[str, str]]:
    """Return candidate references in production priority order.

    An explicit but unavailable transform claims the filter and blocks unrelated
    case-only or wildcard substitutions. A row's missing bands can still make a
    declared route unusable; the numeric resolver checks actual values.
    """
    for token in exact_filter_token_candidates(image_filter):
        if token and token in bands:
            return [(token, "direct_band")]
    routes = [(lookup[token], "lookup") for token in _matching_keys(image_filter, lookup)
              if lookup.get(token)]
    if routes:
        return routes
    for token in _matching_keys(image_filter, bands):
        if token and token in bands:
            return [(token, "direct_band")]
    return [(lookup["*"], "wildcard")] if lookup.get("*") else []


def preferred_fallback_allowed(name: str | None, image_filter: str) -> bool:
    """Retain the compatibility fallback without relabeling known passbands."""
    from . import CATALOGS

    if catalog_key(name) in {"UCAC", "Tycho", "USNO"}:
        return False
    known = {band for catalog in CATALOGS.values() for band in catalog.mags}
    known.update(token for catalog in CATALOGS.values()
                 for token in (getattr(catalog, "filter_lookup", {}) or {}) if token != "*")
    return not _matching_keys(image_filter, known)
