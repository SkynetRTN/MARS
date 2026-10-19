"""SDSS query backend.

SDSS is the exception among MARS's catalogs: it is not served through VizieR
but through SkyServer, which takes SQL. astroquery's ``SDSSClass`` can build
cone-search SQL but not the rectangular queries the image-footprint path needs,
and its default query does not filter on data quality. So the payload is built
here instead.

The SQL restricts to ``Star`` (not galaxies), joins ``Field`` to require
``quality = 3`` — SkyServer's "primary, good photometry" grade — and requires
``clean = 1``, SDSS's own flag for photometry with no known problems. Those two
predicates are why SDSS zero points come out usable without further filtering,
and dropping them would quietly widen the source list with unreliable rows.

EXTRACTED FROM:
``afterglow-core/afterglow_core/resources/catalog_plugins/sdss_catalog.py``
(lines 19-100 and the three query overrides) and its Skynet counterpart. MARS
takes Skynet's ``_args_to_payload`` signature — Afterglow passed ``radius=None``
through to ``super()``, which newer astroquery rejects.
"""

from __future__ import annotations

import logging
import math
import re
from numbers import Integral
from typing import Dict as TDict, List as TList, Optional

import numpy as np
from astropy.coordinates import Angle, SkyCoord
from astropy.units import arcmin, arcsec, deg, hour
from astroquery.sdss import SDSSClass

from algorithms.catalogs.schemas import CatalogSource

from .vizier import VizierCatalog, _round_for_cache

__all__ = ["MARSSDSS", "SDSSQueryBackend"]

logger = logging.getLogger(__name__)


# First-party CAT-02/27 acceptance bounds. SQL quality/geometry stay upstream.
MAX_SDSS_ROWS = 5_000
MAX_SDSS_FIELDS = 64
MAX_SDSS_FIELD_LENGTH = 64
_SQL_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*", re.ASCII)


def _row_limit(limit: int | None, default: int | None = MAX_SDSS_ROWS) -> int:
    value = (MAX_SDSS_ROWS if default is None else default) if limit is None else limit
    if not isinstance(value, Integral) or isinstance(value, bool) or not 1 <= value <= MAX_SDSS_ROWS:
        raise ValueError(f"SDSS limit must be an integer between 1 and {MAX_SDSS_ROWS}.")
    return int(value)


def _projection_fields(fields: object) -> list[str]:
    if not isinstance(fields, (list, tuple)) or not 1 <= len(fields) <= MAX_SDSS_FIELDS:
        raise ValueError(f"SDSS photoobj_fields must contain 1 to {MAX_SDSS_FIELDS} field names.")
    if any(not isinstance(field, str) or len(field) > MAX_SDSS_FIELD_LENGTH
           or not _SQL_IDENTIFIER.fullmatch(field) for field in fields):
        raise ValueError("SDSS field names must be bounded literal SQL identifiers, not expressions.")
    return list(fields)


def _positive_angle(value: object, unit: str) -> float:
    try:
        number = float(Angle(value).to_value(unit))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("SDSS region dimensions must be scalar angles.") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError("SDSS region dimensions must be finite and positive.")
    return number


def _finite_region_inputs(ra_hours: float, dec_degs: float, *sizes: float) -> None:
    try:
        valid = math.isfinite(ra_hours) and math.isfinite(dec_degs) and -90 <= dec_degs <= 90
        valid = valid and math.isfinite(ra_hours * 5400)
        valid = valid and all(math.isfinite(size) and math.isfinite(size * 5) and size > 0 for size in sizes)
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        raise ValueError("SDSS region inputs must be finite with positive dimensions and valid declination.")


class MARSSDSS(SDSSClass):
    """``SDSSClass`` that builds MARS's SkyServer SQL.

    EXTRACTED: was ``AfterglowSDSS``. Renamed — MARS is not Afterglow — but
    the quality predicates/region geometry are preserved. CAT-02/27 adds a
    bounded TOP and literal projection fields; backend regions use query_sql,
    not the pinned SDK's incompatible cross-ID/region payload protocol.
    """

    def _args_to_payload(
        self,
        coordinates=None,
        radius=2 * arcsec,
        photoobj_fields=None,
        data_release=17,
        limit=None,
        **kwargs,
    ):
        """Return the SkyServer request payload.

        A two-element ``radius`` tuple means a rectangular region — that is
        MARS's extension to the astroquery signature, and it is how the
        image-footprint path asks for a box. Anything else is a cone search and
        goes through SkyServer's ``fGetNearbyObjEq``.

        The rectangular branch mirrors ``geometry.clip_sources_to_box``: the RA
        half-width is ``arcsin(sin(w/2)/cos(dec))``, not ``w/2/cos(dec)``, and a
        pole inside the region or a region straddling RA=0/360 splits into the
        same four cases. Here they become SQL predicates instead of a filter.

        Requires scalar coordinates, a finite positive region and bounded
        literal fields. Missing inputs fail locally rather than triggering the
        SDK's metadata requests or an unbounded fallback query.
        """
        limit = _row_limit(limit)
        photoobj_fields = _projection_fields(photoobj_fields)
        if not isinstance(coordinates, SkyCoord) or not coordinates.isscalar:
            raise ValueError("SDSS SQL regions require scalar SkyCoord coordinates.")
        if not math.isfinite(coordinates.ra.degree) or not math.isfinite(coordinates.dec.degree):
            raise ValueError("SDSS SQL coordinates must be finite.")
        if radius is None:
            raise ValueError("SDSS SQL regions require a radius or width/height tuple.")

        if isinstance(radius, tuple) and len(radius) == 2:
            # Rectangular region
            region = ''
            ra, dec = coordinates.ra.degree, coordinates.dec.degree
            height = _positive_angle(radius[1], 'degree')
            width = _positive_angle(radius[0], 'degree')
            h = height/2
            dec_min, dec_max = dec - h, dec + h
            if dec_min < -90:
                # South Pole in FOV, use the whole RA range
                where = f's.dec <= {dec_max}'
            elif dec_max > 90:
                # North Pole in FOV, use the whole RA range
                where = f's.dec >= {dec_min}'
            else:
                ratio = np.sin(np.deg2rad(width/2)) / np.cos(np.deg2rad(dec))
                if not math.isfinite(ratio) or abs(ratio) > 1:
                    raise ValueError("SDSS box has no finite RA span under the preserved geometry.")
                w = np.rad2deg(np.arcsin(ratio))
                ra_min, ra_max = ra - w, ra + w
                if ra_max >= ra_min + 360:
                    # RA spans the whole 360deg range
                    where = f's.dec BETWEEN {dec_min} AND {dec_max}'
                elif ra_min < 0:
                    # RA range encloses RA=0 => two separate RA ranges:
                    # ra_min + 360 <= ra <= 360 and 0 <= ra <= ra_max
                    where = f'(s.ra >= {ra_min + 360} OR s.ra <= {ra_max}) ' \
                        f'AND s.dec BETWEEN {dec_min} AND {dec_max}'
                elif ra_max > 360:
                    # RA range encloses RA=360 => two separate RA ranges:
                    # ra_min <= ra <= 360 and 0 <= ra <= ra_max - 360
                    where = f'(s.ra >= {ra_min} OR s.ra <= {ra_max - 360}) ' \
                        f'AND s.dec BETWEEN {dec_min} AND {dec_max}'
                else:
                    # RA range fully within [0, 24)
                    where = f's.ra BETWEEN {ra_min} AND {ra_max} ' \
                        f'AND s.dec BETWEEN {dec_min} AND {dec_max}'
        else:
            # Circular region
            region = 'fGetNearbyObjEq({},{},{}) AS n, '.format(
                coordinates.ra.degree, coordinates.dec.degree,
                _positive_angle(radius, 'arcmin'))
            where = 'n.objID = s.objID'

        # Construct SQL query
        # noinspection SqlResolve
        q = 'SELECT DISTINCT TOP {} {} ' \
            'FROM {}Star AS s ' \
            'JOIN Field f ON s.fieldID = f.fieldID ' \
            'WHERE {} AND f.quality = 3 AND s.clean = 1' \
            .format(
                limit,
                ', '.join(['s.{0}'.format(sql_field)
                           for sql_field in photoobj_fields]),
                region, where,
            )

        request_payload = dict(cmd=q, format='csv')

        if data_release > 11:
            request_payload['searchtool'] = 'SQL'

        return request_payload


#: Module-level template instance. ``SDSSClass`` is stateless for our purposes;
#: the query methods below call it to get a fresh instance per query, matching
#: upstream.
SDSS = MARSSDSS()


class SDSSQueryBackend(VizierCatalog):
    """SkyServer backend for the SDSS plugin.

    Inherits ``VizierCatalog`` for ``_derive_columns`` and ``table_to_sources``
    — the column-expression machinery is provider-agnostic — but overrides all
    three query methods, so no VizieR request is ever made. The inheritance is
    upstream's arrangement and is kept; ``vizier_catalog`` stays ``None``.

    Region rounding matches ``VizierCatalog``: with the cache on, centres snap
    to 10 arcsec and sizes round up to 0.2 arcmin.

    ``constraints`` is accepted and ignored on every method — the SQL applies
    its own quality predicates and upstream never wired column filters through.
    A caller passing constraints to SDSS gets unfiltered results, silently.

    ``data_release`` comes from the plugin declaration in
    ``catalogs/sdss_catalog.py``, which also builds ``display_name`` from it —
    the two must move together, so the release is not configurable separately.

    Region requests use MARS's bounded quality-filtered SQL via the installed
    SDK's query_sql transport. Limits default to the declaration's row_limit,
    never exceed 5,000, and are applied before mapping even if a provider ignores
    TOP. This does not provide an HTTP-byte or whole-call deadline budget.
    """

    def query_objects(self, names: TList[str]) -> TList[CatalogSource]:
        """Return SDSS objects with the given names, one request each."""
        sdss = SDSS()
        rows = []
        for name in names:
            rows.append(
                sdss.query_object(
                    name,
                    data_release=self.data_release,
                    photoobj_fields=self._columns,
                    cache=self.cache,
                )[0]
            )
        return self.table_to_sources(rows)

    def query_box(
        self,
        ra_hours: float,
        dec_degs: float,
        width_arcmins: float,
        height_arcmins: Optional[float] = None,
        constraints: Optional[TDict[str, str]] = None,
        limit: Optional[int] = None,
    ) -> TList[CatalogSource]:
        """Return SDSS objects in a rectangular region."""
        if height_arcmins is None:
            height_arcmins = width_arcmins

        _row_limit(limit, self.row_limit)
        _finite_region_inputs(ra_hours, dec_degs, width_arcmins, height_arcmins)

        if self.cache:
            ra_hours, dec_degs, (width_arcmins, height_arcmins) = _round_for_cache(
                ra_hours, dec_degs, width_arcmins, height_arcmins
            )

        return self._query_sql_region(
            ra_hours, dec_degs,
            (width_arcmins * arcmin, height_arcmins * arcmin), limit,
        )

    def query_circ(
        self,
        ra_hours: float,
        dec_degs: float,
        radius_arcmins: float,
        constraints: Optional[TDict[str, str]] = None,
        limit: Optional[int] = None,
    ) -> TList[CatalogSource]:
        """Return SDSS objects within a circular region."""
        _row_limit(limit, self.row_limit)
        _finite_region_inputs(ra_hours, dec_degs, radius_arcmins)
        if self.cache:
            ra_hours, dec_degs, (radius_arcmins,) = _round_for_cache(
                ra_hours, dec_degs, radius_arcmins
            )

        return self._query_sql_region(
            ra_hours, dec_degs, radius_arcmins * arcmin, limit,
        )

    def _query_sql_region(self, ra_hours, dec_degs, radius, limit):
        limit = _row_limit(limit, self.row_limit)
        # Build before client construction: no validation path reaches metadata
        # lookups or the SDK's incompatible region/cross-ID payload builder.
        payload = MARSSDSS()._args_to_payload(
            coordinates=SkyCoord(ra=ra_hours, dec=dec_degs, unit=(hour, deg), frame="icrs"),
            radius=radius, photoobj_fields=self._columns,
            data_release=self.data_release, limit=limit,
        )
        client = SDSS()
        rows = client.query_sql(payload["cmd"], data_release=self.data_release, cache=self.cache)
        if rows is None:
            return []
        return self.table_to_sources(rows[:limit])
