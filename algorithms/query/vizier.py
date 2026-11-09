"""VizieR query backend.

Nine of MARS's eleven catalogs are hosted at VizieR, and they differ only in
their declarations: which table, which columns, which bands. This module is the
one engine that drives all of them.

Three jobs:

1. **Work out which columns to request.** A plugin's ``col_mapping`` values are
   Python expressions over provider column names (``'RAJ2000/15'``), not column
   names. ``_derive_columns`` parses each one and reads its data dependencies
   out, so the request asks VizieR only for columns the plugin can actually use.
2. **Map rows onto ``CatalogSource``.** ``table_to_sources`` evaluates those
   same expressions against each row and builds the per-band ``Mag`` objects.
3. **Issue the query.** Object, box and circle queries, with cache-friendly
   rounding of the region.

EXTRACTED FROM:
``afterglow-core/afterglow_core/resources/catalog_plugins/vizier_catalogs.py``
(373 lines) and its de-Flasked counterpart at
``skynet/.../optical_data_processing/catalogs/vizier_catalogs.py`` (352 lines).
MARS takes Afterglow's version — it is the superset — and replaces
``current_app.config`` with ``query/config.py``. The two upstreams had drifted:
Skynet dropped the configurable server and the custom-catalog factory, both of
which are restored here.
"""

from __future__ import annotations

import ast
from io import BytesIO
import logging
import math
import re
from typing import Dict as TDict, List as TList, Optional, Union
from xml.etree.ElementTree import ParseError, iterparse

import numpy
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.units import arcmin, deg, hour
from astroquery.vizier import VizierClass as _AstroqueryVizierClass

from algorithms.catalogs.catalog import Catalog
from algorithms.catalogs.schemas import CatalogSource, Mag

from .cache import install_cache_error_suppression
from .config import settings
from .coverage import note_row_limit

__all__ = ["ProviderResponseError", "Vizier", "VizierCatalog", "build_custom_vizier_catalog"]

logger = logging.getLogger(__name__)


class ProviderResponseError(ValueError):
    """A provider returned rows MARS cannot use (M3, CAT-20).

    Raised for renamed or missing coordinate or magnitude columns, so an
    unusable response is never mistaken for a field with no stars. An empty
    successful response, or well-formed rows with nothing measurable, is still
    ``[]``. Explicit provider error payloads are failures even with HTTP 200.
    """


class VizierClass(_AstroqueryVizierClass):
    """Keep query errors that astroquery otherwise discards during parsing.

    The SDK class name is retained so its cache stays in the Vizier directory
    covered by our existing pruning policy. Other SDK behavior is inherited.
    """

    def _parse_result(self, response, **kwargs):
        if response.content.lstrip().startswith(b"<"):
            try:
                # Clear parsed elements as we go; no second full table tree is
                # needed just to check INFO elements, including trailing ones.
                for _, element in iterparse(BytesIO(response.content), events=("end",)):
                    if element.tag.rsplit("}", 1)[-1] == "INFO":
                        name = element.get("name", "").casefold()
                        value = element.get("value", "")
                        if name == "error" or (name == "query_status" and value.casefold() == "error"):
                            message = (element.text or "").strip()
                            if name == "error":
                                message = value + " " + message
                            raise ProviderResponseError(
                                f"VizieR query failed: {message.strip()[:500] or 'unspecified provider error'}"
                            )
                    element.clear()
            except (ParseError, ProviderResponseError) as exc:
                # The SDK caches HTTP-200 replies before parsing. Evict an
                # explicit failure so a later query can reach the provider.
                query = getattr(self, "_last_query", None)
                if query is not None:
                    query.remove_cache_file(self.cache_location)
                if isinstance(exc, ProviderResponseError):
                    raise
                raise ProviderResponseError(f"VizieR returned malformed XML: {exc}") from exc
        return super()._parse_result(response, **kwargs)


Vizier = VizierClass()

# astroquery treats cache failures as query failures; MARS does not. See
# query/cache.py. Installed on import so that merely importing this module gives
# the same behaviour upstream had, where the patch was a side effect of
# importing the catalog plugins.
install_cache_error_suppression()


class VizierCatalog(Catalog):
    """Query backend for a VizieR-hosted catalog.

    Mixed onto a plugin declaration by ``query/binding.py``; not instantiated
    directly. The declaration supplies ``vizier_catalog``, ``col_mapping``,
    ``mags``, ``row_limit``, ``sort`` and ``extra_cols``.

    ``col_mapping`` values may be plain column names (``'DEJ2000'``),
    arithmetic over them (``'RAJ2000/15'``), NumPy calls, or Python expressions
    against string columns — Landolt parses sexagesimal RA out of a text column
    that way. Anything that is not a valid expression is treated as a literal
    column name.

    ``sort`` entries are VizieR's signed column syntax: ``'+Rmag'`` ascending,
    ``'-Rmag'`` descending. They are folded into the requested column list,
    replacing the unsigned name if it is already there.
    """

    vizier_server = None
    cache: bool = False
    vizier_catalog = None
    row_limit = None
    col_mapping = {"ra_hours": "RAJ2000/15", "dec_degs": "DEJ2000"}
    extra_cols: TList[str] = []
    sort: TList[str] = []

    _columns = None

    def __init__(self, filter_lookup: Optional[TDict[str, str]] = None, **kwargs):
        """Build the backend and resolve the VizieR column list.

        ``vizier_server`` and ``cache`` fall back to ``query/config.py``, which
        is the seam where Afterglow read Flask's ``current_app.config``.
        """
        super().__init__(filter_lookup)

        for key, value in kwargs.items():
            setattr(self, key, value)

        if self.vizier_server is None:
            self.vizier_server = settings.VIZIER_SERVER
        if "cache" not in kwargs:
            self.cache = settings.VIZIER_CACHE_ENABLED

        self._columns = self._derive_columns()

    def _derive_columns(self) -> TList[str]:
        """Return the VizieR column names this catalog needs.

        Share expression analysis with response validation: call targets and
        attribute names are excluded, while literal columns named ``int`` or
        ``sqrt`` remain data dependencies.
        """
        columns: TList[str] = []

        if self.col_mapping:
            for attrname, expr in self.col_mapping.items():
                try:
                    columns.extend(_expression_columns(expr))
                except ValueError as e:
                    raise ValueError(
                        'Bad column definition "{}" for attribute "{}" of '
                        'catalog "{}": {}'.format(expr, attrname, self.name, e)
                    )

        if self.extra_cols:
            columns += self.extra_cols

        if getattr(self, "mags", None):
            for item in self.mags.values():
                mag_col, mag_err_col = _mag_columns(item)
                if mag_col:
                    columns.append(mag_col)
                    if mag_err_col:
                        columns.append(mag_err_col)

        if self.sort:
            for col in self.sort:
                _, colname = col[:1], col[1:]
                if colname in columns:
                    columns[columns.index(colname)] = col
                else:
                    columns.append(col)

        return columns

    def table_to_sources(
        self, table: Union[TList, Table]
    ) -> TList[CatalogSource]:
        """Map an astropy table of VizieR rows onto ``CatalogSource`` objects.

        Per row: evaluate every ``col_mapping`` expression to fill the source's
        attributes, then read each declared band into a ``Mag``.

        Two preserved behaviours worth knowing:

        * **Rows with no magnitudes are dropped.** A source MARS cannot
          photometer is not useful to a caller, and upstream's field calibration
          depends on the filtering. It means ``len(table)`` and
          ``len(sources)`` differ routinely.
        * **A magnitude of 99 or more is "not measured".** VizieR uses 99 as a
          null in several tables, and a 99th-magnitude star would be
          meaningless anyway.

        Column lookups retry with apostrophes replaced by underscores, because
        astroquery renames columns like ``g'mag`` to ``g_mag`` depending on the
        table and version, and with a leading underscore added or removed
        (``_2MASS``/``2MASS``).

        M3 (CAT-20): a response missing its coordinate columns, or every
        declared band column, raises ``ProviderResponseError`` instead of
        mapping to ``[]``. Well-formed rows with nothing measurable still map
        to ``[]`` (logged). See ``docs/extraction.md``, Query §5.12.
        """
        sources: TList[CatalogSource] = []
        if table is None or len(table) == 0:
            # Empty response
            return sources

        context = dict(numpy.__dict__)
        colnames = list(getattr(table, "colnames", None) or table[0].colnames)
        aliases = self._check_response_columns(colnames)

        for row in table:
            source = CatalogSource(catalog_name=self.name, mags={})

            if self.col_mapping:
                for attr, expr in self.col_mapping.items():
                    try:
                        # Fast path: the mapping is a plain column name, or
                        # one the provider now spells differently (M3).
                        val = row[aliases.get(expr, expr)]
                    except KeyError:
                        ctx = dict(context)
                        ctx.update({name: row[name] for name in row.colnames})
                        try:
                            val = eval(expr, ctx, {})
                        except Exception:
                            # A row that cannot supply this attribute leaves it
                            # unset rather than failing the whole query.
                            val = None
                    if val is not None and not numpy.ma.is_masked(val):
                        setattr(source, attr, val)

            if getattr(self, "mags", None):
                for mag, item in self.mags.items():
                    mag_col, mag_err_col = _mag_columns(item)
                    if not mag_col:
                        continue
                    try:
                        val = _row_value(row, mag_col)
                        if val is not None and numpy.isfinite(val) and val < 99:
                            m = Mag(value=float(val))
                            try:
                                err = _row_value(row, mag_err_col)
                                if err is not None and numpy.isfinite(err) and err >= 0:
                                    m.error = float(err)
                            except Exception:
                                # Band present, uncertainty absent.
                                pass
                            source.mags[mag] = m
                    except Exception:
                        # No such magnitude in this table.
                        pass

            if source.mags:
                sources.append(source)

        # A row without a finite position cannot be placed or matched (e.g.
        # Tycho-2 stars with no mean position have masked RAmdeg/DEmdeg); it is
        # dropped like a row without a magnitude. Well-formed rows that all
        # drop are a field with nothing measurable -- a sparse or faint cone --
        # not a broken provider, so the result is [] (the columns were
        # checked above); the count is logged so it is not silent.
        positioned = [source for source in sources if _finite_position(source)]
        if len(positioned) < len(table):
            logger.warning(
                "%s: %d of %d rows had no usable magnitude or finite position and were dropped",
                self.name, len(table) - len(positioned), len(table),
            )
        return positioned

    def _check_response_columns(self, colnames: TList[str]) -> TDict[str, str]:
        """Fail on a response that lacks columns the mapping cannot do without.

        M3 (CAT-20): a renamed coordinate or magnitude column used to make every
        row silently unmappable. Coordinates and at least one declared band are
        required; a missing id column is tolerated (live APASS never returns the
        ``recno`` it requests). Returns renames for plain-column mappings, e.g.
        ``_2MASS`` -> ``2MASS``: astroquery once prefixed leading-digit names.
        """
        present = set(colnames)
        aliases: TDict[str, str] = {}
        for attr, expr in (self.col_mapping or {}).items():
            needed = _expression_columns(expr)
            # Only a plain-column mapping can be read under another spelling:
            # an expression is evaluated against the real column names.
            plain = needed == [expr]
            found = {name: _column_spelling(name, present) if plain else (name if name in present else None)
                     for name in needed}
            if plain and found[expr] not in (None, expr):
                aliases[expr] = found[expr]
            missing = [name for name, spelling in found.items() if spelling is None]
            if missing and attr in ("ra_hours", "dec_degs"):
                raise ProviderResponseError(
                    f"{self.name}: the response has no {', '.join(missing)} column for "
                    f"{attr}; it returned {', '.join(colnames)}."
                )
            if missing:
                logger.info("%s response has no %s column for %s", self.name, ", ".join(missing), attr)
        declared = [
            mag_col for mag_col, _ in (_mag_columns(item) for item in (getattr(self, "mags", None) or {}).values())
            if mag_col
        ]
        if declared and not any(_column_spelling(name, present) for name in declared):
            raise ProviderResponseError(
                f"{self.name}: the response has no declared magnitude column "
                f"({', '.join(declared)}); it returned {', '.join(colnames)}."
            )
        return aliases

    def _vizier(self, **kwargs) -> Vizier:
        """Construct an astroquery ``Vizier`` bound to this catalog."""
        if self.vizier_server:
            kwargs["vizier_server"] = self.vizier_server
        return Vizier(
            catalog=self.vizier_catalog, columns=self._columns, **kwargs
        )

    def query_objects(self, names: TList[str]) -> TList[CatalogSource]:
        """Return catalog objects with the given names.

        One request per name, keeping only the first row of each: VizieR name
        resolution can return several rows and upstream took the first. Names
        that resolve to nothing are silently absent from the result, so the
        output is not positionally aligned with ``names``.
        """
        viz = self._vizier(row_limit=len(names))
        rows = []
        for name in names:
            resp = viz.query_object(name, catalog=viz.catalog, cache=self.cache)
            if resp:
                rows.append(resp[0][0])
        return self.table_to_sources(rows)

    def query_region(
        self,
        ra_hours: float,
        dec_degs: float,
        constraints: Optional[TDict[str, str]] = None,
        limit: Optional[int] = None,
        **region,
    ) -> TList[CatalogSource]:
        """Return catalog objects in a region given by astroquery keywords.

        ``constraints`` splits two ways, which is easy to miss: an entry with a
        value becomes a VizieR *column filter* (``{'flags': '0'}`` ->
        ``flags=0``), while an entry whose value is ``None`` becomes a VizieR
        *keyword* instead. Both are passed through untranslated.
        """
        kwargs = {}
        if not limit:
            limit = self.row_limit
        if limit:
            kwargs["row_limit"] = limit

        viz = self._vizier(
            column_filters={
                name: val for name, val in constraints.items() if val is not None
            } if constraints else {},
            keywords=[
                name for name, val in constraints.items() if val is None
            ] if constraints else None,
            **kwargs,
        )
        resp = viz.query_region(
            SkyCoord(ra=ra_hours, dec=dec_degs, unit=(hour, deg), frame="fk5"),
            catalog=viz.catalog,
            cache=self.cache,
            **region,
        )
        if resp:
            rows = resp[0]
            effective_limit = getattr(viz, "ROW_LIMIT", limit)
            note_row_limit(self.name, len(rows), effective_limit, sort=self.sort)
            if effective_limit is not None and effective_limit > 0:
                rows = rows[:effective_limit]
            return self.table_to_sources(rows)
        return []

    def query_box(
        self,
        ra_hours: float,
        dec_degs: float,
        width_arcmins: float,
        height_arcmins: Optional[float] = None,
        constraints: Optional[TDict[str, str]] = None,
        limit: Optional[int] = None,
    ) -> TList[CatalogSource]:
        """Return catalog objects in a rectangular region.

        ``height_arcmins`` defaults to ``width_arcmins``.
        """
        if self.cache:
            ra_hours, dec_degs, (width_arcmins, height_arcmins) = _round_for_cache(
                ra_hours, dec_degs, width_arcmins, height_arcmins
            )
        return self.query_region(
            ra_hours,
            dec_degs,
            constraints,
            limit,
            width=width_arcmins * arcmin,
            height=(height_arcmins if height_arcmins else width_arcmins) * arcmin,
        )

    def query_circ(
        self,
        ra_hours: float,
        dec_degs: float,
        radius_arcmins: float,
        constraints: Optional[TDict[str, str]] = None,
        limit: Optional[int] = None,
    ) -> TList[CatalogSource]:
        """Return catalog objects within a circular region."""
        if self.cache:
            ra_hours, dec_degs, radius_arcmins = _round_cone_for_cache(
                ra_hours, dec_degs, radius_arcmins)
        return self.query_region(
            ra_hours, dec_degs, constraints, limit, radius=radius_arcmins * arcmin
        )


def _mag_columns(item) -> tuple[Optional[str], Optional[str]]:
    """Unpack a ``mags`` entry into ``(mag_column, error_column)``.

    Entries are ``[mag, err]``, ``[mag]``, or empty — empty meaning the band is
    synthesized by a ``table_to_sources`` override rather than read from a
    column (Landolt's U/B/R/I, for instance).
    """
    try:
        mag_col, mag_err_col = item[:2]
        return mag_col, mag_err_col
    except ValueError:
        pass
    try:
        return item[0], None
    except (IndexError, TypeError, ValueError):
        return None, None


def _expression_columns(expr: str) -> TList[str]:
    """Read data names without confusing call targets with literal columns."""
    if "\x00" in expr:
        raise ValueError("source code string cannot contain null bytes")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return [expr]  # a literal column name that is not an identifier
    if isinstance(tree.body, ast.Name):
        return [tree.body.id]
    names = []

    class Columns(ast.NodeVisitor):
        def __init__(self):
            self.scopes = []

        def visit_Name(self, node):
            if any(node.id in scope for scope in self.scopes):
                return
            # Preserve NumPy constants available to expression evaluation.
            # Callable names used as data (e.g. ``int + float``) are columns.
            if node.id in numpy.__dict__ and not callable(numpy.__dict__[node.id]):
                return
            if node.id not in names:
                names.append(node.id)

        def visit_Call(self, node):
            if not isinstance(node.func, ast.Name):
                self.visit(node.func)  # methods still read their receiver
            for arg in node.args:
                self.visit(arg)
            for keyword in node.keywords:
                self.visit(keyword.value)

        def visit_Lambda(self, node):
            # Defaults execute outside the lambda's parameter scope.
            for default in (*node.args.defaults, *node.args.kw_defaults):
                if default is not None:
                    self.visit(default)
            parameters = {arg.arg for arg in (
                *node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
            for arg in (node.args.vararg, node.args.kwarg):
                if arg is not None:
                    parameters.add(arg.arg)
            self.scopes.append(parameters)
            self.visit(node.body)
            self.scopes.pop()

        def _comprehension(self, node, *values):
            self.scopes.append(set())
            for generator in node.generators:
                self.visit(generator.iter)
                self.scopes[-1].update(
                    target.id for target in ast.walk(generator.target)
                    if isinstance(target, ast.Name))
                for condition in generator.ifs:
                    self.visit(condition)
            for value in values:
                self.visit(value)
            self.scopes.pop()

        def visit_ListComp(self, node):
            self._comprehension(node, node.elt)

        visit_SetComp = visit_GeneratorExp = visit_ListComp

        def visit_DictComp(self, node):
            self._comprehension(node, node.key, node.value)

    Columns().visit(tree)
    return names


def _column_spelling(name: str, present: set) -> Optional[str]:
    """Return how ``name`` is spelled in a response, or ``None`` if absent."""
    for candidate in (name, name.replace("'", "_"), name.lstrip("_"), "_" + name):
        if candidate in present:
            return candidate
    return None


def _finite_position(source: CatalogSource) -> bool:
    if any(numpy.ma.is_masked(value) for value in (source.ra_hours, source.dec_degs)):
        return False
    try:
        return math.isfinite(float(source.ra_hours)) and math.isfinite(float(source.dec_degs))
    except (TypeError, ValueError):
        return False


def _row_value(row, column: Optional[str]):
    """Read a column, retrying with apostrophes as underscores and with a
    leading underscore added or removed.

    astroquery exposes VizieR's ``g'mag`` as either ``g'mag`` or ``g_mag``
    depending on the table and the astroquery version.
    """
    if column is None:
        raise KeyError(column)
    # The same spellings _check_response_columns accepts (M3).
    for candidate in (column, column.replace("'", "_"), column.lstrip("_"), "_" + column):
        try:
            return row[candidate]
        except KeyError:
            continue
    raise KeyError(column)


def _round_for_cache(ra_hours: float, dec_degs: float, *sizes):
    """Snap a query region to a fixed grid so near-identical fields share a cache entry.

    Without this, two queries of the same field differing by a milliarcsecond
    are two cache entries and two round trips. Centres go to 10 arcsec, sizes
    round *up* to 0.2 arcmin. Boxes also grow to enclose the original region
    after moving the centre; cones compensate separately below.

    This is observable: with the cache on, a query returns rows for a slightly
    larger, grid-aligned region than the caller asked for. Callers that need an
    exact region should clip the result, which the WCS path in ``runner.py``
    already does.
    """
    original_ra, original_dec = ra_hours, dec_degs
    ra_hours = round(ra_hours * 5400) / 5400 % 24  # 10 arcsec
    dec_degs = round(dec_degs * 360) / 360
    if dec_degs > 90:
        dec_degs = 90
    elif dec_degs < -90:
        dec_degs = -90
    if len(sizes) == 2:
        width, height = sizes
        if height is None:
            height = width
        height += 120 * abs(dec_degs - original_dec)
        # The rectangular backend uses asin(sin(width/2)/cos(dec)) for
        # longitude extent. Moving latitude changes that extent too, so
        # adding centre displacement to angular width alone is insufficient.
        original_height = sizes[1] if sizes[1] is not None else sizes[0]
        # Above 180 degrees, increasing width decreases asin(sin(width/2)).
        # Use full longitude rather than round into a smaller interval.
        full_ra = abs(original_dec) + original_height / 120 > 90 or width >= 10800
        ratio = math.sin(math.radians(width / 120)) / math.cos(math.radians(original_dec))
        if full_ra or abs(ratio) >= 1:
            width = 21600.0
        else:
            half_ra = math.asin(ratio) + math.radians(
                abs((original_ra * 15 - ra_hours * 15 + 180) % 360 - 180))
            if half_ra >= math.pi / 2:
                width = 21600.0
            else:
                required = math.degrees(2 * math.asin(
                    math.sin(half_ra) * math.cos(math.radians(dec_degs)))) * 60
                width = max(width, required)
        sizes = (width, height)
    rounded = tuple(
        numpy.ceil(size * 5) / 5 if size is not None else None for size in sizes
    )
    return ra_hours, dec_degs, rounded


def _round_cone_for_cache(ra_hours: float, dec_degs: float, radius_arcmins: float):
    """Round a cone while enclosing its original, unrounded region (CAT-17)."""
    ra, dec, (radius,) = _round_for_cache(ra_hours, dec_degs, radius_arcmins)
    shift = SkyCoord(ra_hours * 15, dec_degs, unit=deg).separation(
        SkyCoord(ra * 15, dec, unit=deg)).arcmin
    radius = max(radius, numpy.ceil((radius_arcmins + shift) * 5) / 5)
    return ra, dec, radius


def build_custom_vizier_catalog(spec: TDict) -> type:
    """Build a ``VizierCatalog`` subclass from a plain declaration.

    Lets a deployment add a VizieR table MARS does not ship a plugin for, by
    supplying the same attributes a plugin would (``name``, ``vizier_catalog``,
    ``mags``, ``col_mapping``, ...). The class name is derived from ``name`` by
    stripping illegal characters and prefixing an underscore if it starts with a
    digit.

    PRESERVED BUG: the character class below reads ``a-zA-z``, not ``a-zA-Z``.
    The range ``Z-a`` additionally admits ``[ \\ ] ^ _ ` ``, so a catalog named
    ``my^cat`` keeps the caret in its class name. Harmless — the name is
    cosmetic and Python accepts the resulting identifier via ``type()`` — and
    left as upstream wrote it.

    EXTRACTED FROM: the ``CUSTOM_VIZIER_CATALOGS`` loop at the bottom of
    Afterglow's ``vizier_catalogs.py``, which ran at import time over Flask
    config and swallowed every error into a log line. MARS makes it an
    ordinary function that raises, because a misconfigured catalog should be
    visible at the point it is registered rather than absent at query time.
    """
    name = spec["name"]
    classname = re.sub(r"(^\d)", r"_\1", re.sub(r"[^a-zA-z0-9_]", "", name)) + "Catalog"
    newclass = type(classname, (VizierCatalog,), dict(spec))
    newclass.__module__ = VizierCatalog.__module__
    return newclass
