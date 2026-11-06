"""Reject overflow after finite pulsar channels have been folded and binned."""

import numpy as np
import pytest
from astropy.table import Table

from algorithms.pulsar.folding import fold_lightcurve
from tools.pulsar import fold_pulsar_lightcurve, sonify_pulsar


@pytest.mark.parametrize("sign, derived", [(1., "sum"), (-1., "difference")])
def test_fold_rejects_nonfinite_combined_channels_with_strict_numpy_errors(sign, derived):
    with np.errstate(over="raise", invalid="raise"):
        with pytest.raises(ValueError, match=derived):
            fold_lightcurve(
                np.array([0., .25, .5, .75]),
                np.array([1e308, 1., 1., 1.]),
                np.array([sign * 1e308, 1., 1., 1.]),
                period_s=1., bins=4,
            )


@pytest.mark.parametrize("sign", [1., -1.], ids=["sum", "difference"])
@pytest.mark.parametrize("display_period", [1, 2])
def test_public_fold_rejects_combined_overflow_before_writing(
    tmp_path, artifact_dir, sign, display_period,
):
    path = tmp_path / "channels.ecsv"
    Table({
        "time_s": [0., .25, .5, .75],
        "source1": [1e308, 1., 1., 1.],
        "source2": [sign * 1e308, 1., 1., 1.],
    }).write(path, format="ascii.ecsv")
    result = fold_pulsar_lightcurve(path, 1., bins=4, display_period=display_period)

    assert [e.code for e in result.errors] == ["invalid_input"]
    assert result.artifact is None
    assert result.preview == []
    assert list(artifact_dir.rglob("*")) == [path]


@pytest.mark.parametrize("sign", [1., -1.], ids=["sum", "difference"])
def test_public_folded_audio_rejects_combined_overflow_before_writing(
    tmp_path, artifact_dir, sign,
):
    path = tmp_path / "channels.ecsv"
    Table({
        "time_s": [0., .25, .5, .75],
        "source1": [1e308, 1., 1., 1.],
        "source2": [sign * 1e308, 1., 1., 1.],
    }).write(path, format="ascii.ecsv")
    result = sonify_pulsar(path, period_s=1., bins=4, audio_seconds=.01)

    assert [e.code for e in result.errors] == ["invalid_input"]
    assert result.artifact is None
    assert list(artifact_dir.rglob("*")) == [path]


@pytest.mark.parametrize("sign, difference, total", [
    (1., [0., 0., 0., 0.], [1.4e308, 2., 2., 2.]),
    (-1., [1.4e308, 0., 0., 0.], [0., 2., 2., 2.]),
])
def test_large_representable_combined_channels_still_write_real_artifacts(
    tmp_path, artifact_dir, sign, difference, total,
):
    path = tmp_path / "finite_channels.ecsv"
    Table({
        "time_s": [0., .25, .5, .75],
        "source1": [7e307, 1., 1., 1.],
        "source2": [sign * 7e307, 1., 1., 1.],
    }).write(path, format="ascii.ecsv")
    result = fold_pulsar_lightcurve(path, 1., bins=4)

    assert result.errors == []
    table = Table.read(result.artifact.path, format="ascii.ecsv")
    np.testing.assert_array_equal(table["phase_s"], [.125, .375, .625, .875])
    np.testing.assert_array_equal(table["difference"], difference)
    np.testing.assert_array_equal(table["sum"], total)
