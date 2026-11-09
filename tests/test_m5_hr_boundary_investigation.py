"""M5 TS-22/23/30 investigation: legacy characterizations and live controls.

These tests deliberately distinguish the old display helpers from the
maintained HR fitter. Characterizations document observed legacy behavior;
they do not prescribe a change to a rendering convention or restore old bugs
in the Python fitter. All models and catalog rows are local fixtures.
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")

from algorithms.hrdiagram_py import hrfit, legacy, local_grid
from tools import config, hr_diagram


_FILTERS = {"blue": "BP", "red": "RP", "lum": "G"}
_PARAMS = {"distance": 1.0, "reddening": 0.0}
_POINTS = [[2.0, 9.0], [0.5, 5.0], [1.0, 1.0], [3.0, 0.0]]
_M67 = Path(__file__).parent / "fixtures" / "hrdiagram_m67"


@pytest.mark.parametrize(
    "blue,red,lum,legacy_min,lum_only_min,upper",
    [
        ("BP", "RP", "G", -13.08375, -13.19625, 11.16625),
        ("BP", "RP", "BP", -12.9825, -13.2, 12.1),
        ("B", "R", "V", -13.06, -13.17625, 11.88625),
        ("BP", "G", "RP", -13.66875, -13.55625, 10.20625),
        ("BP", "RP", "RP", -13.55625, -13.55625, 10.20625),
        ("U", "W4", "uprime", -11.51625, -12.43625, 15.32625),
        ("U", "uprime", "W4", -15.76625, -14.84625, 7.41625),
    ],
)
def test_characterization_standard_bright_margin_depends_on_red_filter(
    blue, red, lum, legacy_min, lum_only_min, upper,
):
    """TS-22: only the bright bound changes relative to a lum-only margin.

    Literal bounds use the documented extrema and a one-eighth margin.
    Gaia's default differs by 0.1125 mag; the supported bands allow 0.92 mag.
    A red=lum control has no discrepancy, and neither formula shifts stars.
    """
    filters = {"blue": blue, "red": red, "lum": lum}
    actual = legacy.get_standard_view_range(filters)
    lum_control = legacy.get_standard_view_range({**filters, "red": lum})

    assert actual["y"] == pytest.approx({"min": legacy_min, "max": upper})
    assert lum_control["y"] == pytest.approx({"min": lum_only_min, "max": upper})
    assert actual["y"]["min"] < actual["y"]["max"]


@pytest.mark.parametrize("plot_type,mag_shift", [("HR", 0.0), ("CM", 10.0)])
@pytest.mark.parametrize(
    "skip,retained_indices,gap_index",
    [
        (-1, [0, 1, 2, 3], None),
        (0, [0, 1, 2, 3], None),
        (1, [1, 2, 3], 0),
        (2, [0, 2, 3], 1),
        (3, [0, 1, 3], 2),
        (4, [0, 1, 2, 3], None),
        (5, [0, 1, 2, 3], None),
    ],
)
def test_characterization_legacy_break_replaces_preceding_point_in_both_frames(
    plot_type, mag_shift, skip, retained_indices, gap_index,
):
    """TS-23: interior skips lose exactly index skip-1, including skip=1.

    Negative/zero/out-of-range indices make no break. A 1 kpc, zero-extinction
    CM track is the absolute track plus exactly ten magnitudes.
    """
    response = {"data": [point.copy() for point in _POINTS], "iSkip": skip}

    actual = legacy.apply_isochrone_transform(response, plot_type, _FILTERS, _PARAMS)

    expected = [[_POINTS[i][0], _POINTS[i][1] + mag_shift] for i in retained_indices]
    if gap_index is not None:
        expected.insert(gap_index, [None, None])
    assert actual == expected
    assert len(actual) == 4
    assert response["data"] == _POINTS


@pytest.mark.parametrize(
    "skip,want_colour,want_mag",
    [
        (None, [2.0, 0.5, 1.0, 3.0], [9.0, 5.0, 1.0, 0.0]),
        (-1, [2.0, 0.5, 1.0, 3.0], [9.0, 5.0, 1.0, 0.0]),
        (0, [2.0, 0.5, 1.0, 3.0], [9.0, 5.0, 1.0, 0.0]),
        (1, [2.0, np.nan, 0.5, 1.0, 3.0], [9.0, np.nan, 5.0, 1.0, 0.0]),
        (2, [2.0, 0.5, np.nan, 1.0, 3.0], [9.0, 5.0, np.nan, 1.0, 0.0]),
        (3, [2.0, 0.5, 1.0, np.nan, 3.0], [9.0, 5.0, 1.0, np.nan, 0.0]),
        (4, [2.0, 0.5, 1.0, 3.0], [9.0, 5.0, 1.0, 0.0]),
        (5, [2.0, 0.5, 1.0, 3.0], [9.0, 5.0, 1.0, 0.0]),
    ],
)
def test_working_control_python_break_retains_every_native_point(skip, want_colour, want_mag):
    """The deliberate Python splice correction predates M5, at both ends.

    A gap is inserted at the requested interior index without losing the
    preceding point. Omitting iskip (the maintained callers' behavior) keeps
    the complete native track.
    """
    iso = pd.DataFrame({
        "BP": [10.0, 4.5, 1.0, 2.0],
        "RP": [8.0, 4.0, 0.0, -1.0],
        "G": [9.0, 5.0, 1.0, 0.0],
    })
    kwargs = {} if skip is None else {"iskip": skip}

    colour, mag = hrfit.isochrone_cmd(iso, "BP", "RP", "G", **kwargs)

    np.testing.assert_equal(colour, want_colour)
    np.testing.assert_equal(mag, want_mag)
    np.testing.assert_equal(colour[np.isfinite(colour)], [2.0, 0.5, 1.0, 3.0])
    np.testing.assert_equal(mag[np.isfinite(mag)], [9.0, 5.0, 1.0, 0.0])


def test_working_control_plot_gap_is_aligned_in_both_coordinates():
    """The point renderer masks the gap and preserves every finite vertex."""
    import matplotlib.pyplot as plt

    iso = pd.DataFrame({"BP": [2.0, 1.5, 3.0], "RP": [1.0, 1.0, 1.0], "G": [5.0, 4.0, 3.0]})
    colour, mag = hrfit.isochrone_cmd(iso, "BP", "RP", "G", iskip=1)
    ax = hrfit.plot_cmd([0.0, 1.0], [1.0, 2.0], colour, mag)
    try:
        model = next(c for c in ax.collections if c.get_label() == "Isochrone")
        offsets = model.get_offsets()
        np.testing.assert_array_equal(
            np.ma.getmaskarray(offsets),
            [[False, False], [True, True], [False, False], [False, False]],
        )
        np.testing.assert_array_equal(
            offsets.compressed().reshape(-1, 2), [[1.0, 5.0], [0.5, 4.0], [2.0, 3.0]],
        )
        assert not ax.lines  # Do not reconnect separate evolutionary phases.
        assert ax.yaxis_inverted()
    finally:
        plt.close(ax.figure)


def test_working_control_fit_cost_does_not_interpolate_across_large_phase_jump():
    """A star inside a 1.75-mag gap is 0.75 mag from the nearest segment.

    An invented connecting segment would give it zero cost. This exercises
    the real track resampling and nearest-point cost with uncapped unit errors.
    """
    errors = np.array([1.0])
    cost = hrfit._TrackCost(
        errors, errors, np.array([0.0, 0.0, 0.0, 0.0]), np.array([0.0, 0.25, 2.0, 2.25]),
        floor=0.0, cap=None,
    )

    assert cost(np.array([0.0]), np.array([1.0])) == pytest.approx(0.5625)


@pytest.mark.parametrize(
    "longitude,latitude,distance,want_edge,want_face",
    [
        (0.0, 0.0, 1.0, {"delta_x": -32.0, "delta_y": 0.0}, {"delta_x": 0.0, "delta_y": -32.0}),
        (180.0, 0.0, 1.0, {"delta_x": 32.0, "delta_y": 0.0}, {"delta_x": 0.0, "delta_y": 32.0}),
        (90.0, 0.0, 1.0, {"delta_x": 0.0, "delta_y": 0.0}, {"delta_x": 32.0, "delta_y": 0.0}),
        (0.0, 90.0, 1.0, {"delta_x": 0.0, "delta_y": 16.0}, {"delta_x": 0.0, "delta_y": 0.0}),
        (0.0, -90.0, 1.0, {"delta_x": 0.0, "delta_y": -16.0}, {"delta_x": 0.0, "delta_y": 0.0}),
        # Cartesian displacement (toward centre, transverse, height)=(3,4,12)
        # has distance 13 kpc; the expected pixel offsets are hand-derived.
        (math.degrees(math.atan2(4, 3)), math.degrees(math.asin(12 / 13)), 13.0,
         {"delta_x": -96.0, "delta_y": 192.0}, {"delta_x": 128.0, "delta_y": -96.0}),
        # Equal physical horizontal/vertical components draw at a 2:1 ratio.
        (0.0, 45.0, math.sqrt(2), {"delta_x": -32.0, "delta_y": 16.0}, {"delta_x": 0.0, "delta_y": -32.0}),
    ],
)
def test_characterization_galaxy_offsets_are_pixels_from_degree_kpc_geometry(
    longitude, latitude, distance, want_edge, want_face,
):
    """TS-30 is a display aspect ratio; it is not a kpc coordinate output."""
    assert legacy.galaxy_edge_on_offset(longitude, latitude, distance) == pytest.approx(want_edge, abs=1e-12)
    assert legacy.galaxy_face_on_offset(longitude, latitude, distance) == pytest.approx(want_face, abs=1e-12)


@pytest.mark.parametrize("latitude,sign", [(90.0, 1), (-90.0, -1)])
@pytest.mark.parametrize(
    "distance,positive_height",
    [
        (np.nextafter(31.25, 0.0), np.nextafter(500.0, 0.0)),
        (31.25, 500.0),
        (np.nextafter(31.25, np.inf), 500.0),
    ],
)
def test_characterization_edge_on_marker_clamps_at_canvas_boundary(latitude, sign, distance, positive_height):
    """At either Galactic pole, clipping begins at 31.25 kpc (500 pixels)."""
    result = legacy.galaxy_edge_on_offset(0.0, latitude, distance)

    assert result["delta_y"] == sign * positive_height
    assert result["delta_x"] == pytest.approx(0.0, abs=1e-12)


@pytest.mark.slow
def test_working_control_current_hr_tool_plots_local_track_without_losing_model_points(
    artifact_dir, monkeypatch,
):
    """Current tool → local loader → real optimizer → real plotted vertices.

    Only the remote literature lookup is replaced. The recorded 9.60 track
    has 338 rows: 337 stars plus its final ~30-mag sentinel. No server iSkip
    metadata is present; omission must not lose an ordinary model row.
    """
    import matplotlib.pyplot as plt

    literature = {"log_age": 9.60, "distance_kpc": 0.889, "ebv": 0.023, "age_myr": 10**9.60 / 1e6}
    monkeypatch.setattr(config, "ISOCHRONE_DIR", _M67)
    monkeypatch.setattr(hr_diagram, "_fetch_literature_params", lambda _: literature)
    plotted_axes = []
    real_plot = hrfit.plot_cmd

    def record_plot(*args, **kwargs):
        ax = real_plot(*args, **kwargs)
        plotted_axes.append(ax)
        return ax

    monkeypatch.setattr(hrfit, "plot_cmd", record_plot)
    try:
        result = hr_diagram.fit_and_compare_hr_diagram(
            str(_M67 / "members.csv"), "M67", max_error=0.2, logage_half_width=0.0,
        )

        assert result.status == "ok", result.errors
        assert len(plotted_axes) == 1
        ax = plotted_axes[0]
        # Read raw bands directly; do not derive expected vertices with a
        # loader, isochrone_cmd, or any other production transform.
        raw = np.load(_M67 / "Girardi_9.60_0.00.npy", allow_pickle=False)
        assert raw.shape == (338, 23)
        sentinel = (np.abs(raw[:, [20, 21, 19]]) > 25.0).any(axis=1)
        np.testing.assert_array_equal(np.flatnonzero(sentinel), [337])
        expected = np.column_stack((raw[:337, 20] - raw[:337, 21], raw[:337, 19]))
        model = next(c for c in ax.collections if c.get_label() == "Isochrone")
        offsets = model.get_offsets()
        assert not np.ma.getmaskarray(offsets).any()
        np.testing.assert_array_equal(offsets, expected)
        assert offsets.shape == (337, 2)
        assert not ax.lines
        assert ax.get_xlabel() == "(BP - RP)$_0$"
        assert ax.get_ylabel() == "M$_{G}$"
        assert ax.yaxis_inverted()
        # The local compatibility endpoint explicitly has no break metadata.
        response = local_grid.load_isochrone(
            age=9.60, metallicity=0.0, blue_filter="BP", red_filter="RP", lum_filter="G",
        )
        assert response["iSkip"] == 0
        assert len(response["data"]) == 338
        assert {artifact.format for artifact in result.artifacts} == {"csv", "png"}
        assert all(Path(artifact.path).stat().st_size > 0 for artifact in result.artifacts)
    finally:
        for ax in plotted_axes:
            plt.close(ax.figure)
