"""Bounded spherical catalog queries and observation-epoch preparation (M5).

This first-party layer keeps the two ATLAS searches and reference follow-up on
the same geometry. Reader row/work limits still apply before any selection.
"""

from dataclasses import dataclass
import math

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.time import Time

from algorithms.diagnostics import note_numerical_issue
from algorithms.skylib_lite.util.fits import get_fits_time
from .limits import check_query_budget, validate_catalog_radius


@dataclass
class PreparedCatalog:
    ra_deg: np.ndarray
    dec_deg: np.ndarray
    mag: np.ndarray | None = None
    pm_ra_cosdec_mas_per_year: np.ndarray | None = None
    pm_dec_mas_per_year: np.ndarray | None = None
    epoch_jyear: float | None = None


def observation_epoch(header) -> float | None:
    """Use the recorded exposure midpoint; never substitute today's date."""
    try:
        duration = float(header.get("EXPTIME", header.get("EXPOSURE", 0.)))
        if not math.isfinite(duration) or duration < 0:
            return None
        start, middle, _ = get_fits_time(header)
        value = middle if middle is not None else start
        if value is not None:
            return float(Time(value, scale="utc").jyear)
        if header.get("MJD-OBS") is not None:
            start = float(header["MJD-OBS"])
            if not math.isfinite(start) or not math.isfinite(duration) or duration < 0:
                return None
            return float(Time(start + duration / 172800, format="mjd", scale="utc").jyear)
        return None
    except MemoryError:
        raise
    except (ValueError, TypeError, OverflowError):
        return None


def image_epoch(path) -> float | None:
    try:
        return observation_epoch(fits.getheader(path))
    except MemoryError:
        raise
    except (OSError, ValueError):
        return None


def gnomonic_projection(ra_deg, dec_deg, ra0_deg, dec0_deg) -> np.ndarray:
    """Project only the visible open hemisphere; invalid positions become NaN."""
    ra, dec = np.deg2rad(ra_deg), np.deg2rad(dec_deg)
    ra0, dec0 = np.deg2rad(ra0_deg), np.deg2rad(dec0_deg)
    cosc = np.sin(dec0) * np.sin(dec) + np.cos(dec0) * np.cos(dec) * np.cos(ra - ra0)
    visible = np.isfinite(cosc) & (cosc > 8 * np.finfo(float).eps) & (np.abs(dec) <= np.pi / 2)
    xi = np.full(np.shape(cosc), np.nan)
    eta = np.full(np.shape(cosc), np.nan)
    np.divide(np.cos(dec) * np.sin(ra - ra0), cosc, out=xi, where=visible)
    np.divide(np.cos(dec0) * np.sin(dec) - np.sin(dec0) * np.cos(dec) * np.cos(ra - ra0),
              cosc, out=eta, where=visible)
    return np.stack([xi, eta], axis=-1)


def catalog_indices(xy: np.ndarray, limit: int | None, mag=None) -> np.ndarray:
    """Keep valid positions, preferring measured bright stars when capped."""
    keep = np.flatnonzero(np.isfinite(xy).all(axis=1))
    if not limit or len(keep) <= limit:
        return keep
    distance = np.hypot(xy[keep, 0], xy[keep, 1])
    if mag is None:
        brightness = np.full(len(keep), np.inf)
    else:
        values = np.ma.asarray(mag, dtype=float).filled(np.nan)
        if values.shape != (len(xy),):
            raise ValueError("Catalog magnitudes do not align with positions")
        brightness = values[keep]
        brightness = np.where(np.isfinite(brightness), brightness, np.inf)
    if not np.isfinite(brightness).all():
        note_numerical_issue("astrometry_catalog_brightness_unavailable",
                             "Some reference stars lack catalog brightness. The cap keeps measured "
                             "bright stars first, then unmeasured stars by distance; depth agreement is unverified.")
    return keep[np.lexsort((keep, distance, brightness))[:limit]]


def _optional_array(result, name, count):
    value = getattr(result, name, None)
    if value is None:
        return None
    array = np.ma.asarray(value, dtype=float).filled(np.nan)
    if array.shape != (count,):
        raise ValueError(f"Catalog {name} does not align with positions")
    return array


def query_spherical_catalog(index, ra0_deg, dec0_deg, radius_deg, *, thin=1,
                            epoch_jyear=None, max_radius_deg=2.) -> PreparedCatalog:
    """Enclose a spherical cap, propagate motion, then clip to the requested cap.

    An epoch-aware reader declares a maximum vector proper motion permitted by
    its storage format. Expanding by that bound includes stars moving *into*
    the cap; the expanded footprint must fit the same operational radius limit.
    """
    validate_catalog_radius(radius_deg, max_radius_deg)
    if not math.isfinite(ra0_deg) or not math.isfinite(dec0_deg) or abs(dec0_deg) > 90:
        raise ValueError("Catalog center must have finite sky coordinates")
    if epoch_jyear is not None and not math.isfinite(epoch_jyear):
        raise ValueError("Catalog observation epoch must be finite")
    base_epoch = getattr(index, "epoch_jyear", None)
    maximum_motion = getattr(index, "max_pm_mas_per_year", None)
    halo = 0.
    if epoch_jyear is not None and base_epoch is not None and maximum_motion is not None:
        if not math.isfinite(base_epoch) or not math.isfinite(maximum_motion) or maximum_motion < 0:
            raise ValueError("Catalog motion bound and reference epoch must be finite")
        halo = abs(epoch_jyear - base_epoch) * maximum_motion / 3_600_000
    query_radius = radius_deg + halo
    validate_catalog_radius(query_radius, max_radius_deg)
    # Round outward only after budget validation, to include exact boundaries.
    radius = np.nextafter(float(query_radius), np.inf)
    bottom, top = max(-90., dec0_deg - radius), min(90., dec0_deg + radius)
    if abs(dec0_deg) + radius >= 90:
        lo, hi = 0., 360.
    else:
        half_ra = math.degrees(math.asin(min(1., math.sin(math.radians(radius)) /
                                              math.cos(math.radians(dec0_deg)))))
        lo, hi = ra0_deg - half_ra, ra0_deg + half_ra
    # Both readers preserve full turns. One call also preserves the candidate
    # work budget, including scanned rows that later fail the Dec filter.
    result = index.query_box(lo, hi, bottom, top, thin=thin)
    check_query_budget(0, len(result.ra_deg))
    ra = np.asarray(result.ra_deg, dtype=float)
    dec = np.asarray(result.dec_deg, dtype=float)
    if ra.ndim != 1 or dec.shape != ra.shape:
        raise ValueError("Catalog coordinates do not align")
    count = len(ra)
    mag = _optional_array(result, "mag", count)
    pm_ra = _optional_array(result, "pm_ra_cosdec_mas_per_year", count)
    pm_dec = _optional_array(result, "pm_dec_mas_per_year", count)
    source_epoch = getattr(result, "epoch_jyear", base_epoch)
    if source_epoch is not None and not math.isfinite(source_epoch):
        source_epoch = None
    output_epoch = source_epoch
    valid = np.isfinite(ra) & np.isfinite(dec) & (np.abs(dec) <= 90)
    ra, dec = ra.copy(), dec.copy()
    if count:
        if epoch_jyear is None or source_epoch is None or pm_ra is None or pm_dec is None:
            note_numerical_issue("astrometry_catalog_epoch_unverified",
                                 "Reference positions could not be propagated: the observation date "
                                 "or catalog epoch/proper motion is unavailable. Astrometric epoch agreement is unverified.")
        elif epoch_jyear != source_epoch:
            motion_valid = valid & np.isfinite(pm_ra) & np.isfinite(pm_dec)
            if not motion_valid.all():
                note_numerical_issue("astrometry_catalog_epoch_unverified",
                                     "Some reference stars lack finite proper motions and were omitted "
                                     "because their observation-epoch positions cannot be established.")
            valid &= motion_valid
            # Constant tangential motion along a great circle, with no assumed
            # distance, radial velocity or perspective acceleration.
            sky = SkyCoord(ra[motion_valid] * u.deg, dec[motion_valid] * u.deg)
            dt = epoch_jyear - source_epoch
            moved = sky.directional_offset_by(np.arctan2(pm_ra[motion_valid], pm_dec[motion_valid]) * u.rad,
                                              np.hypot(pm_ra[motion_valid], pm_dec[motion_valid]) * dt * u.mas)
            ra[motion_valid], dec[motion_valid] = moved.ra.deg, moved.dec.deg
            # Transport the tangent direction too, so reference objects can
            # safely carry these motions with their new coordinate epoch.
            rate = np.hypot(pm_ra[motion_valid], pm_dec[motion_valid])
            bearing = moved.position_angle(sky).rad + (np.pi if dt > 0 else 0.)
            pm_ra = pm_ra.copy()
            pm_dec = pm_dec.copy()
            pm_ra[motion_valid] = rate * np.sin(bearing)
            pm_dec[motion_valid] = rate * np.cos(bearing)
            output_epoch = epoch_jyear
    keep = np.zeros(count, dtype=bool)
    if valid.any():
        center = SkyCoord(ra0_deg * u.deg, dec0_deg * u.deg)
        sky = SkyCoord(ra[valid] * u.deg, dec[valid] * u.deg)
        keep[valid] = center.separation(sky).deg <= np.nextafter(radius_deg, np.inf)
    return PreparedCatalog(ra[keep] % 360, dec[keep],
                           None if mag is None else mag[keep],
                           None if pm_ra is None else pm_ra[keep],
                           None if pm_dec is None else pm_dec[keep],
                           output_epoch)
