"""Opt-in transport checks for the M2 coverage contract; no committed downloads."""

import pytest
from astropy.wcs import WCS

from algorithms.query.coverage import collect_query_notices
from algorithms.query.registry import CATALOGS
from algorithms.query.runner import query_catalogs


pytestmark = pytest.mark.network


@pytest.mark.parametrize("ra,dec", [(359.95, 89.95), (201.369, -43.0191)])
def test_live_polar_and_ordinary_detector_footprints_return_on_image_native_sources(ra, dec):
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [ra, dec]
    wcs.wcs.crpix = [48, 24]
    wcs.wcs.cdelt = [-.002, .002]
    wcs.array_shape = (48, 96)
    with collect_query_notices() as notices:
        rows = query_catalogs(["2MASS"], wcs=wcs, image_filter="J")
    assert rows
    assert all(0 <= row.x < 96 and 0 <= row.y < 48 for row in rows)
    assert all(row.catalog_name == "2MASS" and "J" in row.mags for row in rows)
    assert "catalog_coverage_unverified" not in {notice.code for notice in notices}


def test_live_small_row_limit_is_reported_as_possibly_brightness_biased_coverage():
    with collect_query_notices() as notices:
        rows = CATALOGS["2MASS"].query_circ(13.4246, -43.0191, 6, limit=3)
    assert len(rows) == 3
    assert "catalog_rows_capped" in {notice.code for notice in notices}
    assert "bright" in notices[0].message.lower()
