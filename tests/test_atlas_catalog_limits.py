"""WCS-01/25 pre-load footprints and chunked UCAC query budgets, offline."""

from types import SimpleNamespace

import numpy as np
import pytest

from algorithms.skylib_lite.astrometry.atlas.catalog import limits, ucac4, ucac5
from algorithms.skylib_lite.astrometry.atlas.config import AtlasConfig
from algorithms.skylib_lite.astrometry.atlas.solve import solver


@pytest.mark.parametrize("radius", [0, -1, float("nan"), float("inf"), 6])
def test_invalid_constructible_radius_is_rejected(radius):
    with pytest.raises(ValueError, match="radius"):
        AtlasConfig(catalog_max_radius_deg=radius)


def test_radius_and_padding_are_constructible_and_survive_copy():
    from dataclasses import replace
    config = AtlasConfig(catalog_max_radius_deg=.5, catalog_pad_frac=.25)
    assert replace(config).catalog_max_radius_deg == .5
    assert config.catalog_pad_frac == .25
    assert AtlasConfig(catalog_max_radius_deg=None).catalog_max_radius_deg == 2


@pytest.mark.parametrize("padding", [-1, float("nan"), float("inf"), 3])
def test_invalid_padding_is_rejected(padding):
    with pytest.raises(ValueError, match="padding"):
        AtlasConfig(catalog_pad_frac=padding)


def test_oversized_blind_footprint_never_loads_a_catalog(monkeypatch, tmp_path):
    monkeypatch.setattr(solver, "extract_sources", lambda *a, **k: SimpleNamespace(
        xy=np.empty((0, 2)), shape=(4096, 4096)))
    def forbidden(*args):
        pytest.fail("oversized footprint reached catalog initialization")
    monkeypatch.setattr(solver, "_catalog_index", forbidden)
    with pytest.raises(ValueError, match="footprint"):
        solver.solve(tmp_path / "unused.fits", AtlasConfig(), ra0_deg=180, dec0_deg=0,
                     scale_range_arcsec_per_pix=(.1, 60), fov_guess_deg=(68, 68))


@pytest.fixture(params=["ucac4", "ucac5"])
def catalog(request, monkeypatch, tmp_path):
    if request.param == "ucac4":
        index = ucac4.Ucac4Index(tmp_path)
        rows = np.zeros(6, dtype=ucac4._UCAC4_DTYPE)
        rows["ra"] = np.arange(1, 7) * 3_600_000
        monkeypatch.setattr(index, "_load_zone", lambda _: rows)
        monkeypatch.setattr(ucac4, "_zones_for_dec_range", lambda *a: [90])
    else:
        index = ucac5.Ucac5Index.__new__(ucac5.Ucac5Index)
        rows = np.zeros(6, dtype=ucac5._UCAC5_U5Z_DTYPE)
        rows["ra_mas"] = np.arange(1, 7) * 3_600_000
        monkeypatch.setattr(index, "_load_zone", lambda _: rows)
        monkeypatch.setattr(index, "spans_for_radec_box", lambda *a: [ucac5.Ucac5Span(451, 0, 6)])
    return index


def test_chunked_conversion_preserves_order_and_thinning(catalog, monkeypatch):
    module = ucac4 if isinstance(catalog, ucac4.Ucac4Index) else ucac5
    monkeypatch.setattr(module, "QUERY_CHUNK_ROWS", 2)
    result = catalog.query_box(0, 7, -1, 1, thin=2)
    # Pin the original milliarcsecond conversion, including its rounding.
    expected = np.array([1., 3., 5.]) * 3_600_000 * module._MAS_TO_DEG
    np.testing.assert_array_equal(result.ra_deg, expected)
    np.testing.assert_array_equal(result.dec_deg, [0., 0., 0.])


def test_returned_row_budget_fails_instead_of_truncating(catalog, monkeypatch):
    monkeypatch.setattr(limits, "MAX_QUERY_ROWS", 3)
    with pytest.raises(ValueError, match="budget"):
        catalog.query_box(0, 7, -1, 1)


def test_candidate_work_budget_is_checked_before_conversion(catalog, monkeypatch):
    monkeypatch.setattr(limits, "MAX_QUERY_CANDIDATES", 5)
    with pytest.raises(ValueError, match="budget"):
        catalog.query_box(0, 7, -1, 1)


def test_nonfinite_query_is_rejected(catalog):
    with pytest.raises(ValueError, match="finite"):
        catalog.query_box(float("nan"), 7, -1, 1)


def test_followup_footprint_is_checked_before_catalog_initialization(monkeypatch):
    from algorithms.wcs import wcs
    monkeypatch.setattr(wcs, "get_catalog_spec", lambda *a: pytest.fail("catalog loaded"))
    with pytest.raises(ValueError, match="footprint"):
        wcs._load_atlas_catalog_sources(
            AtlasConfig(), ra0_deg=180, dec0_deg=0, width=4096,
            height=4096, max_scale=60, file_id=None)


@pytest.mark.parametrize("line", ["-1 1 451 1\n", "0 4000001 451 1\n", "x" * 257])
def test_ucac5_invalid_index_is_bounded(tmp_path, line):
    (tmp_path / "u5index.asc").write_text(line, encoding="ascii")
    with pytest.raises(ValueError, match="budget"):
        ucac5.Ucac5Index(tmp_path)


def test_ucac5_ordinary_index_preserves_spans(tmp_path):
    (tmp_path / "u5index.asc").write_text("0 21 451 1 0.0\n21 18 451 2\n", encoding="ascii")
    index = ucac5.Ucac5Index(tmp_path)
    assert index.get_start_count(451, 1) == (0, 21)
    assert index.get_start_count(451, 2) == (21, 18)


@pytest.mark.parametrize("reader", [ucac4.Ucac4Index, ucac5.Ucac5Index])
def test_oversized_zone_is_rejected_before_memmap(reader, monkeypatch, tmp_path):
    class FakePath:
        def exists(self):
            return True
        def stat(self):
            return SimpleNamespace(st_size=4_000_001 * (80 if reader == ucac4.Ucac4Index else 52))
    index = reader.__new__(reader)
    index._cache = {}
    monkeypatch.setattr(index, "_zone_path" if reader == ucac4.Ucac4Index else "zone_path", lambda _: FakePath())
    with pytest.raises(ValueError, match="budget"):
        index._load_zone(90)
