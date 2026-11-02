"""Correctness regressions for M5's pointing and alternate-WCS scale hints."""

import math

import pytest

from algorithms.wcs.header_utils import (
    _parse_ra_dec_values,
    estimate_pixel_scale_arcsec_per_pix,
    guess_icrs_radec_from_header,
)


@pytest.mark.parametrize("ra,dec,expected_ra,expected_dec", [
    ("185.6", "-20", 185.6, -20.0),
    ("25", 30.0, 25.0, 30.0),
    (6.0, "30", 90.0, 30.0),
    ("6", 30.0, 90.0, 30.0),
    ("24", "30", 360.0, 30.0),
    ("-1", "30", -15.0, 30.0),
    ("10deg", "-20deg", 10.0, -20.0),
    ("12h", "-20deg", 180.0, -20.0),
    ("06:00:00", "−30:00:00", 90.0, -30.0),
])
def test_ra_numeric_strings_follow_the_numeric_unit_heuristic(ra, dec, expected_ra, expected_dec):
    """String storage and Dec's type must not change the RA interpretation."""
    ra_deg, dec_deg = _parse_ra_dec_values(ra, dec)
    assert ra_deg == pytest.approx(expected_ra)
    assert dec_deg == pytest.approx(expected_dec)


@pytest.mark.parametrize("ra,expected", [
    ("185.6", 185.6),
    ("375", 15.0),
    ("-1", 345.0),
    ("10deg", 10.0),
    (6.0, 90.0),
])
def test_fallback_pointing_normalizes_the_parsed_ra(ra, expected):
    ra_deg, dec_deg = guess_icrs_radec_from_header({"RA_PNT": ra, "DEC_PNT": "0"})
    assert ra_deg == pytest.approx(expected)
    assert dec_deg == pytest.approx(0.0)


def alternate_header(**updates):
    header = {
        "CTYPE1A": "RA---TAN", "CTYPE2A": "DEC--TAN",
        "CDELT1A": -1 / 3600, "CDELT2A": 2 / 3600,
    }
    header.update(updates)
    return header


@pytest.mark.parametrize("unit,cdelt1,cdelt2", [
    (None, -1 / 3600, 2 / 3600),
    ("deg", -1 / 3600, 2 / 3600),
    ("arcsec", -1.0, 2.0),
    ("rad", -math.pi / 648000, math.pi / 324000),
])
def test_alternate_celestial_scale_uses_axis_units(unit, cdelt1, cdelt2):
    header = alternate_header(CDELT1A=cdelt1, CDELT2A=cdelt2)
    if unit is not None:
        header.update(CUNIT1A=unit, CUNIT2A=unit)
    assert estimate_pixel_scale_arcsec_per_pix(header) == pytest.approx(1.5)


def test_alternate_scale_uses_unequal_cdelt_before_pc_rotation():
    header = alternate_header(PC1_1A=.6, PC1_2A=-.8, PC2_1A=.8, PC2_2A=.6)
    # The pixel-axis column lengths of diag(-1, 2) @ PC, in arcsec/pixel.
    expected = (math.sqrt(2.92) + math.sqrt(2.08)) / 2
    assert estimate_pixel_scale_arcsec_per_pix(header) == pytest.approx(expected)


def test_alternate_cd_matrix_supplies_scale_without_cdelt():
    header = {
        "CTYPE1A": "RA---TAN", "CTYPE2A": "DEC--TAN",
        "CUNIT1A": "arcsec", "CUNIT2A": "arcsec",
        "CD1_1A": -.6, "CD1_2A": .8, "CD2_1A": 1.6, "CD2_2A": 1.2,
    }
    assert estimate_pixel_scale_arcsec_per_pix(header) == pytest.approx(
        (math.sqrt(2.92) + math.sqrt(2.08)) / 2)


@pytest.mark.parametrize("header", [
    {"CDELT1A": 1.0, "CDELT2A": 1.0},
    {"CTYPE1A": "LINEAR", "CTYPE2A": "LINEAR", "CUNIT1A": "deg",
     "CUNIT2A": "deg", "CDELT1A": 1.0, "CDELT2A": 1.0},
    {"CTYPE1A": "LINEAR", "CTYPE2A": "LINEAR", "CUNIT1A": "m",
     "CUNIT2A": "m", "CDELT1A": 1.0, "CDELT2A": 1.0},
    alternate_header(CUNIT1A="m", CUNIT2A="m"),
    alternate_header(CDELT1A="bad"),
    alternate_header(CDELT1A=float("inf")),
    alternate_header(CDELT1A=float("nan")),
    alternate_header(CDELT1A=0.0),
    alternate_header(PC1_1A=1., PC1_2A=1., PC2_1A=1., PC2_2A=1.),
    {"CTYPE1A": "RA---TAN", "CTYPE2A": "DEC--TAN"},
    {"CTYPE1A": "RA---TAN", "CTYPE2A": "DEC--TAN", "CDELT1A": 1 / 3600},
])
def test_invalid_or_noncelestial_alternate_scale_is_not_a_hint(header):
    assert estimate_pixel_scale_arcsec_per_pix(header) is None


@pytest.mark.parametrize("keywords,expected", [
    ({"PIXSCALE": .7, "SECPIX": .8}, .7),
    ({"SECPIX": .8}, .8),
    ({"PIXSCALE1": .5, "PIXSCALE2": .9}, .7),
    ({"SECPIX1": .5, "SECPIX2": .9}, .7),
])
def test_arcsecond_keywords_keep_precedence_over_alternate_wcs(keywords, expected):
    header = alternate_header(**keywords)
    assert estimate_pixel_scale_arcsec_per_pix(header) == pytest.approx(expected)


def test_primary_wcs_and_optics_do_not_enable_a_new_scale_path():
    header = {
        "CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN",
        "CDELT1": -1 / 3600, "CDELT2": 1 / 3600,
        "XPIXSZ": 10.0, "YPIXSZ": 10.0, "FOCALLEN": 2000.0,
    }
    assert estimate_pixel_scale_arcsec_per_pix(header) is None
