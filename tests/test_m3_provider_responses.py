"""M3 provider response changes (``docs/working/master-continuation-plan.md``).

Renamed, missing or non-finite columns used to make a populated response look
empty (CAT-20: ``table_to_sources`` swallowed every per-row mapping failure).
A response must now map, or fail as an unusable response that names what is
missing, never look like a field with no stars. The tables here are shaped
after live responses; ``test_m3_provider_responses_live.py`` checks the same
contracts against the services.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest
from astropy.table import MaskedColumn, Table

from algorithms.query.registry import CATALOGS
from algorithms.query.vizier import ProviderResponseError


def _apass(**overrides) -> Table:
    columns = {
        "RAJ2000": [201.36, 201.37], "DEJ2000": [-43.01, -43.02],
        "Bmag": [14.1, 15.2], "e_Bmag": [0.02, 0.03], "Vmag": [13.5, 14.6], "e_Vmag": [0.02, 0.03],
        "g'mag": [13.8, 14.9], "e_g'mag": [0.02, 0.03], "r'mag": [13.3, 14.4], "e_r'mag": [0.02, 0.03],
        "i'mag": [13.1, 14.2], "e_i'mag": [0.02, 0.03],
    }
    columns.update(overrides)
    return Table({name: value for name, value in columns.items() if value is not None})


# --- ordinary responses still map --------------------------------------------


def test_an_ordinary_response_maps_every_row():
    sources = CATALOGS["APASS"].table_to_sources(_apass())
    assert len(sources) == 2
    assert sources[0].ra_hours == pytest.approx(201.36 / 15)
    assert sources[0].mags["gprime"].value == pytest.approx(13.8)


def test_an_empty_response_is_no_matches_not_an_error():
    assert CATALOGS["APASS"].table_to_sources(_apass().copy()[:0]) == []
    assert CATALOGS["APASS"].table_to_sources(None) == []


def test_a_missing_id_column_alone_is_tolerated():
    # Live APASS never returns the recno it asks for; ids are optional.
    sources = CATALOGS["APASS"].table_to_sources(_apass())
    assert all(source.id is None for source in sources)


# --- renamed and missing columns ----------------------------------------------


def test_a_leading_digit_column_is_found_with_or_without_the_underscore():
    # The 2MASS declaration maps id from "_2MASS" (an older astroquery's
    # rename); current astroquery returns "2MASS", so every id was lost.
    table = Table({"RAJ2000": [201.36], "DEJ2000": [-43.01], "2MASS": ["13252640-4301000"],
                   "Jmag": [12.1], "e_Jmag": [0.02], "Hmag": [11.8], "e_Hmag": [0.02],
                   "Kmag": [11.7], "e_Kmag": [0.02]})
    (source,) = CATALOGS["2MASS"].table_to_sources(table)
    assert source.id == "13252640-4301000"


def test_a_renamed_coordinate_column_is_an_unusable_response():
    table = _apass(RAJ2000=None, ra=[201.36, 201.37])
    with pytest.raises(ProviderResponseError, match=r"APASS.*RAJ2000.*ra_hours"):
        CATALOGS["APASS"].table_to_sources(table)


def test_renamed_magnitude_columns_are_an_unusable_response():
    renamed = {name: None for name in ("Bmag", "e_Bmag", "Vmag", "e_Vmag", "g'mag", "e_g'mag",
                                        "r'mag", "e_r'mag", "i'mag", "e_i'mag")}
    table = _apass(**renamed, B=[14.1, 15.2], V=[13.5, 14.6])
    with pytest.raises(ProviderResponseError, match=r"APASS.*no declared magnitude column"):
        CATALOGS["APASS"].table_to_sources(table)


def test_an_apostrophe_spelling_change_still_maps():
    table = _apass(**{"g'mag": None, "e_g'mag": None}, g_mag=[13.8, 14.9], e_g_mag=[0.02, 0.03])
    sources = CATALOGS["APASS"].table_to_sources(table)
    assert sources[0].mags["gprime"].value == pytest.approx(13.8)


# --- non-finite values ---------------------------------------------------------


@pytest.mark.parametrize("value", [math.nan, 99.0, MaskedColumn([14.1, 15.2], mask=[True, True])])
def test_well_formed_rows_with_nothing_measurable_are_no_matches(value, caplog):
    # A sparse or faint cone, not a broken provider: the columns are all there.
    column = value if isinstance(value, MaskedColumn) else [value, value]
    table = _apass(Bmag=column, Vmag=column, **{"g'mag": column, "r'mag": column, "i'mag": column})
    with caplog.at_level("WARNING", logger="algorithms.query.vizier"):
        assert CATALOGS["APASS"].table_to_sources(table) == []
    assert "2 of 2 rows had no usable magnitude or finite position" in caplog.text


def test_rows_with_no_finite_position_are_dropped_not_an_error():
    assert CATALOGS["APASS"].table_to_sources(_apass(RAJ2000=[math.nan, math.nan])) == []


def test_a_coordinate_column_inside_an_expression_is_not_aliased():
    # 'RAJ2000/15' is evaluated against real names: a response with only the
    # VizieR-computed _RAJ2000 must be named as missing RAJ2000.
    table = _apass(RAJ2000=None, _RAJ2000=[201.36, 201.37])
    with pytest.raises(ProviderResponseError, match="no RAJ2000 column for ra_hours"):
        CATALOGS["APASS"].table_to_sources(table)


def test_a_band_column_found_under_an_underscore_spelling_is_read():
    table = _apass(Vmag=None, _Vmag=[13.5, 14.6])
    sources = CATALOGS["APASS"].table_to_sources(table)
    assert [s.mags["V"].value for s in sources] == [pytest.approx(13.5), pytest.approx(14.6)]


def test_a_row_without_a_finite_position_is_dropped_like_one_without_magnitudes():
    # Live Tycho-2 has stars with masked mean positions (no PM solution).
    table = _apass(RAJ2000=MaskedColumn([201.36, 201.37], mask=[True, False]))
    sources = CATALOGS["APASS"].table_to_sources(table)
    assert [s.ra_hours for s in sources] == [pytest.approx(201.37 / 15)]


def test_some_unusable_rows_are_dropped_and_the_rest_mapped():
    nan = [math.nan, 15.2]
    table = _apass(Bmag=nan, Vmag=nan, **{"g'mag": nan, "r'mag": nan, "i'mag": nan})
    assert len(CATALOGS["APASS"].table_to_sources(table)) == 1


# --- Landolt: unset errors and zero colours -----------------------------------


def _landolt(**overrides) -> Table:
    columns = {
        "Star": ["98 961", "98 966"], "RAJ2000": ["06 51 27", "06 51 29"],
        "DEJ2000": ["-00 15 37", "-00 16 27"], "Vmag": [13.089, 14.001], "e_Vmag": [0.0021, 0.0035],
        "B-V": [1.28, 0.62], "e_B-V": [0.003, 0.004], "U-B": [1.2, 0.1], "e_U-B": [0.005, 0.006],
        "V-R": [0.70, 0.35], "e_V-R": [0.002, 0.003], "R-I": [0.662, 0.331], "e_R-I": [0.0, 0.0191],
        "V-I": [1.362, 0.613], "e_V-I": [0.0021, 0.0205],
    }
    columns.update(overrides)
    return Table(columns)


def test_landolt_maps_a_row_whose_catalog_error_is_exactly_zero():
    # e_R-I = 0.0000 occurs live; the unset error used to reach `None ** 2`.
    sources = CATALOGS["Landolt"].table_to_sources(_landolt())
    assert len(sources) == 2
    first = sources[0].mags
    assert first["B"].value == pytest.approx(13.089 + 1.28)
    assert first["R"].value == pytest.approx(13.089 - 0.70)
    assert first["I"].value == pytest.approx(((13.089 - 0.70) - 0.662 + 13.089 - 1.362) / 2)
    assert first["I"].error > 0


def test_landolt_keeps_the_preserved_u_error_bug():
    # U's error is built from V_R, not U_B (upstream, kept deliberately).
    (first, _) = CATALOGS["Landolt"].table_to_sources(_landolt())
    expected = np.hypot(np.hypot(0.0021, 0.003), 0.002)
    assert first.mags["U"].error == pytest.approx(expected)


def test_landolt_omits_only_the_bands_a_zero_colour_leaves_underivable():
    # The row mapper drops a colour of exactly 0.000 (CAT-23), which used to
    # raise KeyError for the whole response.
    sources = CATALOGS["Landolt"].table_to_sources(_landolt(**{"B-V": [0.0, 0.62]}))
    assert len(sources) == 2
    assert "B" not in sources[0].mags and "U" not in sources[0].mags
    assert {"V", "R", "I"} <= set(sources[0].mags)
    assert {"U", "B", "V", "R", "I"} <= set(sources[1].mags)


# --- the runner reports an unusable response, not an empty field ----------------


def test_the_runner_raises_an_unusable_response_instead_of_returning_nothing(monkeypatch):
    from algorithms.query.runner import query_catalogs

    apass = CATALOGS["APASS"]
    monkeypatch.setattr(apass, "query_circ", lambda *a, **k: apass.table_to_sources(_apass(RAJ2000=None)))
    with pytest.raises(ProviderResponseError):
        query_catalogs(["APASS"], ra_hours=13.42, dec_degs=-43.0, radius_arcmins=3.0)


def test_an_unusable_catalog_does_not_abort_the_fallback_chain(monkeypatch):
    from algorithms.query.runner import query_catalogs

    apass, ucac = CATALOGS["APASS"], CATALOGS["UCAC"]
    monkeypatch.setattr(apass, "query_circ", lambda *a, **k: apass.table_to_sources(_apass(RAJ2000=None)))
    monkeypatch.setattr(ucac, "query_circ", lambda *a, **k: apass.table_to_sources(_apass()))
    found = query_catalogs(["APASS", "UCAC"], ra_hours=13.42, dec_degs=-43.0, radius_arcmins=3.0,
                           stop_on_success=True)
    assert len(found) == 2


def test_every_catalog_unusable_names_each_one(monkeypatch):
    from algorithms.query.runner import query_catalogs

    for name in ("APASS", "UCAC"):
        catalog = CATALOGS[name]
        monkeypatch.setattr(catalog, "query_circ",
                            lambda *a, _c=catalog, **k: _c.table_to_sources(Table({"x": [1.0]})))
    with pytest.raises(ProviderResponseError, match=r"APASS.*; UCAC"):
        query_catalogs(["APASS", "UCAC"], ra_hours=13.42, dec_degs=-43.0, radius_arcmins=3.0)


# --- search_vizier asks VizieR for computed J2000 positions -------------------


def test_search_vizier_requests_computed_j2000_positions(monkeypatch):
    import tools.vizier as vizier_tool

    seen = {}

    class Recording:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        def query_region(self, *args, **kwargs):
            return {}

    monkeypatch.setattr(vizier_tool, "Vizier", Recording)
    vizier_tool.search_vizier(ra_hours=1.0, dec_degs=33.0, radius_arcmin=1.0, category="radio")
    # B1950-only catalogs (3C, 4C, ...) have no J2000 column of their own;
    # these computed columns are what lets every catalog be cross-matched.
    assert seen["columns"] == ["**", "_RAJ2000", "_DEJ2000"]


# --- radio: unreadable catalog positions are reported, not "no match" --------


def _detected_radio():
    import pandas as pd

    return pd.DataFrame({"ra_deg": [24.4221], "dec_deg": [33.1598], "flux": [1.0]})


def test_radio_positions_are_read_from_vizier_icrs_columns():
    import pandas as pd

    from algorithms.radio.matching import guess_radec_columns

    table = pd.DataFrame({"RA1950": ["01 34 49.8"], "DE1950": ["+32 54 20"],
                          "_RA.icrs": [24.4221], "_DE.icrs": [33.1598]})
    assert guess_radec_columns(table) == ("_RA.icrs", "_DE.icrs")


def test_identify_radio_sources_warns_about_a_catalog_it_cannot_position(monkeypatch, tmp_path):
    import pandas as pd
    from astropy.table import Table as AstropyTable

    import tools.radio_sources as radio
    from tools.models import ArtifactRef, ToolResult

    b1950 = tmp_path / "VIII_1A_3c.ecsv"
    AstropyTable({"3C": ["48"], "RA1950": ["01 34 49.8"], "DE1950": ["+32 54 20"]}).write(b1950, format="ascii.ecsv")
    j2000 = tmp_path / "VIII_65_nvss.ecsv"
    AstropyTable({"NVSS": ["013741+330935"], "RAJ2000": [24.4221], "DEJ2000": [33.1598]}).write(j2000, format="ascii.ecsv")
    artifacts = [ArtifactRef(path=str(p), format="ecsv", row_count=1) for p in (b1950, j2000)]
    monkeypatch.setattr(radio, "_extract_radio_sources", lambda *a, **k: _detected_radio())
    monkeypatch.setattr(radio, "search_vizier", lambda **k: ToolResult(status="ok", artifacts=artifacts))
    monkeypatch.setattr(radio, "_write_df_artifact", lambda df, stem: None)

    result = radio.identify_radio_sources("unused.fits")
    assert result.status == "ok"
    (warning,) = [w for w in result.warnings if w.code == "catalog_positions_unreadable"]
    assert "VIII_1A_3c" in warning.message and "VIII_65_nvss" not in warning.message


def test_a_renamed_ned_flux_column_is_an_unusable_response(monkeypatch, tmp_path):
    from astropy.table import Table as AstropyTable

    import tools.radio_sources as radio
    from tools.models import ArtifactRef, ToolResult

    path = tmp_path / "ned.ecsv"
    AstropyTable({"Frequency": [1.4e9], "FluxDensity": [15.0]}).write(path, format="ascii.ecsv")
    monkeypatch.setattr(radio, "search_ned", lambda *a, **k: ToolResult(
        status="ok", count=1, artifact=ArtifactRef(path=str(path), format="ecsv", row_count=1)))
    result = radio.analyze_source_spectrum(name="3C 48")
    assert result.status == "error"
    assert [e.code for e in result.errors] == ["unusable_response"]
    assert "Flux Density" in result.errors[0].message


def test_the_radio_name_columns_include_the_current_2mass_spelling():
    import tools.radio_sources as radio

    assert radio._best_name({"2MASS": "01374130+3309350"}) == "01374130+3309350"


# --- HR: Gaia and literature column contracts ---------------------------------


def _vizier_result(tmp_path, columns: dict):
    from astropy.table import Table as AstropyTable

    from tools.models import ArtifactRef, ToolResult

    path = tmp_path / "rows.ecsv"
    AstropyTable(columns).write(path, format="ascii.ecsv", overwrite=True)
    return ToolResult(status="ok", count=1, artifacts=[ArtifactRef(path=str(path), format="ecsv", row_count=1)])


LITERATURE_ROW = {"Cluster": ["NGC_2682"], "RA_ICRS": [132.846], "DE_ICRS": [11.814], "plx": [1.135],
                  "pmRA*": [-10.986], "pmDE": [-2.964], "AgeNN": [9.63], "AVNN": [0.07],
                  "DMNN": [9.75], "DistPc": [889.0]}


def test_literature_params_with_a_renamed_column_are_an_unusable_response(monkeypatch, tmp_path):
    import tools.hr_diagram as hr

    row = {("pmRA_" if k == "pmRA*" else k): v for k, v in LITERATURE_ROW.items()}
    monkeypatch.setattr(hr, "search_vizier", lambda **k: _vizier_result(tmp_path, row))
    for call in (lambda: hr.get_literature_cluster_params("M67"),
                 lambda: hr.crossmatch_gaia_by_position("M67")):
        result = call()  # crossmatch_gaia_by_position let KeyError escape
        assert [e.code for e in result.errors] == ["unusable_response"]
        assert "pmRA*" in result.errors[0].message


def test_non_finite_literature_params_are_an_unusable_response(monkeypatch, tmp_path):
    import tools.hr_diagram as hr

    row = dict(LITERATURE_ROW, AgeNN=[math.nan])
    monkeypatch.setattr(hr, "search_vizier", lambda **k: _vizier_result(tmp_path, row))
    result = hr.get_literature_cluster_params("M67")
    assert [e.code for e in result.errors] == ["unusable_response"]
    assert "AgeNN" in result.errors[0].message


def test_gaia_rows_with_renamed_photometry_are_an_unusable_response(monkeypatch, tmp_path):
    import tools.hr_diagram as hr

    gaia = {"RA_ICRS": [132.84], "DE_ICRS": [11.81], "Source": [1], "G": [12.0], "BP": [12.3], "RP": [11.6]}
    monkeypatch.setattr(hr, "_fetch_literature_params", lambda name: {"ra_deg": 132.84, "dec_deg": 11.81})
    monkeypatch.setattr(hr, "search_vizier", lambda **k: _vizier_result(tmp_path, gaia))
    result = hr.crossmatch_gaia_by_position("M67")
    assert [e.code for e in result.errors] == ["unusable_response"]
    assert "BPmag" in result.errors[0].message


# --- SIMBAD mapping ------------------------------------------------------------


class _Simbad:
    rows: list = []

    def __init__(self):
        pass

    def add_votable_fields(self, *fields):
        pass

    def query_object(self, name, wildcard=False):
        return type(self).rows


@pytest.fixture
def simbad_rows(monkeypatch):
    import astroquery.simbad

    import algorithms.query.simbad as simbad_query

    class Fake(_Simbad):
        rows = []

    monkeypatch.setattr(astroquery.simbad, "Simbad", Fake)
    monkeypatch.setattr(simbad_query, "_simbad", None)
    monkeypatch.setattr(simbad_query, "_simbad_init_error", None)
    monkeypatch.setattr(simbad_query, "_simbad_retry_at", 0.0)
    return Fake


def test_simbad_reads_uppercase_columns_from_older_astroquery(simbad_rows):
    from algorithms.query.simbad import resolve_simbad

    simbad_rows.rows = Table({"MAIN_ID": ["M  31"], "RA": [10.6847], "DEC": [41.2688], "OTYPE": ["AGN"]})
    (target,) = resolve_simbad("M31", strict=True)
    assert target.object_name == "M  31" and target.ra_deg == pytest.approx(10.6847)


def test_simbad_keeps_an_object_at_ra_zero(simbad_rows):
    from algorithms.query.simbad import resolve_simbad

    simbad_rows.rows = Table({"main_id": ["test"], "ra": [0.0], "dec": [0.0], "otype": ["*"]})
    assert len(resolve_simbad("test", strict=True)) == 1


def test_a_simbad_response_missing_columns_is_an_unusable_response(simbad_rows):
    from algorithms.query.simbad import SimbadResponseError, resolve_simbad
    from tools.resolve import resolve_target

    simbad_rows.rows = Table({"main_id": ["M  31"], "ra_deg": [10.68], "dec_deg": [41.27]})
    with pytest.raises(SimbadResponseError, match="ra"):
        resolve_simbad("M31", strict=True)
    assert resolve_simbad("M31") == []  # the default keeps its never-raise contract
    result = resolve_target("M31")
    assert [e.code for e in result.errors] == ["unusable_response"]


# --- calibration reports an unusable catalog response by name ------------------


def test_calibration_reports_an_unusable_catalog_response(monkeypatch):
    import algorithms.query.runner as runner
    from tools.optical import resolve_optical_frame
    from tools.photometry import calibrate_zeropoint

    def unusable(*args, **kwargs):
        raise ProviderResponseError("APASS: the response has no RAJ2000 column for ra_hours")

    monkeypatch.setattr(runner, "query_catalogs", unusable)
    result = calibrate_zeropoint(resolve_optical_frame("ngc5128_galaxy_b_001").path, catalogs=["APASS"])
    assert [e.code for e in result.errors] == ["unusable_response"]
    assert "RAJ2000" in result.errors[0].message


# --- ADS: object: is translated by the objects service before searching -------


def test_ads_fielded_clauses_are_each_grouped():
    from tools.ads import _build_query

    query = _build_query(None, None, False, None, "pulsar timing", None, None, "PSR B1937+21", None)
    assert query == '(abs:"pulsar timing") AND (object:"PSR B1937+21")'


_TRANSLATED = '(abs:"pulsar timing") AND (((=abs:"PSR B1937+21" OR simbid:"2789895") database:astronomy))'


@pytest.fixture
def ads_service(monkeypatch):
    """Stand in for ADS's objects service and search, recording each call.

    Shaped after the live 2026-10-22 responses: search rejects ``object:`` as
    ``undefined field object``; ``POST /v1/objects/query`` rewrites it.
    """
    from astroquery.nasa_ads import ADSClass
    from requests import Response

    import tools.ads as ads

    calls = {"objects": [], "search": []}
    service = {"status": 200, "body": {"query": _TRANSLATED}}

    def request(self, method, url, **kwargs):
        calls["objects"].append((method, url, kwargs.get("json"), kwargs.get("headers")))
        response = Response()
        response.status_code, response.encoding = service["status"], "utf-8"
        response._content = json.dumps(service["body"]).encode()
        return response

    def query_simple(query_string, **kwargs):
        calls["search"].append(query_string)
        return Table({"bibcode": ["2020ApJ...1..1A"], "title": [["A paper"]]})

    monkeypatch.setattr(ADSClass, "_request", request)
    monkeypatch.setattr(ads.ADS, "query_simple", query_simple)
    monkeypatch.setattr(ads.ADS, "TOKEN", "token")
    return calls, service


@pytest.mark.parametrize("call", [
    lambda ads: ads.search_ads(abstract="pulsar timing", object_name="PSR B1937+21"),
    lambda ads: ads.build_literature_review(abstract="pulsar timing", object_name="PSR B1937+21"),
])
def test_ads_object_name_is_translated_before_searching(ads_service, call):
    import tools.ads as ads

    calls, _ = ads_service
    result = call(ads)
    assert result.status == "ok", result.errors
    method, url, payload, headers = calls["objects"][0]
    assert (method, url) == ("POST", "https://api.adsabs.harvard.edu/v1/objects/query")
    assert payload == {"query": ['(abs:"pulsar timing") AND (object:"PSR B1937+21")']}
    assert headers == {"Authorization": "Bearer token"}
    assert calls["search"] == [_TRANSLATED]


def test_ads_raw_query_with_object_is_translated_too(ads_service):
    from tools.ads import search_ads

    calls, _ = ads_service
    assert search_ads('object:"M31" year:2020').status == "ok"
    assert calls["objects"][0][2] == {"query": ['(object:"M31" year:2020)']}


def test_ads_query_without_object_skips_the_objects_service(ads_service):
    from tools.ads import get_citing_papers, search_ads

    calls, _ = ads_service
    assert search_ads(abstract="pulsar timing").status == "ok"
    assert get_citing_papers("1982Natur.300..615B").status == "ok"
    assert calls["objects"] == []
    assert calls["search"] == ['(abs:"pulsar timing")', "citations(bibcode:1982Natur.300..615B)"]


@pytest.mark.parametrize("query", ['title:"object: a study"', 'abs:"compact object: review"'])
def test_ads_object_inside_a_quoted_phrase_is_not_translated(ads_service, query):
    from tools.ads import search_ads

    # Live, the objects service refuses these ("No identifiers/objects
    # found"), while the search answers them untranslated.
    calls, _ = ads_service
    assert search_ads(query).status == "ok"
    assert calls["objects"] == []
    assert calls["search"] == [f"({query})"]


def test_ads_object_name_with_a_double_quote_is_refused(ads_service):
    from tools.ads import build_literature_review, search_ads

    # Live, the objects service splits the name at an escaped quote and
    # returns a query the search rejects.
    calls, _ = ads_service
    for result in (search_ads(object_name='Foo "bar"'), build_literature_review(object_name='Foo "bar"')):
        assert [e.code for e in result.errors] == ["invalid_input"]
    assert calls["objects"] == [] and calls["search"] == []


def test_ads_pages_with_differently_shaped_columns_stack(monkeypatch, ads_service):
    import tools.ads as ads
    from astropy.table import Table as AstropyTable

    # Live 2026-10-22 (M31, year 2020, 120 rows): a field present in every row
    # of a page is a 2-D str column; one missing from some row (astroquery
    # fills [None]) is 1-D object. vstack refused the mix and the exception
    # escaped the tool.
    def query_simple(query_string, **kwargs):
        start, rows = ads.ADS.NSTART, ads.ADS.NROWS
        count = min(rows, 120 - start)
        page = [[f"L{start + i}"] if start == 0 else ([None] if i % 2 else [f"{start + i}"])
                for i in range(count)]
        return AstropyTable({
            "bibcode": [[f"2020b{start + i}"] for i in range(count)],
            "page": page,
            "author": [["A, B"] * (1 + i % 2) for i in range(count)],
        })

    monkeypatch.setattr(ads.ADS, "query_simple", query_simple)
    result = ads.search_ads(object_name="M31", max_results=120)
    assert result.status == "ok", result.errors
    assert result.count == 120
    table = AstropyTable.read(result.artifact.path)
    assert len({ads.flatten_value(cell) for cell in table["bibcode"]}) == 120
    assert ads.flatten_value(table["page"][0]) == "L0"
    assert ads.flatten_value(table["page"][51]) is None


@pytest.mark.parametrize("status, body, code", [
    (503, {"message": "down"}, "provider_unavailable"),
    (500, {"message": "Internal Server Error"}, "provider_unavailable"),
    (200, {"Error": "Unable to get results!", "Error Info": "SIMBAD returned status 500"},
     "provider_unavailable"),
    # Live reply to an object: clause the service cannot parse (object:"").
    (200, {"Error": "Unable to get results!",
           "Error Info": "No identifiers/objects found in Solr object query"}, "invalid_input"),
    (200, {"unexpected": 1}, "unusable_response"),
    (200, {"query": ""}, "unusable_response"),
])
def test_ads_failed_object_translation_never_searches(ads_service, status, body, code):
    from tools.ads import search_ads

    calls, service = ads_service
    service.update(status=status, body=body)
    result = search_ads(object_name="PSR B1937+21")
    assert result.status == "error"
    assert [e.code for e in result.errors] == [code]
    assert calls["search"] == []


def test_ads_object_translation_without_a_token_is_dependency_missing(monkeypatch, ads_service):
    import tools.ads as ads

    calls, _ = ads_service
    monkeypatch.setattr(ads.ADS, "TOKEN", None)
    monkeypatch.delenv("ADS_DEV_KEY", raising=False)
    monkeypatch.setenv("HOME", "/nonexistent")
    result = ads.search_ads(object_name="M31")
    assert [e.code for e in result.errors] == ["dependency_missing"]
    assert calls["objects"] == [] and calls["search"] == []


# --- SDSS: a cached SkyServer error page is not a permanent failure -----------


@pytest.mark.parametrize("page", [
    b"<html><head> <title>Skyserver Error</title> </head><body>Invalid column</body></html>",
    b"<!DOCTYPE html>\n<html>\n<head><title>404</title></head>\n<body>\n<p>Not Found</p>\n</body>\n</html>\n",
])
def test_a_persistent_sdss_error_page_is_a_retryable_service_failure(monkeypatch, page):
    from astroquery.exceptions import RemoteServiceError
    from astroquery.sdss import SDSSClass
    from requests import Response

    calls = []

    def request(self, method, url, **kwargs):
        calls.append(kwargs.get("cache"))
        response = Response()
        response.status_code, response.encoding, response._content = 200, "utf-8", page
        return response

    monkeypatch.setattr(SDSSClass, "_request", request)
    # An outage page is the service failing -- try again later -- not a
    # response MARS can never read.
    with pytest.raises(RemoteServiceError, match="HTML page"):
        CATALOGS["SDSS"].query_circ(12.0, 0.5, 1.0)
    assert len(calls) == 2  # the first attempt, then one refetch


def test_a_cached_sdss_error_page_is_evicted_and_replaced(monkeypatch, tmp_path):
    from astroquery.sdss import SDSSClass

    import algorithms.query.sdss as sdss_module

    good = (b"objID,ra,dec,u,err_u,g,err_g,r,err_r,i,err_i,z,err_z\n"
            b"1,180,0.5,15,0.01,14,0.01,13.5,0.01,13.3,0.01,13.2,0.01\n")
    answers = iter([b"<html><title>Skyserver Error</title></html>", good])
    import requests

    def request(self, method, url, **kwargs):  # the session astroquery's cache fronts
        response = requests.Response()
        response.status_code, response.encoding, response._content = 200, "utf-8", next(answers)
        response.url = url
        response.request = requests.Request(method, url).prepare()  # astroquery's to_cache needs it
        return response

    monkeypatch.setattr(requests.Session, "request", request)
    client = sdss_module.SDSS()
    client.cache_location = tmp_path
    monkeypatch.setattr(sdss_module, "SDSS", lambda: client)
    (source,) = CATALOGS["SDSS"].query_circ(12.0, 0.5, 1.0)
    assert int(source.id) == 1
    # The good reply replaced the poisoned page: a third call needs no network.
    (cached,) = CATALOGS["SDSS"].query_circ(12.0, 0.5, 1.0)
    assert int(cached.id) == 1
    assert len(list(tmp_path.glob("*.pickle"))) == 1


def test_an_sdss_cached_error_page_recovers_when_the_service_answers(monkeypatch):
    from astroquery.sdss import SDSSClass
    from requests import Response

    answers = iter([b"<html><title>Skyserver Error</title></html>",
                    b"objID,ra,dec,u,err_u,g,err_g,r,err_r,i,err_i,z,err_z\n"
                    b"1,180,0.5,15,0.01,14,0.01,13.5,0.01,13.3,0.01,13.2,0.01\n"])

    def request(self, method, url, **kwargs):
        response = Response()
        response.status_code, response.encoding, response._content = 200, "utf-8", next(answers)
        return response

    monkeypatch.setattr(SDSSClass, "_request", request)
    (source,) = CATALOGS["SDSS"].query_circ(12.0, 0.5, 1.0)
    assert int(source.id) == 1


def test_an_sdss_network_failure_is_not_relabelled(monkeypatch):
    from astroquery.sdss import SDSSClass
    from requests import ConnectionError as RequestsConnectionError

    def down(self, method, url, **kwargs):
        raise RequestsConnectionError("connection refused")

    monkeypatch.setattr(SDSSClass, "_request", down)
    with pytest.raises(RequestsConnectionError):
        CATALOGS["SDSS"].query_circ(12.0, 0.5, 1.0)


# --- review follow-ups on ca3c4b9 ------------------------------------------------


def test_a_non_finite_parallax_or_motion_does_not_refuse_the_literature_fit(monkeypatch, tmp_path):
    import tools.hr_diagram as hr

    row = dict(LITERATURE_ROW, **{"pmRA*": [math.nan], "plx": [math.nan]})
    monkeypatch.setattr(hr, "search_vizier", lambda **k: _vizier_result(tmp_path, row))
    result = hr.get_literature_cluster_params("M67")
    assert result.status == "ok", result.errors
    assert result.preview[0]["log_age"] == pytest.approx(9.63)


def test_a_non_finite_cluster_position_cannot_centre_a_gaia_fetch(monkeypatch, tmp_path):
    import tools.hr_diagram as hr

    row = dict(LITERATURE_ROW, RA_ICRS=[math.nan])
    monkeypatch.setattr(hr, "search_vizier", lambda **k: _vizier_result(tmp_path, row))
    result = hr.crossmatch_gaia_by_position("M67")
    assert [e.code for e in result.errors] == ["unusable_response"]
    assert "not finite" in result.errors[0].message


@pytest.mark.parametrize("raised, code", [
    (ProviderResponseError("APASS: the response has no RAJ2000 column for ra_hours"), "unusable_response"),
    (RuntimeError("Could not match any detected sources to catalog sources"), "field_calibration_failed"),
])
def test_the_photometry_pipeline_reports_why_field_calibration_failed(monkeypatch, raised, code):
    import algorithms.query.runner as runner
    from tools.photometry_pipeline import load_fits_image, select_zero_point_mag
    from tools.optical import resolve_optical_frame
    from pathlib import Path

    def fail(*args, **kwargs):
        raise raised

    monkeypatch.setattr(runner, "query_catalogs", fail)
    data, header = load_fits_image(Path(resolve_optical_frame("ngc5128_galaxy_b_001").path))
    header.remove("PHOT_M0", ignore_missing=True)
    resolution = select_zero_point_mag(None, header, data, use_field_cal=True, catalogs=["APASS"])
    assert resolution.value is None
    assert resolution.failure_code == code
    assert str(raised) in resolution.failure


def test_run_photometry_on_target_carries_the_failure_as_a_warning(monkeypatch):
    import tools.photometry as photometry
    from tools.photometry_pipeline import ZeroPointResolution

    failed = ZeroPointResolution(None, "none", verified=False,
                                 failure="unusable catalog response: APASS: no RAJ2000",
                                 failure_code="unusable_response")
    monkeypatch.setattr(photometry, "compute_photometry",
                        lambda *a, **k: (np.zeros((4, 4)), [], failed))
    monkeypatch.setattr(photometry, "plot_photometry", lambda *a, **k: None)
    result = photometry.run_photometry_on_target("ngc5128_galaxy_b_001")
    assert [(w.code, w.message) for w in result.warnings] == [
        ("unusable_response", "unusable catalog response: APASS: no RAJ2000")]
