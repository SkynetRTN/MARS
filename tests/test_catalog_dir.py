"""M4: one catalog folder, ``MARS_CATALOG_DIR``, locates the plate solvers' data.

A user names the folder holding their astrometry.net index files and UCAC
catalogue once, at install time, instead of setting ``ANET_INDEX_PATH`` and
``ATLAS_CATALOG_ROOT`` to each leaf folder. The explicit variables still win.
The trees here are empty files with the solvers' file names, which is all
discovery and the backend checks read.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tools.wcs import CATALOG_DIR_DEPTH, _solver_settings

ROOT = Path(__file__).resolve().parents[1]
OPEN_FRAME = ROOT / "data" / "optical" / "m15_globular_open_000.fits"


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


@pytest.fixture
def catalogs(tmp_path) -> Path:
    """The development host's layout: three index series and a UCAC5 tree."""
    root = tmp_path / "catalogs"
    _touch(root / "astrometry" / "2MASS_ANET" / "4200" / "index-4208.fits")
    _touch(root / "astrometry" / "TYCHO2" / "indices" / "index-110")
    _touch(root / "astrometry" / "UCAC5" / "ucac5-index-5206-00.fits")
    _touch(root / "ATLAS" / "UCAC5" / "u5z" / "u5index.asc")
    _touch(root / "photometry" / "APASS-DR10" / "apass.csv")
    return root


def test_the_folder_supplies_every_index_series_and_the_catalogue_root(catalogs):
    settings, problems = _solver_settings({"MARS_CATALOG_DIR": str(catalogs)})

    assert problems == []
    assert sorted(settings.ANET_INDEX_PATH) == [
        str(catalogs / "astrometry" / "2MASS_ANET" / "4200"),
        str(catalogs / "astrometry" / "TYCHO2" / "indices"),
        str(catalogs / "astrometry" / "UCAC5"),
    ]
    # The UCAC5 folder, not its u5z zone folder.
    assert settings.ATLAS_CATALOG_ROOT == str(catalogs / "ATLAS" / "UCAC5")


def test_a_ucac4_catalogue_is_found_when_atlas_asks_for_it(tmp_path):
    _touch(tmp_path / "UCAC4" / "Z001.UC4")

    settings, problems = _solver_settings({"MARS_CATALOG_DIR": str(tmp_path), "ATLAS_CATALOG": "ucac4"})

    assert problems == []
    assert settings.ATLAS_CATALOG_ROOT == str(tmp_path / "UCAC4")
    assert settings.ANET_INDEX_PATH is None


def test_explicit_locations_win_over_the_folder(catalogs, tmp_path):
    index_dir, atlas_root = tmp_path / "mine", tmp_path / "my-ucac5"
    environ = {
        "MARS_CATALOG_DIR": str(catalogs),
        "ANET_INDEX_PATH": str(index_dir),
        "ATLAS_CATALOG_ROOT": str(atlas_root),
    }

    settings, _ = _solver_settings(environ)
    assert (settings.ANET_INDEX_PATH, settings.ATLAS_CATALOG_ROOT) == (str(index_dir), str(atlas_root))

    settings, _ = _solver_settings(environ, index_path=tmp_path / "argument")
    assert settings.ANET_INDEX_PATH == str(tmp_path / "argument")

    # Each explicit variable replaces only its own half.
    settings, _ = _solver_settings({"MARS_CATALOG_DIR": str(catalogs), "ANET_INDEX_PATH": str(index_dir)})
    assert settings.ANET_INDEX_PATH == str(index_dir)
    assert settings.ATLAS_CATALOG_ROOT == str(catalogs / "ATLAS" / "UCAC5")


def test_data_deeper_than_the_search_is_reported_not_found(tmp_path):
    deep = tmp_path.joinpath(*(f"level{n}" for n in range(CATALOG_DIR_DEPTH + 1)))
    _touch(deep / "index-4208.fits")

    settings, problems = _solver_settings({"MARS_CATALOG_DIR": str(tmp_path)})

    assert settings.ANET_INDEX_PATH is None and settings.ATLAS_CATALOG_ROOT is None
    assert problems == [
        f"MARS_CATALOG_DIR={tmp_path} holds no astrometry.net index files or UCAC5 "
        f"catalogue within {CATALOG_DIR_DEPTH} folder levels"
    ]


def test_a_missing_folder_is_reported(tmp_path):
    _, problems = _solver_settings({"MARS_CATALOG_DIR": str(tmp_path / "absent")})

    assert problems == [f"MARS_CATALOG_DIR={tmp_path / 'absent'} is not a directory"]


@pytest.mark.skipif(os.name == "nt", reason="directory symlinks need privileges on Windows")
def test_linked_folders_are_followed_but_a_loop_ends(tmp_path):
    data = _touch(tmp_path / "elsewhere" / "4200" / "index-4208.fits").parent
    root = tmp_path / "catalogs"
    root.mkdir()
    (root / "astrometry").symlink_to(data.parent, target_is_directory=True)
    (data / "back").symlink_to(root, target_is_directory=True)

    settings, problems = _solver_settings({"MARS_CATALOG_DIR": str(root)})

    assert problems == []
    assert settings.ANET_INDEX_PATH == [str(root / "astrometry" / "4200")]


def test_the_install_facts_read_the_folder_as_the_tool_does(tmp_path):
    """The served instructions say whether plate solving is configured; with
    only a catalog folder set, that must be the tool's own answer."""
    from tools.mcp.install import install_facts

    _touch(tmp_path / "ATLAS" / "UCAC5" / "u5index.asc")

    assert "plate solving configured" in install_facts(tmp_path, {"MARS_CATALOG_DIR": str(tmp_path)})
    assert "plate solving not configured" in install_facts(
        tmp_path, {"MARS_CATALOG_DIR": str(tmp_path / "absent")})


def test_the_tool_solves_with_what_the_folder_holds(catalogs, monkeypatch):
    from algorithms.wcs.results import WcsSolveMetadata, WcsSolveResult
    from tools import wcs as public_wcs

    seen = []

    def capture(*args, solver_settings, **kwargs):
        seen.append(solver_settings)
        return WcsSolveResult(wcs=None, catalog_sources=(), metadata=WcsSolveMetadata(width_px=1, height_px=1))

    monkeypatch.setenv("MARS_CATALOG_DIR", str(catalogs))
    monkeypatch.delenv("ANET_INDEX_PATH", raising=False)
    monkeypatch.delenv("ATLAS_CATALOG_ROOT", raising=False)
    monkeypatch.setattr(public_wcs, "_configured_backend_warnings", lambda settings, *_: (["atlas"], []))
    monkeypatch.setattr(public_wcs, "_solve_wcs", capture)

    public_wcs.solve_astrometry(OPEN_FRAME)

    (settings,) = seen
    assert settings.ATLAS_CATALOG_ROOT == str(catalogs / "ATLAS" / "UCAC5")
    assert len(settings.ANET_INDEX_PATH) == 3


def test_a_folder_without_data_says_so_and_names_the_setting(tmp_path, monkeypatch):
    from tools.wcs import solve_astrometry

    monkeypatch.setenv("MARS_CATALOG_DIR", str(tmp_path))
    monkeypatch.delenv("ANET_INDEX_PATH", raising=False)
    monkeypatch.delenv("ATLAS_CATALOG_ROOT", raising=False)

    summary = solve_astrometry(OPEN_FRAME)

    assert not summary.has_wcs
    # One warning, naming what is wrong rather than how to configure it.
    (warning,) = summary.warnings
    assert warning.code == "solver_unavailable"
    assert warning.message == (
        f"No plate-solving backend is available: MARS_CATALOG_DIR={tmp_path} holds no "
        f"astrometry.net index files or UCAC5 catalogue within {CATALOG_DIR_DEPTH} folder levels."
    )


def test_found_index_files_without_solve_field_name_the_program(catalogs, monkeypatch):
    """Found on a Mac without astrometry.net installed: the message said
    "Set MARS_CATALOG_DIR", which was set, and the folder was found."""
    from tools import wcs as public_wcs

    monkeypatch.setattr(public_wcs, "find_solve_field", lambda: None)
    settings, problems = _solver_settings({"MARS_CATALOG_DIR": str(catalogs), "ATLAS_CATALOG": "ucac4"})

    _, (warning,) = public_wcs._configured_backend_warnings(settings, problems)

    assert warning.code == "solver_unavailable"
    assert "Set MARS_CATALOG_DIR" not in warning.message
    assert "solve-field (astrometry.net) is not on the PATH MARS was started with" in warning.message


def test_a_relative_folder_gives_absolute_paths(catalogs, monkeypatch):
    """solve-field runs in a temporary folder, where a relative path names nothing."""
    monkeypatch.chdir(catalogs.parent)

    settings, problems = _solver_settings({"MARS_CATALOG_DIR": catalogs.name})

    assert problems == []
    assert all(Path(path).is_absolute() for path in settings.ANET_INDEX_PATH)
    assert Path(settings.ATLAS_CATALOG_ROOT).is_absolute()


@pytest.mark.skipif(os.name == "nt", reason="directory symlinks need privileges on Windows")
def test_a_folder_first_reached_at_the_depth_limit_is_still_searched_from_a_shallower_link(tmp_path):
    data = _touch(tmp_path / "data" / "4200" / "index-4208.fits").parent.parent
    root = tmp_path / "catalogs"
    deep = root.joinpath(*(f"level{n}" for n in range(CATALOG_DIR_DEPTH - 1)))
    deep.mkdir(parents=True)
    (deep / "a-link").symlink_to(data, target_is_directory=True)
    (root / "z-link").symlink_to(data, target_is_directory=True)

    settings, problems = _solver_settings({"MARS_CATALOG_DIR": str(root)})

    assert problems == []
    assert settings.ANET_INDEX_PATH == [str(root / "z-link" / "4200")]


def test_an_unknown_atlas_catalog_is_reported_and_not_guessed(tmp_path):
    settings, problems = _solver_settings({"MARS_CATALOG_DIR": str(tmp_path), "ATLAS_CATALOG": "ucac"})

    assert settings.ATLAS_CATALOG_ROOT is None
    assert problems[0] == "ATLAS_CATALOG=ucac: Unsupported catalog: ucac"
    assert problems[1].endswith("holds no astrometry.net index files within 4 folder levels")


def test_what_the_folder_lacks_is_reported_for_the_solver_it_was_asked_for(tmp_path):
    """With ATLAS set explicitly, the folder is searched only for index files."""
    _touch(tmp_path / "ATLAS" / "UCAC5" / "u5index.asc")

    _, problems = _solver_settings({"MARS_CATALOG_DIR": str(tmp_path), "ATLAS_CATALOG_ROOT": "/elsewhere"})

    assert problems == [
        f"MARS_CATALOG_DIR={tmp_path} holds no astrometry.net index files within 4 folder levels"
    ]


def test_index_folders_are_written_for_solve_field_as_utf8(tmp_path):
    """The Desktop folder picker makes a non-ASCII or spaced folder ordinary;
    the config was written as ASCII, which raised on the first."""
    from algorithms.skylib_lite.astrometry.anet.backend import AstrometryNetBackend

    config = AstrometryNetBackend._write_index_config(["/Users/José/Astro Catalogs/4200"], tmp_path)

    assert config.read_text(encoding="utf-8").splitlines()[-1] == "add_path /Users/José/Astro Catalogs/4200"


def test_the_developers_catalog_folder_does_not_reach_ordinary_tests():
    """conftest takes it out of every test's environment; the solver-data
    tests read it from ``OPERATOR_SOLVER_ENV`` instead."""
    assert "MARS_CATALOG_DIR" not in os.environ
    assert _solver_settings(os.environ)[1] == []
