"""Known zero and absent errors remain distinct in Landolt synthesis."""

import math

import pytest
from astropy.table import Table

from algorithms.fieldcal.ref_mag import resolve_ref_mag_for_filter
from algorithms.query.registry import CATALOGS


def _source(errors):
    columns = {
        "Star": ["probe"], "RAJ2000": ["06 30 00"], "DEJ2000": ["-00 30 00"],
        "Vmag": [12.0], "B-V": [0.5], "U-B": [0.25], "V-R": [0.4],
        "R-I": [0.1], "V-I": [0.5],
    }
    columns.update({name: [value] for name, value in errors.items()})
    source, = CATALOGS["Landolt"].table_to_sources(Table(columns))
    assert (source.ra_hours, source.dec_degs) == (6.5, -0.5)
    assert {b: source.mags[b].value for b in "UBVRI"} == pytest.approx({
        "U": 12.75, "B": 12.5, "V": 12.0, "R": 11.6, "I": 11.5,
    })
    return source


_ERRORS = ("e_Vmag", "e_B-V", "e_U-B", "e_V-R", "e_R-I", "e_V-I")


@pytest.mark.parametrize("errors,expected", [
    ({name: 0.0 for name in _ERRORS}, dict.fromkeys("UBRI", 0.0)),
    ({}, dict.fromkeys("UBRI")),
    ({"e_Vmag": 0.0}, dict.fromkeys("UBRI")),
    ({"e_Vmag": 0.0, "e_B-V": 0.0}, {"B": 0.0, "U": None, "R": None, "I": None}),
    ({"e_Vmag": 0.0, "e_V-R": 0.0}, {"B": None, "U": None, "R": 0.0, "I": None}),
    # The retained U formula reads B and V_R; U_B is deliberately not changed here.
    ({name: 0.0 for name in _ERRORS if name != "e_U-B"}, dict.fromkeys("UBRI", 0.0)),
])
def test_zero_requires_recorded_errors_for_the_actual_formula(errors, expected):
    source = _source(errors)
    assert {band: source.mags[band].error for band in "UBRI"} == expected
    for band in "UBRI":
        value, error = resolve_ref_mag_for_filter(
            catalog_name="Landolt", image_filter=band, cs_mags=source.mags,
            allow_preferred_band_fallback=False,
        )
        assert value == source.mags[band].value
        assert error == expected[band]


def test_positive_partial_missing_errors_keep_the_legacy_quadrature():
    source = _source({"e_Vmag": 0.1})
    assert {band: source.mags[band].error for band in "UBR"} == pytest.approx(dict.fromkeys("UBR", 0.1))
    assert source.mags["I"].error == pytest.approx(math.sqrt(0.02 / 2))


@pytest.mark.parametrize("missing", ["e_Vmag", "e_B-V", "e_V-R", "e_R-I", "e_V-I"])
def test_unknown_error_is_not_synthesized_as_zero(missing):
    source = _source({name: 0.0 for name in _ERRORS if name != missing})
    dependent = {
        "e_Vmag": "UBRI", "e_B-V": "UB", "e_V-R": "URI",
        "e_R-I": "I", "e_V-I": "I",
    }[missing]
    assert all(source.mags[band].error is None for band in dependent)
