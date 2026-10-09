"""First-party WCS-01/25 pre-load catalog bounds, not scientific truncation."""

from __future__ import annotations

import math

MAX_QUERY_ROWS = 200_000
MAX_QUERY_CANDIDATES = 2_000_000
MAX_ZONE_RECORDS = 4_000_000
QUERY_CHUNK_ROWS = 16_384


def normalize_catalog_radius_limit(maximum: float | None) -> float:
    maximum = 2.0 if maximum is None else float(maximum)
    if not math.isfinite(maximum) or not 0 < maximum <= 5:
        raise ValueError("ATLAS catalog maximum radius must be finite and in (0, 5] degrees.")
    return maximum


def validate_catalog_radius(radius: float, maximum: float | None) -> float:
    maximum = normalize_catalog_radius_limit(maximum)
    if not math.isfinite(radius) or not 0 < radius <= maximum:
        raise ValueError(f"ATLAS catalog footprint exceeds the {maximum:g}-degree radius budget; provide a reliable scale/FOV.")
    return radius


def validate_query_box(*coordinates: float) -> None:
    if not all(math.isfinite(value) for value in coordinates):
        raise ValueError("Catalog coordinates must be finite.")


def check_query_budget(candidates: int, rows: int) -> None:
    if candidates > MAX_QUERY_CANDIDATES or rows > MAX_QUERY_ROWS:
        raise ValueError("ATLAS catalog query exceeds its candidate/returned-row budget; narrow the footprint.")
