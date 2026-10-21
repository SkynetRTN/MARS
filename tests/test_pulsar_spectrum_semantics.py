"""M2 acceptance: saved spectra and rendered axes describe the searched data.

Inspect the real matplotlib figure at save time as well as the public result;
metadata alone cannot establish what a PNG actually draws.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from astropy.table import Table

from tools.pulsar import compute_pulsar_periodogram, plot_pulsar


@pytest.fixture
def saved_axes(monkeypatch):
    from matplotlib.figure import Figure

    saved = []
    savefig = Figure.savefig

    def capture(figure, *args, **kwargs):
        saved.append(figure.axes[0])
        return savefig(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capture)
    return saved


@pytest.fixture
def two_channel_curve(tmp_path):
    # Distinct signals make a channel mix-up observable in the saved powers.
    rng = np.random.default_rng(42)
    times = np.arange(256) * 0.05
    table = Table({
        "time_s": times,
        "source1": np.sin(2 * np.pi * times / 0.8) + rng.normal(0, 0.2, times.size),
        "source2": np.sin(2 * np.pi * times / 1.6) + rng.normal(0, 0.2, times.size),
    })
    path = tmp_path / "lightcurve.ecsv"
    table.write(path, format="ascii.ecsv")
    return path


@pytest.mark.parametrize("channel, label, strong_periods, weak_periods", [
    ("sum", "Sum", (0.8, 1.6), ()),
    ("source1", "Polarization XX", (0.8,), (1.6,)),
    ("source2", "Polarization YY", (1.6,), (0.8,)),
])
@pytest.mark.parametrize("freq_mode, column, unit, xlabel, scale, mode", [
    (False, "period_s", "s", "Period (s)", "log", "period"),
    (True, "frequency_hz", "Hz", "Frequency (Hz)", "linear", "frequency"),
])
def test_computed_spectrum_round_trips_channel_and_axes(
    two_channel_curve, artifact_dir, saved_axes,
    channel, label, strong_periods, weak_periods,
    freq_mode, column, unit, xlabel, scale, mode,
):
    spectrum = compute_pulsar_periodogram(
        two_channel_curve, channel=channel, freq_mode=freq_mode,
        start=0.4, stop=3.0, steps=80,
    )
    assert spectrum.errors == []
    table = Table.read(spectrum.artifact.path, format="ascii.ecsv")
    assert table.meta.get("channel") == channel
    assert str(table[column].unit) == unit
    assert table.meta["freq_mode"] is freq_mode
    # These periods come from the fixture's injected signals, independently
    # of the periodogram implementation. Both must be present in the sum;
    # each individual feed must suppress the other feed's fundamental.
    for period in strong_periods:
        coordinate = 1 / period if freq_mode else period
        index = np.argmin(np.abs(table[column] - coordinate))
        assert table["power"][index] > 20
    for period in weak_periods:
        coordinate = 1 / period if freq_mode else period
        index = np.argmin(np.abs(table[column] - coordinate))
        assert table["power"][index] < 5

    result = plot_pulsar(spectrum.artifact.path)

    assert result.errors == []
    assert result.channel == channel
    assert result.mode == mode
    assert result.x_axis_label == xlabel
    assert result.y_axis_label == "Power"
    assert result.x_axis_type == ("logarithmic" if scale == "log" else "linear")
    assert result.series[0] == label
    assert "unknown_spectrum_channel" not in [w.code for w in result.warnings]

    axes = saved_axes[-1]
    assert axes.get_xlabel() == xlabel
    assert axes.get_ylabel() == "Power"
    assert axes.get_xscale() == scale
    trace = axes.lines[0]
    assert trace.get_label() == label
    np.testing.assert_array_equal(trace.get_xdata(), table[column])
    np.testing.assert_array_equal(trace.get_ydata(), table["power"])
    np.testing.assert_array_equal(
        axes.collections[0].get_offsets(),
        [[table.meta["peak_x"], table.meta["peak_power"]]],
    )
    legend = [text.get_text() for text in axes.get_legend().get_texts()]
    assert f"Global Maxima ({table.meta['peak_x']:.6g} {unit})" in legend
    assert len(axes.lines) == 4  # spectrum plus three actual confidence lines
    for line, key in zip(axes.lines[1:], (
        "conf-1-sigma", "conf-2-sigma", "conf-3-sigma",
    )):
        np.testing.assert_array_equal(line.get_ydata(), [table.meta["confidence"][key]] * 2)
    assert Path(result.artifact.path).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("channel", [None, "unrecognized"])
@pytest.mark.parametrize("freq_metadata", [None, False, True])
@pytest.mark.parametrize("column, xs, xlabel, scale, mode, unit", [
    ("period_s", [0.5, 1.0, 2.0], "Period (s)", "log", "period", "s"),
    ("frequency_hz", [0.0, 0.5, 1.0], "Frequency (Hz)", "linear", "frequency", "Hz"),
])
def test_legacy_spectrum_uses_column_units_and_discloses_unknown_channel(
    tmp_path, artifact_dir, saved_axes, channel, freq_metadata,
    column, xs, xlabel, scale, mode, unit,
):
    # Old spectra have neither channel metadata nor Astropy column units.
    # Even a stale freq_mode flag must not relabel their saved coordinates.
    table = Table({column: xs, "power": [1.0, 4.0, 2.0]})
    table.meta.update(peak_x=xs[1], peak_power=4.0)
    if channel is not None:
        table.meta["channel"] = channel
    if freq_metadata is not None:
        table.meta["freq_mode"] = freq_metadata
    path = tmp_path / "legacy.ecsv"
    table.write(path, format="ascii.ecsv")

    result = plot_pulsar(path)

    assert result.errors == []
    assert result.channel is None
    assert result.mode == mode
    assert result.series[0] == "Unknown channel"
    assert [w.code for w in result.warnings] == ["unknown_spectrum_channel"]
    assert result.x_axis_label == xlabel
    axes = saved_axes[-1]
    assert axes.get_xlabel() == xlabel
    assert axes.get_xscale() == scale
    assert axes.lines[0].get_label() == "Unknown channel"
    np.testing.assert_array_equal(axes.lines[0].get_xdata(), xs)
    assert f"Global Maxima ({xs[1]:.6g} {unit})" in [
        text.get_text() for text in axes.get_legend().get_texts()
    ]


@pytest.mark.parametrize("channel", [np.array(["sum"]), np.array(["sum", "source1"])])
def test_array_channel_metadata_is_unknown_instead_of_raising(
    tmp_path, artifact_dir, saved_axes, channel,
):
    # Astropy serializes ndarray metadata into valid ECSV. It is not a scalar
    # channel identity, even when its sole element happens to be "sum".
    table = Table({"period_s": [0.5, 1.0, 2.0], "power": [1.0, 4.0, 2.0]})
    table.meta["channel"] = channel
    path = tmp_path / "array_channel.ecsv"
    table.write(path, format="ascii.ecsv")

    result = plot_pulsar(path)

    assert result.errors == []
    assert result.channel is None
    assert [w.code for w in result.warnings] == ["unknown_spectrum_channel"]
    assert result.series == ["Unknown channel"]
    assert saved_axes[-1].lines[0].get_label() == "Unknown channel"


@pytest.mark.parametrize("channel", ["sum", "source1"])
@pytest.mark.parametrize("freq_mode", [False, True])
def test_standard_spectrum_does_not_claim_a_polarization(
    two_channel_curve, tmp_path, artifact_dir, saved_axes, channel, freq_mode,
):
    # Standard files contain one generic flux column, with no XX/YY identity.
    data = Table.read(two_channel_curve, format="ascii.ecsv")
    raw = tmp_path / "standard.txt"
    raw.write_text(
        "# Input file\n# Candidate = single-flux\n"
        + "".join(f"{time} {value}\n" for time, value in zip(data["time_s"], data["source1"])),
        encoding="utf-8",
    )
    spectrum = compute_pulsar_periodogram(
        raw, channel=channel, freq_mode=freq_mode, subtract_background=False,
        start=0.4, stop=3.0, steps=80,
    )
    assert spectrum.errors == []
    table = Table.read(spectrum.artifact.path, format="ascii.ecsv")
    assert table.meta["flavour"] == "standard"
    assert table.meta["channel"] == channel

    result = plot_pulsar(spectrum.artifact.path)

    assert result.errors == []
    assert result.channel == channel
    assert result.series[0] == "Data"
    assert saved_axes[-1].lines[0].get_label() == "Data"
