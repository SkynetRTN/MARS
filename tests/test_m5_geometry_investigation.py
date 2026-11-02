"""Correctness regressions derived from the M5 geometry investigation.

Native backends, source extraction or catalog I/O are replaced only at the
boundary under investigation. Expectations now require corrected geometry.
See docs/analysis/m5-coordinates-image-geometry.md for reachability and limits.
"""

from types import SimpleNamespace

import numpy as np
import pytest
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales

from algorithms.skylib_lite.astrometry.atlas.catalog import ucac4, ucac5
from algorithms.skylib_lite.astrometry.atlas.config import AtlasConfig
from algorithms.skylib_lite.astrometry.atlas.match.triangles import triangle_invariant_and_order
from algorithms.skylib_lite.astrometry.atlas.solve import oriented, solver
from algorithms.skylib_lite.astrometry.types import SolveSolution
from algorithms.skylib_lite.extraction import main as extraction
from algorithms.wcs import header_utils, wcs as pipeline


@pytest.mark.parametrize("ra_key,dec_key,expected", [
    ("RA", "DEC", 185.6), ("TELRA", "TELDEC", 185.6),
    ("OBJRA", "OBJDEC", 185.6),
    ("RA_PNT", "DEC_PNT", 185.6), ("TARGRA", "TARGDEC", 185.6),
    ("OBJCTRA", "OBJCTDEC", 185.6),
])
def test_wcs06_decimal_ra_string_keeps_the_same_hint_for_every_keyword(
    ra_key, dec_key, expected, monkeypatch, tmp_path,
):
    """A decimal RA above 24 has the same degree reading in either parser."""
    header = fits.Header({"NAXIS1": 32, "NAXIS2": 32,
                          ra_key: "185.6", dec_key: "0"})
    monkeypatch.setattr(pipeline, "run_source_extraction", lambda *a, **k: ([], None, None))
    monkeypatch.setattr(pipeline, "build_anet_config", lambda *a: None)
    monkeypatch.setattr(pipeline, "build_atlas_config", lambda *a: None)
    result = pipeline.solve_wcs(header, np.zeros((32, 32)), tmp_path)
    assert result.metadata.search_center_ra_deg == pytest.approx(expected)


def test_wcs08_alternate_celestial_scale_produces_a_valid_atlas_window(monkeypatch, tmp_path):
    header = fits.Header({
        "NAXIS1": 32, "NAXIS2": 32, "RA": 180., "DEC": 0.,
        "CTYPE1A": "RA---TAN", "CTYPE2A": "DEC--TAN",
        "CUNIT1A": "deg", "CUNIT2A": "deg",
        "CDELT1A": -1 / 3600, "CDELT2A": 1 / 3600,
    })
    # Independent reading of the alternate WCS establishes one arcsecond/pixel.
    np.testing.assert_allclose(proj_plane_pixel_scales(WCS(header, key="A")) * 3600, [1, 1])
    seen = []
    monkeypatch.setattr(pipeline, "run_source_extraction", lambda *a, **k: ([], None, None))
    monkeypatch.setattr(pipeline, "build_anet_config", lambda *a: None)
    monkeypatch.setattr(pipeline, "build_atlas_config", lambda *a: AtlasConfig())

    def miss(self, request, config):
        seen.append(request)
        return SolveSolution(backend="atlas")

    monkeypatch.setattr(pipeline.AtlasBackend, "solve", miss)
    result = pipeline.solve_wcs(header, np.zeros((32, 32)), tmp_path)
    assert header_utils.estimate_pixel_scale_arcsec_per_pix(header) == pytest.approx(1)
    assert seen[0].min_scale == pytest.approx(.5)
    assert seen[0].max_scale == pytest.approx(2)
    assert result.metadata.search_atlas_min_scale_arcsec < result.metadata.search_atlas_max_scale_arcsec


def test_wcs07_the_same_noncollinear_triangle_is_accepted_in_radians():
    points = np.array([[50., 50.], [150., 50.], [80., 150.]])
    angular_scale = np.deg2rad(1 / 3600)
    invariant, _ = triangle_invariant_and_order(points, min_side=6, max_side=180)
    angular_invariant, _ = triangle_invariant_and_order(
        points * angular_scale, min_side=6 * angular_scale, max_side=180 * angular_scale,
    )
    assert invariant is not None
    np.testing.assert_allclose(angular_invariant, invariant)


def test_wcs07_perfect_small_field_catalog_reaches_matching(monkeypatch, tmp_path):
    xy = np.array([(80 + 30 * i, 80 + 30 * j) for i in range(4) for j in range(4)], float)
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [180, 0]
    wcs.wcs.crpix = [150, 150]
    wcs.wcs.cdelt = [-1 / 3600, 1 / 3600]
    world = wcs.all_pix2world(xy, 0)
    catalog = SimpleNamespace(ra_deg=world[:, 0], dec_deg=world[:, 1])
    sources = SimpleNamespace(xy=xy, shape=(300, 300), flux=np.ones(len(xy)))
    monkeypatch.setattr(solver, "extract_sources", lambda *a, **k: sources)
    monkeypatch.setattr(solver, "_catalog_index", lambda *a: SimpleNamespace(
        query_box=lambda *a, **k: catalog))
    monkeypatch.setattr(AtlasConfig, "resolve_catalog", lambda self: ("ucac5", tmp_path))
    result = solver.solve(
        tmp_path / "unused.fits", AtlasConfig(n_tri_obs=32, n_tri_cat=32),
        ra0_deg=180, dec0_deg=0, scale_range_arcsec_per_pix=(.5, 2),
        fov_guess_deg=(5 / 60, 5 / 60),
    )
    assert result.metadata.get("reason") != "no_triangles"


@pytest.mark.parametrize("path", ["blind", "oriented"])
@pytest.mark.parametrize("dec", [0., 89., -89., 89.95, -89.95])
def test_wcs10_polar_search_boxes_include_an_on_detector_star(
    path, dec, monkeypatch, tmp_path,
):
    module = solver if path == "blind" else oriented
    bounds = []

    def query(*args, **kwargs):
        bounds.append(args)
        return SimpleNamespace(ra_deg=np.empty(0), dec_deg=np.empty(0))

    sources = SimpleNamespace(xy=np.array([[10., 10.], [20., 10.], [10., 20.], [20., 20.]]),
                              shape=(512, 512), flux=np.ones(4))
    monkeypatch.setattr(module, "extract_sources", lambda *a, **k: sources)
    monkeypatch.setattr(module, "_catalog_index", lambda *a: SimpleNamespace(query_box=query))
    monkeypatch.setattr(AtlasConfig, "resolve_catalog", lambda self: ("ucac5", tmp_path))
    if path == "blind":
        module.solve(tmp_path / "unused.fits", AtlasConfig(), ra0_deg=0, dec0_deg=dec,
                     scale_range_arcsec_per_pix=(.5, 1), fov_guess_deg=(512 / 3600, 512 / 3600))
    else:
        module.solve_oriented(tmp_path / "unused.fits", AtlasConfig(), ra0_deg=0, dec0_deg=dec,
                              scale_arcsec_per_pix=1, rotation_deg=0, parity_sign=-1,
                              pointing_radius_deg=.1)

    center = SkyCoord(0 * u.deg, dec * u.deg)
    star = center.directional_offset_by(90 * u.deg, .05 * u.deg)
    # Verify the witness lies on a 512-pixel, 1 arcsec/pixel detector.
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crpix = [256.5, 256.5]
    wcs.wcs.crval = [0, dec]
    wcs.wcs.cdelt = [-1 / 3600, 1 / 3600]
    x, y = wcs.all_world2pix(star.ra.deg, star.dec.deg, 0)
    assert 0 < x < 512 and 0 < y < 512
    if abs(dec) > 89.9:
        pole_x, pole_y = wcs.all_world2pix(0, np.copysign(90, dec), 0)
        assert 0 < pole_x < 512 and 0 < pole_y < 512
    included = any(
        (hi - lo >= 360 or (star.ra.deg - lo) % 360 <= (hi - lo) % 360)
        and bottom <= star.dec.deg <= top
        for lo, hi, bottom, top in bounds
    )
    assert included


@pytest.mark.parametrize("project", [pipeline._gnomonic_projection, solver._gnomonic_projection])
def test_wcs09_far_side_does_not_project_next_to_center(project):
    xy = project(np.array([.1, 180.]), np.array([0., 0.]), 0., 0.)
    assert np.isfinite(xy[0]).all()
    assert np.isnan(xy[1]).all()
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [0, 0]
    wcs.wcs.crpix = [1, 1]
    wcs.wcs.cdelt = [1, 1]
    assert np.isnan(wcs.all_world2pix([[180, 0]], 0)).all()


@pytest.mark.parametrize("lower,upper,retained", [(0, 360, [0, 50, 180, 350]), (-200, 200, [0, 50, 180, 350]),
                                                (350, 10, [350, 0])])
def test_wcs11_ucac4_full_turn_preserves_all_rows(
    lower, upper, retained, monkeypatch, tmp_path,
):
    # Synthetic records exercise interval arithmetic, not the disputed native format.
    index = ucac4.Ucac4Index(tmp_path)
    rows = np.zeros(4, dtype=ucac4._UCAC4_DTYPE)
    rows["ra"] = np.array([0, 50, 180, 350]) * 3_600_000
    monkeypatch.setattr(index, "_load_zone", lambda zone: rows)
    monkeypatch.setattr(ucac4, "_zones_for_dec_range", lambda *a: [90])
    np.testing.assert_allclose(index.query_box(lower, upper, -1, 1).ra_deg, retained)


def test_wcs11_ucac5_full_turn_control_keeps_all_rows(monkeypatch):
    index = ucac5.Ucac5Index.__new__(ucac5.Ucac5Index)
    rows = np.zeros(4, dtype=ucac5._UCAC5_U5Z_DTYPE)
    rows["ra_mas"] = np.array([0, 50, 180, 350]) * 3_600_000
    monkeypatch.setattr(index, "_load_zone", lambda zone: rows)
    monkeypatch.setattr(index, "spans_for_radec_box", lambda *a: [ucac5.Ucac5Span(451, 0, 4)])
    np.testing.assert_allclose(index.query_box(0, 360, -1, 1).ra_deg, [0, 50, 180, 350])


def test_wcs24_stripped_header_fov_uses_angular_scale_bounds(tmp_path):
    path = tmp_path / "stripped.fits"
    fits.writeto(path, np.zeros((64, 64), np.float32))
    guess = solver._estimate_fov(path, 4096, 4096, (.5, 1))
    assert guess == pytest.approx((.8533333333333334, .8533333333333334))
    actual = solver._search_half_diag_deg(4096, 4096, (.5, 1), guess, pad_frac=0)
    assert actual == pytest.approx(np.hypot(4096, 4096) / 7200)


def test_wcs12_pc_helper_matrix_and_parity_agree_with_the_wcs():
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.cdelt = [-.001, .002]
    angle = np.deg2rad(30)
    wcs.wcs.pc = [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    np.testing.assert_allclose(pipeline._wcs_matrix(wcs), wcs.pixel_scale_matrix)
    assert pipeline._wcs_det(wcs) == pytest.approx(np.linalg.det(wcs.pixel_scale_matrix))


def test_wcs17_catalog_cap_keeps_the_brighter_source():
    ra, dec = pipeline._limit_catalog_sources(
        np.array([180.001, 180.02]), np.array([0., 0.]),
        ra0_deg=180, dec0_deg=0, max_catalog_stars=1,
        mag=np.array([18., 10.]),
    )
    np.testing.assert_allclose(ra, [180.02])


def test_wcs16_real_sep_axes_remain_ordered_and_the_changed_angle_is_equivalent(monkeypatch):
    y, x = np.mgrid[:128, :128]
    angle = np.deg2rad(-30)
    dx, dy = x - 64.2, y - 63.7
    major = dx * np.cos(angle) + dy * np.sin(angle)
    minor = -dx * np.sin(angle) + dy * np.cos(angle)
    image = (100 + np.random.default_rng(1).normal(size=x.shape)
             + 500 * np.exp(-.5 * ((major / 4) ** 2 + (minor / 2) ** 2))).astype(np.float32)
    original_extract = extraction.sep.extract
    raw = []

    def record(*args, **kwargs):
        sources = original_extract(*args, **kwargs)
        raw.append(sources.copy())
        return sources

    monkeypatch.setattr(extraction, "estimate_background", lambda img, **kw: (
        np.full_like(img, 100), np.ones_like(img)))
    monkeypatch.setattr(extraction.sep, "extract", record)
    sources, _, _ = extraction.extract_sources(
        image, downsample=1, threshold=5, fwhm=0, centroid=False,
        deblend=False, min_fwhm=0, max_fwhm=0, max_ellipticity=0,
    )
    assert len(sources) == len(raw[0]) == 1
    assert raw[0][0]["a"] >= raw[0][0]["b"]
    np.testing.assert_array_equal(sources["a"], raw[0]["a"])
    np.testing.assert_array_equal(sources["b"], raw[0]["b"])
    assert raw[0][0]["theta"] < 0
    assert -np.pi / 2 < sources[0]["theta"] <= np.pi / 2
    # A half-turn changes the range convention, not the represented ellipse.
    np.testing.assert_allclose(np.cos(2 * sources["theta"]), np.cos(2 * raw[0]["theta"]), atol=1e-12)
    np.testing.assert_allclose(np.sin(2 * sources["theta"]), np.sin(2 * raw[0]["theta"]), atol=1e-12)
