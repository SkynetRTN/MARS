"""Circular folding regressions for M5's maintained TS-24/TS-25 defects."""

from __future__ import annotations

import numpy as np
import pytest

from algorithms.pulsar import folding


def test_fold_preserves_origin_multiples_and_neighbors_with_their_flux():
    below = np.nextafter(1., 0.)
    above = np.nextafter(1., np.inf)
    times = np.array([0., .5, below, 1., above, 2.])

    phase, flux, second = folding.fold_to_phase(times, np.arange(6.), None, 1.)

    np.testing.assert_array_equal(phase, [below, .5, 2.**-52, 0., 0., 0.])
    np.testing.assert_array_equal(flux, [2., 1., 4., 0., 3., 5.])
    assert second is None


def test_fold_rebases_unsorted_times_before_circular_mapping():
    phase, flux, second = folding.fold_to_phase(
        np.array([12., 10., 10.25, 11.]),
        np.array([20., 10., 12., 14.]),
        np.array([40., 20., 24., 28.]),
        1.,
    )

    np.testing.assert_array_equal(phase, [.25, 0., 0., 0.])
    np.testing.assert_array_equal(flux, [12., 10., 14., 20.])
    np.testing.assert_array_equal(second, [24., 20., 28., 40.])


def test_generic_bins_include_every_tied_right_endpoint():
    centres, values = folding.bin_data(
        np.array([0., .25, .5, .75, 1., 1.]),
        np.array([0., 1., 2., 3., 7., 11.]),
        4,
    )

    np.testing.assert_array_equal(centres, [.125, .375, .625, .875])
    np.testing.assert_array_equal(values, [0., 1., 2., 7.])


def test_generic_equal_coordinates_form_one_occupied_bin():
    centres, values = folding.bin_data(np.array([2., 2., 2.]), np.array([1., 4., 7.]), 4)

    np.testing.assert_array_equal(centres, [2.])
    np.testing.assert_array_equal(values, [4.])


def test_generic_equal_coordinates_reject_nonfinite_derived_mean():
    # Finite inputs must not produce a successful inf artifact. This helper
    # conservatively rejects overflow in its mean rather than advertising it.
    with np.errstate(over="raise", invalid="raise"):
        with pytest.raises(ValueError, match="bin mean"):
            folding.bin_data(np.array([2., 2.]), np.array([1e308, 1e308]), 4)


@pytest.mark.parametrize("phase, expected_flux", [
    (1., [1., 2., 3., 4.]),
    (.75, [2., 3., 4., 1.]),
    (-.25, [2., 3., 4., 1.]),
])
def test_large_finite_cycle_shifts_keep_finite_circular_coordinates(phase, expected_flux):
    with np.errstate(over="raise", invalid="raise"):
        profile = folding.fold_lightcurve(
            np.array([0., 2.5e307, 5e307, 7.5e307]), np.arange(1., 5.),
            period_s=1e308, bins=4, phase=phase,
        )

    np.testing.assert_allclose(profile.phase_s, [1.25e307, 3.75e307, 6.25e307, 8.75e307])
    np.testing.assert_array_equal(profile.source1, expected_flux)
    assert np.isfinite(profile.phase_s).all()


def test_exact_cycle_pulses_survive_in_the_origin_bin():
    profile = folding.fold_lightcurve(
        np.array([0., .25, .5, .75, 1., 1.25, 1.5, 1.75, 2.]),
        np.array([9., 0., 0., 0., 9., 0., 0., 0., 9.]),
        period_s=1., bins=4,
    )

    np.testing.assert_array_equal(profile.phase_s, [.125, .375, .625, .875])
    np.testing.assert_array_equal(profile.source1, [9., 0., 0., 0.])
    assert profile.samples_folded == 9


def test_all_boundary_samples_make_one_real_bin():
    profile = folding.fold_lightcurve(
        np.array([0., 1., 2.]), np.array([3., 6., 9.]), period_s=1., bins=4,
    )

    np.testing.assert_array_equal(profile.phase_s, [.125])
    np.testing.assert_array_equal(profile.source1, [6.])
    assert profile.samples_folded == 3


def test_sparse_profile_uses_full_cycle_support_and_omits_empty_bins():
    profile = folding.fold_lightcurve(
        np.array([0., .1, .6, 1.1]), np.array([2., 4., 8., 6.]),
        period_s=1., bins=4,
    )

    np.testing.assert_array_equal(profile.phase_s, [.125, .625])
    np.testing.assert_array_equal(profile.source1, [4., 8.])


@pytest.mark.parametrize("bins, centres", [(99, [1./198., .5]), (100, [.005, .505])])
def test_boundary_samples_survive_independently_of_bin_count(bins, centres):
    profile = folding.fold_lightcurve(
        np.array([0., .5, 1.]), np.array([9., 0., 9.]), period_s=1., bins=bins,
    )

    np.testing.assert_allclose(profile.phase_s, centres, rtol=1e-15, atol=0.)
    np.testing.assert_array_equal(profile.source1, [9., 0.])


def test_neighbor_below_period_stays_in_the_last_bin():
    profile = folding.fold_lightcurve(
        np.array([0., np.nextafter(1., 0.), 1., np.nextafter(1., np.inf)]),
        np.array([3., 12., 6., 9.]), period_s=1., bins=4,
    )

    np.testing.assert_array_equal(profile.phase_s, [.125, .875])
    np.testing.assert_array_equal(profile.source1, [6., 12.])


def test_neighboring_interior_phases_keep_half_open_bin_membership():
    phase, flux = folding.fold_and_bin(
        np.array([0., np.nextafter(.5, 0.), .5, np.nextafter(.5, 1.)]),
        np.array([1., 2., 4., 8.]), 4, 1., 0.,
    )

    np.testing.assert_array_equal(phase, [.125, .375, .625])
    np.testing.assert_array_equal(flux, [1., 2., 6.])


def test_channels_share_bins_before_calibration_shift_and_display_duplication():
    profile = folding.fold_lightcurve(
        np.array([0., .25, .5, .75, 1., 1.25, 1.5, 1.75, 2.]),
        np.array([8., 0., 4., 0., 8., 0., 4., 0., 8.]),
        np.array([1., 2., 3., 4., 1., 2., 3., 4., 1.]),
        period_s=1., bins=4, phase=.25, display_period=2, cal=2.,
    )

    np.testing.assert_array_equal(profile.phase_s, [.125, .375, .625, .875, 1.125, 1.375, 1.625, 1.875])
    np.testing.assert_array_equal(profile.source1, [0., 8., 0., 4., 0., 8., 0., 4.])
    np.testing.assert_array_equal(profile.source2, [8., 2., 4., 6., 8., 2., 4., 6.])
    np.testing.assert_array_equal(profile.difference, [-8., 6., -4., -2., -8., 6., -4., -2.])
    np.testing.assert_array_equal(profile.sum, [8., 10., 4., 10., 8., 10., 4., 10.])


@pytest.mark.parametrize("use_sum", [False, True], ids=["single-channel", "channel-sum"])
@pytest.mark.parametrize("values, expected", [([1., 2.], None), ([9., 0., 0., 0.], 2.3094010767585034)])
def test_display_duplication_does_not_invent_snr_support(use_sum, values, expected):
    values = np.array(values)
    for display_period in (1, 2):
        rendered = np.tile(values, display_period)
        profile = folding.FoldedProfile(
            phase_s=np.arange(rendered.size, dtype=float), source1=rendered,
            sum=rendered if use_sum else None, display_period=display_period,
        )

        if expected is None:
            assert profile.pulse_snr() is None
        else:
            assert profile.pulse_snr() == pytest.approx(expected)
