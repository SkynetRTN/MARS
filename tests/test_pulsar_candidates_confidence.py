"""M2: explicit candidate units and a conditional finite-grid false-alarm bound."""

from __future__ import annotations

import numpy as np
import pytest
from astropy.table import Table
from astropy.timeseries import LombScargle
from scipy.stats import beta, binom

from algorithms.pulsar import periodogram, significance
from tools import pulsar


def _curve(tmp_path, times, *, meta=None):
    rng = np.random.default_rng(9042)
    values = np.sin(2 * np.pi * times / 0.8) + rng.normal(0, 0.1, len(times))
    table = Table({"time_s": times, "source1": values}, meta=meta or {})
    path = tmp_path / "curve.ecsv"
    table.write(path, format="ascii.ecsv")
    return path


@pytest.mark.parametrize("channel", ["source1", "source2", "sum"])
def test_peak_fold_diagnostic_uses_the_searched_channel(tmp_path, artifact_dir, channel):
    times = np.arange(4000) * .01
    rng = np.random.default_rng(142)
    pulse = 8 * np.exp(-((np.mod(times, 1) - .35) / .025) ** 2) + rng.normal(0, .3, times.size)
    noise = rng.normal(0, 300, times.size)
    source1, source2 = (noise, pulse) if channel == "source2" else (pulse, noise)
    path = tmp_path / "two_feeds.ecsv"
    Table({"time_s": times, "source1": source1, "source2": source2}).write(path, format="ascii.ecsv")

    result = pulsar.compute_pulsar_periodogram(
        path, channel=channel, freq_mode=True, start=1., stop=1.001, steps=1,
    )

    assert result.errors == []
    assert result.channel == channel
    assert result.peak_period_s == pytest.approx(1.)
    codes = {warning.code for warning in result.warnings}
    if channel == "sum":
        assert result.peak_fold_snr < 8
        assert "peak_does_not_fold" in codes
    else:
        assert result.peak_fold_snr > 100
        assert "peak_does_not_fold" not in codes


@pytest.mark.parametrize("freq_mode, start, stop, unit", [
    (False, 0.7, 0.9, "s"),
    (True, 1 / 0.9, 1 / 0.7, "Hz"),
])
def test_candidates_always_carry_seconds_and_hertz(
    tmp_path, artifact_dir, freq_mode, start, stop, unit,
):
    path = _curve(tmp_path, np.arange(256) * 0.05)
    result = pulsar.compute_pulsar_periodogram(
        path, freq_mode=freq_mode, start=start, stop=stop, steps=200,
    )
    assert result.errors == []
    payload = result.model_dump(mode="json")
    assert payload.get("search_unit") == unit
    assert payload["search_start"] == start
    assert payload["search_stop"] == stop
    assert payload.get("peak_frequency_hz") == pytest.approx(1.25, rel=0.005)
    assert payload["top_peaks"][0].get("period_s") == pytest.approx(0.8, rel=0.005)
    for candidate in payload["top_peaks"]:
        assert set(candidate) == {"period_s", "frequency_hz", "power"}
        assert candidate["frequency_hz"] * candidate["period_s"] == pytest.approx(1)
    table = Table.read(result.artifact.path, format="ascii.ecsv")
    assert table.meta.get("search_unit") == unit
    assert table.meta.get("search_start") == start
    assert table.meta.get("search_stop") == stop
    assert table.meta.get("top_peaks") == payload["top_peaks"]


def test_false_alarm_bound_uses_finite_sample_distribution_and_actual_grid():
    # Astropy and scipy provide independent power and distribution references.
    # The population-variance port has power = N/2 times standard LS power.
    times = np.arange(8) * 0.17
    rng = np.random.default_rng(184)
    values = np.sin(2 * np.pi * 1.25 * times) + rng.normal(0, 0.1, len(times))
    result = periodogram.compute_periodogram(
        times, values, start=0.5, stop=2.0, steps=6, freq_mode=True,
    )
    independent = LombScargle(times, values, fit_mean=False, normalization="standard")
    np.testing.assert_allclose(
        result.power * 2 / len(times), independent.power(result.x, method="slow"),
        rtol=1e-11, atol=1e-12,
    )
    trials = len(result.x)
    single_tail = beta.sf(result.peak_power * 2 / len(times), 1, (len(times) - 3) / 2)
    assert getattr(result, "false_alarm_probability_upper_bound", None) == pytest.approx(
        min(1, trials * single_tail), rel=1e-10,
    )
    assert result.false_alarm_method == "gaussian_bonferroni"
    assert result.evaluated_trials == trials
    assert result.confidence == {}
    assert result.peak_confidence_level is None
    for alpha in (0.1, 0.01, 0.001):
        reference = len(times) / 2 * beta.isf(alpha / trials, 1, (len(times) - 3) / 2)
        assert result.false_alarm_thresholds[str(alpha)] == pytest.approx(reference)


@pytest.mark.parametrize("freq_mode, start, stop, unit", [
    (False, 0.02, 3.0, "s"),
    (True, 1 / 3.0, 50.0, "Hz"),
])
def test_gap_does_not_inflate_the_default_cadence_bound(
    tmp_path, artifact_dir, freq_mode, start, stop, unit,
):
    times = np.r_[np.arange(32) * 0.01, 10 + np.arange(32) * 0.01]
    result = pulsar.compute_pulsar_periodogram(
        _curve(tmp_path, times), freq_mode=freq_mode, steps=80,
    )
    assert result.errors == []
    payload = result.model_dump(mode="json")
    assert payload["search_start"] == pytest.approx(start)
    assert payload["search_stop"] == pytest.approx(stop)
    assert payload.get("search_unit") == unit
    assert payload.get("sample_cadence_s") == pytest.approx(0.01)
    assert payload.get("suggested_min_period_s") == pytest.approx(0.02)
    assert payload.get("nyquist_period_s") is None
    assert payload.get("sampling_policy") == "median_spacing_heuristic"
    assert "sampling_limit_heuristic" in [w.code for w in result.warnings]


@pytest.mark.parametrize("gapped", [False, True])
def test_lightcurve_reports_a_nyquist_limit_only_for_uniform_sampling(
    tmp_path, artifact_dir, gapped,
):
    times = np.arange(64) * 0.01
    if gapped:
        times[32:] += 10
    result = pulsar.load_pulsar_lightcurve(_curve(tmp_path, times, meta={
        "mean_sample_interval_s": float(np.mean(np.diff(times))),
        "sample_cadence_s": 99.0,  # stale metadata must not control the bounds
    }))
    assert result.errors == []
    payload = result.model_dump(mode="json")
    assert payload.get("sample_cadence_s") == pytest.approx(0.01)
    assert payload.get("suggested_min_period_s") == pytest.approx(0.02)
    if gapped:
        assert payload.get("nyquist_period_s") is None
        assert payload.get("sampling_policy") == "median_spacing_heuristic"
    else:
        assert payload.get("nyquist_period_s") == pytest.approx(0.02)
        assert payload.get("sampling_policy") == "uniform"


def test_tool_discloses_the_noise_model_and_retires_posterior_confidence(
    tmp_path, artifact_dir,
):
    result = pulsar.compute_pulsar_periodogram(
        _curve(tmp_path, np.arange(128) * 0.05), start=0.5, stop=1.0, steps=80,
    )
    assert result.errors == []
    payload = result.model_dump(mode="json")
    assert payload.get("false_alarm_method") == "gaussian_bonferroni"
    assert 0 < payload["false_alarm_probability_upper_bound"] <= 1
    assert payload["false_alarm_assumptions"]
    assert payload["peak_confidence"] is None
    assert payload["confidence_thresholds"] == {}
    assert "false_alarm_model_assumptions" in [w.code for w in result.warnings]
    table = Table.read(result.artifact.path, format="ascii.ecsv")
    assert table.meta.get("false_alarm_method") == payload["false_alarm_method"]
    assert table.meta.get("false_alarm_thresholds") == payload["false_alarm_thresholds"]


def test_three_samples_do_not_produce_an_unjustified_false_alarm_level(tmp_path, artifact_dir):
    table = Table({"time_s": [0.0, 0.2, 0.5], "source1": [0.0, 1.0, -0.3]})
    path = tmp_path / "three.ecsv"
    table.write(path, format="ascii.ecsv")
    result = pulsar.compute_pulsar_periodogram(path, start=0.7, stop=1.0, steps=20)
    assert result.errors == []
    payload = result.model_dump(mode="json")
    assert payload.get("false_alarm_probability_upper_bound") is None
    assert payload.get("false_alarm_thresholds") == {}
    assert "false_alarm_unavailable" in [w.code for w in result.warnings]


def test_legacy_confidence_lines_are_identified_as_uncalibrated(tmp_path, artifact_dir):
    table = Table({"period_s": [0.1, 0.2, 0.3], "power": [1.0, 6.0, 2.0]}, meta={
        "channel": "sum",
        "confidence": {"conf-1-sigma": 2.0, "conf-2-sigma": 3.0, "conf-3-sigma": 4.0},
    })
    path = tmp_path / "legacy.ecsv"
    table.write(path, format="ascii.ecsv")
    result = pulsar.plot_pulsar(path)
    assert result.errors == []
    assert "legacy_confidence_uncalibrated" in [w.code for w in result.warnings]
    assert all("Confidence" not in name for name in result.series)
    assert len([name for name in result.series if "uncalibrated" in name]) == 3


@pytest.mark.parametrize("pattern", ["regular", "gapped", "irregular"])
def test_fixed_grid_gaussian_null_is_conservative_for_different_sampling(pattern):
    """Independent null simulations exercise frequency correlation and gaps.

    This is a finite empirical check alongside the analytic Beta reference,
    with a binomial rejection tolerance rather than pinned random counts.
    """
    rng = np.random.default_rng(47291)
    times = np.arange(32) * 0.1
    if pattern == "gapped":
        times[16:] += 8
    elif pattern == "irregular":
        times = np.sort(rng.uniform(0, 12, len(times)))
    exceedances = 0
    for index in range(256):
        values = rng.normal(size=len(times))
        result = periodogram.compute_periodogram(
            times, values, start=0.15, stop=3.0, steps=60, freq_mode=True,
        )
        # Float accumulation yields 61 trials here. Never substitute steps.
        assert result.evaluated_trials == len(result.x) == 61
        if index == 0:
            reference = LombScargle(times, values, fit_mean=False, normalization="standard")
            normalized = result.power * 2 / len(times)
            np.testing.assert_allclose(
                normalized, reference.power(result.x, method="slow"), atol=3e-12,
            )
            floating_mean = LombScargle(times, values, normalization="standard")
            assert np.all(normalized <= floating_mean.power(result.x, method="slow") + 3e-12)
        exceedances += result.false_alarm_probability_upper_bound <= 0.1
    assert exceedances <= binom.ppf(0.999, 256, 0.1)


def test_nearly_perfect_signal_has_finite_nonzero_noise_bound():
    times = np.arange(32) * 0.1
    result = periodogram.compute_periodogram(
        times, np.sin(2 * np.pi * times), start=1.0, stop=1.1, steps=20,
    )
    assert np.isfinite(result.false_alarm_probability_upper_bound)
    assert 0 < result.false_alarm_probability_upper_bound < 1e-20
    # A power cutoff that rounds to N/2 is unavailable, not a sufficient level.
    assert significance.threshold(0.001, 4, 200_002) is None


def test_uniform_nyquist_trial_is_a_valid_least_squares_projection():
    # At Nyquist the sine column is only roundoff. Treating it as a second
    # orthogonal regressor in the historical formula can exceed the variance.
    times = np.arange(64) * 0.1
    values = np.cos(2 * np.pi * 5 * times) + 1e-6 * np.random.default_rng(30).normal(size=64)
    result = periodogram.compute_periodogram(
        times, values, start=5.0, stop=5.001, steps=1, freq_mode=True,
    )
    residual = values - values.mean()
    design = np.column_stack((np.cos(2 * np.pi * 5 * times), np.sin(2 * np.pi * 5 * times)))
    fit = design @ np.linalg.lstsq(design, residual, rcond=None)[0]
    reference = np.dot(fit, fit) / (2 * np.var(values))
    assert result.power[0] == pytest.approx(reference, abs=1e-10)
    assert result.power[0] <= len(times) / 2
    assert 0 < result.false_alarm_probability_upper_bound <= 1


@pytest.mark.parametrize("frequency", [5.0, 5 + 1e-14, 5 + 1e-12])
def test_near_nyquist_noise_power_matches_an_orthogonal_projection(frequency):
    times = np.arange(64) * 0.1
    values = np.random.default_rng(30).normal(size=64)
    xs, powers = periodogram.lomb_scargle(
        times, values, frequency, frequency + 0.001, steps=1, freq_mode=True,
    )
    omega = 2 * np.pi * xs[0]
    tau = np.arctan2(np.sum(np.sin(2 * omega * times)), np.sum(np.cos(2 * omega * times))) / (2 * omega)
    angles = omega * (times - tau)
    design = np.column_stack((np.cos(angles), np.sin(angles)))
    # QR is a separate reference for rank 2; exact Nyquist has only rank 1.
    rank = np.linalg.matrix_rank(design)
    basis = np.linalg.qr(design)[0][:, :rank]
    reference = np.sum((basis.T @ (values - values.mean())) ** 2) / (2 * np.var(values))
    assert powers[0] == pytest.approx(reference, rel=1e-10, abs=1e-12)


def test_unrepresentable_candidate_period_is_a_structured_failure(tmp_path, artifact_dir):
    result = pulsar.compute_pulsar_periodogram(
        _curve(tmp_path, np.arange(8.0)),
        start=1e-309, stop=2e-309, steps=1, freq_mode=True,
    )
    assert [e.code for e in result.errors] == ["invalid_input"]
    assert result.artifact is None
    assert result.top_peaks == []


@pytest.mark.parametrize("policy", ["uniform", "old_policy"])
@pytest.mark.parametrize("stage", ["fold", "sonify", "rejected_search"])
def test_every_stage_derives_sampling_instead_of_trusting_saved_metadata(
    tmp_path, artifact_dir, policy, stage,
):
    times = np.r_[np.arange(32) * 0.01, 10 + np.arange(32) * 0.01]
    path = _curve(tmp_path, times, meta={
        "sampling_policy": policy, "sample_cadence_s": 99,
        "suggested_min_period_s": 99, "nyquist_period_s": 99,
    })
    if stage == "fold":
        result = pulsar.fold_pulsar_lightcurve(path, period_s=0.8)
    elif stage == "sonify":
        result = pulsar.sonify_pulsar(path, period_s=0.8, audio_seconds=0.1)
        assert result.errors == []
        return  # sonification reports no observation fields, but must not raise
    else:
        result = pulsar.compute_pulsar_periodogram(path, start=1, stop=0.5)
        assert [e.code for e in result.errors] == ["invalid_input"]
    assert result.nyquist_period_s is None
    assert result.sample_cadence_s == pytest.approx(0.01)
    assert result.suggested_min_period_s == pytest.approx(0.02)
    assert result.sampling_policy == "median_spacing_heuristic"


@pytest.mark.parametrize("freq_mode,start,stop", [(False, 0.01, 0.1), (True, 1.0, 100.0)])
def test_explicit_uniform_super_nyquist_search_warns(
    tmp_path, artifact_dir, freq_mode, start, stop,
):
    result = pulsar.compute_pulsar_periodogram(
        _curve(tmp_path, np.arange(128) * 0.01),
        freq_mode=freq_mode, start=start, stop=stop, steps=80,
    )
    assert result.errors == []
    assert "search_above_nyquist" in [w.code for w in result.warnings]
