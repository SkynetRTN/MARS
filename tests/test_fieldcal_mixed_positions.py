"""Coordinate availability must not silently remove calibration references."""
from datetime import datetime

import numpy as np
import pytest

from algorithms.catalogs.schemas import CatalogSource, Mag
from algorithms.fieldcal.field_cal import _match_detected_sources, perform_field_calibration
from algorithms.fieldcal.schemas import PhotometricCalibrationSettings, PhotometryData
from algorithms.photometry.schemas import SourceExtractionData


@pytest.mark.parametrize("positions", ["sky", "mixed", "pixel"])
def test_provided_calibration_keeps_all_references_without_wcs(positions):
    # Choosing pixels just because one optional centroid exists loses two
    # references. Equal errors give the hand-derived mean ZP (20+20.005+20.02)/3.
    catalog, detections = [], []
    for i in range(3):
        sky = {} if positions == "pixel" else {"ra_hours": 12 + i*.001, "dec_degs": 20}
        pixels = {"x": 10 + i*20, "y": 50} if positions == "pixel" or (
            positions == "mixed" and i == 0) else {}
        catalog.append(CatalogSource(
            id=f"c{i}", catalog_name="APASS", **sky, **pixels,
            mags={"V": Mag(value=14 + i*.1 + .005*i*i, error=.02)},
        ))
        detections.append(PhotometryData(
            id=f"d{i}", **sky, x=10 + i*20, y=50,
            mag=-6 + i*.1, mag_error=.02, flux=1000 + i*10, flux_error=20,
        ))
    zero_point, result = perform_field_calibration(
        {"FILTER": "V"}, np.zeros((100, 100)), catalog_sources=catalog,
        detected_sources=detections, use_provided_photometry=True,
        field_cal_settings=PhotometricCalibrationSettings(
            source_match_tol=.5, source_match_tol_arcsec=2, variable_check_tol=0,
        ),
    )
    assert zero_point == pytest.approx(20.008333333333333)
    assert [source.id for source in result.phot_results] == ["c0", "c1", "c2"]


@pytest.mark.parametrize("extra_pixels", ["other_file", "unrelated_file", "shared"])
def test_matching_selects_coordinates_from_each_files_relevant_rows(extra_pixels):
    # File 2 needs angular matching even though every detection has pixels.
    # An unrelated file must not switch that choice; a shared row is eligible
    # everywhere, but must not hide file 2's sky-only reference either.
    catalog = [CatalogSource(id="sky", file_id=2, ra_hours=12, dec_degs=20)]
    detections = [SourceExtractionData(
        id="d2", file_id=2, x=10, y=10, ra_hours=12, dec_degs=20,
    )]
    pixel_file = {"other_file": 1, "unrelated_file": 3, "shared": None}[extra_pixels]
    catalog.append(CatalogSource(id="pixel", file_id=pixel_file, x=30, y=30))
    if extra_pixels == "other_file":
        detections.insert(0, SourceExtractionData(id="d1", file_id=1, x=30, y=30))
    matched = _match_detected_sources(
        catalog, detections, wcs=None, header={}, data=np.zeros((40, 40)),
        source_match_tol=.5, source_match_tol_arcsec=2,
    )
    expected = [("pixel", 1), ("sky", 2)] if extra_pixels == "other_file" else [("sky", 2)]
    assert [(source.id, source.file_id) for source in matched] == expected


def test_mixed_catalog_angular_matching_applies_reference_epoch_motion():
    catalog = [
        CatalogSource(id="moving", x=10, y=10, ra_hours=12, dec_degs=20,
                      pm_epoch=datetime(2020, 1, 1), pm_sky=2/(3600*86400),
                      pm_pos_angle_sky=0),
        CatalogSource(id="fixed", ra_hours=13, dec_degs=20),
    ]
    detections = [
        SourceExtractionData(id="d0", x=10, y=10, ra_hours=12, dec_degs=20+2/3600),
        SourceExtractionData(id="d1", x=30, y=30, ra_hours=13, dec_degs=20),
    ]
    matched = _match_detected_sources(
        catalog, detections, wcs=None, header={"DATE-OBS": "2020-01-02T00:00:00"},
        data=np.zeros((40, 40)), source_match_tol=.1, source_match_tol_arcsec=.5,
    )
    assert [source.id for source in matched] == ["moving", "fixed"]
    assert [(source.x, source.y) for source in matched] == [(10, 10), (30, 30)]
    assert matched[0].dec_degs == pytest.approx(20+2/3600)


@pytest.mark.parametrize("pixel_tolerance", [.1, 100])
@pytest.mark.parametrize("angular_tolerance", [.5, 2])
def test_mixed_catalog_matches_use_the_angular_tolerance(pixel_tolerance, angular_tolerance):
    catalog = [
        CatalogSource(id="first", x=99, y=99, ra_hours=12, dec_degs=20),
        CatalogSource(id="second", ra_hours=13, dec_degs=20),
    ]
    detections = [
        SourceExtractionData(id="d0", x=10, y=10, ra_hours=12, dec_degs=20+1/3600),
        SourceExtractionData(id="d1", x=30, y=30, ra_hours=13, dec_degs=20+1/3600),
    ]
    arguments = dict(wcs=None, header={}, data=np.zeros((100, 100)),
                     source_match_tol=pixel_tolerance, source_match_tol_arcsec=angular_tolerance)
    if angular_tolerance < 1:
        with pytest.raises(RuntimeError, match="Could not match any"):
            _match_detected_sources(catalog, detections, **arguments)
    else:
        matched = _match_detected_sources(catalog, detections, **arguments)
        assert [source.id for source in matched] == ["first", "second"]


@pytest.mark.parametrize("extra_sky_row", [False, True])
def test_unrelated_sky_row_keeps_all_same_file_pixel_matches(extra_sky_row):
    catalog = [CatalogSource(id=f"pixel{i}", file_id=1, x=10+i*20, y=10) for i in range(3)]
    if extra_sky_row:
        catalog.append(CatalogSource(id="unrelated", file_id=1, ra_hours=15, dec_degs=20))
    detections = [SourceExtractionData(
        id=f"d{i}", file_id=1, x=10+i*20, y=10, ra_hours=12+i*.001, dec_degs=20,
    ) for i in range(3)]
    matched = _match_detected_sources(
        catalog, detections, wcs=None, header={}, data=np.zeros((100, 100)),
        source_match_tol=.5, source_match_tol_arcsec=2,
    )
    assert [source.id for source in matched] == ["pixel0", "pixel1", "pixel2"]


@pytest.mark.parametrize("reverse_catalog", [False, True])
def test_pixel_only_and_sky_only_references_both_match_without_wcs(reverse_catalog):
    catalog = [CatalogSource(id="pixel", x=10.4, y=10),
               CatalogSource(id="sky", ra_hours=13, dec_degs=20)]
    if reverse_catalog:
        catalog.reverse()
    detections = [
        SourceExtractionData(id="d0", x=10, y=10, ra_hours=12, dec_degs=20),
        SourceExtractionData(id="d1", x=30, y=30, ra_hours=13, dec_degs=20+1/3600),
    ]
    matched = _match_detected_sources(
        catalog, detections, wcs=None, header={}, data=np.zeros((100, 100)),
        source_match_tol=.5, source_match_tol_arcsec=2,
    )
    assert [source.id for source in matched] == ["pixel", "sky"]
    assert [(source.x, source.y) for source in matched] == [(10, 10), (30, 30)]


@pytest.mark.parametrize("reverse_catalog", [False, True])
def test_cross_domain_competition_does_not_assign_two_references_to_one_detection(reverse_catalog, caplog):
    # Both domain-specific references claim d0. Their distances have different
    # units, so neither provides a justified winner; preserve only unambiguous d1.
    catalog = [
        CatalogSource(id="pixel", x=10, y=10),
        CatalogSource(id="sky", ra_hours=12, dec_degs=20),
        CatalogSource(id="independent", ra_hours=13, dec_degs=20),
    ]
    if reverse_catalog:
        catalog.reverse()
    detections = [
        SourceExtractionData(id="d0", x=10, y=10, ra_hours=12, dec_degs=20),
        SourceExtractionData(id="d1", x=30, y=30, ra_hours=13, dec_degs=20),
    ]
    matched = _match_detected_sources(
        catalog, detections, wcs=None, header={}, data=np.zeros((100, 100)),
        source_match_tol=.5, source_match_tol_arcsec=2,
    )
    assert [source.id for source in matched] == ["independent"]
    assert "ambiguous" in caplog.text.lower()
    assert all(name in caplog.text for name in ("d0", "pixel", "sky"))


def test_mixed_pixel_reference_applies_pixel_epoch_motion():
    catalog = [
        CatalogSource(id="pixel", x=8, y=10, pm_epoch=datetime(2020, 1, 1),
                      pm_pixel=2/86400, pm_pos_angle_pixel=0),
        CatalogSource(id="sky", ra_hours=13, dec_degs=20),
    ]
    detections = [
        SourceExtractionData(id="d0", x=10, y=10, ra_hours=12, dec_degs=20),
        SourceExtractionData(id="d1", x=30, y=30, ra_hours=13, dec_degs=20),
    ]
    matched = _match_detected_sources(
        catalog, detections, wcs=None, header={"DATE-OBS": "2020-01-02T00:00:00"},
        data=np.zeros((100, 100)), source_match_tol=.5, source_match_tol_arcsec=2,
    )
    assert [source.id for source in matched] == ["pixel", "sky"]


@pytest.mark.parametrize("sky_reference", [False, True])
@pytest.mark.parametrize("sky_detection_has_pixels", [False, True])
def test_mixed_groups_only_require_their_own_detection_coordinates(sky_reference, sky_detection_has_pixels):
    catalog = [CatalogSource(id="pixel", x=10, y=10)]
    if sky_reference:
        catalog.append(CatalogSource(id="sky", ra_hours=13, dec_degs=20))
    detections = [
        SourceExtractionData(id="d0", x=10, y=10),
        SourceExtractionData(id="d1", ra_hours=13, dec_degs=20,
                             **({"x": 30, "y": 30} if sky_detection_has_pixels else {})),
    ]
    matched = _match_detected_sources(
        catalog, detections, wcs=None, header={}, data=np.zeros((100, 100)),
        source_match_tol=.5, source_match_tol_arcsec=2,
    )
    assert [source.id for source in matched] == (["pixel", "sky"] if sky_reference else ["pixel"])


@pytest.mark.parametrize("reference_positions,detection_positions,expected_ids", [
    ("sky", "sky", ["target", "independent"]),
    ("sky", "pixel", ["independent"]),
    ("sky", "dual", ["target", "independent"]),
    ("pixel", "sky", ["independent"]),
    ("pixel", "pixel", ["target", "independent"]),
    ("pixel", "dual", ["target", "independent"]),
    ("dual", "sky", ["target", "independent"]),
    ("dual", "pixel", ["target", "independent"]),
    ("dual", "dual", ["target", "independent"]),
])
def test_mixed_coordinate_pairs_preserve_every_supported_association(
    reference_positions, detection_positions, expected_ids,
):
    sky = {"ra_hours": 12, "dec_degs": 20}
    pixel = {"x": 10, "y": 10}
    positions = {"sky": sky, "pixel": pixel, "dual": dict(sky, **pixel)}
    catalog = [
        CatalogSource(id="target", **positions[reference_positions]),
        CatalogSource(id="independent", ra_hours=13, dec_degs=20),
    ]
    detections = [
        SourceExtractionData(id="target_detection", **positions[detection_positions]),
        SourceExtractionData(id="independent_detection", x=30, y=30, ra_hours=13, dec_degs=20),
    ]
    matched = _match_detected_sources(
        catalog, detections, wcs=None, header={}, data=np.zeros((100, 100)),
        source_match_tol=.5, source_match_tol_arcsec=2,
    )
    assert [source.id for source in matched] == expected_ids


@pytest.mark.parametrize("reverse_inputs", [False, True])
def test_dual_reference_competing_sky_and_pixel_detections_are_both_withheld(reverse_inputs, caplog):
    catalog = [
        CatalogSource(id="dual", x=10, y=10, ra_hours=12, dec_degs=20),
        CatalogSource(id="independent", ra_hours=13, dec_degs=20),
    ]
    detections = [
        SourceExtractionData(id="sky_detection", ra_hours=12, dec_degs=20),
        SourceExtractionData(id="pixel_detection", x=10, y=10),
        SourceExtractionData(id="independent_detection", ra_hours=13, dec_degs=20),
    ]
    if reverse_inputs:
        catalog.reverse()
        detections.reverse()
    matched = _match_detected_sources(
        catalog, detections, wcs=None, header={}, data=np.zeros((100, 100)),
        source_match_tol=.5, source_match_tol_arcsec=2,
    )
    assert [source.id for source in matched] == ["independent"]
    assert "ambiguous" in caplog.text.lower()
    assert all(name in caplog.text for name in ("dual", "sky_detection", "pixel_detection"))


@pytest.mark.parametrize("reverse_catalog", [False, True])
@pytest.mark.parametrize("nearest_reference", ["pixel", "dual"])
def test_pixel_only_detection_chooses_nearest_reference_across_pixel_groups(
    nearest_reference, reverse_catalog,
):
    # Both distances are in pixels: 0.1 beats 0.4 regardless of which
    # reference also has sky coordinates or where it appears in the catalog.
    catalog = [
        CatalogSource(id="pixel", x=10.1 if nearest_reference == "pixel" else 10.4, y=10),
        CatalogSource(id="dual", x=10.1 if nearest_reference == "dual" else 10.4,
                      y=10, ra_hours=12, dec_degs=20),
        CatalogSource(id="independent", ra_hours=13, dec_degs=20),
    ]
    if reverse_catalog:
        catalog.reverse()
    detections = [
        SourceExtractionData(id="pixel_detection", x=10, y=10),
        SourceExtractionData(id="independent_detection", ra_hours=13, dec_degs=20),
    ]
    matched = _match_detected_sources(
        catalog, detections, wcs=None, header={}, data=np.zeros((100, 100)),
        source_match_tol=.5, source_match_tol_arcsec=2,
    )
    assert [source.id for source in matched] == [nearest_reference, "independent"]
    assert (matched[0].x, matched[0].y) == (10, 10)


@pytest.mark.parametrize("reverse_catalog", [False, True])
@pytest.mark.parametrize("nearest_reference,blocker_positions", [
    ("pixel", "pixel"), ("pixel", "dual"), ("dual", "pixel"),
])
def test_pixel_nearest_rejected_by_reverse_neighbor_does_not_fall_back(
    nearest_reference, blocker_positions, reverse_catalog,
):
    # d0's nearest is 0.2 pixels away, but d1 is only 0.05 from it.
    # The other group's reference is 0.4 from d0 and 0.65 from d1: accepting
    # it would bypass the forward nearest-neighbor requirement.
    catalog = [
        CatalogSource(id="pixel", x=10.2 if nearest_reference == "pixel" else 9.6, y=10),
        CatalogSource(id="dual", x=10.2 if nearest_reference == "dual" else 9.6,
                      y=10, ra_hours=12, dec_degs=20),
        CatalogSource(id="independent", ra_hours=13, dec_degs=20),
    ]
    if reverse_catalog:
        catalog.reverse()
    detections = [
        SourceExtractionData(id="d0", x=10, y=10),
        SourceExtractionData(id="d1", x=10.25, y=10,
                             **({"ra_hours": 14, "dec_degs": 20} if blocker_positions == "dual" else {})),
        SourceExtractionData(id="independent_detection", ra_hours=13, dec_degs=20),
    ]
    matched = _match_detected_sources(
        catalog, detections, wcs=None, header={}, data=np.zeros((100, 100)),
        source_match_tol=.5, source_match_tol_arcsec=2,
    )
    assert [source.id for source in matched] == [nearest_reference, "independent"]
    assert (matched[0].x, matched[0].y) == (10.25, 10)


def test_dual_reference_pixel_reverse_neighbor_excludes_angular_only_pair():
    # The closer dual detection must use angular distance for the dual row.
    # Its mismatching sky position cannot block the eligible pixel-only pair.
    catalog = [
        CatalogSource(id="pixel", x=9.6, y=10),
        CatalogSource(id="dual", x=10.1, y=10, ra_hours=12, dec_degs=20),
        CatalogSource(id="independent", ra_hours=13, dec_degs=20),
    ]
    detections = [
        SourceExtractionData(id="pixel_detection", x=10, y=10),
        SourceExtractionData(id="dual_detection", x=10.11, y=10, ra_hours=14, dec_degs=20),
        SourceExtractionData(id="independent_detection", ra_hours=13, dec_degs=20),
    ]
    matched = _match_detected_sources(
        catalog, detections, wcs=None, header={}, data=np.zeros((100, 100)),
        source_match_tol=.5, source_match_tol_arcsec=2,
    )
    assert [source.id for source in matched] == ["dual", "independent"]


@pytest.mark.parametrize("reverse_catalog", [False, True])
def test_joint_pixel_nearest_keeps_true_cross_domain_reference_ambiguity(reverse_catalog, caplog):
    # A jointly nearest pixel reference also has an angular claimant. There
    # is no unit-compatible winner and d0 must not be reassigned to "far".
    catalog = [
        CatalogSource(id="far", x=10.4, y=10),
        CatalogSource(id="dual", x=10.1, y=10, ra_hours=12, dec_degs=20),
        CatalogSource(id="independent", ra_hours=13, dec_degs=20),
    ]
    if reverse_catalog:
        catalog.reverse()
    detections = [
        SourceExtractionData(id="pixel_detection", x=10, y=10),
        SourceExtractionData(id="sky_detection", ra_hours=12, dec_degs=20),
        SourceExtractionData(id="independent_detection", ra_hours=13, dec_degs=20),
    ]
    matched = _match_detected_sources(
        catalog, detections, wcs=None, header={}, data=np.zeros((100, 100)),
        source_match_tol=.5, source_match_tol_arcsec=2,
    )
    assert [source.id for source in matched] == ["independent"]
    assert all(name in caplog.text for name in ("dual", "pixel_detection", "sky_detection"))
