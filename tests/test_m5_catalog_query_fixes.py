"""Independent boundary controls for M5 box and column corrections."""

import math

import pytest
from astropy.table import MaskedColumn, Table
from astropy.units import arcmin

from algorithms.query.registry import CATALOGS
from algorithms.query.vizier import ProviderResponseError, build_custom_vizier_catalog


def _half_longitude(dec, width, height):
    # Original public rectangle definition, independent of cache rounding.
    if abs(dec) + height / 120 > 90 or width >= 21600:
        return 180.0
    ratio = math.sin(math.radians(width / 120)) / math.cos(math.radians(dec))
    return 180.0 if abs(ratio) >= 1 else math.degrees(math.asin(ratio))


@pytest.mark.parametrize("name", ["APASS", "SDSS"])
@pytest.mark.parametrize("ra,dec,width,height", [
    (0.0013, 70.0013, 2.0, 0.4),
    (359.9987, -70.0013, 0.4, 2.0),
    (20.0, 89.9013, 4.0, 0.4),  # snapping toward the equator changes RA span
    (20.0, -89.9013, 4.0, 0.4),
    (0.0013, 89.999, 0.2, 0.2),
    (359.9987, -89.999, 0.2, 0.2),
    (359.9987, 89.0, 119.999, 0.2),  # near the full-longitude transition
    (0.0013, -89.0, 120.0, 0.2),
    (15.0, 0.0013, 21600.0, 2.0),
    (117.4488, 11.0824888, 20116.5425, 0.0076),  # asin decreases above 180 deg
    (15.0013, -20.0013, 2.0, None),  # omitted height is the original width
])
def test_public_cached_box_encloses_original_bounds(name, ra, dec, width, height, monkeypatch):
    catalog = CATALOGS[name]
    monkeypatch.setattr(catalog, "cache", True)
    captured = []
    if name == "SDSS":
        def capture(ra, dec, region, limit):
            captured.append((ra * 15, dec, *[x.to_value(arcmin) for x in region]))
            return []
        monkeypatch.setattr(catalog, "_query_sql_region", capture)
    else:
        def capture(ra, dec, constraints, limit, **region):
            captured.append((ra * 15, dec, region["width"].to_value(arcmin),
                             region["height"].to_value(arcmin)))
            return []
        monkeypatch.setattr(catalog, "query_region", capture)
    assert catalog.query_box(ra / 15, dec, width, height) == []
    if height is None:
        height = width
    snapped_ra, snapped_dec, snapped_width, snapped_height = captured[0]
    assert snapped_dec - snapped_height / 120 <= dec - height / 120 + 1e-12
    assert snapped_dec + snapped_height / 120 >= dec + height / 120 - 1e-12
    original_span = _half_longitude(dec, width, height)
    snapped_span = _half_longitude(snapped_dec, snapped_width, snapped_height)
    shift = abs((ra - snapped_ra + 180) % 360 - 180)
    if original_span == 180:
        assert snapped_span == 180
    else:
        assert snapped_span + 1e-10 >= original_span + shift


def _catalog(expression):
    return build_custom_vizier_catalog({
        "name": "expression_probe", "vizier_catalog": "local/probe",
        "col_mapping": {"ra_hours": expression, "dec_degs": "DEC"},
        "mags": {"V": ["Vmag"]},
    })(cache=False)


@pytest.mark.parametrize("column", ["int", "float", "sqrt", "split", "pi", "nan"])
def test_literal_names_are_data_even_when_exported_or_callable(column):
    catalog = _catalog(column)
    assert column in catalog._columns
    source, = catalog.table_to_sources(Table({column: [6.5], "DEC": [-0.5], "Vmag": [12.0]}))
    assert source.ra_hours == 6.5
    with pytest.raises(ProviderResponseError, match=column + ".*ra_hours"):
        catalog.table_to_sources(Table({"DEC": [-0.5], "Vmag": [12.0]}))


@pytest.mark.parametrize("expression,columns,value", [
    ("float(RA.strip()) / 15", {"RA": ["97.5"]}, 6.5),
    ("sqrt(RA) + abs(offset)", {"RA": [36.0], "offset": [-0.5]}, 6.5),
    ("int + float", {"int": [6.0], "float": [0.5]}, 6.5),
    ("(lambda x: x/15)(RA)", {"RA": [97.5]}, 6.5),
    ("[x/15 for x in [RA]][0]", {"RA": [97.5]}, 6.5),
    ("next(x/15 for x in [RA])", {"RA": [97.5]}, 6.5),
    ("{x: x/15 for x in [RA]}[RA]", {"RA": [97.5]}, 6.5),
    ("(lambda x, y=RA: x+y)(0.0)", {"RA": [6.5]}, 6.5),
])
def test_column_analysis_distinguishes_data_reads_calls_and_attributes(expression, columns, value):
    catalog = _catalog(expression)
    assert set(catalog._columns) == set(columns) | {"DEC", "Vmag"}
    source, = catalog.table_to_sources(Table({**columns, "DEC": [-0.5], "Vmag": [12.0]}))
    assert source.ra_hours == value


def test_masked_optional_id_stays_unset_without_dropping_numeric_zero_id():
    catalog = type(CATALOGS["APASS"])(cache=False)
    sources = catalog.table_to_sources(Table({
        "recno": MaskedColumn([42, 0], mask=[True, False]),
        "RAJ2000": [0.0, 15.0], "DEJ2000": [0.0, 0.0], "Vmag": [12.0, 13.0],
    }))
    assert len(sources) == 2
    assert sources[0].id is None
    assert sources[1].id == 0


def test_invalid_null_byte_mapping_keeps_contextual_definition_error():
    with pytest.raises(ValueError, match='Bad column definition.*ra_hours.*expression_probe'):
        _catalog("RA\x00/15")
