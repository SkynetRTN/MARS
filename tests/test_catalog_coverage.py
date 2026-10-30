"""M2: coverage cannot disappear at poles or leak constraints across queries."""

import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.units import arcmin, deg
from astropy.wcs import WCS

from algorithms.catalogs.schemas import CatalogSource
from algorithms.query.geometry import clip_sources_to_box
from algorithms.query.registry import CATALOGS
from algorithms.query.runner import query_catalogs, query_catalogs_for_image


@pytest.mark.parametrize("sign", [-1, 1])
def test_wide_short_polar_box_keeps_every_ra_in_its_declination_band(sign):
    sources = [CatalogSource(id=str(i), ra_hours=ra, dec_degs=sign * dec)
               for i, (ra, dec) in enumerate([(0, 88), (6, 88), (12, 88), (18, 88), (12, 80)])]
    with np.errstate(invalid="raise"):
        kept = clip_sources_to_box(sources, 12, sign * 88, 600, 120)
    assert [s.id for s in kept] == ["0", "1", "2", "3"]


@pytest.mark.parametrize("sign", [-1, 1])
def test_wide_short_polar_sql_is_finite_and_keeps_the_declination_band(sign):
    from algorithms.query.sdss import MARSSDSS

    sql = MARSSDSS()._args_to_payload(
        coordinates=SkyCoord(180, sign * 88, unit=deg), radius=(600 * arcmin, 120 * arcmin),
        photoobj_fields=["ra", "dec"], limit=10,
    )["cmd"]
    assert "nan" not in sql.lower()
    assert "s.ra BETWEEN" not in sql
    assert "s.dec BETWEEN" in sql


@pytest.mark.parametrize("flags", [None, "<4"])
def test_skymapper_default_never_changes_the_callers_constraints(monkeypatch, flags):
    from algorithms.query.vizier import VizierCatalog

    constraints = {"gmag": "<18"}
    if flags is not None:
        constraints["flags"] = flags
    original = dict(constraints)
    received = []

    def transport(self, **kwargs):
        received.append(kwargs["column_filters"])
        return type("Client", (), {"catalog": self.vizier_catalog,
                    "query_region": lambda *a, **k: []})()

    monkeypatch.setattr(VizierCatalog, "_vizier", transport)
    CATALOGS["SkyMapper"].query_circ(1, -30, 1, constraints=constraints)
    CATALOGS["APASS"].query_circ(1, -30, 1, constraints=constraints)
    assert constraints == original
    assert received[0]["flags"] == ("0" if flags is None else flags)
    assert received[1] == original


def _detector(dec, rotation, crpix):
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [359.95, dec]
    wcs.wcs.crpix = crpix
    angle = np.deg2rad(rotation)
    wcs.wcs.cd = np.array([[np.cos(angle), -np.sin(angle)],
                           [np.sin(angle), np.cos(angle)]]) @ np.diag([-0.01, 0.003])
    wcs.array_shape = (48, 96)
    return wcs


def test_allocation_failure_does_not_continue_the_catalog_fallback(monkeypatch):
    def exhausted(*args, **kwargs):
        raise MemoryError("test catalog allocation failure")

    monkeypatch.setattr(CATALOGS["APASS"], "query_circ", exhausted)
    monkeypatch.setattr(CATALOGS["Stetson"], "query_circ", lambda *args, **kwargs: [])
    with pytest.raises(MemoryError, match="catalog allocation"):
        query_catalogs(["APASS", "Stetson"], wcs=_detector(0., 0., [10., 10.]), skip_failed=True)


@pytest.mark.parametrize("entry", ["wcs", "image"])
@pytest.mark.parametrize("dec,rotation,crpix", [
    (0, 0, [48, 24]), (85, 37, [48, 24]), (89.9, 0, [48, 24]),
    (-89.9, 71, [48, 24]), (45, 17, [-50, 70]),
])
def test_every_detector_grid_position_is_queried_across_seams_and_poles(
    entry, dec, rotation, crpix, monkeypatch,
):
    wcs = _detector(dec, rotation, crpix)
    pixels = np.array([(x, y) for x in np.linspace(0.01, 95.99, 15)
                       for y in np.linspace(0.01, 47.99, 9)])
    world = wcs.all_pix2world(pixels, 0)
    rows = [CatalogSource(id=str(i), ra_hours=ra / 15, dec_degs=latitude)
            for i, (ra, latitude) in enumerate(world)]
    sky = SkyCoord(world[:, 0], world[:, 1], unit=deg)

    def cone(ra, latitude, radius, constraints=None, **kwargs):
        distance = SkyCoord(ra * 15, latitude, unit=deg).separation(sky).arcmin
        return [row for row, inside in zip(rows, distance <= radius) if inside]

    def box(ra, latitude, width, height, constraints=None, **kwargs):
        return clip_sources_to_box(rows, ra, latitude, width, height)

    monkeypatch.setattr(CATALOGS["APASS"], "query_circ", cone)
    monkeypatch.setattr(CATALOGS["APASS"], "query_box", box)
    if entry == "wcs":
        result = query_catalogs(["APASS"], wcs=wcs)
    else:
        result = query_catalogs_for_image(["APASS"], wcs)
    assert {row.id for row in result} == {str(i) for i in range(135)}
    assert all(0 <= row.x < 96 and 0 <= row.y < 48 for row in result)


def test_distorted_footprint_explicitly_discloses_unverified_coverage(monkeypatch):
    from algorithms.query.coverage import collect_query_notices

    wcs = _detector(30, 20, [48, 24])
    wcs.wcs.ctype = ["RA---SIN", "DEC--SIN"]
    monkeypatch.setattr(CATALOGS["APASS"], "query_circ", lambda *a, **k: [])
    with collect_query_notices() as notices:
        assert query_catalogs(["APASS"], wcs=wcs) == []
    assert "catalog_coverage_unverified" in {item.code for item in notices}


@pytest.mark.parametrize("name", ["APASS", "SDSS"])
def test_cached_cone_growth_compensates_for_centre_rounding(name, monkeypatch):
    catalog = CATALOGS[name]
    monkeypatch.setattr(catalog, "cache", True)
    requested = SkyCoord(15.0013, 20.0013, unit=deg)
    edge = requested.directional_offset_by(45 * deg, 1.2 * arcmin)

    def check(ra, latitude, radius):
        assert SkyCoord(ra * 15, latitude, unit=deg).separation(edge).arcmin <= radius

    if name == "SDSS":
        def query(ra, latitude, radius, limit):
            check(ra, latitude, radius.to_value(arcmin))
            return []
        monkeypatch.setattr(catalog, "_query_sql_region", query)
    else:
        def query(ra, latitude, constraints, limit, **region):
            check(ra, latitude, region["radius"].to_value(arcmin))
            return []
        monkeypatch.setattr(catalog, "query_region", query)
    assert catalog.query_circ(requested.ra.hour, requested.dec.deg, 1.2) == []


@pytest.mark.parametrize("name", ["APASS", "SDSS"])
@pytest.mark.parametrize("raw_count", [1, 2, 3])
def test_raw_response_limit_is_disclosed_before_bad_rows_are_dropped(name, raw_count, monkeypatch):
    from astroquery.vizier.core import VizierClass
    from algorithms.query import sdss
    from algorithms.query.coverage import collect_query_notices

    if name == "APASS":
        table = Table({"RAJ2000": [15.] * raw_count, "DEJ2000": [-30.] * raw_count,
                       "Vmag": [99.] * raw_count})
        monkeypatch.setattr(VizierClass, "query_region", lambda *a, **k: [table])
    else:
        table = Table({"ra": [15.] * raw_count, "dec": [-30.] * raw_count,
                       "g": [99.] * raw_count})
        monkeypatch.setattr(sdss, "_query_sql", lambda *a, **k: table)
    with collect_query_notices() as notices:
        assert CATALOGS[name].query_circ(1, -30, 1, limit=2) == []
    assert ("catalog_rows_capped" in {item.code for item in notices}) == (raw_count >= 2)
    if raw_count >= 2:
        assert name in notices[0].message
        assert "2" in notices[0].message
        if name == "APASS":
            assert "bright" in notices[0].message.lower()


def test_the_sdk_default_row_limit_is_also_disclosed(monkeypatch):
    from astroquery.vizier.core import VizierClass
    from algorithms.query.coverage import collect_query_notices

    monkeypatch.setattr(CATALOGS["APASS"], "row_limit", None)
    # astroquery 0.4.11's constructor defaults to 50 rows, even when the
    # declaration has no explicit row limit.
    table = Table({"RAJ2000": [15.] * 50, "DEJ2000": [-30.] * 50, "Vmag": [14.] * 50})
    monkeypatch.setattr(VizierClass, "query_region", lambda *a, **k: [table])
    with collect_query_notices() as notices:
        assert len(CATALOGS["APASS"].query_circ(1, -30, 1)) == 50
    assert "catalog_rows_capped" in {item.code for item in notices}


def test_first_nonempty_catalog_names_the_unqueried_alternatives(monkeypatch):
    from algorithms.query.coverage import collect_query_notices

    monkeypatch.setattr(CATALOGS["APASS"], "query_circ", lambda *a, **k: [CatalogSource(id="one")])
    with collect_query_notices() as notices:
        rows = query_catalogs(["APASS", "Stetson"], ra_hours=1, dec_degs=-30,
                              radius_arcmins=1, stop_on_success=True)
    assert [s.id for s in rows] == ["one"]
    assert "catalog_fallback_not_exhausted" in {item.code for item in notices}
    assert "Stetson" in notices[0].message


def test_failed_wcs_catalog_is_disclosed_even_when_a_later_catalog_succeeds(monkeypatch):
    from algorithms.query.coverage import collect_query_notices

    wcs = _detector(30, 0, [48, 24])
    ra, dec = wcs.all_pix2world(48, 24, 0)

    def fail(*a, **k):
        raise TimeoutError("no response")

    monkeypatch.setattr(CATALOGS["APASS"], "query_circ", fail)
    monkeypatch.setattr(CATALOGS["Stetson"], "query_circ", lambda *a, **k: [
        CatalogSource(id="ok", ra_hours=float(ra) / 15, dec_degs=float(dec))])
    with collect_query_notices() as notices:
        assert len(query_catalogs(["APASS", "Stetson"], wcs=wcs, skip_failed=True)) == 1
    assert "catalog_query_incomplete" in {item.code for item in notices}


def test_nested_collectors_reset_after_an_exception_without_leaking_to_later_calls():
    from algorithms.query.coverage import collect_query_notices, note_query_issue

    with collect_query_notices() as outer:
        with pytest.raises(RuntimeError):
            with collect_query_notices() as inner:
                note_query_issue("catalog_rows_capped", "first operation")
                raise RuntimeError("stop")
        note_query_issue("catalog_query_incomplete", "outer operation")
    with collect_query_notices() as later:
        note_query_issue("catalog_rows_capped", "later operation")
    assert [item.message for item in inner] == ["first operation"]
    assert [item.message for item in outer] == ["first operation", "outer operation"]
    assert [item.message for item in later] == ["later operation"]


def test_concurrent_operations_collect_only_their_own_query_notices():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from algorithms.query.coverage import collect_query_notices, note_query_issue

    barrier = Barrier(2)

    def operation(name):
        with collect_query_notices() as notices:
            barrier.wait(timeout=5)
            note_query_issue("catalog_rows_capped", name)
            barrier.wait(timeout=5)
        return [item.message for item in notices]

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(operation, ["first", "second"]))
    assert results == [["first"], ["second"]]


@pytest.mark.parametrize("distortion", [-3., -60.])
def test_wcslib_tpv_distortion_keeps_curved_edges_and_discloses_sampled_coverage(distortion, monkeypatch):
    from astropy.io.fits import Header
    from algorithms.query.coverage import collect_query_notices

    wcs = WCS(Header({
        "NAXIS": 2, "NAXIS1": 100, "NAXIS2": 100,
        "CTYPE1": "RA---TPV", "CTYPE2": "DEC--TPV", "CRVAL1": 180., "CRVAL2": 0.,
        "CRPIX1": 51., "CRPIX2": 51., "CD1_1": -.01, "CD1_2": 0., "CD2_1": 0., "CD2_2": .002,
        "PV1_1": 1., "PV2_1": 1., "PV1_9": distortion,
    }))
    world = wcs.all_pix2world([[0.1, 50], [99.9, 50]], 0)
    sky = SkyCoord(world[:, 0], world[:, 1], unit=deg)
    rows = [CatalogSource(id=str(i), ra_hours=ra / 15, dec_degs=dec)
            for i, (ra, dec) in enumerate(world)]

    def transport(ra, dec, radius, *a, **k):
        distances = SkyCoord(ra * 15, dec, unit=deg).separation(sky).arcmin
        return [row for row, distance in zip(rows, distances) if distance <= radius]

    monkeypatch.setattr(CATALOGS["APASS"], "query_circ", transport)
    with collect_query_notices() as notices:
        result = query_catalogs(["APASS"], wcs=wcs)
    assert {row.id for row in result} == {"0", "1"}
    assert "catalog_coverage_unverified" in {item.code for item in notices}
