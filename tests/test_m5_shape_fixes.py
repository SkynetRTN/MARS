"""Correctness regressions for M5 triangle and source-ellipse geometry."""

from itertools import permutations

import numpy as np
import pytest
from astropy.stats import gaussian_fwhm_to_sigma

from algorithms.skylib_lite.astrometry.atlas.match.triangles import (
    sample_triangles,
    triangle_invariant_and_order,
)
from algorithms.skylib_lite.extraction import main as extraction


@pytest.mark.parametrize("scale", [1e-200, 1e-20, np.deg2rad(1 / 3600), 1., 1e100, 1e200])
def test_triangle_invariants_and_order_do_not_depend_on_coordinate_units(scale):
    points = np.array([[0., 0.], [4., 0.], [1., 2.]])
    for indices in permutations(range(3)):
        invariant, ordered = triangle_invariant_and_order(
            points[list(indices)] * scale, min_side=2 * scale, max_side=5 * scale,
        )
        assert invariant is not None
        np.testing.assert_allclose(invariant, [np.sqrt(5) / 4, np.sqrt(13) / 4], rtol=1e-14)
        # The existing convention starts with the longest edge, retaining its
        # direction in the input's cyclic vertex order.
        expected = points if indices in ((0, 1, 2), (1, 2, 0), (2, 0, 1)) else points[[1, 0, 2]]
        np.testing.assert_allclose(ordered / scale, expected, rtol=1e-14)


@pytest.mark.parametrize("scale", [1e-200, 1e-8, 1., 1e8, 1e200])
@pytest.mark.parametrize("height,accepted", [(5e-7, False), (2e-6, True)])
def test_triangle_collinearity_tolerance_is_dimensionless(scale, height, accepted):
    points = np.array([[0., 0.], [1., 0.], [.5, height]]) * scale
    invariant, ordered = triangle_invariant_and_order(
        points, min_side=0, max_side=2 * scale,
    )
    assert (invariant is not None) == accepted
    assert (ordered is not None) == accepted


@pytest.mark.parametrize("points", [
    [[0., 0.], [0., 0.], [1., 1.]],
    [[0., 0.], [1., 1.], [2., 2.]],
    [[0., 0.], [0., 0.], [0., 0.]],
    [[0., 0.], [1., 0.], [np.nan, 1.]],
    [[0., 0.], [1., 0.], [np.inf, 1.]],
    [[0., 0.], [1., 0.], [-np.inf, 1.]],
    [[-1e308, 0.], [1e308, 0.], [0., 1e308]],
])
def test_invalid_or_exactly_degenerate_triangles_are_rejected(points):
    with np.errstate(divide="raise", invalid="raise", over="raise"):
        invariant, ordered = triangle_invariant_and_order(
            np.array(points), min_side=0, max_side=np.inf, collinear_eps=0,
        )
    assert invariant is None
    assert ordered is None


@pytest.mark.parametrize("min_side,max_side,accepted", [
    (2.2, 4.1, True), (2.3, 4.1, False), (2.2, 3.9, False),
])
@pytest.mark.parametrize("scale", [1e-200, 1., 1e200])
def test_triangle_side_limits_remain_in_the_input_units(min_side, max_side, accepted, scale):
    invariant, _ = triangle_invariant_and_order(
        np.array([[0., 0.], [4., 0.], [1., 2.]]) * scale,
        min_side=min_side * scale, max_side=max_side * scale,
    )
    assert (invariant is not None) == accepted


def test_triangle_sampling_retains_small_angular_catalog_triangles():
    points = np.array([[0., 0.], [4., 0.], [1., 2.]]) * np.deg2rad(1 / 3600)
    triangles = sample_triangles(
        points, 8, min_side=0, max_side=np.deg2rad(10 / 3600),
        rng=np.random.default_rng(1),
    )
    assert len(triangles.triangles) == 8
    np.testing.assert_allclose(
        triangles.invariants, np.tile([np.sqrt(5) / 4, np.sqrt(13) / 4], (8, 1)),
    )


def _rotated_gaussian(angle):
    y, x = np.mgrid[:96, :96]
    dx, dy = x - 48.2, y - 47.7
    major = dx * np.cos(angle) + dy * np.sin(angle)
    minor = -dx * np.sin(angle) + dy * np.cos(angle)
    return (100 + np.random.default_rng(1).normal(size=x.shape)
            + 500 * np.exp(-.5 * ((major / 4) ** 2 + (minor / 2) ** 2))).astype(np.float32)


def _ellipse_covariance(sources):
    a2, b2 = sources["a"] ** 2, sources["b"] ** 2
    cosine, sine = np.cos(sources["theta"]), np.sin(sources["theta"])
    return np.array([
        a2 * cosine ** 2 + b2 * sine ** 2,
        (a2 - b2) * sine * cosine,
        a2 * sine ** 2 + b2 * cosine ** 2,
    ])


def _extract_without_shape_cuts(image, **kwargs):
    options = dict(downsample=1, threshold=5, fwhm=0, centroid=False,
                   deblend=False, min_fwhm=0, max_fwhm=0, max_ellipticity=0)
    options.update(kwargs)
    return extraction.extract_sources(image, **options)[0]


@pytest.mark.parametrize("angle", [-.7, .4])
def test_real_sep_ellipse_is_canonical_and_preserves_covariance(angle, monkeypatch):
    image = _rotated_gaussian(angle)
    original_extract = extraction.sep.extract
    raw = []

    def record(*args, **kwargs):
        sources = original_extract(*args, **kwargs)
        raw.append(sources.copy())
        return sources

    monkeypatch.setattr(extraction, "estimate_background", lambda img, **kw: (
        np.full_like(img, 100), np.ones_like(img)))
    monkeypatch.setattr(extraction.sep, "extract", record)
    sources = _extract_without_shape_cuts(image)
    assert len(sources) == len(raw[0]) == 1
    assert np.all(sources["a"] >= sources["b"])
    assert np.all((sources["theta"] > -np.pi / 2) & (sources["theta"] <= np.pi / 2))
    np.testing.assert_array_equal(sources["a"], raw[0]["a"])
    np.testing.assert_array_equal(sources["b"], raw[0]["b"])
    np.testing.assert_allclose(_ellipse_covariance(sources), _ellipse_covariance(raw[0]), atol=1e-12)


@pytest.mark.parametrize("a,b,theta,expected_theta", [
    (2., 4., 0., np.pi / 2),
    (2., 4., np.pi / 2, 0.),
    (2., 4., -.3, np.pi / 2 - .3),
    (4., 2., -np.pi / 2, np.pi / 2),
    (4., 2., 3 * np.pi / 4, -np.pi / 4),
])
def test_controlled_sep_axes_are_swapped_and_rotated(a, b, theta, expected_theta, monkeypatch):
    # Real SEP currently orders its axes. Replace only ellipse fields on its
    # complete real output to exercise the wrapper's reversed-axis contract.
    original_extract = extraction.sep.extract
    raw = []

    def controlled(*args, **kwargs):
        sources = original_extract(*args, **kwargs)
        sources["a"], sources["b"], sources["theta"] = a, b, theta
        raw.append(sources.copy())
        return sources

    monkeypatch.setattr(extraction, "estimate_background", lambda img, **kw: (
        np.full_like(img, 100), np.ones_like(img)))
    monkeypatch.setattr(extraction.sep, "extract", controlled)
    sources = _extract_without_shape_cuts(_rotated_gaussian(.4))
    assert len(sources) == 1
    np.testing.assert_allclose(sources["a"], [4.])
    np.testing.assert_allclose(sources["b"], [2.])
    np.testing.assert_allclose(sources["theta"], [expected_theta], atol=1e-15)
    np.testing.assert_allclose(_ellipse_covariance(sources), _ellipse_covariance(raw[0]), atol=1e-12)


@pytest.mark.parametrize("shape_cut", [
    {"min_fwhm": 3 / gaussian_fwhm_to_sigma},
    {"max_fwhm": 3 / gaussian_fwhm_to_sigma},
    {"max_ellipticity": 1.5},
])
def test_shape_cuts_use_canonical_major_and_minor_axes(shape_cut, monkeypatch):
    original_extract = extraction.sep.extract

    def reversed_axes(*args, **kwargs):
        sources = original_extract(*args, **kwargs)
        sources["a"], sources["b"], sources["theta"] = 2., 4., 0.
        return sources

    monkeypatch.setattr(extraction, "estimate_background", lambda img, **kw: (
        np.full_like(img, 100), np.ones_like(img)))
    monkeypatch.setattr(extraction.sep, "extract", reversed_axes)
    sources = _extract_without_shape_cuts(_rotated_gaussian(.4), **shape_cut)
    assert len(sources) == 0
