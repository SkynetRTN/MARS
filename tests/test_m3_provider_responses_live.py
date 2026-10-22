"""Live provider-response contracts (M3, "Provider response changes").

Each test checks that a live response still has the columns its mapping reads,
and that the mapping yields populated, finite results -- the evidence the
offline ``test_m3_provider_responses.py`` stands in for. Never run by default:
``MARS_TEST_NETWORK=1`` and ``-m network``. The ADS test also needs
``ADS_DEV_KEY`` and skips without it.
"""

from __future__ import annotations

import math
import os

import pytest

pytestmark = [
    pytest.mark.network,
    pytest.mark.filterwarnings("ignore:Pydantic serializer warnings:UserWarning"),
]

NGC5128 = (13.4246, -43.0191)
STRIPE82 = (12.0, 0.5)

#: catalog -> (ra_hours, dec_degs, radius_arcmin, bands every source should have)
FIELDS = {
    "APASS": (*NGC5128, 3.0, {"B", "V"}),
    "SkyMapper": (*NGC5128, 3.0, set()),
    "UCAC": (*NGC5128, 3.0, {"Open"}),
    "2MASS": (*NGC5128, 2.0, {"J", "H", "K"}),
    "USNO": (*NGC5128, 2.0, set()),
    "Tycho": (*NGC5128, 30.0, {"B", "V"}),
    "SDSS": (*STRIPE82, 2.0, {"u", "g", "r", "i", "z"}),
    "PanSTARRS": (*STRIPE82, 2.0, set()),
    "Landolt": (6.8667, -0.33, 30.0, {"V"}),      # SA 98
    "Stetson": (21.4997, 12.167, 2.0, {"V"}),     # M15: a globular-cluster table
}


@pytest.mark.parametrize("name", sorted(FIELDS))
def test_live_catalog_mapping_is_populated(name):
    from algorithms.query.registry import CATALOGS

    ra, dec, radius, bands = FIELDS[name]
    sources = CATALOGS[name].query_circ(ra, dec, radius)  # ProviderResponseError if unusable
    assert sources, f"{name} returned no rows over a field it covers"
    assert all(math.isfinite(s.ra_hours) and math.isfinite(s.dec_degs) for s in sources)
    assert all(s.mags for s in sources)
    for band in bands:
        assert all(band in s.mags for s in sources), f"{name} rows lack {band}"


def test_live_2mass_ids_survive_the_column_rename():
    from algorithms.query.registry import CATALOGS

    sources = CATALOGS["2MASS"].query_circ(*NGC5128, 2.0)
    assert sources and all(s.id for s in sources)


def test_live_landolt_derives_ubvri():
    from algorithms.query.registry import CATALOGS

    sources = CATALOGS["Landolt"].query_circ(6.8667, -0.33, 30.0)
    assert sources
    derived = [s for s in sources if {"U", "B", "V", "R", "I"} <= set(s.mags)]
    assert len(derived) >= len(sources) - 2  # a zero colour can leave one row short


def test_live_simbad_columns_and_mapping():
    from algorithms.query.simbad import resolve_simbad

    (m31,) = [t for t in resolve_simbad("M31", strict=True) if t.object_name.startswith("M  31")]
    assert m31.ra_deg == pytest.approx(10.6847, abs=1e-3)
    assert m31.object_type


def test_live_gaia_and_literature_columns_and_values():
    from astropy.table import Table

    from tools.hr_diagram import (
        _GAIA_COLUMNS, _LITERATURE_COLUMNS, crossmatch_gaia_by_position, get_literature_cluster_params,
    )
    from tools.vizier import search_vizier

    literature = get_literature_cluster_params("M67")
    assert literature.status == "ok", literature.errors
    params = literature.preview[0]
    assert params["log_age"] == pytest.approx(9.63, abs=0.05)
    rows = Table.read(search_vizier(target="M67", catalog="J/A+A/640/A1/table1", max_catalogs=None).artifacts[0].path)
    assert set(_LITERATURE_COLUMNS) <= set(rows.colnames)

    gaia = search_vizier(ra_hours=8.85, dec_degs=11.81, radius_arcmin=2, catalog="I/355/gaiadr3",
                         column_filters={"Gmag": "<14"}, max_catalogs=None)
    assert set(_GAIA_COLUMNS) <= set(Table.read(gaia.artifacts[0].path).colnames)
    fetched = crossmatch_gaia_by_position("M67", radius_arcmin=3, mag_limit=14)
    assert fetched.status == "ok" and fetched.count > 10


def test_live_radio_catalogs_are_all_positionable_and_3c_matches():
    import pandas as pd
    from astropy.table import Table

    from algorithms.radio.matching import UnreadablePositions, match_sources_to_catalog
    from tools.vizier import search_vizier

    result = search_vizier(ra_hours=24.4221 / 15, dec_degs=33.1598, radius_arcmin=1.0,
                           category="radio", max_catalogs=40)
    assert result.artifacts
    tables = {a.path.split("/")[-1]: Table.read(a.path).to_pandas() for a in result.artifacts}
    source = pd.DataFrame({"ra_deg": [24.4221], "dec_deg": [33.1598]})
    unreadable = []
    for name, df in tables.items():
        try:
            match_sources_to_catalog(source, df, radius_arcsec=90, unreadable_raises=True)
        except UnreadablePositions:
            unreadable.append(name)
    assert unreadable == []  # was 17 of 40, B1950-only catalogs among them
    three_c = next(df for name, df in tables.items() if name.startswith("VIII_1A_3c"))
    # 3C positions are 1950s-era and coarse: 3C 48 sits ~40" from NED's.
    assert match_sources_to_catalog(source, three_c, radius_arcsec=90)


def test_live_ned_photometry_columns_and_spectrum():
    from tools.radio_sources import analyze_source_spectrum

    result = analyze_source_spectrum(name="3C 48")
    assert result.status == "ok", result.errors


@pytest.mark.skipif(not os.environ.get("ADS_DEV_KEY"), reason="needs ADS_DEV_KEY to query ADS")
def test_live_ads_accepts_grouped_abs_and_object_clauses():
    from tools.ads import search_ads

    result = search_ads(abstract="millisecond pulsar", object_name="PSR B1937+21", max_results=5)
    assert result.status in ("ok", "not_found"), result.errors
    assert not result.errors
