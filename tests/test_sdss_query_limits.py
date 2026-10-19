"""CAT-02/27: bounded SDSS SQL and the pinned client's transport contract."""

from __future__ import annotations

import math
import re

import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.units import arcmin, deg
from astroquery.sdss import SDSSClass
from requests import Response

from algorithms.query import sdss
from algorithms.query.registry import CATALOGS
from algorithms.query.runner import query_catalogs


@pytest.fixture(autouse=True)
def no_remote_request(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("offline SDSS test attempted a remote request")

    monkeypatch.setattr(SDSSClass, "_request", forbidden)


def _payload(**overrides):
    arguments = dict(coordinates=SkyCoord(180., 20., unit=deg), radius=1 * arcmin,
                     photoobj_fields=["objID", "ra", "dec", "g", "err_g"])
    arguments.update(overrides)
    return sdss.MARSSDSS()._args_to_payload(**arguments)


@pytest.mark.parametrize("limit", [None, 1, 7, 5000, np.int64(3)])
def test_payload_has_a_finite_server_side_limit(limit):
    result = _payload(limit=limit)
    expected = 5000 if limit is None else int(limit)
    assert result["cmd"].startswith(f"SELECT DISTINCT TOP {expected} ")
    assert "JOIN Field f ON s.fieldID = f.fieldID" in result["cmd"]
    assert "f.quality = 3 AND s.clean = 1" in result["cmd"]
    assert result["searchtool"] == "SQL"


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "3", math.inf, math.nan, 5001, 10**100])
def test_invalid_limits_fail_before_payload_or_transport(limit):
    with pytest.raises(ValueError, match="limit"):
        _payload(limit=limit)


@pytest.mark.parametrize("fields", [
    [], None, "objID", ["g; DROP TABLE Star"], ["g --"], ["g AS fake"],
    ["s.g"], ["g,ra"], ["g)"], ["1g"], ["g" * 65], ["g"] * 65, [1],
])
def test_projection_fields_are_bounded_literal_identifiers(fields):
    with pytest.raises(ValueError, match="field"):
        _payload(photoobj_fields=fields)


@pytest.mark.parametrize("changes", [
    {"coordinates": None}, {"coordinates": SkyCoord([180., 181.], [20., 21.], unit=deg)},
    {"coordinates": SkyCoord(math.nan, 20., unit=deg)},
    {"radius": None}, {"radius": 0 * arcmin}, {"radius": -1 * arcmin},
    {"radius": math.inf * arcmin}, {"radius": math.nan * arcmin},
    {"radius": (0 * arcmin, 1 * arcmin)},
    {"radius": (1 * arcmin, math.nan * arcmin)},
])
def test_invalid_geometry_is_rejected_without_sdk_fallback(changes):
    with pytest.raises(ValueError):
        _payload(**changes)


@pytest.mark.parametrize("coordinate, radius, fragment", [
    (SkyCoord(180., 20., unit=deg), 1 * arcmin, "fGetNearbyObjEq(180.0,20.0,1.0)"),
    (SkyCoord(180., 20., unit=deg), (1 * arcmin, 2 * arcmin), "s.ra BETWEEN"),
    (SkyCoord(.001, 20., unit=deg), (2 * arcmin, 2 * arcmin), " OR s.ra <= "),
    (SkyCoord(359.999, 20., unit=deg), (2 * arcmin, 2 * arcmin), " OR s.ra <= "),
    (SkyCoord(180., 89.9, unit=deg), (60 * arcmin, 60 * arcmin), "s.dec >= "),
])
def test_accepted_geometry_and_quality_predicates_are_preserved(coordinate, radius, fragment):
    sql = _payload(coordinates=coordinate, radius=radius)["cmd"]
    assert fragment in sql
    assert "f.quality = 3 AND s.clean = 1" in sql


@pytest.fixture
def sql_client(monkeypatch):
    class Client:
        def __init__(self):
            self.calls = []

        def _args_to_payload(self, **kwargs):
            return sdss.MARSSDSS()._args_to_payload(**kwargs)

        def query_sql(self, query, **kwargs):
            self.calls.append((query, kwargs))
            return Table({"objID": [1, 2, 3], "ra": [180.] * 3, "dec": [20.] * 3,
                          "g": [14., 15., 16.], "err_g": [.1] * 3})

    client = Client()
    monkeypatch.setattr(sdss, "SDSS", lambda: client)
    return client


@pytest.mark.parametrize("method, arguments", [
    ("query_circ", (12., 20., 1.)), ("query_box", (12., 20., 1., 2.)),
])
def test_backend_uses_sql_transport_and_caps_rows_even_if_provider_ignores_top(sql_client, method, arguments):
    backend = CATALOGS["SDSS"]
    result = getattr(backend, method)(*arguments, limit=2)
    assert len(result) == 2
    assert [int(row.id) for row in result] == [1, 2]
    assert len(sql_client.calls) == 1
    sql, kwargs = sql_client.calls[0]
    assert sql.startswith("SELECT DISTINCT TOP 2 ")
    assert kwargs["data_release"] == 17
    assert kwargs["cache"] == backend.cache


def test_runner_default_reaches_bounded_sql_transport(sql_client):
    result = query_catalogs(["SDSS"], ra_hours=12., dec_degs=20., radius_arcmins=1.)
    assert len(result) == 3
    assert sql_client.calls[0][0].startswith("SELECT DISTINCT TOP 5000 ")


def test_backend_invalid_limit_rejects_before_client_creation(monkeypatch):
    def forbidden():
        pytest.fail("invalid limit reached client construction")

    monkeypatch.setattr(sdss, "SDSS", forbidden)
    with pytest.raises(ValueError, match="limit"):
        CATALOGS["SDSS"].query_circ(12., 20., 1., limit=0)


def test_backend_empty_sql_response_is_an_empty_catalog(sql_client, monkeypatch):
    monkeypatch.setattr(sql_client, "query_sql", lambda *args, **kwargs: None)
    assert CATALOGS["SDSS"].query_circ(12., 20., 1., limit=2) == []


def test_native_sdk_sql_payload_keeps_the_generated_query():
    client = sdss.MARSSDSS()
    query = _payload(limit=3)["cmd"]
    result = client.query_sql_async(query, data_release=17, get_query_payload=True)
    assert result["cmd"].strip() == query
    assert result["searchtool"] == "SQL"


def test_pinned_region_sdk_path_is_incompatible_with_the_old_scalar_payload_shape():
    # Characterization: even payload-only cone lookup passes a list to our old
    # scalar-coordinate seam. Region backend calls must use query_sql instead.
    with pytest.raises((AttributeError, ValueError)):
        sdss.MARSSDSS().query_region_async(
            SkyCoord(180., 20., unit=deg), radius=1 * arcmin,
            photoobj_fields=["objID", "ra", "dec"], get_query_payload=True,
        )


@pytest.mark.parametrize("method, arguments", [
    ("query_circ", (12., 20., 1.)), ("query_box", (12., 20., 1., 2.)),
])
def test_native_sdk_sql_transport_and_response_parser_are_exercised_offline(monkeypatch, method, arguments):
    calls = []

    def request(self, method, url, **kwargs):
        calls.append((method, url, kwargs))
        response = Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = b"objID,ra,dec,g,err_g\n1,180,20,14,0.1\n2,180,20,15,0.1\n"
        return response

    monkeypatch.setattr(SDSSClass, "_request", request)
    result = getattr(CATALOGS["SDSS"], method)(*arguments, limit=1)
    assert len(result) == 1
    assert int(result[0].id) == 1
    assert result[0].mags["g"].value == 14.
    assert len(calls) == 1
    verb, url, kwargs = calls[0]
    assert verb == "GET"
    assert "/dr17/" in url and "crossid" not in url.lower()
    assert kwargs["params"]["cmd"].strip().startswith("SELECT DISTINCT TOP 1 ")
    assert kwargs["params"]["searchtool"] == "SQL"


def test_response_cap_precedes_row_mapping(sql_client, monkeypatch):
    backend = CATALOGS["SDSS"]
    sizes = []

    def mapper(rows):
        sizes.append(len(rows))
        return []

    monkeypatch.setattr(backend, "table_to_sources", mapper)
    assert backend.query_circ(12., 20., 1., limit=1) == []
    assert sizes == [1]


def test_configured_catalog_default_is_honored(sql_client, monkeypatch):
    backend = CATALOGS["SDSS"]
    monkeypatch.setattr(backend, "row_limit", 1)
    assert len(backend.query_circ(12., 20., 1.)) == 1
    assert sql_client.calls[0][0].startswith("SELECT DISTINCT TOP 1 ")


@pytest.mark.parametrize("value", [math.nan, math.inf, -1., 0.])
def test_cached_invalid_dimensions_fail_before_rounding_or_rpc(monkeypatch, value):
    backend = CATALOGS["SDSS"]
    monkeypatch.setattr(backend, "cache", True)

    def forbidden(*args, **kwargs):
        pytest.fail("invalid dimension reached rounding")

    monkeypatch.setattr(sdss, "_round_for_cache", forbidden)
    with pytest.raises(ValueError):
        backend.query_circ(12., 20., value)


def test_unrepresentable_polar_box_is_rejected_not_sent_as_nan_sql():
    with pytest.raises(ValueError, match="RA span"):
        _payload(coordinates=SkyCoord(180., 89.9, unit=deg), radius=(120 * arcmin, 1 * arcmin))


@pytest.mark.parametrize("ra, radius", [(1e308, 1.), (12., 1e308)])
def test_cached_derived_overflow_is_rejected_before_rounding(monkeypatch, ra, radius):
    backend = CATALOGS["SDSS"]
    monkeypatch.setattr(backend, "cache", True)

    def forbidden(*args, **kwargs):
        pytest.fail("unrepresentable cache input reached rounding")

    monkeypatch.setattr(sdss, "_round_for_cache", forbidden)
    with pytest.raises(ValueError):
        backend.query_circ(ra, 20., radius)


def test_normal_cache_rounding_is_retained(sql_client, monkeypatch):
    backend = CATALOGS["SDSS"]
    monkeypatch.setattr(backend, "cache", True)
    backend.query_circ(12., 20., 1.01)
    match = re.search(r"fGetNearbyObjEq\(([^)]+)\)", sql_client.calls[0][0])
    assert match is not None
    assert tuple(map(float, match.group(1).split(","))) == pytest.approx((180., 20., 1.2))


def test_sql_service_error_is_not_reported_as_an_empty_catalog(monkeypatch):
    from astroquery.exceptions import RemoteServiceError

    def request(*args, **kwargs):
        response = Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = b"error_message: service refused request"
        return response

    monkeypatch.setattr(SDSSClass, "_request", request)
    with pytest.raises(RemoteServiceError, match="refused request"):
        CATALOGS["SDSS"].query_circ(12., 20., 1., limit=1)
