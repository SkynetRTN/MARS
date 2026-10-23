"""Live counterparts of ``test_m3_catalog_lookup_failures.py``.

The offline file stubs every transport. These run the same three repairs
against the real services -- SkyServer, SIMBAD, VizieR (APASS) and CASDA --
so the stubbed response shapes are checked against what the providers
actually return. Never run by default: they require ``MARS_TEST_NETWORK=1``
(and ``-m network`` to select only these).
"""

from __future__ import annotations

import pytest
from astropy.io import fits

pytestmark = pytest.mark.network


def test_live_sdss_objid_lookup_round_trips_a_region_row():
    from algorithms.query.registry import CATALOGS

    sdss = CATALOGS["SDSS"]
    # A Stripe 82 field: SDSS photometry is dense and quality-flagged here.
    region = sdss.query_circ(12.0, 0.5, 2.0, limit=5)
    assert len(region) >= 2, "SkyServer returned too few rows to test a named lookup"

    wanted = {str(row.id): row for row in region[:2]}
    found = sdss.query_objects(list(wanted) + ["1"])  # objID 1 does not exist

    assert sorted(str(row.id) for row in found) == sorted(wanted)
    for row in found:
        original = wanted[str(row.id)]
        assert row.ra_hours == pytest.approx(original.ra_hours)
        assert row.dec_degs == pytest.approx(original.dec_degs)
        assert row.mags["g"].value == pytest.approx(original.mags["g"].value)


def test_live_sdss_objid_lookup_spans_several_requests():
    """More objIDs than one request carries: every chunk's URL is accepted."""
    from algorithms.query import sdss as sdss_module
    from algorithms.query.registry import CATALOGS

    sdss = CATALOGS["SDSS"]
    region = sdss.query_circ(12.0, 0.5, 6.0, limit=250)
    assert len(region) >= 200, "too few rows to need several requests"
    assert len(list(sdss_module._objid_queries(sdss._columns, [int(row.id) for row in region]))) > 1

    wanted = sorted(str(row.id) for row in region)
    found = sdss.query_objects(wanted)
    assert sorted(str(row.id) for row in found) == wanted


def test_live_simbad_distinguishes_a_match_from_no_match():
    from algorithms.query.simbad import resolve_simbad
    from tools.resolve import resolve_target

    result = resolve_target("M31")
    assert result.status == "ok"
    assert result.preview[0]["ra_deg"] == pytest.approx(10.6847, abs=1e-3)
    assert result.preview[0]["dec_deg"] == pytest.approx(41.2688, abs=1e-3)

    # A reachable SIMBAD with no such object is not_found, not an error, and
    # strict resolution does not raise for it.
    assert resolve_target("zzqx not an object 1234").status == "not_found"
    assert resolve_simbad("zzqx not an object 1234", strict=True) == []


def test_live_casda_resolves_its_target_through_strict_simbad():
    from tools.casda import search_casda

    result = search_casda(target="NGC 5128", radius_arcmin=1.0)
    assert result.errors == []
    assert result.status == "ok" and result.count > 0


def test_live_apass_carries_no_uprime_band():
    """CAT-06's premise against the live provider: APASS DR9 serves no u'."""
    from algorithms.query.registry import CATALOGS

    rows = CATALOGS["APASS"].query_circ(13.4246, -43.0191, 5.0)
    assert rows, "VizieR returned no APASS rows around NGC 5128"
    bands = set().union(*(row.mags for row in rows))
    assert "uprime" not in bands
    assert {"B", "V", "gprime"} <= bands


def test_live_b_band_calibration_is_not_blocked_by_the_filter_check():
    """The supported live path still solves, against Afterglow's value."""
    from tools.optical import resolve_optical_frame
    from tools.photometry import calibrate_zeropoint

    frame = resolve_optical_frame("ngc5128_galaxy_b_001")
    comparison = calibrate_zeropoint(frame.path, catalogs=["APASS"], compare_to="ngc5128_b_002")
    assert comparison.errors == []
    assert abs(comparison.delta_vs_afterglow) < 0.1


def test_live_u_band_calibration_against_apass_fails_by_name(tmp_path):
    from tools.optical import resolve_optical_frame
    from tools.photometry import calibrate_zeropoint

    source = resolve_optical_frame("ngc5128_galaxy_b_001").path
    target = tmp_path / "u_band.fits"
    with fits.open(source) as hdul:
        hdul[0].header["FILTER"] = "U"
        hdul.writeto(target)

    result = calibrate_zeropoint(target, catalogs=["APASS"])
    assert [error.code for error in result.errors] == ["unsupported_filter"]
    assert "uprime" in result.errors[0].message
