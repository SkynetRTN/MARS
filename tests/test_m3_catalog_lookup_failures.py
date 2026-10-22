"""M3 catalog lookup failures: SDSS named lookup, APASS U, SIMBAD recovery.

Each lookup must return data or explain the specific failure, and a transient
failure must have a defined recovery (``docs/working/master-continuation-plan.md``,
M3; ``docs/analysis/algorithm-remediation-plan.md`` CAT-06, CAT-18, CAT-22).
None of these tests opens a socket.
"""

from __future__ import annotations

import pytest
from astropy.io import fits
from astropy.table import Table
from astroquery.sdss import SDSSClass
from requests import Response

from algorithms.query import sdss
from algorithms.query import simbad as simbad_query
from algorithms.query.registry import CATALOGS
from algorithms.query.runner import query_catalogs


# --- SDSS named lookup (CAT-18) ---------------------------------------------


@pytest.fixture
def no_remote_sdss(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("offline SDSS test attempted a remote request")

    monkeypatch.setattr(SDSSClass, "_request", forbidden)


@pytest.fixture
def sql_client(monkeypatch, no_remote_sdss):
    class Client:
        def __init__(self):
            self.calls = []

        def query_sql(self, query, **kwargs):
            self.calls.append((query, kwargs))
            return Table({"objID": [1237648720693755918, 1237648720693755919],
                          "ra": [180.] * 2, "dec": [20.] * 2,
                          "g": [14., 15.], "err_g": [.1] * 2})

    client = Client()
    monkeypatch.setattr(sdss, "SDSS", lambda: client)
    return client


def test_sdss_object_lookup_uses_bounded_quality_filtered_sql(sql_client):
    names = ["1237648720693755918", " 1237648720693755919 "]
    result = CATALOGS["SDSS"].query_objects(names)

    assert [int(row.id) for row in result] == [1237648720693755918, 1237648720693755919]
    assert len(sql_client.calls) == 1
    sql, kwargs = sql_client.calls[0]
    assert sql.startswith("SELECT DISTINCT TOP 2 ")
    assert "s.objID IN (1237648720693755918, 1237648720693755919)" in sql
    assert "f.quality = 3 AND s.clean = 1" in sql
    assert kwargs["data_release"] == 17


def test_sdss_object_lookup_through_the_runner(sql_client):
    result = query_catalogs(["SDSS"], source_ids=["1237648720693755918"])
    assert len(result) == 1  # capped at one row per requested objID, even if the provider ignores TOP
    assert "s.objID IN (1237648720693755918)" in sql_client.calls[0][0]


@pytest.mark.parametrize("names", [
    ["M31"], ["1; DROP TABLE Star"], ["-5"], ["1.5"], [""], [None], [12],
    ["9" * 25],
])
def test_sdss_object_lookup_rejects_non_objid_names_before_any_request(monkeypatch, names):
    monkeypatch.setattr(sdss, "SDSS", lambda: pytest.fail("invalid name reached the client"))
    with pytest.raises(ValueError, match="SDSS objID"):
        CATALOGS["SDSS"].query_objects(names)


def test_sdss_object_lookup_bounds_the_name_count(monkeypatch):
    monkeypatch.setattr(sdss, "SDSS", lambda: pytest.fail("oversized lookup reached the client"))
    with pytest.raises(ValueError, match="at most 5000"):
        CATALOGS["SDSS"].query_objects([str(i + 1) for i in range(5001)])


def test_sdss_object_lookup_of_nothing_makes_no_request(monkeypatch):
    monkeypatch.setattr(sdss, "SDSS", lambda: pytest.fail("empty lookup reached the client"))
    assert CATALOGS["SDSS"].query_objects([]) == []


def test_sdss_object_lookup_with_no_matching_rows_is_empty(sql_client, monkeypatch):
    monkeypatch.setattr(sql_client, "query_sql", lambda *args, **kwargs: None)
    assert CATALOGS["SDSS"].query_objects(["1"]) == []


def test_sdss_object_lookup_through_the_native_sdk_transport(monkeypatch):
    calls = []

    def request(self, method, url, **kwargs):
        calls.append((method, url, kwargs))
        response = Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = b"objID,ra,dec,g,err_g\n42,180,20,14,0.1\n"
        return response

    monkeypatch.setattr(SDSSClass, "_request", request)
    result = CATALOGS["SDSS"].query_objects(["42"])
    assert [int(row.id) for row in result] == [42]
    assert result[0].mags["g"].value == 14.
    (verb, url, kwargs), = calls
    assert "/dr17/" in url
    assert "s.objID IN (42)" in kwargs["params"]["cmd"]
    assert kwargs["params"]["searchtool"] == "SQL"


# --- SIMBAD recovery (CAT-22) -----------------------------------------------


class _FakeSimbad:
    """Stands in for ``astroquery.simbad.Simbad``; class attributes script it."""

    init_failures = 0
    query_error: Exception | None = None
    rows: list = []

    def __init__(self):
        if type(self).init_failures:
            type(self).init_failures -= 1
            raise ConnectionError("SIMBAD field list unreachable")

    def add_votable_fields(self, *fields):
        pass

    def query_object(self, name, wildcard=False):
        if type(self).query_error is not None:
            raise type(self).query_error
        return type(self).rows


@pytest.fixture
def fake_simbad(monkeypatch):
    import astroquery.simbad

    class Fake(_FakeSimbad):
        init_failures = 0
        query_error = None
        rows = []

    monkeypatch.setattr(astroquery.simbad, "Simbad", Fake)
    monkeypatch.setattr(simbad_query, "_simbad", None)
    monkeypatch.setattr(simbad_query, "_simbad_enabled", None)
    monkeypatch.setattr(simbad_query, "_simbad_init_error", None)
    return Fake


M31_ROW = {"main_id": "M  31", "ra": 10.684708, "dec": 41.26875, "otype": "AGN"}


def test_simbad_initialization_failure_is_retried_on_the_next_call(fake_simbad):
    fake_simbad.init_failures = 1
    fake_simbad.rows = [M31_ROW]

    assert simbad_query.simbad_available() is False
    assert simbad_query.simbad_available() is True
    assert [t.object_name for t in simbad_query.resolve_simbad("M31")] == ["M  31"]


def test_simbad_resolution_recovers_after_a_transient_initialization_failure(fake_simbad):
    fake_simbad.init_failures = 1
    fake_simbad.rows = [M31_ROW]

    assert simbad_query.resolve_simbad("M31") == []
    assert len(simbad_query.resolve_simbad("M31")) == 1


def test_strict_simbad_resolution_names_an_initialization_failure(fake_simbad):
    fake_simbad.init_failures = 1
    with pytest.raises(simbad_query.SimbadUnavailableError, match="SIMBAD.*field list unreachable"):
        simbad_query.resolve_simbad("M31", strict=True)


def test_strict_simbad_resolution_names_a_query_failure(fake_simbad):
    fake_simbad.query_error = TimeoutError("read timed out")
    with pytest.raises(simbad_query.SimbadUnavailableError, match="read timed out"):
        simbad_query.resolve_simbad("M31", strict=True)
    # The default keeps the extracted never-raise contract.
    assert simbad_query.resolve_simbad("M31") == []


def test_strict_simbad_resolution_returns_empty_for_a_genuine_no_match(fake_simbad):
    fake_simbad.rows = []
    assert simbad_query.resolve_simbad("not a real object", strict=True) == []


def test_resolve_target_reports_an_unreachable_simbad_as_a_provider_failure(fake_simbad):
    from tools.resolve import resolve_target

    fake_simbad.query_error = ConnectionError("connection refused")
    result = resolve_target("M31")
    assert result.status == "error"
    (error,) = result.errors
    assert error.code == "provider_unavailable"
    assert "SIMBAD" in error.message and "connection refused" in error.message


def test_resolve_target_still_reports_an_unknown_name_as_not_found(fake_simbad):
    from tools.resolve import resolve_target

    fake_simbad.rows = []
    result = resolve_target("not a real object")
    assert result.status == "not_found"
    assert result.errors == []


def test_resolve_target_recovers_once_simbad_comes_back(fake_simbad):
    from tools.resolve import resolve_target

    fake_simbad.init_failures = 1
    fake_simbad.rows = [M31_ROW]
    assert resolve_target("M31").status == "error"
    assert resolve_target("M31").status == "ok"


def test_casda_reports_an_unreachable_simbad_rather_than_no_data(fake_simbad, monkeypatch):
    from tools import casda

    fake_simbad.query_error = ConnectionError("connection refused")
    monkeypatch.setattr(casda, "Casda", lambda: pytest.fail("CASDA queried without a position"))
    result = casda.search_casda(target="M31")
    assert result.status == "error"
    assert [e.code for e in result.errors] == ["provider_unavailable"]
    assert "SIMBAD" in result.errors[0].message


# --- APASS U (CAT-06) -------------------------------------------------------


def test_reference_band_resolution_names_the_band_apass_lacks():
    from tools.catalogs import resolve_reference_band

    resolution = resolve_reference_band("APASS", "U")
    assert resolution.supported is False
    (warning,) = resolution.warnings
    assert warning.code == "unsupported_filter"
    assert "uprime" in warning.message and "APASS" in warning.message


@pytest.fixture
def u_band_frame(tmp_path):
    from tools.optical import resolve_optical_frame

    source = resolve_optical_frame("ngc5128_galaxy_b_001").path
    with fits.open(source) as hdul:
        hdul[0].header["FILTER"] = "U"
        target = tmp_path / "u_band.fits"
        hdul.writeto(target)
    return target


@pytest.fixture
def no_catalog_query(monkeypatch):
    import algorithms.query.runner as runner

    monkeypatch.setattr(runner, "query_catalogs",
                        lambda *a, **k: pytest.fail("unsupported filter reached a catalog query"))


def test_calibration_against_a_catalog_that_cannot_supply_the_filter_fails_by_name(
    u_band_frame, no_catalog_query,
):
    from tools.photometry import calibrate_zeropoint

    result = calibrate_zeropoint(u_band_frame, catalogs=["APASS"])
    (error,) = result.errors
    assert error.code == "unsupported_filter"
    assert "'U'" in error.message and "APASS" in error.message
    assert "uprime" in error.message
    # The caller is told where the filter can be calibrated instead.
    assert "SDSS" in error.message and "VSX" not in error.message
    assert result.zero_point is None


def test_offline_rows_from_a_catalog_that_cannot_supply_the_filter_fail_by_name(u_band_frame):
    from tools.fieldcal_reference import replay_catalog_sources
    from tools.photometry import calibrate_zeropoint

    result = calibrate_zeropoint(
        u_band_frame, catalog_sources=replay_catalog_sources("ngc5128_b_002"),
    )
    assert [e.code for e in result.errors] == ["unsupported_filter"]
    assert "APASS" in result.errors[0].message


def test_pipeline_calibration_reports_the_unsupported_filter(u_band_frame, no_catalog_query):
    from tools.photometry_pipeline import compute_field_cal_zero_point

    with fits.open(u_band_frame) as hdul:
        header, data = hdul[0].header, hdul[0].data.astype(float)
    zero_point, diagnostics, message, result = compute_field_cal_zero_point(
        header, data, catalogs=["APASS"],
    )
    assert zero_point is None and result is None
    assert "'U'" in message and "APASS" in message
