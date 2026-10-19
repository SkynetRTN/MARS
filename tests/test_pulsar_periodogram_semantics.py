"""PUL-01/04/08: preserve what a spectrum measured across tool handoffs."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.table import Table

from tools.pulsar import compute_pulsar_periodogram, fold_pulsar_lightcurve, plot_pulsar


@pytest.fixture
def lightcurve(tmp_path):
    # Independent signal: two feeds observe the same 2-Hz oscillation.
    time = np.arange(160) * 0.05
    table = Table({
        "time_s": time,
        "source1": np.sin(4 * np.pi * time),
        "source2": 0.5 * np.sin(4 * np.pi * time + 0.3),
    })
    table.meta["background_subtracted"] = True
    path = tmp_path / "two-feeds.ecsv"
    table.write(path, format="ascii.ecsv")
    return path


@pytest.mark.parametrize("freq_mode", [False, True])
@pytest.mark.parametrize("channel,label", [
    ("sum", "Sum"),
    ("source1", "Polarization XX"),
    ("source2", "Polarization YY"),
])
def test_periodogram_channel_survives_artifact_roundtrip(
    lightcurve, artifact_dir, freq_mode, channel, label
):
    spectrum = compute_pulsar_periodogram(
        lightcurve, channel=channel, freq_mode=freq_mode,
        start=1.8 if freq_mode else 0.4,
        stop=2.2 if freq_mode else 0.6, steps=80,
    )
    assert spectrum.errors == []
    table = Table.read(spectrum.artifact.path, format="ascii.ecsv")
    assert table.meta["channel"] == channel
    rendered = plot_pulsar(spectrum.artifact.path)
    assert rendered.errors == []
    assert rendered.series[0] == label


@pytest.mark.parametrize("freq_mode", [False, True])
def test_periodogram_candidates_have_explicit_foldable_units(
    lightcurve, artifact_dir, freq_mode
):
    spectrum = compute_pulsar_periodogram(
        lightcurve, freq_mode=freq_mode,
        start=1.8 if freq_mode else 0.4,
        stop=2.2 if freq_mode else 0.6, steps=80,
    )
    assert spectrum.errors == []
    assert spectrum.search_unit == ("Hz" if freq_mode else "s")
    assert spectrum.peak_period_s == pytest.approx(0.5, abs=0.003)
    assert spectrum.peak_frequency_hz == pytest.approx(2.0, abs=0.012)
    candidates = spectrum.model_dump(mode="json")["top_peaks"]
    assert len(candidates) > 1
    for peak in candidates:
        assert set(peak) == {"period_s", "frequency_hz", "power"}
        assert peak["period_s"] * peak["frequency_hz"] == pytest.approx(1.0)
        assert 0.4 <= peak["period_s"] <= 0.6
    assert candidates[0]["period_s"] == spectrum.peak_period_s
    assert candidates[0]["frequency_hz"] == spectrum.peak_frequency_hz
    assert candidates[0]["power"] == spectrum.peak_power
    folded = fold_pulsar_lightcurve(lightcurve, candidates[0]["period_s"])
    assert folded.errors == []
    assert folded.period_s == pytest.approx(0.5, abs=0.003)
    table = Table.read(spectrum.artifact.path, format="ascii.ecsv")
    column, unit = ("frequency_hz", "Hz") if freq_mode else ("period_s", "s")
    assert str(table[column].unit) == unit
    assert table.meta["search_unit"] == spectrum.search_unit


@pytest.mark.parametrize("freq_mode", [False, True])
@pytest.mark.parametrize("channel", [None, "unrecognised", ["sum"]])
def test_legacy_periodogram_does_not_guess_channel(
    tmp_path, artifact_dir, freq_mode, channel
):
    column = "frequency_hz" if freq_mode else "period_s"
    table = Table({column: [0.4, 0.5, 0.6], "power": [1.0, 3.0, 2.0]})
    if channel is not None:
        table.meta["channel"] = channel
    # The column remains authoritative even with stale/missing mode metadata.
    table.meta["freq_mode"] = not freq_mode
    path = tmp_path / "legacy.ecsv"
    table.write(path, format="ascii.ecsv")
    rendered = plot_pulsar(path)
    assert rendered.errors == []
    assert rendered.series == ["Unknown channel"]
    assert rendered.x_axis_label == ("Frequency (Hz)" if freq_mode else "Period (s)")
    assert rendered.x_axis_type == ("linear" if freq_mode else "logarithmic")


@pytest.mark.parametrize("freq_mode", [False, True])
def test_rendered_axes_match_spectrum_mode(
    lightcurve, artifact_dir, freq_mode, monkeypatch
):
    from matplotlib.figure import Figure

    spectrum = compute_pulsar_periodogram(
        lightcurve, freq_mode=freq_mode, channel="source2",
        start=1.8 if freq_mode else 0.4,
        stop=2.2 if freq_mode else 0.6, steps=80,
    )
    table = Table.read(spectrum.artifact.path, format="ascii.ecsv")
    observed = []
    save = Figure.savefig

    def inspect_then_save(figure, *args, **kwargs):
        axes = figure.axes[0]
        assert axes.get_xlabel() == ("Frequency (Hz)" if freq_mode else "Period (s)")
        assert axes.get_xscale() == ("linear" if freq_mode else "log")
        assert axes.lines[0].get_label() == "Polarization YY"
        column = "frequency_hz" if freq_mode else "period_s"
        np.testing.assert_array_equal(axes.lines[0].get_xdata(), table[column])
        np.testing.assert_array_equal(axes.lines[0].get_ydata(), table["power"])
        np.testing.assert_allclose(
            axes.collections[0].get_offsets(),
            [[table.meta["peak_x"], table.meta["peak_power"]]],
        )
        observed.append(True)
        return save(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", inspect_then_save)
    rendered = plot_pulsar(spectrum.artifact.path)
    assert rendered.errors == []
    assert observed == [True]


@pytest.mark.parametrize("freq_mode,start,stop,unit", [
    (False, 0.1, 3.0, "s"),
    (True, 0.1, 10.0, "Hz"),
])
def test_default_search_bounds_report_their_units(
    lightcurve, artifact_dir, freq_mode, start, stop, unit
):
    spectrum = compute_pulsar_periodogram(lightcurve, freq_mode=freq_mode, steps=100)
    assert spectrum.errors == []
    assert spectrum.search_start == start
    assert spectrum.search_stop == stop
    assert spectrum.search_unit == unit
