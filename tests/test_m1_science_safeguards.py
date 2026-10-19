"""Independent CAT-01/TS-01 safeguards, not snapshots of the known bugs."""

import math

import pytest
from astropy.coordinates import SkyCoord
import astropy.units as u

from algorithms.fieldcal.ref_mag import resolve_ref_mag_for_filter
from algorithms.hrdiagram_py import legacy
from algorithms.query.selection import catalog_supports_filter, select_catalogs_for_filter


@pytest.mark.parametrize("token", ["V", " V "])
def test_johnson_v_does_not_select_violet(token):
    assert not catalog_supports_filter("SkyMapper", token)
    assert select_catalogs_for_filter(["SkyMapper", "APASS"], token) == ["APASS"]
    from tools.catalogs import resolve_reference_band
    resolution = resolve_reference_band("SkyMapper", token)
    assert not resolution.supported
    assert resolution.reference != "v"


@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("token", ["V", " V "])
def test_johnson_v_does_not_resolve_violet(token, fallback):
    assert resolve_ref_mag_for_filter(
        image_filter=token, catalog_name="SkyMapper", cs_mags={"v": 12.3},
        allow_preferred_band_fallback=fallback) == (None, None)


def test_native_violet_and_explicit_transform_are_retained():
    assert catalog_supports_filter("SkyMapper", "v")
    assert resolve_ref_mag_for_filter(
        image_filter="v", catalog_name="SkyMapper", cs_mags={"v": 12.3}) == (12.3, None)
    lookup = {"SkyMapper": {"V": "g - 0.5*(g-r)"}}
    assert catalog_supports_filter("SkyMapper", "V", custom_filter_lookup=lookup)
    assert resolve_ref_mag_for_filter(
        image_filter="V", catalog_name="SkyMapper", cs_mags={"g": 12., "r": 11.},
        custom_filter_lookup=lookup, propagate_error=False) == (11.5, None)


@pytest.mark.parametrize("ra,dec", [(132.825, 11.8), (0, 0), (90, 0), (180, 0),
                                    (270, 0), (15, 75), (345, -75), (0, 90), (0, -90)])
def test_galactic_quadrants_match_independent_icrs_reference(ra, dec):
    actual = legacy.equatorial_to_galactic(ra, dec)
    reference = SkyCoord(ra=ra*u.deg, dec=dec*u.deg, frame="icrs").galactic
    delta = (actual["l"] - reference.l.deg + 180) % 360 - 180
    # Retain the legacy pole/node constants (about 0.0013 degrees from ICRS).
    assert abs(delta) < .002
    assert actual["b"] == pytest.approx(reference.b.deg, abs=.002)
    assert 0 <= actual["l"] < 360


@pytest.mark.parametrize("ra,dec", [(math.nan, 0), (0, math.inf), (0, 91), (0, -91)])
def test_invalid_equatorial_coordinates_are_rejected(ra, dec):
    with pytest.raises(ValueError):
        legacy.equatorial_to_galactic(ra, dec)
