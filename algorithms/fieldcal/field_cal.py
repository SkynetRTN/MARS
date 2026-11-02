"""Photometric calibration helpers for optical observation asset processing.

EXTRACTED FROM: skynet/packages/py/skynet-db/skynet_db/runners/
observation_asset_processing/optical_data_processing/field_cal.py (701 lines).

Originally copied verbatim. The maintained interface supplies WCS and catalog
rows explicitly, while deterministic extraction and photometry are ordinary
imports. M5 corrects detector-pixel and spherical matching, measured-flux SNR
selection, and calibration measurement validity, and forwards extraction RMS
without changing annular sky subtraction. The M3
malformed-input guards, marked ``M3`` inline, do change outcomes: inputs that
used to abort now solve or fail by name, unusable rows are left out, and a
degenerate solve -- including upstream's single-star zero point with a NaN
error -- is refused rather than returned (``docs/extraction.md``, Field
Calibration §5b).
"""
from __future__ import annotations

from datetime import datetime
import logging
import math
from numbers import Integral
from typing import Iterable, Mapping

import numpy as np
from astropy.wcs import WCS
from scipy.spatial import cKDTree

# EXTRACTED: was `from skylib.util.angle import angdist` /
# `from skylib.util.fits import get_fits_time` (installed skylib package) —
# now the shared vendored copy under algorithms.skylib_lite.
from algorithms.skylib_lite.util.angle import angdist
from algorithms.skylib_lite.util.fits import get_fits_time

# EXTRACTED: was `from skynet_db.runners.common.schemas import (...)`
from .schemas import (
    FieldCalResult,
    Mag,
    PhotometricCalibrationSettings,
    PhotometryData,
    PhotometrySettings,
    SourceExtractionData,
    SourceExtractionSettings,
)
# EXTRACTED: was `from skynet_db.runners.utils import calc_solution,
# resolve_ref_mag_for_filter` (907-line grab-bag module; the two field-cal
# functions now live in fieldcal/solution.py and fieldcal/ref_mag.py).
from .solution import _calc_solution_with_mask
from .ref_mag import _resolve_ref_mag_for_filter_with_route
# Catalog metadata (band tables and colour transforms) is pure local data.
from algorithms.catalogs import CATALOGS
from algorithms.photometry.photometry import run_photometry
from algorithms.photometry.source_extraction import get_source_radec, run_source_extraction
from .schemas import CatalogSource

__all__ = ["DegenerateCalibrationError", "perform_field_calibration"]

logger = logging.getLogger(__name__)


class DegenerateCalibrationError(RuntimeError):
    """The solve ran but its zero point or uncertainty is not usable.

    M3 (PHOT-08): raised before any ``PHOT_*`` header keyword is written, so a
    degenerate solve is never stored or returned as a calibration.
    """

    def __init__(self, message: str, *, num_stars: int):
        super().__init__(message)
        self.num_stars = num_stars

def _normalize_catalog_sources(
    sources: Iterable[CatalogSource | Mapping[str, object]],
    *,
    file_id: int | None,
) -> list[CatalogSource]:
    normalized: list[CatalogSource] = []
    for source in sources:
        if isinstance(source, CatalogSource):
            data = source.model_dump(exclude_unset=True)
        else:
            data = dict(source)
        if data.get("file_id") is None:
            data["file_id"] = file_id
        # M3: catalog backends assign provider values without validation, so
        # SkyMapper (int32), SDSS (uint64), UCAC and PanSTARRS (int64) rows
        # arrive with integer ids that ``CatalogSource.id: str`` rejects here.
        # A masked integer column can arrive as float; NaN means no id, and
        # _ensure_unique_source_ids assigns one.
        source_id = data.get("id")
        if isinstance(source_id, Integral) and not isinstance(source_id, bool):
            data["id"] = str(int(source_id))
        elif isinstance(source_id, float):
            data["id"] = str(int(source_id)) if source_id.is_integer() else None
        normalized.append(CatalogSource(**data))
    return normalized


def _ensure_unique_source_ids(
    sources: list[CatalogSource],
    *,
    file_id: int | None,
) -> None:
    prefix = f"fieldcal_{file_id if file_id is not None else 'source'}_"
    source_ids: set[str | tuple[str, int | None]] = set()
    for idx, source in enumerate(sources):
        source_id = getattr(source, "id", None)
        if source_id is None:
            source.id = source_id = prefix + str(idx + 1)
        source_key = source_id
        if getattr(source, "file_id", None) is not None:
            source_key = (source_id, source.file_id)
        if source_key in source_ids:
            raise ValueError(f'Non-unique source ID "{source_id}"')
        source_ids.add(source_key)


def _attach_catalog_magnitudes(sources: list[CatalogSource]) -> None:
    for source in sources:
        mags = getattr(source, "mags", {}) or {}
        for name, val in list(mags.items()):
            if isinstance(val, dict):
                mags[name] = Mag(**val)
        source.mags = mags


def _has_reference_magnitudes(sources: list[CatalogSource]) -> bool:
    for source in sources:
        if getattr(source, "ref_mag", None) is not None:
            return True
        if (getattr(source, "mags", None) or {}):
            return True
    return False


def _catalogs_from_sources(sources: list[CatalogSource]) -> list[str]:
    catalogs: list[str] = []
    seen: set[str] = set()
    for source in sources:
        catalog_name = getattr(source, "catalog_name", None)
        if catalog_name and catalog_name not in seen:
            catalogs.append(catalog_name)
            seen.add(catalog_name)
    return catalogs


def _image_filter_from_header(header) -> str | None:
    """Extract the FILTER keyword from a FITS header, returning None if absent or blank."""
    if header is None:
        return None
    try:
        val = header.get("FILTER")
    except Exception:
        return None
    if val is None:
        return None
    return str(val).strip() or None


def _catalog_filter_lookup(catalog_name: str | None) -> dict[str, str]:
    from algorithms.catalogs.filters import catalog_filter_lookup

    return catalog_filter_lookup(catalog_name)


def _catalog_filter_lookup_map(
    sources: Iterable[CatalogSource],
    configured_catalogs: Iterable[str] | None = None,
) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for catalog_name in configured_catalogs or []:
        if catalog_name:
            lookup[catalog_name] = dict(_catalog_filter_lookup(catalog_name))
    for source in sources:
        catalog_name = getattr(source, "catalog_name", None)
        if catalog_name:
            lookup[catalog_name] = dict(_catalog_filter_lookup(catalog_name))
    return lookup


def _filter_variable_stars(
    sources: list[CatalogSource],
    *,
    variable_sources: Iterable[CatalogSource] | None,
    wcs: WCS | None,
    header,
    variable_check_tol: float | None,
) -> list[CatalogSource]:
    if not variable_check_tol or variable_check_tol <= 0:
        return sources
    if wcs is None:
        return sources

    var_stars = list(variable_sources or [])
    if not var_stars:
        return sources

    epoch = get_fits_time(header)[0]

    filtered: list[CatalogSource] = []
    for source in sources:
        ra, dec = get_source_radec(
            SourceExtractionData(**source.model_dump(exclude={"mags", "catalog_name", "label"})),
            epoch,
            wcs,
        )
        if ra is None or dec is None:
            filtered.append(source)
            continue
        is_variable = any(
            angdist(ra, dec, star.ra_hours, star.dec_degs) * 3600 < variable_check_tol
            for star in var_stars
            if getattr(star, "ra_hours", None) is not None and getattr(star, "dec_degs", None) is not None
        )
        if not is_variable:
            filtered.append(source)
    return filtered


def _match_detected_sources(
    catalog_sources: list[CatalogSource],
    detected_sources: list[SourceExtractionData],
    *,
    wcs: WCS | None,
    header,
    data: np.ndarray,
    source_match_tol: float | None,
    source_match_tol_arcsec: float | None = None,
    matched_shapes: list | None = None,
) -> list[CatalogSource]:
    if not detected_sources:
        return catalog_sources
    epoch = get_fits_time(header)[0]
    file_ids = set(getattr(source, "file_id", None) for source in detected_sources)
    catalog_sources_for_file: dict[int | None, list[CatalogSource]] = {
        file_id: [] for file_id in file_ids
    }
    for catalog_source in catalog_sources:
        catalog_file_id = getattr(catalog_source, "file_id", None)
        if catalog_file_id is None:
            for file_id in file_ids:
                catalog_sources_for_file[file_id].append(catalog_source)
        else:
            if catalog_file_id in catalog_sources_for_file:
                catalog_sources_for_file[catalog_file_id].append(catalog_source)

    def has_position(source, x_name, y_name):
        return all(value is not None and np.isfinite(value)
                   for value in (getattr(source, x_name, None), getattr(source, y_name, None)))

    # A WCS always means detector-pixel distance. Without one, retain supplied
    # pixel coordinates when both lists have them; sky-only matching has its own
    # explicit angular contract and never reinterprets source_match_tol.
    have_pixels = (all(has_position(s, "x", "y") for s in detected_sources)
                   and any(has_position(s, "x", "y") for s in catalog_sources))
    use_angular = wcs is None and not have_pixels
    if use_angular:
        if not all(has_position(s, "ra_hours", "dec_degs") for s in detected_sources):
            raise ValueError("Missing WCS or shared pixel/sky coordinates for catalog source matching")
        if (source_match_tol_arcsec is None or not np.isfinite(source_match_tol_arcsec)
                or source_match_tol_arcsec <= 0):
            raise ValueError("Positive source_match_tol_arcsec required for sky-only matching without WCS")
        # Unit-vector chord distance is monotonic in spherical separation,
        # including longitude seams and poles. A sphere's maximum angle is pi.
        match_tol = 2 * np.sin(np.deg2rad(min(source_match_tol_arcsec / 3600, 180)) / 2)
    else:
        if source_match_tol is None or not np.isfinite(source_match_tol) or source_match_tol <= 0:
            raise ValueError("Positive catalog source match tolerance expected")
        match_tol = source_match_tol

    def sky_vectors(ra, dec):
        longitude, latitude = np.deg2rad(ra), np.deg2rad(dec)
        cos_latitude = np.cos(latitude)
        return np.column_stack([cos_latitude * np.cos(longitude),
                                cos_latitude * np.sin(longitude), np.sin(latitude)])

    # ---- build catalog match coordinates ----------------------------------------
    # Both angular and pixel paths need the epoch-corrected catalog RA/Dec.
    # For the pixel path they are additionally projected through the WCS.
    catalog_source_coord_for_file: dict[int | None, np.ndarray] = {}
    catalog_source_kdtree_for_file: dict[int | None, cKDTree | None] = {}
    catalog_index_for_file: dict[int | None, np.ndarray] = {}

    for file_id, catalog_source_list in catalog_sources_for_file.items():
        if not catalog_source_list:
            catalog_source_kdtree_for_file[file_id] = None
            continue
        catalog_xy_data = []
        catalog_pm_epochs = []
        for source in catalog_source_list:
            x = getattr(source, "x", None)
            if x is None:
                x = np.nan
            y = getattr(source, "y", None)
            if y is None:
                y = np.nan
            ra = getattr(source, "ra_hours", None)
            if ra is None:
                ra = np.nan
            else:
                ra = float(ra) * 15.0
            dec = getattr(source, "dec_degs", None)
            if dec is None:
                dec = np.nan
            pm_epoch = getattr(source, "pm_epoch", None)
            if epoch is None or pm_epoch is None:
                pm_epoch = np.nan
                pm_sky = pm_pos_angle_sky = 0
                pm_pixel = pm_pos_angle_pixel = 0
            else:
                pm_sky = getattr(source, "pm_sky", 0) or 0
                pm_pos_angle_sky = getattr(source, "pm_pos_angle_sky", 0) or 0
                pm_pixel = getattr(source, "pm_pixel", 0) or 0
                pm_pos_angle_pixel = getattr(source, "pm_pos_angle_pixel", 0) or 0
            catalog_xy_data.append([x, y, ra, dec, pm_sky, pm_pos_angle_sky, pm_pixel, pm_pos_angle_pixel])
            catalog_pm_epochs.append(pm_epoch)

        # M3 (PHOT-04): was one np.transpose over rows that also held pm_epoch.
        # A datetime among the floats made every column an object array, and
        # np.isfinite then raised TypeError for any catalog carrying an epoch.
        # The epochs now travel separately; the arithmetic below is unchanged.
        x, y, ra, dec, pm_sky, pm_pos_angle_sky, pm_pixel, pm_pos_angle_pixel = np.transpose(
            np.asarray(catalog_xy_data, dtype=float)
        )
        pm_epoch = np.asarray(catalog_pm_epochs, dtype=object)
        have_radec = np.isfinite(ra) & np.isfinite(dec)
        if have_radec.any():
            if epoch is not None:
                have_pm_epoch = np.array([isinstance(val, datetime) for val in pm_epoch])
                have_pm = have_radec & have_pm_epoch
                if have_pm.any():
                    mu = pm_sky[have_pm] * np.asarray(
                        [(epoch - dt).total_seconds() for dt in pm_epoch[have_pm]]
                    )
                    theta = np.deg2rad(pm_pos_angle_sky[have_pm])
                    cd = np.clip(np.cos(np.deg2rad(dec[have_pm])), 1e-7, None)
                    ra[have_pm] = (ra[have_pm] + mu * np.sin(theta) / cd) % 360
                    dec[have_pm] = np.clip(dec[have_pm] + mu * np.cos(theta), -90, 90)

            if wcs is not None:
                # Catalog sky coordinates are at their reference epoch; project
                # the corrected coordinates into FITS origin-1 detector pixels.
                x[have_radec], y[have_radec] = wcs.all_world2pix(
                    ra[have_radec], dec[have_radec], 1, quiet=True,
                )

        if not use_angular:
            if epoch is not None:
                have_pm_epoch = np.array([isinstance(val, datetime) for val in pm_epoch])
                # Sky motion has already been applied before WCS projection.
                have_pm = have_pm_epoch & (pm_pixel != 0) & ~(have_radec & (wcs is not None))
                if have_pm.any():
                    mu = pm_pixel[have_pm] * np.asarray(
                        [(epoch - dt).total_seconds() for dt in pm_epoch[have_pm]]
                    )
                    theta = np.deg2rad(pm_pos_angle_pixel[have_pm])
                    x[have_pm] += mu * np.cos(theta)
                    y[have_pm] += mu * np.sin(theta)
            coords = np.transpose([x, y])
        else:
            coords = sky_vectors(ra, dec)

        # M3 (PHOT-05): a row with no usable position cannot be matched, and
        # one NaN coordinate made cKDTree reject the whole catalog. Such rows
        # are left out; ``catalog_index`` maps tree indices back to the list.
        positioned = np.isfinite(coords).all(axis=1)
        if not positioned.all():
            # Warning, not info: in pixel mode a valid RA/Dec projecting to
            # NaN points at the WCS, and the solve then runs on what is left.
            logger.warning(
                "Skipping %d of %d catalog sources with no usable match position%s",
                int((~positioned).sum()), len(positioned),
                "" if use_angular else " (in pixel mode, check the WCS projection)",
            )
        catalog_index_for_file[file_id] = np.flatnonzero(positioned)
        coords = coords[positioned]
        catalog_source_coord_for_file[file_id] = coords
        catalog_source_kdtree_for_file[file_id] = cKDTree(coords) if len(coords) else None

    # ---- build detected-source match coordinates --------------------------------
    detected_sources_for_file: dict[int | None, list[SourceExtractionData]] = {}
    detected_source_file_idx: dict[int, tuple[int | None, int]] = {}
    for source in detected_sources:
        file_id = getattr(source, "file_id", None)
        idx = len(detected_sources_for_file.get(file_id, []))
        detected_sources_for_file.setdefault(file_id, []).append(source)
        detected_source_file_idx[id(source)] = (file_id, idx)

    detected_source_coord_for_file: dict[int | None, np.ndarray] = {}
    detected_source_kdtree_for_file: dict[int | None, cKDTree] = {}
    for file_id, sources in detected_sources_for_file.items():
        if use_angular:
            det_ra_deg = np.array([float(getattr(s, "ra_hours", 0)) * 15.0 for s in sources])
            det_dec_deg = np.array([float(getattr(s, "dec_degs", 0)) for s in sources])
            coords = sky_vectors(det_ra_deg, det_dec_deg)
        else:
            # A measured centroid is already at the image epoch. Prefer it to
            # supplied RA/Dec; project sky-only detections only when necessary.
            coords = np.array([(s.x, s.y) for s in sources], dtype=float)
            need_projection = ~np.isfinite(coords).all(axis=1)
            if need_projection.any() and wcs is not None:
                det_ra = np.array([s.ra_hours if s.ra_hours is not None else np.nan for s in sources]) * 15
                det_dec = np.array([s.dec_degs if s.dec_degs is not None else np.nan for s in sources])
                coords[need_projection] = np.column_stack(wcs.all_world2pix(
                    det_ra[need_projection], det_dec[need_projection], 1, quiet=True))
            if not np.isfinite(coords).all():
                raise ValueError("Detected sources need usable detector positions for pixel matching")
        detected_source_coord_for_file[file_id] = coords
        detected_source_kdtree_for_file[file_id] = cKDTree(coords)

    # ---- mutual nearest-neighbour matching --------------------------------------
    matched_sources: list[CatalogSource] = []
    for source in detected_sources:
        file_id, src_idx = detected_source_file_idx[id(source)]
        tree = catalog_source_kdtree_for_file.get(file_id)
        if tree is None:
            continue
        catalog_source_list = catalog_sources_for_file[file_id]
        det_coord = detected_source_coord_for_file[file_id][src_idx]
        i = tree.query(det_coord, distance_upper_bound=match_tol)[1]
        if i >= tree.n:
            continue
        catalog_source = catalog_source_list[catalog_index_for_file[file_id][i]]
        cat_coord = catalog_source_coord_for_file[file_id][i]
        detected_source_list = detected_sources_for_file[file_id]
        reverse_tree = detected_source_kdtree_for_file[file_id]
        j = reverse_tree.query(cat_coord, distance_upper_bound=match_tol)[1]
        if j >= len(detected_source_list) or detected_source_list[j] is not source:
            continue

        source_map = source.model_dump(
            exclude={
                "time",
                "filter",
                "telescope",
                "exp_length",
                "fwhm_x",
                "fwhm_y",
                "theta",
            }
        )
        if not use_angular:
            source_map["x"], source_map["y"] = det_coord
        for attr in (
            "id",
            "catalog_name",
            "mags",
            "label",
            "mag",
            "mag_error",
            "ref_mag",
            "ref_mag_error",
            "flux",
            "flux_error",
            "pm_sky",
            "pm_pos_angle_sky",
            "pm_ra",
            "pm_dec",
            "pm_ra_error",
            "pm_dec_error",
            "pm_pixel",
            "pm_pos_angle_pixel",
            "pm_epoch",
        ):
            val = getattr(catalog_source, attr, None)
            if val is not None:
                source_map[attr] = val

        # A catalog's default zero must not erase saturation measured in the
        # image. Keep the most restrictive supplied pixel count.
        saturation = [s.sat_pixels for s in (source, catalog_source) if s.sat_pixels is not None]
        if saturation:
            source_map["sat_pixels"] = max(saturation)

        matched_sources.append(CatalogSource(**source_map))
        if matched_shapes is not None:
            # M3 (PHOT-11): CatalogSource has no FWHM fields, so the detected
            # shape was lost here and adaptive photometry had none to scale.
            # Kept aligned with matched_sources, index for index.
            matched_shapes.append(
                {attr: getattr(source, attr, None) for attr in ("fwhm_x", "fwhm_y", "theta")}
            )

    if not matched_sources:
        listed = sum(len(rows) for rows in catalog_sources_for_file.values())
        positioned_total = sum(len(index) for index in catalog_index_for_file.values())
        if listed and not positioned_total:
            raise RuntimeError("No catalog source has a usable position to match against")
        raise RuntimeError("Could not match any detected sources to catalog sources")

    return matched_sources


def _collect_calibration_sources(
    photometry_results: list[PhotometryData],
    catalog_sources: list[CatalogSource],
    *,
    catalog_filter_lookup: dict[str, dict[str, str]] | None,
    custom_filter_lookup: dict[str, dict[str, str]] | None,
    allow_preferred_band_fallback: bool = True,
    reference_routes: dict[str, tuple[str, str | None]] | None = None,
) -> list[PhotometryData]:
    from algorithms.catalogs.filters import catalog_filter_lookup as filter_lookup_for
    sources: list[PhotometryData] = []
    catalogs_by_id = {source.id: source for source in catalog_sources if source.id is not None}
    inferred_catalog_name = None
    if catalog_filter_lookup and len(catalog_filter_lookup) == 1:
        inferred_catalog_name = next(iter(catalog_filter_lookup))

    for source in photometry_results:
        catalog_source = catalogs_by_id.get(source.id)
        if catalog_source is None:
            continue

        catalog_name = catalog_source.catalog_name or inferred_catalog_name
        if catalog_name and not catalog_source.catalog_name:
            catalog_source.catalog_name = catalog_name

        ref_mag = getattr(catalog_source, "ref_mag", None)
        ref_err = getattr(catalog_source, "ref_mag_error", None)
        if ref_mag is not None and not math.isfinite(ref_mag):
            # M3: a non-finite supplied ref_mag is unusable, like an absent one.
            ref_mag = ref_err = None
        if ref_mag is None:
            # Apply metadata and custom maps separately so custom entries win
            # across both identities, with source-name priority independent of
            # dictionary order. The helper copies all maps before overlaying.
            lookup = filter_lookup_for(
                catalog_name, custom_filter_lookup, base_filter_lookup=catalog_filter_lookup,
            )
            resolved = _resolve_ref_mag_for_filter_with_route(
                image_filter=getattr(source, "filter", None),
                catalog_name=catalog_name,
                cs_mags=catalog_source.mags,
                custom_filter_lookup={catalog_name: lookup} if catalog_name else None,
                allow_preferred_band_fallback=allow_preferred_band_fallback,
            )
            ref_mag, ref_err = resolved.value, resolved.error
            route = (resolved.kind, resolved.reference)
        else:
            route = ("provided", None)
        if ref_mag is None or not math.isfinite(ref_mag):
            continue
        if ref_err is not None and not math.isfinite(ref_err):
            # M3: calc_solution's `error or 0` keeps NaN (it is truthy), which
            # turns every weight -- and the zero point -- into NaN. An unusable
            # catalog error is treated as no catalog error.
            ref_err = None

        source.ref_mag = ref_mag
        if ref_err is not None:
            source.ref_mag_error = ref_err
        source.catalog_name = catalog_name
        if reference_routes is not None and source.id is not None:
            reference_routes[source.id] = route
        sources.append(source)

    return sources


def perform_field_calibration(
    header,
    data: np.ndarray,
    *,
    wcs: WCS | None = None,
    catalog_sources: Iterable[CatalogSource | Mapping[str, object]] | None = None,
    variable_sources: Iterable[CatalogSource] | None = None,
    file_id: int | None = None,
    field_cal_settings: PhotometricCalibrationSettings | None = None,
    photometry_settings: PhotometrySettings | None = None,
    extraction_settings: SourceExtractionSettings | None = None,
    detected_sources: list[SourceExtractionData] | None = None,
    use_provided_photometry: bool = False,
) -> tuple[float | None, FieldCalResult] | None:
    settings = field_cal_settings or PhotometricCalibrationSettings()
    phot_settings = photometry_settings or PhotometrySettings()
    configured_catalogs = list(settings.catalogs or [])

    logger.info("Starting field calibration for file_id=%s", file_id)
    logger.info("WCS available for field calibration: %s", wcs is not None)

    sources = _normalize_catalog_sources(catalog_sources, file_id=file_id) if catalog_sources else []
    _attach_catalog_magnitudes(sources)

    if not sources or not _has_reference_magnitudes(sources):
        raise ValueError("Missing catalog sources for field calibration")
    logger.info("Using %d provided catalog sources for field calibration", len(sources))

    if not sources:
        raise RuntimeError("No catalog sources available for calibration")

    _ensure_unique_source_ids(sources, file_id=file_id)
    sources = _filter_variable_stars(
        sources,
        variable_sources=variable_sources,
        wcs=wcs,
        header=header,
        variable_check_tol=settings.variable_check_tol,
    )
    logger.info("Catalog sources after variable-star filter: %d", len(sources))

    background: np.ndarray | None = None
    background_rms: np.ndarray | None = None

    if extraction_settings is not None and detected_sources is None:
        detected_sources, background, background_rms = run_source_extraction(
            data,
            header,
            extraction_settings,
            file_id=file_id,
        )

    matched_shapes: list[dict] = []
    sources = _match_detected_sources(
        sources,
        detected_sources or [],
        wcs=wcs,
        header=header,
        data=data,
        source_match_tol=settings.source_match_tol,
        source_match_tol_arcsec=settings.source_match_tol_arcsec,
        matched_shapes=matched_shapes,
    )
    logger.info("Catalog sources after detected-source matching: %d", len(sources))
    logger.info(
        "Matched %d detected sources to catalogs: %s",
        len(sources),
        ", ".join(_catalogs_from_sources(sources)) or "unknown",
    )

    if use_provided_photometry:
        # Legacy "photometry disabled" mode: do not re-measure fluxes; use the
        # magnitudes already carried by the matched sources (e.g. Afterglow-
        # measured photometry supplied via detected_sources). This lets callers
        # exercise the real selection + zero-point algorithm on externally
        # measured photometry. The FILTER is restored from the header because
        # _match_detected_sources drops it from the matched source.
        image_filter = _image_filter_from_header(header)
        photometry_results = []
        for source in sources:
            src_map = source.model_dump(
                exclude={"mags", "catalog_name", "label", "ref_mag", "ref_mag_error"}
            )
            if src_map.get("file_id") is None:
                src_map["file_id"] = file_id
            if not src_map.get("filter"):
                src_map["filter"] = image_filter
            photometry_results.append(PhotometryData(**src_map))
    else:
        normalized_sources: list[SourceExtractionData] = []
        # matched_shapes is empty when no detections were matched (no-op path).
        shapes = matched_shapes if len(matched_shapes) == len(sources) else [{}] * len(sources)
        for source, shape in zip(sources, shapes):
            src_map = source.model_dump(
                exclude_unset=True,
                exclude={
                    "catalog_name",
                    "label",
                    "mags",
                    "ref_mag",
                    "ref_mag_error",
                    "mag",
                    "mag_error",
                    "flux_error",
                },
            )
            if src_map.get("file_id") is None:
                src_map["file_id"] = file_id
            # M3 (PHOT-11): restore the matched detection's FWHM. Read only by
            # mode="auto"; aperture photometry ignores it.
            src_map.update({attr: value for attr, value in shape.items() if value is not None})
            if matched_shapes:
                # Matching supplies the observed detector position, already at
                # the frame epoch. Do not reproject a supplied sky position or
                # apply the catalog's proper motion to that measurement again.
                for attr in ("ra_hours", "dec_degs", "pm_sky", "pm_pos_angle_sky",
                             "pm_pixel", "pm_pos_angle_pixel", "pm_epoch"):
                    src_map[attr] = None
            normalized_sources.append(SourceExtractionData(**src_map))

        # LEGACY AFTERGLOW PARITY — DO NOT "CLEAN UP".  Forcing apcorr_tol to 0
        # is what disables aperture correction for calibration photometry: the
        # aperture-photometry kernel gates its correction pass on
        # `apcorr_tol > 0`.  Restoring the caller's apcorr_tol (default 1e-4)
        # silently switches aperture correction on and the zero point diverges
        # from legacy Afterglow output.  (Annotation added by the extraction;
        # the statement itself is verbatim from field_cal.py:612.)
        cal_phot_settings = phot_settings.model_copy(update={"apcorr_tol": 0.0})
        photometry_results = run_photometry(
            data,
            header,
            normalized_sources,
            cal_phot_settings,
            wcs=wcs,
            background=None,
            background_rms=background_rms,
        )
    # M3: a non-finite magnitude reached calc_solution and raised LinAlgError.
    # An infinite mag_error survives calc_solution's `> 0` filter, gives a
    # zero SNR, and turns the limiting magnitude (limmag5) into NaN.
    photometry_results = [
        source for source in photometry_results
        if source.mag is not None and math.isfinite(source.mag)
        and (source.mag_error is None or math.isfinite(source.mag_error))
        and (source.flux is None or (math.isfinite(source.flux) and source.flux > 0))
        and not (getattr(source, "sat_pixels", None) or 0) > 0
    ]

    if not photometry_results:
        raise RuntimeError("No catalog sources could be photometered")
    logger.info("Photometry produced %d catalog-linked measurements", len(photometry_results))

    min_snr = settings.min_snr if settings.min_snr is not None else 0
    max_snr = settings.max_snr if settings.max_snr is not None else np.inf
    if settings.min_snr or settings.max_snr:
        def measurement_snr(source):
            if source.flux is not None and source.flux_error is not None:
                if (math.isfinite(source.flux) and source.flux > 0
                        and math.isfinite(source.flux_error) and source.flux_error > 0):
                    return source.flux / source.flux_error
                return np.nan
            # Invert the retained mag_error = 2.5*log10(1 + error/flux)
            # relation for legacy rows carrying only magnitude uncertainty.
            if source.mag_error is None or not math.isfinite(source.mag_error) or source.mag_error <= 0:
                return np.nan
            with np.errstate(over="ignore"):
                return 1 / np.expm1(np.log(10) * source.mag_error / 2.5)

        photometry_results = [
            source
            for source in photometry_results
            if min_snr <= measurement_snr(source) <= max_snr
        ]
        logger.info("Photometry results after SNR filter: %d", len(photometry_results))
        if not photometry_results:
            raise RuntimeError("All sources violate SNR constraints")

    reference_routes: dict[str, tuple[str, str | None]] = {}
    calibration_sources = _collect_calibration_sources(
        photometry_results,
        sources,
        catalog_filter_lookup=_catalog_filter_lookup_map(sources, configured_catalogs),
        custom_filter_lookup=settings.custom_filter_lookup or None,
        allow_preferred_band_fallback=not settings.strict_filter_parity,
        reference_routes=reference_routes,
    )
    logger.info("Calibration sources after ref-mag resolution: %d", len(calibration_sources))

    if not calibration_sources:
        raise RuntimeError("No calibration sources matched catalog magnitudes")

    # max_stars: limit to brightest N calibration stars (by ref_mag, ascending = brightest first)
    max_stars = settings.max_stars
    if max_stars and len(calibration_sources) > max_stars:
        calibration_sources = sorted(
            calibration_sources,
            key=lambda s: s.ref_mag if s.ref_mag is not None else np.inf,
        )[:max_stars]
        logger.info("Calibration sources after max_stars=%d limit: %d", max_stars, len(calibration_sources))

    logger.info(
        "Resolving zero-point from %d sources (catalogs: %s)",
        len(calibration_sources),
        ", ".join(_catalogs_from_sources(sources)) or "unknown",
    )

    solution, survivor_mask = _calc_solution_with_mask(calibration_sources)
    m0, m0_error, slop, limmag, rej_percent = solution
    logger.info(
        "Field calibration solution: m0=%.4f m0_err=%s slop=%s limmag=%s rej=%.1f%%",
        m0,
        m0_error,
        slop,
        limmag,
        rej_percent,
    )

    # M3 (PHOT-08): a degenerate solve wrote no keywords (astropy rejected the
    # NaN PHOT_M0), logged a warning and was returned as a calibration. A
    # solve without a finite zero point and a finite, positive uncertainty is
    # refused here, before the header is touched.
    num_stars = len(calibration_sources)
    survivors = int(np.count_nonzero(survivor_mask))
    if not np.isfinite(m0):
        raise DegenerateCalibrationError(
            f"The solve over {num_stars} calibration star(s) produced a non-finite zero point.",
            num_stars=num_stars,
        )
    if m0_error is None or not np.isfinite(m0_error) or m0_error <= 0:
        if survivors < 2:
            reason = (
                f"{survivors} of {num_stars} calibration stars survived outlier rejection"
                if survivors != num_stars
                else f"{num_stars} calibration star"
            ) + "; at least two are needed to estimate its uncertainty"
        else:
            reason = (
                f"over {survivors} calibration stars its uncertainty is {m0_error!r} "
                "(identical residuals or no usable errors)"
            )
        raise DegenerateCalibrationError(
            f"The zero point is not usable: {reason}.",
            num_stars=survivors,
        )

    # Write photometric zero-point to FITS header if accessible
    try:
        zero_point_offset = getattr(phot_settings, "zero_point_mag", 0) or 0
        header["PHOT_M0"] = (
            float(m0) + float(zero_point_offset),
            "Photometric zero point",
        )
        header["PHOT_M0E"] = (float(m0_error), "Photometric zero point error")
        catalog_str = ", ".join(_catalogs_from_sources(calibration_sources)) or "unknown"
        header["PHOT_CAL"] = (catalog_str[:68], "Photometric calibration catalog")
    except Exception as exc:
        logger.warning("Could not write photometric keywords to header: %s", exc)

    result = FieldCalResult(
        file_id=file_id,
        phot_results=calibration_sources,
        zero_point_corr=m0,
        zero_point_error_mag=m0_error,
        zero_point_slop=slop,
        limmag5=limmag,
        rej_percent=rej_percent,
    )
    result._reference_routes = {
        source.id: reference_routes[source.id]
        for source, survived in zip(result.phot_results, survivor_mask)
        if survived and source.id in reference_routes
    }
    result._num_calibration_stars = survivors
    return result.zero_point_corr, result
