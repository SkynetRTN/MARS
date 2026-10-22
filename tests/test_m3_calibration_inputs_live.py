"""Live counterpart of ``test_m3_calibration_inputs.py``'s integer-id case.

SkyMapper (int32), UCAC (int64), SDSS (uint64) and PanSTARRS (int64) return
integer row ids, which field calibration's ``CatalogSource`` revalidation
rejected, so every live calibration against them failed with a Pydantic
validation error. These run that path against the live providers. They assert
only that a solve is reached, not its value: which band each catalog
substitutes for B is an M2 question (catalog magnitudes and filters), and
SkyMapper's and UCAC's B zero points are not validated here.

Never run by default: they require ``MARS_TEST_NETWORK=1`` (and ``-m network``).
"""

from __future__ import annotations

import math

import pytest

pytestmark = [
    pytest.mark.network,
    pytest.mark.filterwarnings("ignore:Pydantic serializer warnings:UserWarning"),
]


@pytest.mark.parametrize("catalog", ["SkyMapper", "UCAC"])
def test_live_integer_id_catalogs_reach_a_solve(catalog):
    from algorithms.query.registry import CATALOGS
    from tools.optical import resolve_optical_frame
    from tools.photometry import calibrate_zeropoint

    rows = CATALOGS[catalog].query_circ(13.4246, -43.0191, 2.0)
    assert rows and not isinstance(rows[0].id, str), f"{catalog} no longer returns integer ids"

    frame = resolve_optical_frame("ngc5128_galaxy_b_001")
    result = calibrate_zeropoint(frame.path, catalogs=[catalog])
    assert result.errors == [], result.errors
    assert math.isfinite(result.zero_point)
