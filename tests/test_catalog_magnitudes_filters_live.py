"""M2 live values: fresh queries -> native columns -> unchanged transforms.

Run explicitly with MARS_TEST_NETWORK=1. Transport failures and empty fields
fail these tests; they are not converted to skips. The observer records the
real response passed to the real mapper, avoiding a second query or a match
against a different release. Expectations below do not call production routing,
mapping or expression-evaluation helpers.
"""

import math

import numpy as np
import pytest

from algorithms.fieldcal.ref_mag import resolve_ref_mag_for_filter
from algorithms.query.selection import catalog_supports_filter
from tools.catalogs import resolve_reference_band

pytestmark = pytest.mark.network

FIELDS = {
    "APASS": (13.4246, -43.0191, 3.0),
    "SkyMapper": (13.4246, -43.0191, 3.0),
    "UCAC": (13.4246, -43.0191, 3.0),
    "2MASS": (8.85, 11.8, 5.0),
    "USNO": (13.4246, -43.0191, 2.0),
    "Tycho": (13.4246, -43.0191, 30.0),
    "SDSS": (12.0, 0.5, 2.0),
    "PanSTARRS": (12.0, 0.5, 2.0),
    "Landolt": (6.8667, -0.33, 30.0),
    "Stetson": (21.4997, 12.167, 2.0),
}

# Independent provider-column contract; do not derive this from Catalog.mags.
COLUMNS = {
    "APASS": {"B": "Bmag", "V": "Vmag", "gprime": "g'mag", "rprime": "r'mag", "iprime": "i'mag"},
    "SkyMapper": {band: f"{band}PSF" for band in "uvgriz"},
    "UCAC": {"Open": "f.mag", "G": "Gmag", "Rphot": "Rmag", "J": "Jmag", "H": "Hmag", "K": "Kmag"},
    "2MASS": {"J": "Jmag", "H": "Hmag", "K": "Kmag", "Bopt": "Bmag", "Ropt": "Rmag"},
    "USNO": {"B1": "B1mag", "B2": "B2mag", "R1": "R1mag", "R2": "R2mag"},
    "Tycho": {"BT": "BTmag", "VT": "VTmag"},
    "SDSS": {band: band for band in "ugriz"},
    "PanSTARRS": {band: f"{band}mag" for band in "grizy"},
    "Landolt": {"V": "Vmag", "B_V": "B-V", "U_B": "U-B", "V_R": "V-R", "R_I": "R-I", "V_I": "V-I"},
    "Stetson": {band: f"{band}mag" for band in "UBVRI"},
}


def number(row, column):
    for spelling in (column, column.replace("'", "_")):
        if spelling in row:
            value = row[spelling]
            if not np.ma.is_masked(value) and value is not None:
                value = float(value)
                if math.isfinite(value) and value < 99:
                    return value
    return None


def position(name, row):
    if name in {"Landolt", "Stetson"}:
        h, m, s = map(float, row["RAJ2000"].split())
        d, dm, ds = map(float, row["DEJ2000"].split())
        return h + m / 60 + s / 3600, math.copysign(abs(d) + dm / 60 + ds / 3600, d)
    ra, dec = {"SkyMapper": ("RAICRS", "DEICRS"), "Tycho": ("RAmdeg", "DEmdeg"),
               "SDSS": ("ra", "dec")}.get(name, ("RAJ2000", "DEJ2000"))
    return float(row[ra]) / 15, float(row[dec])


def expected_references(name, values):
    """Independent arithmetic from retained upstream formulas, no production eval."""
    result = dict(values)
    if name == "USNO":
        for band in ("B", "R"):
            epochs = [values[key] for key in (band + "1", band + "2") if key in values]
            if epochs:
                result[band + "phot"] = sum(epochs) / len(epochs)
    if name == "Landolt" and {"V", "B_V", "U_B", "V_R", "R_I", "V_I"} <= values.keys():
        v = values["V"]
        result.update(B=v + values["B_V"], U=v + values["B_V"] + values["U_B"],
                      R=v - values["V_R"],
                      I=(v - values["V_R"] - values["R_I"] + v - values["V_I"]) / 2)
    if name == "APASS" and {"rprime", "iprime"} <= values.keys():
        r, i = values["rprime"], values["iprime"]
        result.update(R=r - .2936 * (r - i) - .1439, I=i - .3136 * (r - i) - .3539)
        for alias in ("Red", "Halpha", "H_alpha", "R+Red", "R,Red", "Red+R", "Red,R"):
            result[alias] = result["R"]
    if name in {"APASS", "Landolt", "Stetson"} and "V" in values:
        for alias in ("Open", "Clear", "Lum"):
            result[alias] = values["V"]
    if name == "2MASS" and {"J", "K"} <= values.keys():
        j, c = values["J"], values["J"] - values["K"]
        for band, (a, b, d, e) in {"B": (.1980, 5.2150, -2.7785, 1.7495),
                                   "V": (.1496, 3.5143, -2.3250, 1.4688),
                                   "R": (.1045, 2.5105, -1.7849, 1.1230),
                                   "I": (.0724, 1.2816, -.4866, .2963)}.items():
            result[band] = j + a + b*c + d*c*c + e*c*c*c
    if name == "SkyMapper":
        for native, offset in {"u": -.069, "g": .088, "r": -.006, "i": .001, "z": -.005}.items():
            if native in values:
                result[native + "prime"] = values[native] + offset
    if name == "SDSS" and set("ugriz") <= values.keys():
        u, g, r, i, z = (values[b] for b in "ugriz")
        result.update(uprime=u, gprime=g - .06*(g-r-.53), rprime=r - .035*(r-i-.21),
                      iprime=i - .041*(r-i-.21), zprime=z + .03*(i-z-.09),
                      U=g + .39*(g-r) + .78*(u-g) - .67,
                      B=u - .8116*(u-g) + .1313, V=g - .5784*(g-r) - .0038,
                      R=r - .2936*(r-i) - .1439, I=i - .378*(i-z) - .3974)
    if name == "PanSTARRS" and set("griz") <= values.keys():
        g, r, i, z = (values[b] for b in "griz")
        c = g - r
        gs, rs = g + .013 + .145*c + .019*c*c, r - .001 + .004*c + .007*c*c
        ins, zs = i - .005 + .011*c + .010*c*c, z + .013 - .039*c - .012*c*c
        result.update(gprime=.94*gs + .06*rs + .0318, rprime=.965*rs + .035*ins + .00735,
                      iprime=1.041*ins - .041*rs + .00861, zprime=.97*zs + .03*ins - .0027)
    for prime in ("g", "r", "i", "z"):
        if prime + "prime" in result:
            result[prime + "'"] = result[prime + "prime"]
            result[prime + "p"] = result[prime + "prime"]
    if name in {"APASS", "SDSS", "PanSTARRS"}:
        for alias in ("OIII", "Hbeta", "H_beta"):
            if "gprime" in result:
                result[alias] = result["gprime"]
        if "rprime" in result:
            result["SII"] = result["rprime"]
            if name != "APASS":
                result["Halpha"] = result["H_alpha"] = result["rprime"]
    if name == "APASS":
        for alias in ("Green", "Green+V", "Green,V", "V+Green", "V,Green"):
            if "V" in result:
                result[alias] = result["V"]
        for alias in ("Blue", "Blue+B", "Blue,B", "B+Blue", "B,Blue"):
            if "B" in result:
                result[alias] = result["B"]
    return result


@pytest.mark.parametrize("name", sorted(FIELDS))
def test_live_native_magnitudes_and_resolved_filters_match_provider_values(name, monkeypatch, record_property):
    from algorithms.query.registry import CATALOGS

    catalog = CATALOGS[name]
    raw = []
    original = catalog.table_to_sources

    def observe(table):
        raw.extend(dict(zip(table.colnames, row)) for row in table)
        return original(table)

    monkeypatch.setattr(catalog, "table_to_sources", observe)
    monkeypatch.setattr(catalog, "cache", False)
    constraints = {"Nopt": ">0"} if name == "2MASS" else None
    sources = catalog.query_circ(*FIELDS[name], limit=40, constraints=constraints)
    assert sources and raw, f"{name} returned no usable rows"
    checks = 0
    checked_filters = set()
    for source in sources:
        row = next(row for row in raw if np.allclose(position(name, row),
                   (source.ra_hours, source.dec_degs), rtol=0, atol=1e-8, equal_nan=False))
        values = {band: value for band, column in COLUMNS[name].items()
                  if (value := number(row, column)) is not None}
        for band, value in values.items():
            assert source.mags[band].value == pytest.approx(value, rel=0, abs=1e-12)
        for image_filter, expected in expected_references(name, values).items():
            report = resolve_reference_band(name, image_filter)
            # Only literal supported routes are tested; no preferred-band fallback.
            assert report.supported, (name, image_filter, report)
            assert catalog_supports_filter(name, image_filter), (name, image_filter)
            actual, _ = resolve_ref_mag_for_filter(
                catalog_name=source.catalog_name, image_filter=image_filter, cs_mags=source.mags,
                allow_preferred_band_fallback=False,
            )
            assert actual == pytest.approx(expected, rel=0, abs=1e-9), (name, source.id, image_filter)
            checks += 1
            checked_filters.add(image_filter)
    required = {
        "APASS": {"B", "V", "R", "I", "Halpha", "H_alpha", "g'", "r'", "i'"},
        "2MASS": {"J", "H", "K", "Bopt", "Ropt", "B", "V", "R", "I"},
        "SDSS": {"U", "B", "V", "R", "I", "gprime", "rprime", "iprime", "zprime"},
        "PanSTARRS": {"gprime", "rprime", "iprime", "zprime"},
        "SkyMapper": {"uprime", "gprime", "rprime", "iprime", "zprime"},
        "Landolt": {"U", "B", "V", "R", "I", "B_V"},
        "Stetson": {"U", "B", "V", "R", "I", "Open"},
        "Tycho": {"BT", "VT"}, "UCAC": {"Open", "G", "Rphot", "J", "H", "K"},
        "USNO": {"Bphot", "Rphot"},
    }[name]
    assert required <= checked_filters, f"{name}: no live values checked for {required - checked_filters}"
    assert checks >= len(sources)
    record_property("catalog", name)
    record_property("raw_rows", len(raw))
    record_property("mapped_rows", len(sources))
    record_property("value_checks", checks)
    record_property("filters", ",".join(sorted(checked_filters)))
