"""Offline M5 dispositions for CAT-23/24/28 through maintained catalog paths.

Controls cover corrected zero values, spelling, expression dependencies and
uncertainties. Provider transport is replaced only after the installed SDK
has constructed its real request.
"""

from io import BytesIO
import math

import numpy as np
import pytest
from astropy.table import MaskedColumn, Table
from astroquery.vizier import VizierClass
from requests import Response

from algorithms.catalogs.filters import filter_token_candidates
from algorithms.fieldcal.ref_mag import resolve_ref_mag_for_filter
from algorithms.query.registry import CATALOGS
from algorithms.query.selection import catalog_supports_filter, select_catalogs_for_filter
from algorithms.query.vizier import ProviderResponseError, build_custom_vizier_catalog
from tools.catalogs import resolve_reference_band


def _landolt(**overrides):
    columns = {
        "Star": ["probe"], "RAJ2000": ["06 30 00"], "DEJ2000": ["-00 30 00"],
        "Vmag": [12.0], "e_Vmag": [0.1],
        "B-V": [0.5], "e_B-V": [0.2], "U-B": [0.25], "e_U-B": [0.3],
        "V-R": [0.4], "e_V-R": [0.4], "R-I": [0.1], "e_R-I": [0.5],
        "V-I": [0.5], "e_V-I": [0.6],
    }
    columns.update(overrides)
    return Table(columns)


def _stetson():
    return Table({
        "Star": ["probe"], "RAJ2000": ["06 30 00"], "DEJ2000": ["-00 30 00"],
        "Umag": [12.75], "e_Umag": [0.3], "Bmag": [12.5], "e_Bmag": [0.2],
        "Vmag": [12.0], "e_Vmag": [0.1], "Rmag": [11.6], "e_Rmag": [0.4],
        "Imag": [11.5], "e_Imag": [0.5],
    })


def _offline_votable(monkeypatch, table):
    """Retain real SDK payload construction, XML parsing, and bound mapping."""
    buffer = BytesIO()
    table.write(buffer, format="votable")
    requests = []

    def transport(self, *args, **kwargs):
        requests.append(kwargs)
        response = Response()
        response.status_code = 200
        response._content = buffer.getvalue()
        return response

    monkeypatch.setattr(VizierClass, "_request", transport)
    return requests


def _resolve(source, image_filter):
    return resolve_ref_mag_for_filter(
        catalog_name=source.catalog_name, image_filter=image_filter,
        cs_mags=source.mags, allow_preferred_band_fallback=False,
    )


def _literal_coordinate_catalog(ra_column, dec_column):
    catalog_class = build_custom_vizier_catalog({
        "name": "literal_coordinate_columns", "vizier_catalog": "local/literals",
        "col_mapping": {"ra_hours": ra_column, "dec_degs": dec_column},
        "mags": {"V": ["Vmag", "e_Vmag"]},
    })
    return catalog_class(cache=False)


@pytest.mark.parametrize("catalog_name", ["Landolt", "Stetson"])
@pytest.mark.parametrize("query_mode", ["region", "objects"])
def test_sexagesimal_call_targets_do_not_reach_the_actual_sdk_request(
    catalog_name, query_mode, monkeypatch,
):
    """CAT-24: request real data columns while retaining sexagesimal parsing."""
    catalog = CATALOGS[catalog_name]
    table = _landolt() if catalog_name == "Landolt" else _stetson()
    requests = _offline_votable(monkeypatch, table)
    monkeypatch.setattr(catalog, "cache", False)

    if query_mode == "objects":
        source, = catalog.query_objects(["probe"])
    else:
        source, = catalog.query_circ(6.5, -0.5, 2.0)

    assert "int" not in catalog._columns
    assert "float" not in catalog._columns
    assert len(requests) == 1
    payload = dict(line.split("=", 1) for line in requests[0]["data"].splitlines())
    requested = payload["-out"].split(",")
    assert not {"int", "float"} & set(requested)
    assert {"RAJ2000", "DEJ2000", "Vmag", "e_Vmag"} <= set(requested)
    assert not {"split", "strip", "startswith", "abs"} & set(requested)

    # Hand-specified controls, independent of col_mapping or a mocked mapper:
    # 06:30:00 = 6.5 h; -00:30:00 = -0.5 deg, including negative-zero degrees.
    assert source.ra_hours == 6.5
    assert source.dec_degs == -0.5
    assert {band: source.mags[band].value for band in "UBVRI"} == pytest.approx({
        "U": 12.75, "B": 12.5, "V": 12.0, "R": 11.6, "I": 11.5,
    })
    assert source.mags["V"].error == 0.1
    if catalog_name == "Landolt":
        assert source.mags["B"].error == pytest.approx(math.sqrt(0.05))
        assert source.mags["R"].error == pytest.approx(math.sqrt(0.17))
        # U's disclosed upstream use of the wrong color error is covered by
        # M2/M3. The retained I error/averaging formula also belongs to a
        # photometric uncertainty review rather than column parsing.


@pytest.mark.parametrize("ra_column,dec_column", [("int", "float"), ("float", "int")])
def test_literal_builtin_named_columns_are_requested_and_read(ra_column, dec_column, monkeypatch):
    """A correction must distinguish a call target from a real column name."""
    catalog = _literal_coordinate_catalog(ra_column, dec_column)
    table = Table({ra_column: [6.5], dec_column: [-0.5], "Vmag": [0.0], "e_Vmag": [0.0]})
    requests = _offline_votable(monkeypatch, table)
    source, = catalog.query_circ(6.5, -0.5, 2.0)
    payload = dict(line.split("=", 1) for line in requests[0]["data"].splitlines())
    assert {"int", "float"} <= set(payload["-out"].split(","))
    assert (source.ra_hours, source.dec_degs) == (6.5, -0.5)
    assert (source.mags["V"].value, source.mags["V"].error) == (0.0, 0.0)


@pytest.mark.parametrize("ra_column", ["int", "float"])
def test_missing_literal_builtin_coordinate_is_a_schema_error(ra_column, monkeypatch):
    """A builtin name used as data must pass the same coordinate guard."""
    catalog = _literal_coordinate_catalog(ra_column, "Declination")
    _offline_votable(monkeypatch, Table({"Declination": [-0.5], "Vmag": [12.0]}))
    with pytest.raises(ProviderResponseError, match=ra_column + ".*ra_hours"):
        catalog.query_circ(6.5, -0.5, 2.0)


def test_missing_ordinary_literal_coordinate_is_a_provider_schema_error(monkeypatch):
    catalog = _literal_coordinate_catalog("RAhours", "Declination")
    _offline_votable(monkeypatch, Table({"Declination": [-0.5], "Vmag": [12.0]}))
    with pytest.raises(ProviderResponseError, match="RAhours.*ra_hours"):
        catalog.query_circ(6.5, -0.5, 2.0)


@pytest.mark.parametrize("image_filter", [" g′ ", "\tg’\n", " g_p ", " g_′ "])
def test_composed_prime_spelling_reaches_selection_numeric_and_tool_resolution(image_filter):
    """CAT-28 is corrected: stripping composes with quote/underscore changes."""
    source, = CATALOGS["APASS"].table_to_sources(Table({
        "RAJ2000": [97.5], "DEJ2000": [-0.5], "g'mag": [0.0], "e_g'mag": [0.0],
    }))
    assert "gprime" in filter_token_candidates(image_filter)
    assert catalog_supports_filter("APASS", image_filter)
    assert select_catalogs_for_filter(["2MASS", "APASS"], image_filter) == ["APASS"]
    assert _resolve(source, image_filter) == (0.0, 0.0)
    report = resolve_reference_band("APASS", image_filter)
    assert report.supported
    assert report.reference == "gprime"


@pytest.mark.parametrize("image_filter,compatible", [(" V ", "APASS"), (" v ", "SkyMapper")])
def test_padded_single_letter_case_preserves_violet_and_johnson_identity(image_filter, compatible):
    sources = {
        "APASS": CATALOGS["APASS"].table_to_sources(Table({
            "RAJ2000": [97.5], "DEJ2000": [-0.5], "Vmag": [12.0], "e_Vmag": [0.0],
        }))[0],
        "SkyMapper": CATALOGS["SkyMapper"].table_to_sources(Table({
            "RAICRS": [97.5], "DEICRS": [-0.5], "vPSF": [13.0], "e_vPSF": [0.0],
        }))[0],
    }
    assert select_catalogs_for_filter(["APASS", "SkyMapper"], image_filter) == [compatible]
    for name, source in sources.items():
        assert catalog_supports_filter(name, image_filter) == (name == compatible)
        assert resolve_reference_band(name, image_filter).supported == (name == compatible)
        assert _resolve(source, image_filter) == (
            ((12.0 if name == "APASS" else 13.0), 0.0) if name == compatible else (None, None)
        )


@pytest.mark.parametrize("name,positions,band,column,error_column", [
    ("APASS", {"RAJ2000": [0.0], "DEJ2000": [0.0]}, "V", "Vmag", "e_Vmag"),
    ("Stetson", {"RAJ2000": ["00 00 00"], "DEJ2000": ["+00 00 00"]}, "V", "Vmag", "e_Vmag"),
    ("Landolt", {"RAJ2000": ["00 00 00"], "DEJ2000": ["+00 00 00"]}, "V", "Vmag", "e_Vmag"),
    ("2MASS", {"RAJ2000": [0.0], "DEJ2000": [0.0]}, "J", "Jmag", "e_Jmag"),
    ("PanSTARRS", {"RAJ2000": [0.0], "DEJ2000": [0.0]}, "g", "gmag", "e_gmag"),
])
def test_finite_zero_magnitude_uncertainty_and_position_survive_bound_mapping(
    name, positions, band, column, error_column,
):
    """CAT-23's base mapper report was corrected before this investigation."""
    source, = CATALOGS[name].table_to_sources(Table({
        **positions, column: [0.0], error_column: [0.0],
    }))
    assert (source.ra_hours, source.dec_degs) == (0.0, 0.0)
    assert (source.mags[band].value, source.mags[band].error) == (0.0, 0.0)
    assert _resolve(source, band) == (0.0, 0.0)


def test_zero_landolt_colours_generate_finite_ubvri_values():
    overrides = {name: [0.0] for name in ("B-V", "U-B", "V-R", "R-I", "V-I")}
    source, = CATALOGS["Landolt"].table_to_sources(_landolt(**overrides))
    assert {band: source.mags[band].value for band in "UBVRI"} == dict.fromkeys("UBVRI", 12.0)
    assert all(source.mags[band].value == 0.0 for band in ("B_V", "U_B", "V_R", "R_I", "V_I"))


def test_landolt_synthesized_zero_errors_remain_known():
    """Known-zero quadrature errors survive on all synthesized bands."""
    overrides = {name: [0.0] for name in (
        "e_Vmag", "e_B-V", "e_U-B", "e_V-R", "e_R-I", "e_V-I",
    )}
    source, = CATALOGS["Landolt"].table_to_sources(_landolt(**overrides))
    assert source.mags["V"].error == 0.0
    assert all(source.mags[band].error == 0.0 for band in ("B_V", "U_B", "V_R", "R_I", "V_I"))
    assert all(source.mags[band].error == 0.0 for band in "UBRI")


_UNMEASURED = [
    pytest.param(None, id="absent"), pytest.param(math.nan, id="nan"),
    pytest.param(math.inf, id="positive-infinity"), pytest.param(-math.inf, id="negative-infinity"),
    pytest.param(np.ma.masked, id="masked"), pytest.param(99.0, id="sentinel"),
]


def _cell(value):
    return MaskedColumn([17.0], mask=[True]) if value is np.ma.masked else [value]


@pytest.mark.parametrize("value", _UNMEASURED)
def test_unmeasured_magnitudes_do_not_drop_a_different_usable_band(value):
    source, = CATALOGS["APASS"].table_to_sources(Table({
        "RAJ2000": [97.5], "DEJ2000": [-0.5], "Vmag": _cell(value), "e_Vmag": [0.0],
        "Bmag": [13.0], "e_Bmag": [0.0],
    }))
    assert "V" not in source.mags
    assert (source.mags["B"].value, source.mags["B"].error) == (13.0, 0.0)
    assert _resolve(source, "V") == (None, None)


@pytest.mark.parametrize("value", _UNMEASURED[:-1] + [pytest.param(-0.1, id="negative-error")])
def test_unmeasured_uncertainties_keep_the_finite_zero_magnitude(value):
    source, = CATALOGS["APASS"].table_to_sources(Table({
        "RAJ2000": [97.5], "DEJ2000": [-0.5], "Vmag": [0.0], "e_Vmag": _cell(value),
    }))
    assert (source.mags["V"].value, source.mags["V"].error) == (0.0, None)
    assert _resolve(source, "V") == (0.0, None)


@pytest.mark.parametrize("value", _UNMEASURED)
def test_unmeasured_landolt_colour_leaves_dependent_bands_underived(value):
    source, = CATALOGS["Landolt"].table_to_sources(_landolt(**{"B-V": _cell(value)}))
    assert not {"B_V", "B", "U"} & source.mags.keys()
    assert source.mags["V"].value == 12.0
    assert source.mags["R"].value == pytest.approx(11.6)
    assert source.mags["I"].value == pytest.approx(11.5)


def test_zero_usno_epoch_values_participate_in_the_preserved_photographic_average():
    source, = CATALOGS["USNO"].table_to_sources(Table({
        "RAJ2000": [97.5], "DEJ2000": [-0.5],
        "B1mag": [0.0], "B2mag": [2.0], "R1mag": [0.0], "R2mag": [0.0],
    }))
    assert source.mags["Bphot"].value == 1.0
    assert source.mags["Rphot"].value == 0.0
