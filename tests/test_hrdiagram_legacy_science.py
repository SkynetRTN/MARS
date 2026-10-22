"""M2 legacy coordinate, CCM extinction and observed-motion science checks."""

import math

import astropy.units as u
from astropy.constants import G
from astropy.coordinates import Angle
import pytest

from algorithms.hrdiagram_py import legacy


@pytest.mark.parametrize("degrees", [-90., -30.5, -.5, -1 / 3600, -0., 0., .5, 30.5, 90.])
def test_signed_dms_matches_astropy_and_round_trips_subdegree_sign(degrees):
    actual = legacy.d2_dms(degrees)
    reference = Angle(abs(degrees), u.deg).signed_dms
    assert [abs(actual[0]), *actual[1:]] == pytest.approx([reference.d, reference.m, reference.s], abs=1e-9)
    assert math.copysign(1., actual[0]) == math.copysign(1., degrees)
    restored = math.copysign(abs(actual[0]) + actual[1] / 60 + actual[2] / 3600, actual[0])
    assert restored == pytest.approx(degrees, abs=1e-12)
    assert 0 <= actual[1] < 60 and 0 <= actual[2] < 60


@pytest.mark.parametrize("degrees", [-30.5, -.5, -0., 0., 30.5, 359.999999])
def test_signed_hms_matches_astropy_without_flooring_negative_angles(degrees):
    actual = legacy.d2_hms(degrees)
    reference = Angle(abs(degrees), u.deg).hms
    assert [abs(actual[0]), *actual[1:]] == pytest.approx(list(reference), abs=1e-9)
    assert math.copysign(1., actual[0]) == math.copysign(1., degrees)
    restored = math.copysign(abs(actual[0]) + actual[1] / 60 + actual[2] / 3600, actual[0]) * 15
    assert restored == pytest.approx(degrees, abs=1e-12)
    assert 0 <= actual[1] < 60 and 0 <= actual[2] < 60


# Recorded CCM89 reference values using dust_extinction's published Horner
# evaluation; our legacy implementation uses expanded powers. E(B-V)=0.2 mag.
@pytest.mark.parametrize("band, rv, expected", [
    ("B", 5., 1.1969097033070515), ("V", 5., .9991640842744225),
    ("G", 5., .8304184716504184), ("J", 5., .3271727793125482),
    ("H", 5., .2092440580466436), ("K", 5., .13663953135139112),
    ("V", 3.1, .6192870019303767), ("V", 2., .3993581647838239),
])
def test_ccm_extinction_matches_independent_monochromatic_reference(band, rv, expected):
    assert legacy._legacy_extinction(band, .2, rv) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("band", ["W1", "W2", "W3", "W4", "unrecognized"])
def test_extinction_outside_supported_law_is_not_reported_as_zero(band):
    with pytest.raises(ValueError):
        legacy._legacy_extinction(band, .2)


@pytest.mark.parametrize("rv, reddening", [(1., .2), (7., .2), (math.nan, .2), (3.1, -.1), (3.1, math.inf)])
def test_extinction_rejects_values_outside_the_supported_model(rv, reddening):
    with pytest.raises(ValueError):
        legacy._legacy_extinction("V", reddening, rv)


@pytest.mark.parametrize("inverse_micron, expected", [(.3, .06744775587163446), (1.1, .5463882268796434)])
def test_ccm_supported_branch_boundaries_do_not_return_zero(monkeypatch, inverse_micron, expected):
    monkeypatch.setitem(legacy._FILTER_WAVELENGTH, "boundary", 1 / inverse_micron)
    assert legacy._legacy_extinction("boundary", .2, 5.) == pytest.approx(expected, rel=1e-12)


def test_plot_transforms_propagate_rv_and_reject_unsupported_extinction():
    filters = {"blue": "B", "red": "V", "lum": "V"}
    params = {"distance": 2., "reddening": .2, "rv": 5.}
    assert legacy.compute_plot_delta(filters, params) == pytest.approx({
        "x": -.19774561903262902, "y": -12.504314062594329,
    })
    unsupported = {"blue": "J", "red": "W1", "lum": "W1"}
    with pytest.raises(ValueError):
        legacy.get_plot_data([], "HR", unsupported, params, .1)
    with pytest.raises(ValueError):
        legacy.apply_isochrone_transform({"data": [[1., 2.]], "iSkip": 0}, "CM", unsupported, params)


def _sources(motions):
    return [{"fsr": {"pm_ra": ra, "pm_dec": dec}} for ra, dec in motions]


@pytest.mark.parametrize("scale", [1e-200, 1., 1e200, 4e307])
def test_observed_one_dimensional_rms_uses_both_motion_components_stably(scale):
    sources = _sources([(3 * scale, 4 * scale), (-3 * scale, -4 * scale)])
    result = legacy.get_velocity_dispersion(sources, 0., 0.)
    assert result == pytest.approx(3.5355339059327378 * scale, rel=1e-14, abs=0)


def test_observed_rms_uses_all_paired_motions_without_radial_percentile_trimming():
    sources = _sources([(10., -20.), (13., -20.), (10., -16.)])
    assert legacy.get_velocity_dispersion(sources, 10., -20.) == pytest.approx(2.041241452319315)
    rotated = _sources([(20., 10.), (20., 13.), (16., 10.)])
    assert legacy.get_velocity_dispersion(rotated[::-1], 20., 10.) == pytest.approx(2.041241452319315)


def test_missing_motion_is_omitted_but_measured_zero_is_kept():
    sources = _sources([(0., 0.), (3., 4.), (None, 4.)]) + [{"fsr": None}]
    assert legacy.get_velocity_dispersion(sources, 0., 0.) == pytest.approx(2.5)


def test_constant_motion_has_exactly_zero_observed_scatter():
    assert legacy.get_velocity_dispersion(_sources([(1e300, -1e300)] * 3), 1e300, -1e300) == 0.


@pytest.mark.parametrize("motions", [[], [(None, 0.)], [(math.nan, 0.)], [(0., math.inf)]])
def test_dispersion_rejects_undefined_or_nonfinite_statistics(motions):
    with pytest.raises(ValueError):
        legacy.get_velocity_dispersion(_sources(motions), 0., 0.)


@pytest.mark.parametrize("motion, distance, radius", [(1., 1., 1.), (.2, .3, 5.), (3., 2., 10.)])
def test_protected_mass_conversion_matches_independent_astropy_units(motion, distance, radius):
    angular_rate = (motion * u.mas / u.yr).to_value(u.rad / u.s)
    speed = angular_rate * distance * u.kpc / u.s
    reference = (10 * speed**2 * radius * u.lyr / G).to_value(u.Msun)
    # Preserve the legacy rounded constants and both cancelling unit factors.
    assert legacy.get_mass(motion, distance, radius) == pytest.approx(reference, rel=1e-4)


def test_summary_identifies_observed_rms_units_and_virial_proxy_limitations():
    sources = [
        {"astrometry": {"ra": 0., "dec": 0.}, "fsr": {"pm_ra": 1., "pm_dec": 0.}},
        {"astrometry": {"ra": 1., "dec": 0.}, "fsr": {"pm_ra": 2., "pm_dec": 0.}},
    ]
    summary = legacy.compute_cluster_summary(
        sources, 0., 0., [1., 2.], [0., 0.],
        {"distance": 1., "reddening": .1}, {"age": 8., "metallicity": -.1},
    )
    assert summary["velocityDispersion"] == pytest.approx(.5)
    assert summary["units"]["velocityDispersion"] == "mas/yr"
    assert summary["units"]["physicalRadius"] == "lyr"
    assert summary["units"]["distance"] == "kpc"
    assert summary["units"]["mass"] == "solMass"
    assert summary["methods"]["velocityDispersion"] == "observed_isotropic_1d_rms"
    assert summary["methods"]["mass"] == "virial_proxy_eta10"
    assert summary["methods"]["angularRadius"] == "median_projected_number_radius"
    assert {warning["code"] for warning in summary["warnings"]} >= {
        "observed_motion_scatter", "virial_mass_proxy",
    }
