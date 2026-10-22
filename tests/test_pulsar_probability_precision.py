"""Regression checks for variance-normalized powers near their floating limit."""

from decimal import Decimal, localcontext

import numpy as np
import pytest
from astropy.table import Table

from algorithms.pulsar import periodogram, significance
from tools import pulsar


def _quadrature(exponent):
    times = np.arange(4) * 0.25
    delta = 2.0**-exponent
    return times, np.array([delta, 1 - delta, delta, -1 - delta])


def _reference_tail(exponent):
    # Ideal 1-Hz quadrature: SSE=4*d*d, TSS=2+4*d*d, Beta(1, 1/2).
    # Decimal prevents the reference from losing the same complement as power.
    with localcontext() as context:
        context.prec = 70
        delta = Decimal(2) ** -exponent
        residual_fraction = 2 * delta * delta / (1 + 2 * delta * delta)
        return float(residual_fraction.sqrt()), float(residual_fraction)


@pytest.mark.parametrize("freq_mode", [False, True])
def test_public_bound_uses_resolvable_residual_even_when_power_rounds_to_maximum(
    tmp_path, artifact_dir, freq_mode,
):
    times, values = _quadrature(27)
    path = tmp_path / "near-perfect.ecsv"
    Table({"time_s": times, "source1": values}, meta={"flavour": "standard"}).write(
        path, format="ascii.ecsv",
    )
    result = pulsar.compute_pulsar_periodogram(
        path, start=1.0, stop=1.001, steps=1, freq_mode=freq_mode,
    )
    assert result.errors == []
    expected, residual_fraction = _reference_tail(27)
    assert result.peak_power == pytest.approx(2.0)
    assert result.false_alarm_probability_upper_bound == pytest.approx(expected, rel=1e-7, abs=0)
    payload = result.model_dump(mode="json")
    assert payload.get("peak_residual_fraction") == pytest.approx(residual_fraction, rel=2e-7, abs=0)
    assert payload.get("false_alarm_resolution_limited") is False
    saved = Table.read(result.artifact.path, format="ascii.ecsv")
    assert saved.meta["false_alarm_probability_upper_bound"] == payload["false_alarm_probability_upper_bound"]
    assert saved.meta["peak_residual_fraction"] == payload["peak_residual_fraction"]
    assert saved.meta["false_alarm_statistic"] == "residual_fraction"


@pytest.mark.parametrize("exponent", [10, 20, 27, 35])
def test_residual_tail_tracks_noise_below_the_power_complement_resolution(exponent):
    times, values = _quadrature(exponent)
    result = periodogram.compute_periodogram(
        times, values, start=1.0, stop=1.001, steps=1, freq_mode=True,
    )
    expected, _ = _reference_tail(exponent)
    assert result.false_alarm_probability_upper_bound == pytest.approx(expected, rel=1e-5, abs=0)


def test_unresolved_fit_reports_null_and_warns_in_result_and_plot(tmp_path, artifact_dir):
    path = tmp_path / "exact.ecsv"
    Table({"time_s": np.arange(4) * 0.25, "source1": [0.0, 1.0, 0.0, -1.0]}).write(
        path, format="ascii.ecsv",
    )
    result = pulsar.compute_pulsar_periodogram(path, start=1.0, stop=1.001, steps=1)
    assert result.errors == []
    assert result.false_alarm_probability_upper_bound is None
    assert result.model_dump(mode="json").get("false_alarm_resolution_limited") is True
    assert "false_alarm_resolution_limited" in [warning.code for warning in result.warnings]
    saved = Table.read(result.artifact.path, format="ascii.ecsv")
    assert "false_alarm_probability_upper_bound" not in saved.meta
    assert saved.meta["false_alarm_resolution_limited"] is True
    plot = pulsar.plot_pulsar(result.artifact.path)
    assert plot.errors == []
    assert "false_alarm_resolution_limited" in [warning.code for warning in plot.warnings]


def test_scalar_maximum_power_does_not_invent_a_tail():
    assert significance.upper_bound(2.0, 4, 1) is None


@pytest.mark.parametrize("alpha", [0.1, 0.01])
@pytest.mark.parametrize("count_type", [int, np.int32, np.int64])
def test_representable_threshold_rounds_toward_sufficient_power(alpha, count_type):
    value = significance.threshold(alpha, count_type(4), count_type(200_002))
    assert value is not None
    # Evaluate the inverse with high precision, independent of upper_bound.
    with localcontext() as context:
        context.prec = 70
        residual_fraction = (Decimal(2) - Decimal(value)) / 2
        probability = 200_002 * residual_fraction.sqrt()
        assert probability <= Decimal(alpha)


def test_unrepresentable_threshold_is_unavailable():
    assert significance.threshold(0.001, 4, 200_002) is None


def test_old_gaussian_artifact_does_not_advertise_pre_fix_thresholds_as_current(
    tmp_path, artifact_dir,
):
    path = tmp_path / "old-gaussian.ecsv"
    Table({"period_s": [0.9, 1.0, 1.1], "power": [1.0, 2.0, 1.0]}, meta={
        "channel": "sum", "false_alarm_method": "gaussian_bonferroni",
        "false_alarm_probability_upper_bound": 2.2250738585072014e-308,
        "false_alarm_thresholds": {"0.1": 1.99, "0.01": 1.9999, "0.001": 2.0},
    }).write(path, format="ascii.ecsv")
    result = pulsar.plot_pulsar(path)
    assert result.errors == []
    assert "legacy_confidence_uncalibrated" in [warning.code for warning in result.warnings]
    assert not any("Gaussian noise FAP" in name for name in result.series)
    assert len([name for name in result.series if "uncalibrated" in name]) == 3


def test_omitted_threshold_warns_even_with_a_resolved_peak_bound(tmp_path, artifact_dir):
    path = tmp_path / "short-grid.ecsv"
    Table({
        "time_s": np.arange(4) * 0.25,
        "source1": [0.2, 0.7, -0.2, -0.6],
    }).write(path, format="ascii.ecsv")
    result = pulsar.compute_pulsar_periodogram(
        path, start=1.0, stop=1.001, steps=100_000, freq_mode=True,
    )
    assert result.errors == []
    assert result.false_alarm_probability_upper_bound is not None
    assert set(result.false_alarm_thresholds) == {"0.1", "0.01"}
    assert result.false_alarm_resolution_limited is True
    assert "false_alarm_resolution_limited" in [warning.code for warning in result.warnings]
    plotted = pulsar.plot_pulsar(result.artifact.path)
    assert plotted.errors == []
    assert len([name for name in plotted.series if "Gaussian noise FAP" in name]) == 2
    assert "false_alarm_resolution_limited" in [warning.code for warning in plotted.warnings]
