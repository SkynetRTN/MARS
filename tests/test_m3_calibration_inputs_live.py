"""Live counterpart of ``test_m3_calibration_inputs.py``'s integer-id case.

SkyMapper (int32), UCAC (int64), SDSS (uint64) and PanSTARRS (int64) return
integer row ids, which field calibration's ``CatalogSource`` revalidation
rejected. These check real provider IDs through the same normalization boundary.
M2 rejects B-band calibration against SkyMapper or UCAC because neither has a
B band or a B transform; the former successful wrong-band solves are not kept.

Never run by default: they require ``MARS_TEST_NETWORK=1`` (and ``-m network``).
"""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.network,
    pytest.mark.filterwarnings("ignore:Pydantic serializer warnings:UserWarning"),
]


@pytest.mark.parametrize("catalog", ["SkyMapper", "UCAC"])
def test_live_integer_ids_normalize_and_unsupported_b_is_refused(catalog):
    from algorithms.fieldcal.field_cal import _normalize_catalog_sources
    from algorithms.query.registry import CATALOGS
    from tools.optical import resolve_optical_frame
    from tools.photometry import calibrate_zeropoint

    rows = CATALOGS[catalog].query_circ(13.4246, -43.0191, 2.0)
    assert rows and not isinstance(rows[0].id, str), f"{catalog} no longer returns integer ids"

    normalized = _normalize_catalog_sources(rows, file_id=None)
    assert [row.id for row in normalized] == [str(int(row.id)) for row in rows]
    assert all(row.mags for row in normalized)

    frame = resolve_optical_frame("ngc5128_galaxy_b_001")
    result = calibrate_zeropoint(frame.path, catalogs=[catalog])
    assert [error.code for error in result.errors] == ["unsupported_filter"]
    assert result.zero_point is None
