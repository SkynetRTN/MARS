"""M4: every supported plot draws its data, not just its labels.

The older plot tests check dimensions, labels and series names, which a plot
with an empty or misplaced trace still passes. These capture the matplotlib
figure each tool saves and compare what is drawn -- traces, markers, fitted
lines, error bars, axis units -- with the data the tool was given.
``test_pulsar_spectrum_semantics.py`` does the same for both pulsar spectrum
modes; this file covers the rest:

- pulsar light curves and folded profiles (``plot_pulsar``);
- the photometry overlay and the zero-point diagnostic (``run_photometry``);
- the HR diagram fit (``fit_and_compare_hr_diagram``);
- the radio spectrum (``analyze_source_spectrum``) and field SED
  (``plot_field_sed``).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from astropy.table import Table

from algorithms.pulsar import charts
from tests.conftest import PULSAR_PERIODS_S


@pytest.fixture
def saved_figures(monkeypatch):
    """Each figure as it was saved, in order."""
    from matplotlib.figure import Figure

    saved = []
    savefig = Figure.savefig

    def capture(figure, *args, **kwargs):
        saved.append(figure)
        return savefig(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capture)
    return saved


def _offsets(collection) -> np.ndarray:
    return np.asarray(collection.get_offsets(), dtype=float)


def _labelled(axes, label):
    artists = [*axes.lines, *axes.collections, *axes.patches]
    found = [artist for artist in artists if artist.get_label() == label]
    assert len(found) == 1, f"no single artist labelled {label!r}"
    return found[0]


# ---------------------------------------------------------------------------
# Pulsar light curves and folded profiles
# ---------------------------------------------------------------------------


@pytest.fixture
def b0329(pulsar_path, artifact_dir):
    from tools.pulsar import fold_pulsar_lightcurve, load_pulsar_lightcurve

    lightcurve = load_pulsar_lightcurve(pulsar_path("b0329"))
    profile = fold_pulsar_lightcurve(lightcurve.artifact.path, PULSAR_PERIODS_S["b0329"])
    return lightcurve, profile


def test_a_light_curve_draws_both_feeds_over_time(b0329, saved_figures):
    from tools.pulsar import plot_pulsar

    lightcurve, _ = b0329
    table = Table.read(lightcurve.artifact.path, format="ascii.ecsv")

    result = plot_pulsar(lightcurve.artifact.path)

    assert result.errors == []
    axes = saved_figures[-1].axes[0]
    assert [line.get_label() for line in axes.lines] == ["Polarization XX", "Polarization YY"]
    for line, column in zip(axes.lines, ("source1", "source2")):
        np.testing.assert_array_equal(line.get_xdata(), table["time_s"])
        np.testing.assert_array_equal(line.get_ydata(), table[column])
    assert (axes.get_xlabel(), axes.get_ylabel()) == ("Time (s)", "Intensity")


@pytest.mark.parametrize("show_hidden", [False, True])
def test_a_folded_profile_draws_its_bins_over_one_period(b0329, saved_figures, show_hidden):
    from tools.pulsar import plot_pulsar

    _, profile = b0329
    table = Table.read(profile.artifact.path, format="ascii.ecsv")

    result = plot_pulsar(profile.artifact.path, show_hidden_series=show_hidden)

    assert result.errors == []
    axes = saved_figures[-1].axes[0]
    drawn = {line.get_label(): line for line in axes.lines}
    expected = {"Polarization XX": "source1", "Polarization YY": "source2"}
    if show_hidden:
        expected.update({series.name: series.column for series in charts.FOLDED_CHART.series
                         if not series.visible})
    assert set(drawn) == set(expected)
    for label, column in expected.items():
        np.testing.assert_array_equal(drawn[label].get_xdata(), table["phase_s"])
        np.testing.assert_array_equal(drawn[label].get_ydata(), table[column])
    # The pulse is drawn, not flat: its peak stands far above the off-pulse spread.
    flux = np.asarray(drawn["Polarization XX"].get_ydata(), dtype=float)
    spread = np.median(np.abs(flux - np.median(flux)))
    assert flux.max() - np.median(flux) > 20 * spread
    period = float(table.meta["period_s"])
    assert axes.get_xlim() == pytest.approx((0, charts.folded_x_axis_maximum(period, 1)))


# ---------------------------------------------------------------------------
# Photometry overlay and zero-point diagnostic
# ---------------------------------------------------------------------------


@pytest.fixture
def ngc5128_replayed(frame_path, monkeypatch, tmp_path, saved_figures):
    """``run_photometry`` on NGC 5128 B, calibrated against the recorded
    APASS and VSX rows instead of the network."""
    from algorithms.query import runner
    from tools.fieldcal_reference import replay_catalog_sources, replay_variable_sources
    from tools.photometry import run_photometry_on_target

    def query(names, **kwargs):
        if names == ["VSX"]:
            return replay_variable_sources("ngc5128_b_002")
        return replay_catalog_sources("ngc5128_b_002", fixture="full_response")

    monkeypatch.setattr(runner, "query_catalogs", query)
    result = run_photometry_on_target(frame_path("ngc5128_b"), catalogs=["APASS"],
                                     use_field_cal=True, output_dir=tmp_path)
    assert result.errors == []
    assert result.zero_point is not None
    overlay, zero_point = saved_figures[-2:]
    return result, overlay, zero_point


@pytest.mark.slow
def test_overlay_markers_sit_on_their_stars(ngc5128_replayed, frame_image):
    """Positions are FITS (1-based) pixels; the image must be drawn on the
    same grid. It was not: every marker sat one pixel up and right."""
    import sep

    _, overlay, _ = ngc5128_replayed
    data, _ = frame_image("ngc5128_b")
    axes = overlay.axes[0]
    image = axes.get_images()[0]
    ny, nx = data.shape
    assert image.get_extent() == [0.5, nx + 0.5, 0.5, ny + 0.5]
    np.testing.assert_allclose(image.get_array(), data)

    markers = _offsets(axes.collections[0])
    assert len(markers) > 50
    # The eight numbered brightest sources, each centroided independently in
    # array coordinates by sep and converted to FITS pixels.
    brightest = _offsets(axes.collections[1])
    assert len(brightest) == 8
    image_data = np.ascontiguousarray(data, dtype=float)
    background = sep.Background(image_data)
    x0, y0, flags = sep.winpos(image_data - background, brightest[:, 0] - 1, brightest[:, 1] - 1, 2.0)
    good = flags == 0
    assert good.sum() >= 6
    np.testing.assert_allclose(x0[good] + 1, brightest[good, 0], atol=0.3)
    np.testing.assert_allclose(y0[good] + 1, brightest[good, 1], atol=0.3)


@pytest.mark.slow
def test_stars_dropped_before_the_fit_are_not_called_outliers(ngc5128_replayed):
    """Six of NGC 5128 B's 35 calibration stars have no instrumental error,
    so the solver drops them before fitting; its outlier loop rejects none.
    The plot called all six "rejected outlier"."""
    result, _, figure = ngc5128_replayed
    left, right = figure.axes[:2]

    labels = [text.get_text() for text in left.get_legend().get_texts()]
    assert labels[:2] == ["kept in fit (29)", "not fitted: no instrumental error (6)"]
    assert not any("rejected" in label for label in labels)
    assert "29 kept, 0 rejected, 6 not fitted" in figure.get_suptitle()
    assert result.zero_point.source_count == 29


def _calibration_star(mag, ref_mag, mag_error, ref_mag_error=0.02):
    return SimpleNamespace(mag=mag, ref_mag=ref_mag, mag_error=mag_error,
                           ref_mag_error=ref_mag_error, catalog_name="APASS")


def test_the_zero_point_plot_draws_the_solve_it_reports(tmp_path, saved_figures):
    """Kept, rejected and unfitted stars, the fitted line, each star's
    measurement error and the fitted extra scatter, against the solver."""
    from algorithms.fieldcal.solution import _calc_solution_with_mask
    from tools.photometry_pipeline import ZeroPointResolution, plot_zero_point_solution

    rng = np.random.default_rng(7)
    mags = np.linspace(-10.0, -5.0, 20)
    stars = [_calibration_star(m, m + 21.0 + rng.normal(0, 0.03), 0.01) for m in mags]
    stars.append(_calibration_star(-7.0, -7.0 + 21.0 + 1.5, 0.01))  # an outlier
    stars.append(_calibration_star(-4.5, -4.5 + 21.0 + 0.2, 0.0))  # no instrumental error
    (m0, m0_error, scatter, _, _), kept = _calc_solution_with_mask(stars)
    zero_point = ZeroPointResolution(
        value=m0, source="field-cal", verified=True, calibration_sources=stars,
        diagnostics={"zero_point_error_mag": m0_error, "zero_point_slop": scatter},
    )

    assert plot_zero_point_solution(zero_point, tmp_path / "zp.png") is not None

    figure = saved_figures[-1]
    left, right = figure.axes[:2]
    mag = np.array([s.mag for s in stars])
    ref = np.array([s.ref_mag for s in stars])
    kept_rows, rejected_rows, unfitted_rows = kept, np.zeros(len(stars), bool), np.zeros(len(stars), bool)
    rejected_rows[20], unfitted_rows[21] = True, True
    assert kept_rows.sum() == 20 and not kept_rows[20] and not kept_rows[21]

    for label, rows in (("kept in fit (20)", kept_rows), ("rejected outlier (1)", rejected_rows),
                        ("not fitted: no instrumental error (1)", unfitted_rows)):
        np.testing.assert_allclose(_offsets(_labelled(left, label)), np.c_[mag[rows], ref[rows]])
    fit = _labelled(left, f"fit: ref_mag = mag + {m0:.3f}")
    np.testing.assert_allclose(fit.get_ydata(), np.asarray(fit.get_xdata()) + m0)

    residual = ref - mag - m0
    np.testing.assert_allclose(
        _offsets(_labelled(right, "kept in fit (bars: measurement error)")),
        np.c_[mag[kept_rows], residual[kept_rows]],
    )
    # One bar per fitted star, as long as the error the fit weighed it with.
    bars = right.containers[0].lines[2][0]
    fitted = ~unfitted_rows
    half_lengths = [abs(segment[1, 1] - segment[0, 1]) / 2 for segment in bars.get_segments()]
    np.testing.assert_allclose(half_lengths, np.hypot(0.01, 0.02) * np.ones(fitted.sum()))
    assert scatter > 0
    band = _labelled(right, f"additional scatter ±{scatter:.3f} mag")
    band_y = band.get_patch_transform().transform(band.get_path().vertices)[:, 1]
    np.testing.assert_allclose((band_y.min(), band_y.max()), (-scatter, scatter))
    assert "20 kept, 1 rejected, 1 not fitted" in figure.get_suptitle()


# ---------------------------------------------------------------------------
# HR diagram
# ---------------------------------------------------------------------------


def test_the_hr_fit_draws_the_members_and_the_fitted_isochrone(tmp_path, monkeypatch, saved_figures):
    from algorithms.hrdiagram_py import hrfit, isochrones
    from tools import config

    track = np.zeros((4, 23))
    track[:, 0], track[:, 1] = 8.60, 0.0
    track[:, 19:22] = [[10.0, 11.0, 9.0], [8.0, 9.0, 7.0], [6.0, 6.8, 5.4], [4.0, 4.6, 3.3]]
    np.save(tmp_path / "Girardi_8.60_0.00.npy", track)
    members = pd.DataFrame({
        "BP": [21.0, 19.0, 17.5], "RP": [19.0, 17.0, 16.2], "G": [20.0, 18.0, 16.9],
        "BP_err": [0.01] * 3, "RP_err": [0.01] * 3, "G_err": [0.01] * 3,
    })
    monkeypatch.setattr(config, "ISOCHRONE_DIR", tmp_path)

    report = isochrones.fit_and_compare(
        members, {"log_age": 8.60, "distance_kpc": 1.0, "ebv": 0.0, "age_myr": 400.0}, "local",
        members_csv_path=tmp_path / "members.csv", out_png=tmp_path / "fit.png",
        logage_half_width=0.0, max_error=1.0,
    )

    axes = saved_figures[-1].axes[0]
    fitted = report["fitted"]
    df = hrfit.load_photometry(tmp_path / "members.csv", "BP", "RP", "G", max_error=1.0)
    colour, mag = hrfit.to_absolute_cmd(df, "BP", "RP", "G", fitted["distance_kpc"], fitted["ebv"])
    np.testing.assert_allclose(_offsets(_labelled(axes, "Photometry")), np.c_[colour, mag])
    # The grid's rows as points: no segment joins two evolutionary phases.
    np.testing.assert_allclose(_offsets(_labelled(axes, "Isochrone")),
                               np.c_[track[:, 20] - track[:, 21], track[:, 19]])
    assert len(axes.lines) == 0
    assert axes.yaxis_inverted()
    assert axes.get_ylabel() == "M$_{G}$"


# ---------------------------------------------------------------------------
# Radio spectrum and field SED
# ---------------------------------------------------------------------------

# 3C 48 (Jy), steep and curved enough that both fits are drawn.
_FREQ_HZ = [74e6, 178e6, 365e6, 408e6, 750e6, 1.4e9, 2.7e9, 4.85e9, 8.4e9, 15e9]
_FLUX_JY = [60.0, 50.0, 37.0, 34.0, 25.0, 16.0, 9.3, 5.5, 3.2, 1.9]


def test_a_radio_spectrum_draws_its_points_and_both_fits(artifact_dir, saved_figures):
    from algorithms.radio import spectral_fitting
    from tools.radio_sources import analyze_source_spectrum

    result = analyze_source_spectrum(name="3C 48", frequencies_hz=_FREQ_HZ, fluxes_jy=_FLUX_JY)

    assert result.status == "ok"
    fit = result.preview[0]
    axes = saved_figures[-1].axes[0]
    np.testing.assert_allclose(_offsets(_labelled(axes, "Measured flux")), np.c_[_FREQ_HZ, _FLUX_JY])
    power_law = fit["power_law"]
    curve = next(line for line in axes.lines if line.get_label().startswith("Power law"))
    np.testing.assert_allclose(
        curve.get_ydata(),
        spectral_fitting.evaluate_power_law(curve.get_xdata(), power_law["amplitude"],
                                            power_law["spectral_index"]),
    )
    assert f"alpha={power_law['spectral_index']:.2f}" in curve.get_label()
    assert fit["log_parabola"] is not None
    parabola = next(line for line in axes.lines if line.get_label().startswith("Log-parabola"))
    lp = fit["log_parabola"]
    np.testing.assert_allclose(
        parabola.get_ydata(),
        spectral_fitting.evaluate_log_parabola(parabola.get_xdata(), lp["curvature"],
                                               lp["spectral_index_at_ref"], lp["log_amplitude"]),
    )
    assert (axes.get_xscale(), axes.get_yscale()) == ("log", "log")
    assert (axes.get_xlabel(), axes.get_ylabel()) == ("Frequency (Hz)", "Flux density (Jy)")


def test_a_csv_spectrum_is_labelled_with_its_own_columns(artifact_dir, tmp_path, saved_figures):
    """A CSV may be in any units, so the plot must not claim Hz and Jy."""
    from tools.radio_sources import analyze_source_spectrum

    path = tmp_path / "spectrum.csv"
    pd.DataFrame({"freq_mhz": np.array(_FREQ_HZ) / 1e6, "flux_mjy": np.array(_FLUX_JY) * 1e3}).to_csv(
        path, index=False)

    result = analyze_source_spectrum(csv_path=str(path))

    assert result.status == "ok"
    axes = saved_figures[-1].axes[0]
    assert (axes.get_xlabel(), axes.get_ylabel()) == ("freq_mhz", "flux_mjy")
    np.testing.assert_allclose(_offsets(_labelled(axes, "Measured flux")),
                               np.c_[np.array(_FREQ_HZ) / 1e6, np.array(_FLUX_JY) * 1e3])


def test_a_field_sed_draws_each_source_with_its_own_fit(tmp_path, saved_figures):
    from matplotlib.colors import to_rgba

    from algorithms.radio import spectral_fitting
    from tools.radio_sources import _plot_field_sed

    freq = np.array(_FREQ_HZ)
    spectra = {"3C 48": (freq, np.array(_FLUX_JY)), "flat": (freq, np.array(_FLUX_JY) ** 0.2)}
    fits = {name: spectral_fitting.analyze_spectrum(*spectra[name]) for name in spectra}

    _plot_field_sed(spectra, fits, tmp_path / "sed.png")

    axes = saved_figures[-1].axes[0]
    assert len(axes.collections) == len(axes.lines) == 2
    for points, line, (name, (x, y)) in zip(axes.collections, axes.lines, spectra.items()):
        np.testing.assert_allclose(_offsets(points), np.c_[x, y])
        law = fits[name]["power_law"]
        assert line.get_label() == f"{name} (alpha={law['spectral_index']:.2f})"
        np.testing.assert_allclose(
            line.get_ydata(),
            spectral_fitting.evaluate_power_law(line.get_xdata(), law["amplitude"], law["spectral_index"]),
        )
        np.testing.assert_allclose(points.get_facecolor()[0], to_rgba(line.get_color()))
    assert [text.get_text() for text in axes.texts] == list(spectra)
    assert (axes.get_xlabel(), axes.get_ylabel()) == ("Frequency (Hz)", "Flux density (Jy)")
