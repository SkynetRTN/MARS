"""M5 investigation: characterize pulsar boundaries, without accepting defects.

The tests named ``characterization`` deliberately describe current behavior.
In particular, endpoint loss, a silent/empty successful fold, index pairing of
unmatched bins and clipping a second displayed cycle are BUG PINS, not acceptance
criteria for a future repair. Literal small fixtures provide independent phase,
flux and coordinate controls; no external data or numerical search is needed.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest
from astropy.table import Table

from algorithms.pulsar import folding
from tools.pulsar import (
    compute_pulsar_periodogram,
    fold_pulsar_lightcurve,
    load_pulsar_lightcurve,
    plot_pulsar,
    sonify_pulsar,
)


@pytest.fixture
def saved_axes(monkeypatch):
    """Observe the actual PNG trace and limits while keeping rendering real."""
    from matplotlib.figure import Figure

    saved = []
    savefig = Figure.savefig

    def capture(figure, *args, **kwargs):
        saved.append(figure.axes[0])
        return savefig(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capture)
    return saved


@pytest.mark.parametrize("times, cadence, phase_s, flux", [
    ([0., .5, 1., 1.5], .5, [.6875, 1.0625, 1.4375], [2., 4., 6.]),
    ([0., 1., 2., 3.], 1., [1.125], [4.]),
], ids=["seconds-like", "index-like"])
def test_characterization_standard_axis_is_used_as_seconds_without_index_rescaling(
    tmp_path, artifact_dir, saved_axes, times, cadence, phase_s, flux,
):
    """TS-08's retired index/count division is absent from maintained callers.

    Both synthetic files declare P=2 s. The first has actual half-second
    coordinates; the second has sample-index-like coordinates. The latter is
    still interpreted as seconds, not inferred to mean half-second bins. These
    literals establish current semantics, not the unknown upstream file format.
    """
    raw = tmp_path / "standard.txt"
    raw.write_text(
        "# Input file\n# P_topo (ms) = 2000\n"
        + "\n".join(f"{x} {y}" for x, y in zip(times, [99., 2., 4., 6.])),
    )
    loaded = load_pulsar_lightcurve(raw, subtract_background=False)
    assert loaded.errors == []
    assert loaded.flavour == "standard"
    assert loaded.sample_cadence_s == cadence
    lightcurve = Table.read(loaded.artifact.path, format="ascii.ecsv")
    np.testing.assert_array_equal(lightcurve["time_s"], times)

    folded = fold_pulsar_lightcurve(loaded.artifact.path, 2., bins=4)
    assert folded.errors == []
    table = Table.read(folded.artifact.path, format="ascii.ecsv")
    np.testing.assert_array_equal(table["phase_s"], phase_s)
    np.testing.assert_array_equal(table["source1"], flux)
    assert table.meta["period_s"] == 2.

    plotted = plot_pulsar(folded.artifact.path)
    assert plotted.errors == []
    assert plotted.x_axis_label == "Time (s)"
    np.testing.assert_array_equal(saved_axes[-1].lines[0].get_xdata(), phase_s)
    np.testing.assert_array_equal(saved_axes[-1].lines[0].get_ydata(), flux)
    assert Path(plotted.artifact.path).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_characterization_origin_and_period_neighbors_fold_to_the_upper_boundary():
    """TS-25: a display convention becomes sample loss only at later binning.

    A circular [0, P) coordinate would put samples 0, 3 and 5 at zero. The
    preceding representable float (sample 2) also rounds up to P in the
    intermediate P+remainder addition, while the following float stays above 0.
    The fold itself keeps every sample paired with its original flux.
    """
    times = np.array([0., .5, np.nextafter(1., 0.), 1., np.nextafter(1., np.inf), 2.])
    phase_s, flux, second = folding.fold_to_phase(times, np.arange(6.), None, 1.)

    np.testing.assert_array_equal(phase_s, [1., 1., 1., 1., .5, 2.**-52])
    np.testing.assert_array_equal(flux, [0., 2., 3., 5., 1., 4.])
    assert second is None


def test_characterization_exact_phase_pulses_are_lost_before_artifact_and_audio(
    tmp_path, artifact_dir,
):
    """BUG PIN, TS-24 + TS-25: three pulses disappear, not just one sample.

    For a 1 s cycle, quarter-second samples and four circular bins, the three
    phase-zero values average to 9 and the other bins to zero: [9, 0, 0, 0].
    Current folding moves those three samples to P, then drops all maximum ties.
    This public consequence is stronger than the existing single-bin edge pin.
    """
    raw = tmp_path / "exact_pulse.txt"
    raw.write_text(
        "# Input file\n# P_topo (ms) = 1000\n"
        "0 9\n.25 0\n.5 0\n.75 0\n1 9\n1.25 0\n1.5 0\n1.75 0\n2 9\n",
    )
    loaded = load_pulsar_lightcurve(raw, subtract_background=False)
    assert loaded.errors == []
    folded = fold_pulsar_lightcurve(loaded.artifact.path, 1., bins=4)
    assert folded.errors == []
    assert folded.samples_folded == 9  # counted before any endpoint loss
    assert folded.bins_filled == 3
    assert folded.pulse_snr is None
    assert folded.warnings == []
    table = Table.read(folded.artifact.path, format="ascii.ecsv")
    np.testing.assert_array_equal(table["phase_s"], [.34375, .53125, .71875])
    np.testing.assert_array_equal(table["source1"], [0., 0., 0.])
    assert np.max(table["source1"]) < 9.  # independent circular-bin pulse height

    audio = sonify_pulsar(loaded.artifact.path, period_s=1., bins=4, audio_seconds=.01)
    assert audio.errors == []
    assert audio.pulse_snr is None
    codes = {warning.code for warning in audio.warnings}
    assert "flat_light_curve" in codes
    assert "weak_or_absent_pulse" not in codes
    with wave.open(audio.artifact.path, "rb") as handle:
        assert handle.getnframes() == 441
        pcm = np.frombuffer(handle.readframes(441), dtype="<i2")
    assert np.count_nonzero(pcm) == 0


def test_characterization_an_all_boundary_fold_succeeds_with_an_empty_artifact(
    tmp_path, artifact_dir,
):
    """BUG PIN: three phase-zero samples have mean 6, but every bin is empty."""
    raw = tmp_path / "all_boundary.txt"
    raw.write_text("# Input file\n# P_topo (ms) = 1000\n0 3\n1 6\n2 9\n")
    loaded = load_pulsar_lightcurve(raw, subtract_background=False)
    assert loaded.errors == []
    folded = fold_pulsar_lightcurve(loaded.artifact.path, 1., bins=4)

    assert folded.errors == []
    assert folded.samples_folded == 3
    assert folded.bins_filled == 0
    assert folded.artifact.row_count == 0
    assert folded.pulse_snr is None
    assert folded.warnings == []
    assert len(Table.read(folded.artifact.path, format="ascii.ecsv")) == 0
    audio = sonify_pulsar(loaded.artifact.path, period_s=1., bins=4, audio_seconds=.01)
    assert [error.code for error in audio.errors] == ["invalid_input"]
    assert audio.artifact is None


def test_characterization_endpoint_loss_withholds_the_public_peak_fold_diagnostic(
    tmp_path, artifact_dir,
):
    """BUG PIN: stage 2 uses the same defective fold for its concentration check.

    This is one fixed 1 s trial, not a period-recovery or false-alarm test. Its
    positive finite spectrum still receives no empirical fold diagnostic and
    no weak-fold warning because the exact-phase pulses were discarded.
    """
    path = tmp_path / "one_trial_pulse.ecsv"
    Table({
        "time_s": [0., .25, .5, .75, 1., 1.25, 1.5, 1.75, 2.],
        "source1": [9., 0., 0., 0., 9., 0., 0., 0., 9.],
    }).write(path, format="ascii.ecsv")
    spectrum = compute_pulsar_periodogram(path, start=1., stop=1.001, steps=1)

    assert spectrum.errors == []
    assert spectrum.evaluated_trials == 1
    assert spectrum.peak_period_s == 1.
    assert np.isfinite(spectrum.peak_power) and spectrum.peak_power > 0.
    assert spectrum.peak_fold_snr is None
    assert "peak_does_not_fold" not in {warning.code for warning in spectrum.warnings}
    table = Table.read(spectrum.artifact.path, format="ascii.ecsv")
    np.testing.assert_array_equal(table["period_s"], [1.])
    assert np.isfinite(table["power"]).all() and table["power"][0] > 0.


@pytest.mark.parametrize("bins, retained_flux", [
    (99, [0., 9.]),
    (100, [0.]),
])
def test_characterization_endpoint_loss_can_change_with_bin_division_roundoff(
    tmp_path, artifact_dir, bins, retained_flux,
):
    """BUG PIN: the old report's 'always discards' is numerically too strong.

    Two phase-zero pulses of height 9 should survive either bin count. The
    observed range is .5 s: .5/(.5/99) rounds below 99, retaining the maxima;
    the 100-bin default evaluates exactly to 100 and drops both of them.
    """
    path = tmp_path / "rounded_edge.ecsv"
    Table({"time_s": [0., .5, 1.], "source1": [9., 0., 9.]}).write(
        path, format="ascii.ecsv",
    )
    result = fold_pulsar_lightcurve(path, 1., bins=bins)
    assert result.errors == []
    assert result.samples_folded == 3
    table = Table.read(result.artifact.path, format="ascii.ecsv")

    np.testing.assert_array_equal(table["source1"], retained_flux)


def test_characterization_independently_supported_bins_are_paired_at_wrong_phases():
    """BUG PIN, TS-26: latent helper behavior if callers bin unequal supports.

    Only x=.5 and x=2.5 match. Their correct differences are [9, 10] and sums
    [11, 14]. Index pairing instead uses channel 1's x=1.5 against channel 2's
    x=2.5 for the second value and truncates channel 1's remaining support.
    """
    x1, y1 = folding.fold_and_bin(np.arange(5.), np.arange(10., 15.), 4, 8., 0.)
    x2, y2 = folding.fold_and_bin(np.array([0., 2., 4.]), np.array([1., 2., 4.]), 4, 8., 0.)
    np.testing.assert_array_equal(x1, [.5, 1.5, 2.5, 3.5])
    np.testing.assert_array_equal(x2, [.5, 2.5])
    difference, total = folding.difference_and_sum(y1, y2)

    np.testing.assert_array_equal(difference, [9., 9.])
    np.testing.assert_array_equal(total, [11., 13.])
    assert difference[1] != 10.
    assert total[1] != 14.


def test_current_public_channels_share_bin_support_and_keep_difference_alignment(
    tmp_path, artifact_dir,
):
    """TS-26 control: finite synchronized channels cannot lose different bins."""
    path = tmp_path / "two_channels.ecsv"
    Table({
        "time_s": [0., .25, .5, .75, 1.],
        "source1": [90., 2., 4., 6., 80.],
        "source2": [9., 10., 20., 30., 8.],
    }).write(path, format="ascii.ecsv")
    result = fold_pulsar_lightcurve(path, 1., bins=4)
    assert result.errors == []
    table = Table.read(result.artifact.path, format="ascii.ecsv")

    np.testing.assert_array_equal(table["phase_s"], [.34375, .53125, .71875])
    np.testing.assert_array_equal(table["source1"], [2., 4., 6.])
    np.testing.assert_array_equal(table["source2"], [10., 20., 30.])
    np.testing.assert_array_equal(table["difference"], [-8., -16., -24.])
    np.testing.assert_array_equal(table["sum"], [12., 24., 36.])


def test_current_public_channel_holes_are_rejected_instead_of_independently_binned(
    tmp_path, artifact_dir,
):
    """M1 finiteness guard prevents a missing channel row reaching TS-26."""
    path = tmp_path / "channel_hole.ecsv"
    Table({
        "time_s": [0., .25, .5, .75, 1.],
        "source1": [90., 2., 4., 6., 80.],
        "source2": [9., 10., np.nan, 30., 8.],
    }).write(path, format="ascii.ecsv")
    result = fold_pulsar_lightcurve(path, 1., bins=4)

    assert [error.code for error in result.errors] == ["invalid_input"]
    assert result.artifact is None


def test_characterization_sparse_phase_gaps_are_erased_from_folded_audio(
    tmp_path, artifact_dir,
):
    """BUG PIN: dropped empty bins leave phase gaps the sonifier never sees.

    The second profile has a .375 s middle gap instead of .125 s. Both lose
    the origin value 99, leaving the same [0, 1, 0, 1] flux sequence. Playing
    that sequence by index produces identical whole-loop WAVs even though its
    phase spacing differs. A single global stretch value cannot disclose this
    relative timing difference.
    """
    wavs = []
    stretches = []
    for name, times, phase_s in [
        ("contiguous", [0., .125, .25, .375, .5], [.1875, .3125, .4375, .5625]),
        ("gapped", [0., .125, .25, .625, .75], [.1875, .3125, .6875, .8125]),
    ]:
        path = tmp_path / f"{name}.ecsv"
        Table({"time_s": times, "source1": [99., 0., 1., 0., 1.]}).write(
            path, format="ascii.ecsv",
        )
        folded = fold_pulsar_lightcurve(path, 1., bins=7)
        assert folded.errors == []
        table = Table.read(folded.artifact.path, format="ascii.ecsv")
        np.testing.assert_array_equal(table["phase_s"], phase_s)
        np.testing.assert_array_equal(table["source1"], [0., 1., 0., 1.])
        audio = sonify_pulsar(path, period_s=1., bins=7, audio_seconds=1.)
        assert audio.errors == []
        wavs.append(Path(audio.artifact.path).read_bytes())
        stretches.append(audio.playback_stretch)

    assert wavs[0] == wavs[1]
    assert stretches == pytest.approx([.7500907029478459, .7500907029478459])


def test_characterization_two_cycle_artifact_loses_display_extent_and_plot_clips_it(
    tmp_path, artifact_dir, saved_axes,
):
    """BUG PIN: second cycle exists in ECSV but is outside the actual PNG axes.

    A 2 s period with display_period=2 needs an extent through 4 s. The result
    advertises two cycles, but the artifact omits that setting. Its plot takes
    the one-cycle default and clips all three bins of the duplicate cycle.
    """
    path = tmp_path / "two_cycles.ecsv"
    Table({"time_s": [0., .5, 1., 1.5], "source1": [99., 2., 4., 6.]}).write(
        path, format="ascii.ecsv",
    )
    folded = fold_pulsar_lightcurve(path, 2., bins=4, display_period=2)
    assert folded.errors == []
    assert folded.display_period == 2
    table = Table.read(folded.artifact.path, format="ascii.ecsv")
    np.testing.assert_array_equal(table["phase_s"], [.6875, 1.0625, 1.4375, 2.6875, 3.0625, 3.4375])
    np.testing.assert_array_equal(table["source1"], [2., 4., 6., 2., 4., 6.])

    plotted = plot_pulsar(folded.artifact.path)
    assert plotted.errors == []
    assert plotted.warnings == []
    axes = saved_axes[-1]
    np.testing.assert_array_equal(axes.lines[0].get_xdata(), table["phase_s"])
    assert axes.get_xlim() == (0., 2.1)
    assert np.count_nonzero(axes.lines[0].get_xdata() > axes.get_xlim()[1]) == 3
