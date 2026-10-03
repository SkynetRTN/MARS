"""Local Girardi-grid contract for the former Astromancer isochrone endpoint."""

from __future__ import annotations

import socket
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from algorithms.hrdiagram_py import isochrones, local_grid
from tools import config
from tools import hr_diagram


def test_operator_grid_setting_has_no_bundled_default():
    assert config.ISOCHRONE_DIR_ENV == "MARS_ISOCHRONE_DIR"
    assert config.ISOCHRONE_DIR is None


def _track() -> np.ndarray:
    rows = np.zeros((2, 23), dtype=float)
    rows[:, 0] = 8.60
    rows[:, 1] = -0.05
    rows[:, 2:7] = [[10, 11, 12, 13, 14], [20, 21, 22, 23, 24]]
    rows[:, 7:12] = [[30, 31, 32, 33, 34], [40, 41, 42, 43, 44]]
    rows[:, 12:15] = [[50, 51, 52], [60, 61, 62]]
    rows[:, 15:19] = [[70, 71, 72, 73], [80, 81, 82, 83]]
    rows[:, 19:22] = [[90, 91, 92], [100, 101, 102]]
    rows[:, 22] = -0.05
    return rows


def test_exact_girardi_track_returns_browser_colour_magnitude_shape(tmp_path, monkeypatch):
    np.save(tmp_path / "Girardi_8.60_-0.05.npy", _track())
    monkeypatch.setattr(config, "ISOCHRONE_DIR", tmp_path)

    response = local_grid.load_isochrone(
        age=8.60, metallicity=-0.05,
        blue_filter="BP", red_filter="RP", lum_filter="G",
    )

    assert response["data"] == [[-1.0, 90.0], [-1.0, 100.0]]
    assert response["iSkip"] == 0


def test_missing_exact_track_is_an_actionable_error(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ISOCHRONE_DIR", tmp_path)
    with pytest.raises(local_grid.GridUnavailableError, match="Girardi_8.60_0.00.npy"):
        local_grid.load_isochrone(
            age=8.60, metallicity=0.0,
            blue_filter="BP", red_filter="RP", lum_filter="G",
        )


def test_rejects_unknown_filter_and_wrong_shape(tmp_path, monkeypatch):
    np.save(tmp_path / "Girardi_8.60_0.00.npy", np.zeros((2, 22)))
    monkeypatch.setattr(config, "ISOCHRONE_DIR", tmp_path)

    with pytest.raises(local_grid.GridUnavailableError, match="23 columns"):
        local_grid.load_isochrone(
            age=8.60, metallicity=0.0,
            blue_filter="BP", red_filter="RP", lum_filter="G",
        )

    np.save(tmp_path / "Girardi_8.60_0.00.npy", _track())
    with pytest.raises(local_grid.GridUnavailableError, match="unsupported filter"):
        local_grid.load_isochrone(
            age=8.60, metallicity=0.0,
            blue_filter="X", red_filter="RP", lum_filter="G",
        )


def test_load_tracks_preserves_exact_age_and_all_supported_filter_columns(tmp_path, monkeypatch):
    np.save(tmp_path / "Girardi_8.60_-0.05.npy", _track())
    np.save(tmp_path / "Girardi_8.65_-0.05.npy", _track() + np.array([0.05, 0, *([0] * 21)]))
    monkeypatch.setattr(config, "ISOCHRONE_DIR", tmp_path)

    grid = local_grid.load_tracks(ages=[8.60, 8.65], metallicity=-0.05)

    assert list(grid[["logAge", "MH", "G", "BP", "RP"]].iloc[0]) == [8.60, -0.05, 90.0, 91.0, 92.0]
    assert set(grid["logAge"]) == {8.60, 8.65}


def test_grid_loader_rejects_tracks_above_configured_resource_limits(tmp_path, monkeypatch):
    np.save(tmp_path / "Girardi_8.60_0.00.npy", _track())
    monkeypatch.setattr(config, "ISOCHRONE_DIR", tmp_path)
    monkeypatch.setattr(local_grid, "MAX_TRACK_BYTES", 1, raising=False)

    with pytest.raises(local_grid.GridUnavailableError, match="maximum size"):
        local_grid.load_isochrone(
            age=8.60, metallicity=0.0,
            blue_filter="BP", red_filter="RP", lum_filter="G",
        )


def test_fit_uses_configured_local_grid_without_socket_access(tmp_path, monkeypatch):
    track = _track()
    track[:, 19:22] = [[10.0, 11.0, 9.0], [8.0, 9.0, 7.0]]
    np.save(tmp_path / "Girardi_8.60_0.00.npy", track)
    members = pd.DataFrame({
        "BP": [21.0, 19.0], "RP": [19.0, 17.0], "G": [20.0, 18.0],
        "BP_err": [0.01, 0.01], "RP_err": [0.01, 0.01], "G_err": [0.01, 0.01],
    })
    monkeypatch.setattr(config, "ISOCHRONE_DIR", tmp_path)
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("socket access"))
    report = isochrones.fit_and_compare(
        members, {"log_age": 8.60, "distance_kpc": 1.0, "ebv": 0.0, "age_myr": 400.0}, "local",
        members_csv_path=tmp_path / "members.csv", out_png=tmp_path / "fit.png",
        logage_half_width=0.0, max_error=1.0,
    )

    assert report["isochrone_path"] == str(tmp_path)
    assert (tmp_path / "fit.png").is_file()


@pytest.mark.parametrize(
    ("log_age", "half_width", "expected"),
    [
        (8.17, 0.4, [round(7.80 + 0.05 * i, 2) for i in range(16)]),  # M35: 7.77..8.57 on the grid
        (8.60, 0.1, [8.50, 8.55, 8.60, 8.65, 8.70]),
        (8.17, 0.01, [8.15]),  # no grid age inside: the nearest one
    ],
)
def test_the_age_window_names_only_grid_ages(tmp_path, monkeypatch, log_age, half_width, expected):
    """The grid holds ages at multiples of 0.05 and a literature age is
    any two-decimal value. Stepping from the literature age asked for
    Girardi_7.77, which no grid has, so every such cluster failed."""
    requested = {}

    def load_tracks(*, ages, metallicity):
        requested["ages"] = ages
        raise local_grid.GridUnavailableError("stop after the request")

    monkeypatch.setattr(config, "ISOCHRONE_DIR", tmp_path)
    monkeypatch.setattr(isochrones.local_grid, "load_tracks", load_tracks)
    members = pd.DataFrame({"BP": [], "RP": [], "G": [], "BP_err": [], "RP_err": [], "G_err": []})
    with pytest.raises(local_grid.GridUnavailableError):
        isochrones.fit_and_compare(
            members, {"log_age": log_age, "distance_kpc": 1.0, "ebv": 0.0}, "local",
            members_csv_path=tmp_path / "members.csv", out_png=tmp_path / "fit.png",
            logage_half_width=half_width,
        )
    assert requested["ages"] == expected


def test_fit_rejects_nonfinite_age_width_before_expanding_tracks(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ISOCHRONE_DIR", tmp_path)
    members = pd.DataFrame({"BP": [], "RP": [], "G": [], "BP_err": [], "RP_err": [], "G_err": []})

    with pytest.raises(ValueError, match="logage_half_width must be finite"):
        isochrones.fit_and_compare(
            members, {"log_age": 8.60, "distance_kpc": 1.0, "ebv": 0.0, "age_myr": 400.0}, "local",
            members_csv_path=tmp_path / "members.csv", out_png=tmp_path / "fit.png",
            logage_half_width=float("inf"),
        )


def test_failed_track_serialization_removes_temporary_conversion(tmp_path, monkeypatch):
    class FailingTrackFrame(pd.DataFrame):
        @property
        def _constructor(self):
            return FailingTrackFrame

        def to_csv(self, *args, **kwargs):
            raise OSError("injected conversion failure")

    columns = [
        "logAge", "MH", "U", "B", "V", "R", "I", "uprime", "gprime", "rprime", "iprime", "zprime",
        "J", "H", "K", "W1", "W2", "W3", "W4", "G", "BP", "RP", "MH_repeat",
    ]
    monkeypatch.setattr(config, "ISOCHRONE_DIR", tmp_path)
    monkeypatch.setattr(isochrones.local_grid, "load_tracks", lambda **kwargs: FailingTrackFrame(_track(), columns=columns))
    members = pd.DataFrame({"BP": [], "RP": [], "G": [], "BP_err": [], "RP_err": [], "G_err": []})

    with pytest.raises(OSError, match="injected conversion failure"):
        isochrones.fit_and_compare(
            members, {"log_age": 8.60, "distance_kpc": 1.0, "ebv": 0.0, "age_myr": 400.0}, "local",
            members_csv_path=tmp_path / "members.csv", out_png=tmp_path / "fit.png",
            logage_half_width=0.0,
        )

    assert not list(tmp_path.glob("mars_girardi_*.dat"))


def test_hr_tool_reads_operator_grid_from_config(tmp_path, monkeypatch):
    track = _track()
    track[:, 19:22] = [[10.0, 11.0, 9.0], [8.0, 9.0, 7.0]]
    np.save(tmp_path / "Girardi_8.60_0.00.npy", track)
    members_path = tmp_path / "members.csv"
    pd.DataFrame({
        "BP": [21.0, 19.0], "RP": [19.0, 17.0], "G": [20.0, 18.0],
        "BP_err": [0.01, 0.01], "RP_err": [0.01, 0.01], "G_err": [0.01, 0.01],
    }).to_csv(members_path, index=False)
    monkeypatch.setattr(config, "ISOCHRONE_DIR", tmp_path)
    monkeypatch.setattr(hr_diagram, "_fetch_literature_params", lambda _: {"log_age": 8.60, "distance_kpc": 1.0, "ebv": 0.0, "age_myr": 400.0})
    monkeypatch.setattr(hr_diagram, "_output_path", lambda stem, suffix: tmp_path / f"{stem}{suffix}")

    result = hr_diagram.fit_and_compare_hr_diagram(str(members_path), "local", max_error=1.0, logage_half_width=0.0)

    assert result.status == "ok"
    assert result.preview[0]["isochrone_path"] == str(tmp_path)


_M67 = Path(__file__).parent / "fixtures" / "hrdiagram_m67"


@pytest.mark.slow
def test_m67_fits_near_its_literature_age(tmp_path, monkeypatch):
    """M67 against Cantat-Gaudin & Anders 2020 (log age 9.63, 0.889 kpc,
    E(B-V) 0.023), offline: 548 Gaia DR3 members recorded from a live
    run_full_hr_pipeline_from_catalog on 2026-10-02, and the 16 grid tracks
    its +-0.4 dex window reads (float32 copies from the isochrones bundle).

    The nearest-vertex, uncapped cost fitted log age 9.25 (1.8 Gyr), 0.815 kpc
    and E(B-V) 0.092: the young edge of the window. Blue stragglers set that
    fit; see SYSTEMATIC_FLOOR_MAG and CHI2_CAP in hrfit."""
    members = pd.read_csv(_M67 / "members.csv")
    literature = {"log_age": 9.63, "distance_kpc": 0.889, "ebv": 0.022580645257426847, "age_myr": 4265.8}
    monkeypatch.setattr(config, "ISOCHRONE_DIR", _M67)
    report = isochrones.fit_and_compare(
        members, literature, "M67",
        members_csv_path=tmp_path / "members.csv", out_png=tmp_path / "fit.png",
        logage_half_width=0.4, max_error=0.2,
    )
    fitted = report["fitted"]
    assert abs(fitted["log_age"] - 9.63) <= 0.1
    assert abs(fitted["distance_kpc"] - 0.889) / 0.889 < 0.06
    assert abs(fitted["ebv"] - 0.023) < 0.03
