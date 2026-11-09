"""M5 shared catalog preparation: spherical coverage, epochs and selection."""

from types import SimpleNamespace

import numpy as np
import pytest
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.wcs import WCS

from algorithms.query.geometry import boxes_from_wcs, image_boxes_from_wcs, clip_sources_to_box
from algorithms.catalogs.schemas import CatalogSource


@pytest.mark.parametrize("helper", [boxes_from_wcs, image_boxes_from_wcs])
@pytest.mark.parametrize("center,crpix", [([359.99, 45], [-40, 70]), ([0, 89.95], [50, 25])])
def test_legacy_boxes_enclose_rotated_anisotropic_and_displaced_detectors(helper, center, crpix):
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = center
    wcs.wcs.crpix = crpix
    angle = np.deg2rad(43)
    wcs.wcs.cd = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]) @ np.diag([-.003, .001])
    wcs.array_shape = (50, 100)
    xy = np.array([(x, y) for x in np.linspace(.01, 99.99, 12) for y in np.linspace(.01, 49.99, 9)])
    world = wcs.all_pix2world(xy, 0)
    rows = [CatalogSource(id=str(i), ra_hours=ra / 15, dec_degs=dec) for i, (ra, dec) in enumerate(world)]
    selected = set()
    for ra, dec, width, height in helper(wcs):
        selected.update(s.id for s in clip_sources_to_box(rows, ra / 15, dec, width * 60, height * 60))
    assert selected == {str(i) for i in range(len(rows))}


def test_spherical_query_propagates_a_star_moving_into_the_footprint():
    from algorithms.skylib_lite.astrometry.atlas.catalog.geometry import query_spherical_catalog

    seen = []
    # 100 mas/yr west over 10 years enters a 0.01-degree footprint.
    def query(lo, hi, bottom, top, **kwargs):
        seen.append((lo, hi))
        if lo <= .0102 <= hi:
            return SimpleNamespace(ra_deg=np.array([.0102]), dec_deg=np.array([0.]),
                                   mag=np.array([12.]), epoch_jyear=2015.,
                                   pm_ra_cosdec_mas_per_year=np.array([-100.]),
                                   pm_dec_mas_per_year=np.array([0.]))
        return SimpleNamespace(ra_deg=np.array([]), dec_deg=np.array([]))

    index = SimpleNamespace(query_box=query, epoch_jyear=2015., max_pm_mas_per_year=100.)
    result = query_spherical_catalog(index, 0., 0., .01, epoch_jyear=2025., max_radius_deg=2.)
    assert result.ra_deg == pytest.approx([.009922222222222222], abs=1e-10)
    assert result.dec_deg == pytest.approx([0.])
    assert result.mag == pytest.approx([12.])
    assert seen[0][1] > .0102


def test_catalog_motion_crosses_ra_zero_without_losing_alignment():
    from algorithms.skylib_lite.astrometry.atlas.catalog.geometry import query_spherical_catalog

    def query(*args, **kwargs):
        return SimpleNamespace(ra_deg=np.array([359.9999]), dec_deg=np.array([0.]),
                               mag=np.array([11.]), epoch_jyear=2015.,
                               pm_ra_cosdec_mas_per_year=np.array([100.]),
                               pm_dec_mas_per_year=np.array([0.]))
    index = SimpleNamespace(query_box=query, epoch_jyear=2015., max_pm_mas_per_year=100.)
    result = query_spherical_catalog(index, 0., 0., .01, epoch_jyear=2025., max_radius_deg=2.)
    assert result.ra_deg == pytest.approx([.0001777777777777778], abs=1e-10)
    assert result.mag == pytest.approx([11.])


def test_spherical_query_covers_a_full_turn_across_a_pole():
    from algorithms.skylib_lite.astrometry.atlas.catalog.geometry import query_spherical_catalog

    seen = []
    def query(*args, **kwargs):
        seen.append(args)
        return SimpleNamespace(ra_deg=np.array([0., 180.]), dec_deg=np.array([89.99, 89.99]))
    result = query_spherical_catalog(SimpleNamespace(query_box=query), 0, 89.99, .05, max_radius_deg=2)
    assert seen == [(0., 360., 89.94, 90.)]
    assert len(result.ra_deg) == 2


def test_motion_halo_cannot_silently_exceed_the_catalog_radius_budget():
    from algorithms.skylib_lite.astrometry.atlas.catalog.geometry import query_spherical_catalog

    def forbidden(*args, **kwargs):
        pytest.fail("oversized footprint reached catalog I/O")
    index = SimpleNamespace(query_box=forbidden, epoch_jyear=2015., max_pm_mas_per_year=10000.)
    with pytest.raises(ValueError, match="footprint"):
        query_spherical_catalog(index, 0, 0, 1.99, epoch_jyear=2025, max_radius_deg=2)


def test_mjd_only_observation_uses_the_exposure_midpoint():
    from algorithms.skylib_lite.astrometry.atlas.catalog.geometry import observation_epoch
    from astropy.time import Time
    # MJD 51544 is 2000-01-01 00:00; a full-day exposure centers at J2000 noon.
    assert observation_epoch({"MJD-OBS": 51544., "EXPTIME": 86400.}) == pytest.approx(2000., rel=0, abs=1e-10)


def test_unknown_catalog_epoch_is_disclosed_through_the_public_warning_collector():
    from algorithms.skylib_lite.astrometry.atlas.catalog.geometry import query_spherical_catalog
    from tools.science_warnings import capture_numerical_warnings
    warnings = []
    index = SimpleNamespace(query_box=lambda *a, **k: SimpleNamespace(
        ra_deg=np.array([0.]), dec_deg=np.array([0.])))
    with capture_numerical_warnings(warnings):
        result = query_spherical_catalog(index, 0, 0, .01, epoch_jyear=2025)
    assert len(result.ra_deg) == 1
    assert [warning.code for warning in warnings] == ["astrometry_catalog_epoch_unverified"]


def test_brightness_selection_preserves_zero_and_masked_rows():
    from algorithms.skylib_lite.astrometry.atlas.catalog.geometry import catalog_indices
    xy = np.array([[.001, 0], [.002, 0], [.003, 0]])
    magnitudes = np.ma.array([10., 0., -5.], mask=[False, False, True])
    np.testing.assert_array_equal(catalog_indices(xy, 1, magnitudes), [1])


def test_a_nonfinite_catalog_projection_cannot_enter_the_selection():
    from algorithms.skylib_lite.astrometry.atlas.catalog.geometry import catalog_indices
    np.testing.assert_array_equal(catalog_indices(np.array([[np.nan, np.nan], [.01, 0.]]), 3), [1])


def test_pc_backend_metadata_matches_the_actual_transformation(monkeypatch, tmp_path):
    from astropy.io import fits
    from algorithms.wcs import wcs as pipeline
    from algorithms.wcs.schemas import SourceExtractionData
    from algorithms.skylib_lite.astrometry.types import SolveSolution
    solution = WCS(naxis=2)
    solution.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    solution.wcs.crval = [180, 0]
    solution.wcs.crpix = [16.5, 16.5]
    solution.wcs.cdelt = [-.001, .002]
    angle = np.deg2rad(30)
    solution.wcs.pc = [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    monkeypatch.setattr(pipeline, "run_source_extraction", lambda *a, **k: (
        [SourceExtractionData(x=10, y=10, flux=100)], None, None))
    monkeypatch.setattr(pipeline, "build_anet_config", lambda *a: object())
    monkeypatch.setattr(pipeline, "build_atlas_config", lambda *a: None)
    monkeypatch.setattr(pipeline.AstrometryNetBackend, "is_available", lambda *a: True)
    monkeypatch.setattr(pipeline.AstrometryNetBackend, "solve", lambda *a, **k: SolveSolution(wcs=solution))
    header = fits.Header({"NAXIS1": 32, "NAXIS2": 32, "RA": 180, "DEC": 0})
    result = pipeline.solve_wcs(header, np.zeros((32, 32)), tmp_path)
    assert result.wcs is not None
    actual = np.array([[result.metadata.cd11, result.metadata.cd12],
                       [result.metadata.cd21, result.metadata.cd22]])
    np.testing.assert_allclose(actual, solution.pixel_scale_matrix)


def test_reference_followup_keeps_the_propagated_epoch_and_motion(monkeypatch, tmp_path):
    from algorithms.wcs import wcs as pipeline
    from algorithms.skylib_lite.astrometry.atlas.config import AtlasConfig
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [180, 0]
    wcs.wcs.crpix = [16.5, 16.5]
    wcs.wcs.cdelt = [-1 / 3600, 1 / 3600]
    def query(*a, **k):
        return SimpleNamespace(ra_deg=np.array([180.]), dec_deg=np.array([0.]),
                               mag=np.array([12.]), epoch_jyear=2015.,
                               pm_ra_cosdec_mas_per_year=np.array([100.]),
                               pm_dec_mas_per_year=np.array([0.]))
    index = SimpleNamespace(query_box=query, epoch_jyear=2015., max_pm_mas_per_year=100.)
    monkeypatch.setattr(pipeline, "get_catalog_spec", lambda name: SimpleNamespace(index_factory=lambda root: index))
    rows = pipeline._load_atlas_catalog_sources(AtlasConfig(catalog_roots={"ucac5": tmp_path}),
                                               wcs_obj=wcs, width=32, height=32, file_id=None,
                                               epoch_jyear=2025.)
    assert len(rows) == 1
    assert rows[0].ra_hours * 15 == pytest.approx(180.00027777777778)
    assert rows[0].pm_sky == pytest.approx(100 / 3_600_000 / (365.25 * 86400), rel=1e-12, abs=0)
    assert rows[0].pm_pos_angle_sky == pytest.approx(90.)
    assert rows[0].pm_epoch is not None
    # The downstream extraction/calibration convention is a naive UTC epoch.
    from algorithms.wcs.source_extraction import get_source_xy
    from datetime import datetime
    x, y = get_source_xy(rows[0], datetime(2025, 1, 1), wcs)
    assert np.isfinite([x, y]).all()


def test_polar_query_cannot_double_the_native_candidate_budget(monkeypatch, tmp_path):
    from algorithms.skylib_lite.astrometry.atlas.catalog import ucac4, limits
    from algorithms.skylib_lite.astrometry.atlas.catalog.geometry import query_spherical_catalog
    index = ucac4.Ucac4Index(tmp_path)
    rows = np.zeros(18, dtype=ucac4._UCAC4_DTYPE)
    rows["ra"] = np.arange(10, 360, 20) * 3_600_000
    # Candidates lie in the zone but outside the requested narrow Dec range.
    rows["dec"] = int(89.5 * 3_600_000)
    monkeypatch.setattr(index, "_load_zone", lambda zone: rows)
    monkeypatch.setattr(ucac4, "_zones_for_dec_range", lambda *a: [179])
    monkeypatch.setattr(limits, "MAX_QUERY_CANDIDATES", 10)
    with pytest.raises(ValueError, match="budget"):
        query_spherical_catalog(index, 0, 89.99, .02)


def test_missing_source_epoch_is_not_relabelled_as_the_observation_epoch():
    from algorithms.skylib_lite.astrometry.atlas.catalog.geometry import query_spherical_catalog
    index = SimpleNamespace(query_box=lambda *a, **k: SimpleNamespace(
        ra_deg=np.array([0.]), dec_deg=np.array([0.]),
        pm_ra_cosdec_mas_per_year=np.array([100.]), pm_dec_mas_per_year=np.array([0.])))
    result = query_spherical_catalog(index, 0, 0, .01, epoch_jyear=2025)
    assert result.epoch_jyear is None


@pytest.mark.parametrize("duration", [-86400., float("nan"), float("inf")])
def test_invalid_exposure_does_not_create_an_observation_epoch(duration):
    from algorithms.skylib_lite.astrometry.atlas.catalog.geometry import observation_epoch
    assert observation_epoch({"DATE-OBS": "2025-01-01T00:00:00", "EXPTIME": duration}) is None


def test_nonfinite_motion_is_not_presented_at_a_propagated_epoch():
    from algorithms.skylib_lite.astrometry.atlas.catalog.geometry import query_spherical_catalog
    index = SimpleNamespace(epoch_jyear=2015., max_pm_mas_per_year=100.,
        query_box=lambda *a, **k: SimpleNamespace(
            ra_deg=np.array([0., 0.]), dec_deg=np.array([0., 0.]), epoch_jyear=2015.,
            pm_ra_cosdec_mas_per_year=np.array([100., np.nan]), pm_dec_mas_per_year=np.array([0., 0.])))
    result = query_spherical_catalog(index, 0, 0, .01, epoch_jyear=2025)
    assert len(result.ra_deg) == 1
    assert result.epoch_jyear == 2025.
