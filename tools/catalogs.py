"""Catalog declaration tool wrappers."""

from __future__ import annotations

from algorithms.catalogs import CATALOGS
from algorithms.catalogs.filters import (
    catalog_filter_lookup, catalog_key, filter_token_candidates, reference_routes,
)
from algorithms.fieldcal.ref_mag import resolve_ref_mag_for_filter
from tools.models import CatalogSummary, ReferenceBandResolution, ToolError, ToolWarning

_MATH_NAMES = frozenset(("abs", "exp", "log", "log10", "sqrt"))


def _filter_token_candidates(image_filter: str) -> list[str]:
    return [token for token in filter_token_candidates(image_filter) if token]


def _expression_deps(expr: str) -> set[str]:
    try:
        return {
            name
            for name in compile(expr, "<string>", "eval").co_names
            if name not in _MATH_NAMES
        }
    except (SyntaxError, ValueError):
        return set()


def _effective_catalog(name: str):
    return CATALOGS.get(catalog_key(name))


def _effective_lookup(name: str) -> dict[str, str]:
    return catalog_filter_lookup(name)


def _resolve_target(
    target: str,
    catalog_mags: set[str],
    lookup: dict[str, str],
) -> tuple[bool, str, str]:
    seen: set[str] = set()
    current = target
    while current and current not in seen:
        seen.add(current)
        if current in catalog_mags:
            return True, current, "lookup_band"
        next_target = lookup.get(current)
        if next_target:
            current = next_target
            continue
        deps = _expression_deps(current)
        if deps and all(dep in catalog_mags for dep in deps):
            return True, current, "expression"
        return False, current, "unresolved"
    return False, target, "unresolved"


def _reference_resolves(
    *,
    catalog_name: str,
    image_filter: str,
    catalog_mags: set[str],
    lookup: dict[str, str],
    allow_preferred_band_fallback: bool = False,
) -> bool:
    dummy_mags = {
        band: {"value": 1.0, "error": 0.1}
        for band in catalog_mags
    }
    ref_mag, _ref_error = resolve_ref_mag_for_filter(
        image_filter=image_filter,
        catalog_name=catalog_name,
        cs_mags=dummy_mags,
        custom_filter_lookup={catalog_name: lookup},
        allow_preferred_band_fallback=allow_preferred_band_fallback,
    )
    return ref_mag is not None


def _missing_bands(target: str, catalog_mags: set[str], lookup: dict[str, str]) -> list[str]:
    """Return the bands a lookup target needs that the catalog does not carry."""
    missing: set[str] = set()
    pending, seen = [target], set()
    while pending:
        current = pending.pop()
        if current in seen or current in catalog_mags:
            continue
        seen.add(current)
        if current in lookup:
            pending.append(lookup[current])
            continue
        deps = _expression_deps(current)
        if deps == {current}:
            missing.add(current)
        else:
            pending.extend(deps)
    return sorted(missing)


def reference_band_unavailable(catalog: str, image_filter: str | None) -> str | None:
    """Explain why a field calibration against ``catalog`` cannot produce any
    reference magnitude for ``image_filter``, or return ``None`` if it can.

    Unlike ``resolve_reference_band``'s ``supported``, this allows the
    preferred-band fallback that a default field calibration also allows, so
    it reports only failures that are certain: a filter whose explicit
    transform needs bands the catalog does not carry (CAT-06, APASS ``U``),
    or a pairing resolution refuses. A catalog MARS does not declare is not
    certain to fail -- its rows may match a band directly -- so it returns
    ``None``. Rows missing some magnitudes are a separate matter.
    """
    catalog_name = str(catalog).strip()
    normalized_filter = (image_filter or "").strip()
    if not normalized_filter:
        return None
    declaration = _effective_catalog(catalog_name)
    if declaration is None:
        return None
    catalog_mags = set((getattr(declaration, "mags", {}) or {}).keys())
    lookup = _effective_lookup(catalog_name)
    if _reference_resolves(
        catalog_name=catalog_name,
        image_filter=normalized_filter,
        catalog_mags=catalog_mags,
        lookup=lookup,
        allow_preferred_band_fallback=True,
    ):
        return None
    for token in _filter_token_candidates(normalized_filter):
        target = lookup.get(token)
        if target:
            missing = _missing_bands(target, catalog_mags, lookup)
            if missing:
                return (
                    f"{catalog_name} cannot supply a reference magnitude for filter "
                    f"{normalized_filter!r}: its transform {target!r} needs "
                    f"{', '.join(missing)}, which {catalog_name} does not carry."
                )
            break
    return (
        f"{catalog_name} has no usable reference-band mapping for filter "
        f"{normalized_filter!r}."
    )


def list_photometric_catalogs() -> list[CatalogSummary]:
    """List local photometric catalog declarations without querying them."""

    summaries: list[CatalogSummary] = []
    for name, catalog in CATALOGS.items():
        lookup = getattr(catalog, "filter_lookup", {}) or {}
        summaries.append(
            CatalogSummary(
                name=name,
                display_name=getattr(catalog, "display_name", None),
                num_sources=getattr(catalog, "num_sources", None),
                bands=list((getattr(catalog, "mags", {}) or {}).keys()),
                filter_aliases=sorted(lookup.keys()),
            )
        )
    return summaries


def reference_band_warnings(catalog: str | None, image_filter: str | None) -> list[ToolWarning]:
    """Disclose retained transform limitations without changing their numbers."""
    key = catalog_key(catalog)
    tokens = set(filter_token_candidates(image_filter or ""))
    folded = {token.casefold() for token in tokens}
    warnings: list[ToolWarning] = []
    if key == "UCAC" and "open" in folded:
        warnings.append(ToolWarning(
            code="nonstandard_passband",
            message="UCAC Open is the native UCAC model magnitude (approximately 579-642 nm). "
            "It does not establish Johnson V photometry or match every instrument's clear response.",
        ))
    if folded & {"halpha", "hbeta", "oiii", "sii"}:
        warnings.append(ToolWarning(
            code="broadband_reference",
            message=f"{catalog}: filter {image_filter!r} uses a broadband stellar reference. "
            "This is a relative zero point, not an absolute narrowband magnitude or emission-line flux calibration.",
        ))
    if key == "2MASS" and tokens & {"B", "V", "R", "I"}:
        warnings.append(ToolWarning(
            code="approximate_transform",
            message="The retained 2MASS J-K optical conversion is a stellar approximation. "
            "Its validity for this source is not established; values are not range-clipped, "
            "and propagated measurement errors exclude transformation scatter.",
        ))
    if key == "APASS" and "I" in tokens:
        warnings.append(ToolWarning(
            code="approximate_transform",
            message="APASS I uses the retained r'-i' stellar-locus approximation, "
            "not a measured I magnitude or the published i-z relation. "
            "Propagated measurement errors exclude transformation scatter.",
        ))
    if key == "SkyMapper" and tokens & {"uprime", "gprime", "rprime", "iprime", "zprime"}:
        warnings.append(ToolWarning(
            code="approximate_transform",
            message="The retained SkyMapper prime-band offsets are for an F5V spectrum. "
            "They are not general stellar colour transformations; propagated measurement errors exclude this systematic.",
        ))
    return warnings


def calibration_reference_warnings(sources) -> list[ToolWarning]:
    """Carry each used catalog/filter limitation into a completed calibration."""
    warnings: list[ToolWarning] = []
    seen: set[tuple[str, str]] = set()
    for source in sources or []:
        for warning in reference_band_warnings(
            getattr(source, "catalog_name", None), getattr(source, "filter", None),
        ):
            signature = (warning.code, warning.message)
            if signature not in seen:
                seen.add(signature)
                warnings.append(warning)
    return warnings


def resolve_reference_band(catalog: str, image_filter: str | None) -> ReferenceBandResolution:
    """Resolve the catalog band or expression MARS would use for an image filter."""

    catalog_name = str(catalog).strip()
    warnings: list[ToolWarning] = []
    errors: list[ToolError] = []
    declaration = _effective_catalog(catalog_name)
    if declaration is None:
        errors.append(ToolError(code="unknown_catalog", message=f"Unknown catalog: {catalog_name}"))
        return ReferenceBandResolution(
            catalog=catalog_name,
            image_filter=image_filter,
            supported=False,
            errors=errors,
        )

    normalized_filter = (image_filter or "").strip()
    if not normalized_filter:
        warnings.append(ToolWarning(code="blank_filter", message="No image filter was provided."))
        return ReferenceBandResolution(
            catalog=catalog_name,
            image_filter=normalized_filter or None,
            supported=False,
            warnings=warnings,
        )

    catalog_mags = set((getattr(declaration, "mags", {}) or {}).keys())
    lookup = _effective_lookup(catalog_name)
    reference_resolves = _reference_resolves(
        catalog_name=catalog_name,
        image_filter=normalized_filter,
        catalog_mags=catalog_mags,
        lookup=lookup,
    )

    for target, route_kind in reference_routes(normalized_filter, catalog_mags, lookup):
        supported, reference, kind = _resolve_target(target, catalog_mags, lookup)
        missing = _missing_bands(target, catalog_mags, lookup)
        if missing:
            warnings.append(ToolWarning(
                code="unsupported_filter",
                message=f"{catalog_name}'s transform for filter {normalized_filter!r} "
                f"needs {', '.join(missing)}, which {catalog_name} does not carry.",
            ))
        if route_kind == "direct_band":
            kind = "direct_band"
        elif route_kind == "wildcard" and supported:
            kind = "wildcard"
        if supported and reference_resolves:
            warnings.extend(reference_band_warnings(catalog_name, normalized_filter))
        return ReferenceBandResolution(
            catalog=catalog_name,
            image_filter=normalized_filter,
            supported=supported and reference_resolves,
            reference=reference,
            kind=kind if reference_resolves else "unresolved",
            warnings=warnings,
        )

    warnings.append(
        ToolWarning(
            code="unsupported_filter",
            message=f"{catalog_name} has no reference-band mapping for filter {normalized_filter!r}.",
        )
    )
    return ReferenceBandResolution(
        catalog=catalog_name,
        image_filter=normalized_filter,
        supported=False,
        warnings=warnings,
    )
