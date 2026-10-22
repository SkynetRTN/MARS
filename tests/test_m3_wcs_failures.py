"""M3 WCS setup and I/O failures (``docs/working/master-continuation-plan.md``).

No-hint ATLAS input (WCS-05), textual equinoxes such as ``J2000`` (WCS-22), and
missing binaries, bad catalog roots and a full output disk (WCS-23) must be
distinguishable from a genuine no-solution result -- through the tool, and in
``solve_wcs``'s own result for direct callers. Backends are stubbed; no solver
data is needed.
"""

from __future__ import annotations

import errno
from pathlib import Path

import pytest
from astropy.coordinates import FK4, FK5, ICRS
from astropy.io import fits
from astropy.wcs import WCS

import algorithms.wcs.wcs as wcs_module
from algorithms.skylib_lite.astrometry.types import SolveSolution
from algorithms.wcs.config import SolverSettings
from algorithms.wcs.header_utils import _frame_from_header, guess_icrs_radec_from_header
from tools.wcs import solve_astrometry

ROOT = Path(__file__).resolve().parents[1]
FRAME = ROOT / "data" / "optical" / "m15_globular_lum_000.fits"
POINTING_KEYS = ("OBJRA", "OBJDEC", "TELRA", "TELDEC", "RA", "DEC")
ENOSPC = OSError(errno.ENOSPC, "No space left on device")


def _frame(tmp_path, name, *, pointing=True, **extra) -> Path:
    """The M15 frame without its WCS, with or without its pointing keywords."""
    with fits.open(FRAME) as hdul:
        header, data = hdul[0].header.copy(), hdul[0].data
    for key in list(header.keys()):
        if wcs_module.WCS_REGEX.match(key):
            del header[key]
    if not pointing:
        for key in POINTING_KEYS:
            header.remove(key, ignore_missing=True)
    for key, value in extra.items():
        header[key] = value
    path = tmp_path / f"{name}.fits"
    fits.writeto(path, data, header)
    return path


def _solved_wcs() -> WCS:
    with fits.open(FRAME) as hdul:
        return WCS(hdul[0].header)


@pytest.fixture
def fake_anet(monkeypatch, tmp_path):
    index_path = tmp_path / "indexes"
    index_path.mkdir()
    (index_path / "index-4107.fits").touch()
    monkeypatch.delenv("ATLAS_CATALOG_ROOT", raising=False)
    monkeypatch.setattr("tools.wcs.find_solve_field", lambda: "/fake/solve-field")
    monkeypatch.setattr("algorithms.wcs.wcs.AstrometryNetBackend.is_available", lambda self: True)
    return index_path


@pytest.fixture
def fake_atlas_root(monkeypatch, tmp_path):
    root = tmp_path / "ucac5"
    (root / "u5z").mkdir(parents=True)
    (root / "u5z" / "u5index.asc").touch()
    monkeypatch.setenv("ATLAS_CATALOG_ROOT", str(root))
    monkeypatch.setenv("ATLAS_CATALOG", "ucac5")
    return root


def _direct(path: Path, tmp_path, settings: SolverSettings):
    with fits.open(path) as hdul:
        header, data = hdul[0].header.copy(), hdul[0].data
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    return wcs_module.solve_wcs(header, data, work, solver_settings=settings)


# --- WCS-22: textual equinoxes ------------------------------------------------


@pytest.mark.parametrize("equinox, frame, year", [
    ("J2000", FK5, 2000.0), ("J2000.0", FK5, 2000.0), (" j2000 ", FK5, 2000.0),
    ("B1950", FK4, 1950.0), ("2000", FK5, 2000.0), (2000.0, FK5, 2000.0), (1950, FK4, 1950.0),
])
def test_textual_and_numeric_equinoxes_select_their_frame(equinox, frame, year):
    result = _frame_from_header(fits.Header({"EQUINOX": equinox}))
    assert isinstance(result, frame)
    assert result.equinox.jyear == pytest.approx(year) or result.equinox.byear == pytest.approx(year)


@pytest.mark.parametrize("equinox", ["unknown", "", "JNOW"])
def test_an_unreadable_equinox_falls_back_to_icrs(equinox):
    assert isinstance(_frame_from_header(fits.Header({"EQUINOX": equinox})), ICRS)


def test_a_j2000_string_no_longer_discards_the_pointing_hint():
    header = fits.Header({"OBJCTRA": "21 29 58.3", "OBJCTDEC": "+12 10 01.2"})
    numeric = guess_icrs_radec_from_header(fits.Header({**header, "EQUINOX": 2000.0}))
    textual = guess_icrs_radec_from_header(fits.Header({**header, "EQUINOX": "J2000"}))
    assert textual == pytest.approx(numeric)
    assert textual[0] == pytest.approx(322.4929, abs=1e-3)


def test_the_tool_centres_a_bounded_search_on_a_j2000_header(fake_anet, monkeypatch, tmp_path):
    seen = {}

    def record(request, config):
        seen["ra_hours"], seen["dec_degs"] = request.ra_hours, request.dec_degs
        return SolveSolution(backend="astrometry.net")

    monkeypatch.setattr("algorithms.wcs.wcs.anet_solve_field_glob", record)
    path = _frame(tmp_path, "j2000", pointing=False,
                  OBJCTRA="21 29 58.3", OBJCTDEC="+12 10 01.2", EQUINOX="J2000")
    summary = solve_astrometry(path, index_path=fake_anet, search_radius_deg=1,
                               min_scale_arcsec=0.4, max_scale_arcsec=0.8)
    # Was search_radius_without_hint: the header "yields no pointing".
    assert summary.errors == []
    assert summary.search.center_ra_deg == pytest.approx(322.4929, abs=1e-3)
    assert seen["ra_hours"] * 15 == pytest.approx(322.4929, abs=1e-3)
    assert "no_solution" in [warning.code for warning in summary.warnings]


# --- WCS-05: ATLAS without a pointing hint ------------------------------------


def test_atlas_without_a_hint_is_a_named_setup_failure(fake_atlas_root, monkeypatch, tmp_path):
    monkeypatch.delenv("ANET_INDEX_PATH", raising=False)
    monkeypatch.setattr("algorithms.wcs.wcs.AtlasBackend.solve",
                        lambda *args, **kwargs: pytest.fail("ATLAS ran without a hint"))
    summary = solve_astrometry(_frame(tmp_path, "nohint", pointing=False))
    (error,) = summary.errors
    assert error.code == "solver_failed"
    assert "atlas" in error.message and "pointing hint" in error.message
    assert "NoneType" not in error.message
    assert "no_solution" not in [warning.code for warning in summary.warnings]


def test_direct_atlas_without_a_hint_records_why_in_the_result(fake_atlas_root, monkeypatch, tmp_path):
    monkeypatch.setattr("algorithms.wcs.wcs.AtlasBackend.solve",
                        lambda *args, **kwargs: pytest.fail("ATLAS ran without a hint"))
    result = _direct(_frame(tmp_path, "nohint", pointing=False), tmp_path,
                     SolverSettings(atlas_catalog_root=str(fake_atlas_root), atlas_catalog="ucac5"))
    assert result.wcs is None
    assert any("pointing hint" in failure for failure in result.metadata.solver_failures)


# --- WCS-23: missing binaries, bad catalog roots, a full disk -----------------


def test_direct_solve_field_missing_at_solve_time_is_recorded(monkeypatch, tmp_path, fake_anet):
    monkeypatch.setattr("algorithms.wcs.wcs.AstrometryNetBackend.is_available", lambda self: False)
    result = _direct(_frame(tmp_path, "hinted"), tmp_path,
                     SolverSettings(anet_index_path=str(fake_anet)))
    assert result.wcs is None
    assert result.metadata.solver_failures == (
        "astrometry.net: solve-field is not available",
    )


def test_direct_bad_catalog_root_is_in_the_result_without_side_channel_lists(tmp_path):
    result = _direct(_frame(tmp_path, "hinted"), tmp_path,
                     SolverSettings(atlas_catalog_root=str(tmp_path / "missing"), atlas_catalog="ucac5"))
    assert result.wcs is None
    (failure,) = result.metadata.solver_failures
    assert failure.startswith("atlas: ") and "u5index.asc" in failure


def test_a_full_disk_writing_atlas_input_is_labelled_and_named(fake_atlas_root, monkeypatch, tmp_path):
    monkeypatch.delenv("ANET_INDEX_PATH", raising=False)
    path = _frame(tmp_path, "hinted")
    monkeypatch.setattr(wcs_module.fits, "writeto", lambda *args, **kwargs: (_ for _ in ()).throw(ENOSPC))
    summary = solve_astrometry(path)
    assert summary.attempted_backends == ["atlas"]
    (error,) = summary.errors
    assert error.code == "solver_failed"
    assert error.message.startswith("atlas: could not write its input image")
    assert "No space left on device" in error.message


def test_a_full_disk_in_astrometry_net_is_a_solver_failure(fake_anet, monkeypatch, tmp_path):
    def disk_full(request, config):
        raise ENOSPC

    monkeypatch.setattr("algorithms.wcs.wcs.anet_solve_field_glob", disk_full)
    summary = solve_astrometry(_frame(tmp_path, "hinted"), index_path=fake_anet)
    assert [error.code for error in summary.errors] == ["solver_failed"]
    assert summary.errors[0].message.startswith("astrometry.net: ")
    assert "No space left on device" in summary.errors[0].message


def test_a_solve_that_skipped_a_failed_backend_says_so(fake_anet, fake_atlas_root, monkeypatch, tmp_path):
    # astrometry.net vanished after the preflight; ATLAS still solved.
    monkeypatch.setattr("algorithms.wcs.wcs.AstrometryNetBackend.is_available", lambda self: False)
    monkeypatch.setattr("tools.wcs._atlas_catalog_problem", lambda settings: None)
    monkeypatch.setattr("algorithms.wcs.wcs.AtlasBackend.solve",
                        lambda self, request, config: SolveSolution(wcs=_solved_wcs(), backend="atlas"))
    monkeypatch.setattr("algorithms.wcs.wcs._load_atlas_catalog_sources", lambda *args, **kwargs: [])
    summary = solve_astrometry(_frame(tmp_path, "hinted"), index_path=fake_anet)
    assert summary.has_wcs
    assert summary.errors == []
    codes = {warning.code: warning.message for warning in summary.warnings}
    assert "solve-field is not available" in codes["solver_backend_unavailable"]


def test_a_genuine_miss_is_still_no_solution(fake_anet, monkeypatch, tmp_path):
    monkeypatch.setattr("algorithms.wcs.wcs.anet_solve_field_glob",
                        lambda request, config: SolveSolution(backend="astrometry.net"))
    summary = solve_astrometry(_frame(tmp_path, "hinted"), index_path=fake_anet)
    assert summary.errors == []
    assert [warning.code for warning in summary.warnings] == ["no_solution"]
    assert not summary.has_wcs
