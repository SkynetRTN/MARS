"""Correctness controls for M5 folded-artifact, diagnostic and audio handoffs."""

from pathlib import Path

import numpy as np
import pytest
from astropy.table import Table

from tools.pulsar import (
    compute_pulsar_periodogram,
    fold_pulsar_lightcurve,
    plot_pulsar,
    sonify_pulsar,
)


@pytest.mark.parametrize("display_period", [1, 2])
def test_fold_artifact_persists_display_settings_and_png_extent(
    tmp_path, artifact_dir, monkeypatch, display_period,
):
    from matplotlib.figure import Figure

    saved = []
    savefig = Figure.savefig

    def capture(figure, *args, **kwargs):
        saved.append(figure.axes[0])
        return savefig(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capture)
    path = tmp_path / "profile.ecsv"
    Table({"time_s": [0., .5, 1., 1.5], "source1": [99., 2., 4., 6.]}).write(
        path, format="ascii.ecsv",
    )
    result = fold_pulsar_lightcurve(
        path, 2., bins=4, phase=.25, display_period=display_period, cal=2.,
    )
    assert result.errors == []
    table = Table.read(result.artifact.path, format="ascii.ecsv")
    assert table.meta["period_s"] == 2.
    assert table.meta["bins"] == 4
    assert table.meta["phase"] == .25
    assert table.meta["cal"] == 2.
    assert table.meta["display_period"] == display_period

    plotted = plot_pulsar(result.artifact.path)
    assert plotted.errors == []
    assert plotted.warnings == []
    assert Path(plotted.artifact.path).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    axes = saved[-1]
    assert axes.get_xlim() == (0., 2.1 * display_period)
    np.testing.assert_array_equal(axes.lines[0].get_xdata(), table["phase_s"])
    assert np.all(axes.lines[0].get_xdata() <= axes.get_xlim()[1])


@pytest.mark.parametrize("values", [[4., 4., 4., 4.], [3., 6., 9., 12.]])
def test_undefined_fold_concentration_warns_in_fold_and_audio(
    tmp_path, artifact_dir, values,
):
    # One bin cannot support a concentration diagnostic, even when nonconstant
    # input samples have a perfectly valid mean. Flat multi-bin data also
    # cannot validate a pulse.
    times = [0., .25, .5, .75] if len(set(values)) == 1 else [0., 1., 2., 3.]
    path = tmp_path / "undefined.ecsv"
    Table({"time_s": times, "source1": values}).write(path, format="ascii.ecsv")
    folded = fold_pulsar_lightcurve(path, 1., bins=4)
    assert folded.errors == []
    assert folded.pulse_snr is None
    warnings = {w.code: w.message for w in folded.warnings}
    assert "weak_or_absent_pulse" in warnings
    assert "cannot" in warnings["weak_or_absent_pulse"].lower()

    audio = sonify_pulsar(path, period_s=1., bins=4, audio_seconds=.01)
    assert audio.errors == []
    assert audio.pulse_snr is None
    assert "weak_or_absent_pulse" in {w.code for w in audio.warnings}


def test_undefined_peak_fold_concentration_is_disclosed(tmp_path, artifact_dir):
    # Fixed single-trial spectrum: only two phase bins are observed, fewer
    # than the four needed for the empirical concentration diagnostic.
    path = tmp_path / "two_phase_bins.ecsv"
    Table({"time_s": [0., .5, 1.], "source1": [9., 0., 9.]}).write(
        path, format="ascii.ecsv",
    )
    result = compute_pulsar_periodogram(path, start=1., stop=1.001, steps=1)
    assert result.errors == []
    assert result.peak_period_s == 1.
    assert result.peak_power > 0.
    assert result.peak_fold_snr is None
    warnings = {w.code: w.message for w in result.warnings}
    assert "peak_does_not_fold" in warnings
    assert "cannot" in warnings["peak_does_not_fold"].lower()


def test_nonfinite_bin_mean_is_rejected_before_artifact_or_audio(tmp_path, artifact_dir):
    # The retained phase-zero ties must not overflow into a successful profile.
    path = tmp_path / "overflowed_mean.ecsv"
    Table({"time_s": [0., .25, 1.], "source1": [1e308, 1., 1e308]}).write(
        path, format="ascii.ecsv",
    )
    with np.errstate(over="raise", invalid="raise"):
        for result in (
            fold_pulsar_lightcurve(path, 1., bins=4),
            sonify_pulsar(path, period_s=1., bins=4, audio_seconds=.01),
        ):
            assert [error.code for error in result.errors] == ["invalid_input"]
            assert result.artifact is None


def test_sparse_audio_discloses_relative_phase_compression_even_without_drift(
    tmp_path, artifact_dir,
):
    # Eight occupied bins out of sixteen. With a 1 s period and 64 Hz output,
    # integer synthesis has an exact whole-loop duration; that does not make
    # the missing middle phase bins audible as a gap.
    path = tmp_path / "sparse.ecsv"
    Table({
        "time_s": [0., .0625, .125, .1875, .75, .8125, .875, .9375],
        "source1": [0., 1., 0., 1., 0., 1., 0., 1.],
    }).write(
        path, format="ascii.ecsv",
    )
    audio = sonify_pulsar(
        path, period_s=1., bins=16, sample_rate=64, audio_seconds=1.,
    )
    assert audio.errors == []
    assert audio.playback_stretch == pytest.approx(1.)
    warnings = {w.code: w.message for w in audio.warnings}
    assert "playback_not_real_time" in warnings
    assert "phase" in warnings["playback_not_real_time"].lower()
    assert "occupied" in warnings["playback_not_real_time"].lower()
