"""Photometric calibration tool wrappers."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from algorithms.fieldcal.ref_mag import resolve_ref_mag_for_filter
from algorithms.fieldcal.ref_mag import _resolve_ref_mag_for_filter_with_route
from algorithms.fieldcal.schemas import CatalogSource, Mag, PhotometryData
from algorithms.fieldcal.solution import _calc_solution_with_mask
from tools.models import ToolError, ToolWarning, ZeropointSolution
from tools.science_warnings import capture_numerical_warnings


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def _to_mapping(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_unset=True)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"Expected a mapping or Pydantic model, got {type(value).__name__}")


def _normalize_catalog_source(value: Any) -> CatalogSource:
    source = value if isinstance(value, CatalogSource) else CatalogSource(**_to_mapping(value))
    mags = getattr(source, "mags", {}) or {}
    normalized_mags = {
        name: mag if isinstance(mag, Mag) else Mag(**mag) if isinstance(mag, Mapping) else Mag(value=mag)
        for name, mag in mags.items()
    }
    source.mags = normalized_mags
    return source


def _normalize_measurement(value: Any) -> PhotometryData:
    return value if isinstance(value, PhotometryData) else PhotometryData(**_to_mapping(value))


def _catalog_by_id(catalog_sources: list[CatalogSource]) -> dict[str, CatalogSource]:
    return {
        str(source.id): source
        for source in catalog_sources
        if getattr(source, "id", None) is not None
    }


def solve_zeropoint_from_measurements(
    measurements: Iterable[Mapping[str, Any] | PhotometryData],
    catalog_sources: Iterable[Mapping[str, Any] | CatalogSource],
) -> ZeropointSolution:
    """Solve a photometric zero point from local measurements and catalog rows."""

    normalized_measurements = [_normalize_measurement(item) for item in measurements]
    normalized_catalog_sources = [_normalize_catalog_source(item) for item in catalog_sources]
    catalogs_by_id = _catalog_by_id(normalized_catalog_sources)

    warnings: list[ToolWarning] = []
    usable_sources: list[PhotometryData] = []
    reference_routes: list[tuple[str | None, str, str | None]] = []

    for index, measurement in enumerate(normalized_measurements):
        source = measurement.model_copy(deep=True)
        # Match the pixel calibration path: a known saturation count cannot
        # be rescued by a finite magnitude or absorbed into fitted scatter.
        if (source.sat_pixels or 0) > 0:
            continue
        route = (source.catalog_name, "provided", None)
        if source.mag is None:
            warnings.append(ToolWarning(code="missing_mag", message=f"Measurement {index} has no instrumental mag."))
            continue

        catalog_source = None
        if source.id is not None:
            catalog_source = catalogs_by_id.get(str(source.id))
        if catalog_source is None and index < len(normalized_catalog_sources):
            catalog_source = normalized_catalog_sources[index]
        if catalog_source is not None and (catalog_source.sat_pixels or 0) > 0:
            continue

        if source.ref_mag is None and catalog_source is not None:
            if getattr(catalog_source, "ref_mag", None) is not None:
                source.ref_mag = catalog_source.ref_mag
                source.ref_mag_error = catalog_source.ref_mag_error
            elif source.filter:
                resolved = _resolve_ref_mag_for_filter_with_route(
                    image_filter=source.filter,
                    catalog_name=catalog_source.catalog_name,
                    cs_mags=catalog_source.mags,
                )
                source.ref_mag = resolved.value
                source.ref_mag_error = resolved.error
                route = (catalog_source.catalog_name, resolved.kind, resolved.reference)
            source.catalog_name = source.catalog_name or catalog_source.catalog_name

        if source.ref_mag is None:
            warnings.append(
                ToolWarning(
                    code="missing_ref_mag",
                    message=f"Measurement {index} has no resolvable catalog reference magnitude.",
                )
            )
            continue

        usable_sources.append(source)
        reference_routes.append(route)

    if not usable_sources:
        return ZeropointSolution(
            source_count=0,
            warnings=warnings,
            errors=[
                ToolError(
                    code="no_usable_sources",
                    message="No unsaturated measurements had both instrumental and reference magnitudes.",
                )
            ],
        )

    try:
        with capture_numerical_warnings(warnings):
            solution, survivor_mask = _calc_solution_with_mask(usable_sources)
        m0, m0_error, slop, limmag, rej_percent = solution
    except ValueError as exc:
        # Invalid measurement variances or an unusable numerical fit must
        # return a structured failure. M2 removes the old zero-scatter
        # cancellation crash, but the numerical-error boundary still applies.
        return ZeropointSolution(
            source_count=len(usable_sources),
            warnings=warnings,
            errors=[ToolError(code="numerical_error", message=str(exc))],
        )
    from tools.catalogs import calibration_sample_warnings, reference_band_warnings

    surviving = int(sum(survivor_mask))
    for source, kept, (catalog, kind, reference) in zip(usable_sources, survivor_mask, reference_routes):
        if kept:
            for warning in reference_band_warnings(catalog, source.filter, kind=kind, reference=reference):
                if warning not in warnings:
                    warnings.append(warning)
    warnings.extend(calibration_sample_warnings(usable_sources, surviving))
    if _finite(m0) is None or _finite(m0_error) is None or m0_error <= 0:
        return ZeropointSolution(
            source_count=surviving, warnings=warnings,
            errors=[ToolError(code="no_solution", message=
                f"The fit over {surviving} surviving star(s) has no finite zero point "
                "and positive finite uncertainty; it cannot establish a calibration.")],
        )
    return ZeropointSolution(
        zero_point=_finite(m0),
        zero_point_error_mag=_finite(m0_error),
        zero_point_slop=_finite(slop),
        limmag5=_finite(limmag),
        rej_percent=_finite(rej_percent),
        source_count=surviving,
        warnings=warnings,
    )
