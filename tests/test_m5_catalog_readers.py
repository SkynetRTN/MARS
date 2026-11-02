"""Correctness regressions for M5 catalog intervals and UCAC5 metadata.

UCAC4 fixtures exercise only the reader's existing logical record dtype. They
do not validate the disputed native UCAC4 binary layout. UCAC5 records are
packed independently from the authors' readmeU5.txt v2.0, section 4c:
https://vizier.cfa.harvard.edu/ftp/cats/I/340/readmeU5.txt
"""

import struct

import numpy as np
import pytest

from algorithms.skylib_lite.astrometry.atlas.catalog import ucac4, ucac5


@pytest.fixture
def synthetic_ucac4(tmp_path):
    records = np.zeros(4, dtype=ucac4._UCAC4_DTYPE)
    records["ra"] = np.array([0, 50, 180, 350]) * 3_600_000
    records.tofile(tmp_path / "Z090.UC4")
    return ucac4.Ucac4Index(tmp_path)


@pytest.mark.parametrize("lower,upper", [
    (0, 360), (10, 370), (-200, 200), (400, 0), (-720, 720),
])
def test_ucac4_full_turn_and_larger_spans_keep_every_ra(
    synthetic_ucac4, lower, upper,
):
    result = synthetic_ucac4.query_box(lower, upper, -.1, .1)
    np.testing.assert_allclose(result.ra_deg, [0, 50, 180, 350])


@pytest.mark.parametrize("lower,upper,expected", [
    (350, 10, [350, 0]), (-10, 10, [350, 0]), (50, 50, [50]),
])
def test_ucac4_seam_and_zero_width_intervals_keep_their_order(
    synthetic_ucac4, lower, upper, expected,
):
    np.testing.assert_allclose(
        synthetic_ucac4.query_box(lower, upper, -.1, .1).ra_deg, expected,
    )


def _write_ucac5(tmp_path, records, *, zone=451, bin_=41):
    """Pack 52-byte records in one native RA bin without using MARS's dtype."""
    payload = bytearray()
    for row, (ra, dec, pm_ra, pm_dec, gmag) in enumerate(records):
        # Signed Fortran INTEGER*2 components are 0.1 mas/yr; G is mmag.
        payload.extend(struct.pack(
            "<qii2h2bhiihhhhhhhh", row + 1,
            round(ra * 3_600_000), round(dec * 3_600_000), 5, 6,
            2, 4, 3500, round(ra * 3_600_000), round(dec * 3_600_000),
            pm_ra, pm_dec, 11, 12, gmag, 16000, 15500, 14000,
        ))
        # The final two INTEGER*2 columns contain H and K magnitudes.
        payload.extend(struct.pack("<hh", 13000, 12000))
    (tmp_path / f"z{zone:03d}").write_bytes(payload)
    (tmp_path / "u5index.asc").write_text(
        f"0 {len(records)} {zone} {bin_} 0.2\n", encoding="ascii",
    )
    return ucac5.Ucac5Index(tmp_path)


def test_ucac5_decodes_native_52_byte_metadata_without_losing_row_alignment(
    tmp_path, monkeypatch,
):
    # Literal expected values catch wrong offsets, unsigned reads and units.
    index = _write_ucac5(tmp_path, [
        (10.01, .01, -1234, 567, 14321),
        (10.02, .15, 300, -400, 12000),
        (10.03, .03, 0, 0, 18543),
        (10.04, .04, 32767, -32768, 3240),
    ])
    monkeypatch.setattr(ucac5, "QUERY_CHUNK_ROWS", 2)
    result = index.query_box(10, 10.2, 0, .1)
    np.testing.assert_allclose(result.ra_deg, [10.01, 10.03, 10.04])
    np.testing.assert_allclose(result.dec_deg, [.01, .03, .04])
    assert result.epoch_jyear == 2015.0
    np.testing.assert_allclose(result.mag, [14.321, 18.543, 3.240])
    np.testing.assert_allclose(
        result.pm_ra_cosdec_mas_per_year, [-123.4, 0, 3276.7],
    )
    np.testing.assert_allclose(result.pm_dec_mas_per_year, [56.7, 0, -3276.8])


def test_ucac5_metadata_follows_original_thinning_before_filtering(tmp_path, monkeypatch):
    index = _write_ucac5(tmp_path, [
        (10.01, .01, -100, 200, 14000),
        (10.02, .02, -300, 400, 15000),
        (10.03, .03, -500, 600, 16000),
        (10.04, .04, -700, 800, 17000),
    ])
    monkeypatch.setattr(ucac5, "QUERY_CHUNK_ROWS", 1)
    result = index.query_box(10, 10.2, 0, .1, thin=2)
    np.testing.assert_allclose(result.ra_deg, [10.01, 10.03])
    np.testing.assert_allclose(result.mag, [14, 16])
    np.testing.assert_allclose(result.pm_ra_cosdec_mas_per_year, [-10, -50])
    np.testing.assert_allclose(result.pm_dec_mas_per_year, [20, 60])


@pytest.mark.parametrize("ra_min,ra_max,dec_min,dec_max", [
    (20, 21, 0, .1), (10, 10.2, .1, .15),
])
def test_ucac5_empty_queries_return_empty_metadata_arrays(
    tmp_path, ra_min, ra_max, dec_min, dec_max,
):
    index = _write_ucac5(tmp_path, [(10.01, .01, 0, 0, 15000)])
    result = index.query_box(ra_min, ra_max, dec_min, dec_max)
    assert result.ra_deg.shape == result.dec_deg.shape == (0,)
    assert result.mag.shape == (0,)
    assert result.pm_ra_cosdec_mas_per_year.shape == (0,)
    assert result.pm_dec_mas_per_year.shape == (0,)
    assert result.epoch_jyear == 2015.0


def test_ucac5_declares_conservative_epoch_motion_query_bound(tmp_path):
    index = _write_ucac5(tmp_path, [(10.01, .01, -32768, -32768, 15000)])
    result = index.query_box(10, 10.2, 0, .1)
    speed = np.hypot(result.pm_ra_cosdec_mas_per_year, result.pm_dec_mas_per_year)[0]
    assert index.epoch_jyear == result.epoch_jyear
    assert index.max_pm_mas_per_year >= speed
    assert index.max_pm_mas_per_year == pytest.approx(4634.095001184158)


def test_ucac5_two_array_result_construction_remains_supported():
    result = ucac5.Ucac5QueryResult(np.array([10.]), np.array([0.]))
    assert result.mag is None
    assert result.pm_ra_cosdec_mas_per_year is None
    assert result.pm_dec_mas_per_year is None
    assert result.epoch_jyear == 2015.0


@pytest.mark.parametrize("lo,hi", [(0., 360.), (10., 370.), (-200., 200.)])
def test_ucac5_full_turn_uses_real_spans_without_duplicate_records(tmp_path, lo, hi):
    index = _write_ucac5(tmp_path, [(.01, 89.99, 100, 200, 12000),
                                  (.02, 89.99, 300, 400, 14000)], zone=900, bin_=1)
    result = index.query_box(lo, hi, 89.98, 90.)
    np.testing.assert_allclose(result.ra_deg, [.01, .02])
    np.testing.assert_allclose(result.mag, [12., 14.])
    assert index.spans_for_radec_box(lo, hi, 89.98, 90.) == [ucac5.Ucac5Span(900, 0, 2)]
