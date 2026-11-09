"""Field-calibration orchestration and matching.

``fieldcal`` receives WCS and catalog data as explicit inputs, then composes
deterministic extraction and photometry locally. This file covers those inputs
and the source matching that feeds the solver; the solver itself is in
``test_fieldcal_solution.py``.

Two documented invariants get particular attention because both are the kind of
thing a tidy-up would break:

* calibration photometry forces ``apcorr_tol = 0.0``, which is what keeps the
  zero point matching legacy Afterglow.

The end-to-end test at the bottom runs the whole thing on a real frame with the
seam wired to MARS's own ``algorithms/photometry/`` and ``algorithms/wcs/`` — no network, catalog
sources supplied directly.

Modelled on ``skynet .../tests/runners/test_field_cal.py``.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.wcs import WCS

from algorithms.catalogs.schemas import CatalogSource, Mag
from algorithms.fieldcal.field_cal import (
    _attach_catalog_magnitudes,
    _catalog_filter_lookup_map,
    _catalogs_from_sources,
    _collect_calibration_sources,
    _ensure_unique_source_ids,
    _has_reference_magnitudes,
    _image_filter_from_header,
    _match_detected_sources,
    _normalize_catalog_sources,
    perform_field_calibration,
)
from algorithms.fieldcal.schemas import (
    PhotometricCalibrationSettings,
    PhotometryData,
    SourceExtractionData,
    SourceExtractionSettings,
)
from algorithms.fieldcal.schemas import PhotometrySettings as FieldCalPhotometrySettings


def _wcs(crpix=(512.0, 512.0), crval=(180.0, 10.0), scale=1.7e-4, shape=(1027, 1056)):
    w = WCS(naxis=2)
    w.wcs.crpix = list(crpix)
    w.wcs.crval = list(crval)
    w.wcs.cd = np.array([[scale, 0.0], [0.0, scale]])
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.array_shape = shape
    return w


def _catalog_source(idx, ra_hours, dec_degs, *, mags=None, **kw):
    return CatalogSource(
        id=f"cat-{idx}",
        catalog_name="APASS",
        ra_hours=ra_hours,
        dec_degs=dec_degs,
        mags=mags or {"V": Mag(value=14.0 + idx * 0.1, error=0.02)},
        **kw,
    )


# ---------------------------------------------------------------------------
# Explicit calibration inputs
# ---------------------------------------------------------------------------

def test_calibration_requires_supplied_catalog_sources():
    with pytest.raises(ValueError, match="Missing catalog sources"):
        perform_field_calibration({}, np.zeros((4, 4), dtype=np.float32), wcs=_wcs())


def test_calibration_settings_cannot_supply_catalog_sources():
    assert "catalog_sources" not in PhotometricCalibrationSettings.model_fields
    with pytest.raises(ValueError, match="Missing catalog sources"):
        perform_field_calibration(
            {},
            np.zeros((4, 4), dtype=np.float32),
            wcs=_wcs(),
            field_cal_settings=PhotometricCalibrationSettings(),
        )


# ---------------------------------------------------------------------------
# Catalog-source normalisation
# ---------------------------------------------------------------------------

def test_normalize_accepts_models_and_mappings_alike():
    normalized = _normalize_catalog_sources(
        [
            _catalog_source(0, 12.0, 13.5),
            {"id": "cat-1", "catalog_name": "APASS", "ra_hours": 12.001, "dec_degs": 13.51},
        ],
        file_id=77,
    )
    assert [s.id for s in normalized] == ["cat-0", "cat-1"]
    assert all(isinstance(s, CatalogSource) for s in normalized)


def test_normalize_backfills_file_id_but_never_overwrites_one():
    normalized = _normalize_catalog_sources(
        [_catalog_source(0, 12.0, 13.5), _catalog_source(1, 12.0, 13.5, file_id=5)],
        file_id=77,
    )
    assert [s.file_id for s in normalized] == [77, 5]


def test_missing_source_ids_are_generated_with_a_call_local_prefix():
    sources = [CatalogSource(ra_hours=1.0, dec_degs=2.0) for _ in range(3)]
    _ensure_unique_source_ids(sources, file_id=42)

    assert all(s.id and s.id.endswith(f"_{i + 1}") for i, s in enumerate(sources))
    assert all(s.id.startswith("fieldcal_42_") for s in sources)


def test_duplicate_source_ids_are_rejected():
    """Duplicate IDs would make ``_collect_calibration_sources`` drop matches.

    That stage keys photometry back to catalog rows by ``id``; a collision there
    silently attaches the wrong reference magnitude, so it is caught up front.
    """
    sources = [CatalogSource(id="dup", ra_hours=1.0, dec_degs=2.0) for _ in range(2)]
    with pytest.raises(ValueError, match='Non-unique source ID "dup"'):
        _ensure_unique_source_ids(sources, file_id=1)


def test_ids_may_repeat_across_different_files():
    """Uniqueness is per ``(id, file_id)`` — a stack shares catalog IDs."""
    sources = [
        CatalogSource(id="shared", file_id=1, ra_hours=1.0, dec_degs=2.0),
        CatalogSource(id="shared", file_id=2, ra_hours=1.0, dec_degs=2.0),
    ]
    _ensure_unique_source_ids(sources, file_id=1)  # must not raise


def test_magnitude_dicts_are_promoted_to_mag_models():
    source = CatalogSource(id="x", ra_hours=1.0, dec_degs=2.0)
    source.mags = {"V": {"value": 14.2, "error": 0.03}}
    _attach_catalog_magnitudes([source])

    assert isinstance(source.mags["V"], Mag)
    assert source.mags["V"].value == pytest.approx(14.2)


def test_has_reference_magnitudes_accepts_either_ref_mag_or_a_mags_table():
    assert _has_reference_magnitudes([CatalogSource(id="a", ref_mag=14.0)])
    assert _has_reference_magnitudes(
        [CatalogSource(id="b", mags={"V": Mag(value=14.0)})]
    )
    assert not _has_reference_magnitudes([CatalogSource(id="c")])
    assert not _has_reference_magnitudes([])


def test_catalogs_from_sources_preserves_first_seen_order():
    """Order matters: it becomes the PHOT_CAL header string."""
    sources = [
        CatalogSource(id="a", catalog_name="APASS"),
        CatalogSource(id="b", catalog_name="SDSS"),
        CatalogSource(id="c", catalog_name="APASS"),
        CatalogSource(id="d", catalog_name=None),
    ]
    assert _catalogs_from_sources(sources) == ["APASS", "SDSS"]


def test_catalog_filter_lookup_map_covers_configured_and_observed_catalogs():
    lookup = _catalog_filter_lookup_map(
        [CatalogSource(id="a", catalog_name="SDSS")], configured_catalogs=["APASS"]
    )
    assert set(lookup) == {"APASS", "SDSS"}
    assert lookup["APASS"]["R"].startswith("rprime")


def test_unknown_catalog_name_maps_to_an_empty_lookup_not_an_error():
    assert _catalog_filter_lookup_map(
        [CatalogSource(id="a", catalog_name="NoSuchCatalog")]
    ) == {"NoSuchCatalog": {}}


# ---------------------------------------------------------------------------
# FILTER extraction from real headers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "frame,expected",
    [("ngc3628", "V"), ("m15_lum", "Lum"), ("m15_open", "Open"), ("carina", "V")],
)
def test_image_filter_read_from_real_headers(frame_header, frame, expected):
    assert _image_filter_from_header(frame_header(frame)) == expected


def test_image_filter_handles_absent_blank_and_none_headers():
    assert _image_filter_from_header(None) is None
    assert _image_filter_from_header({}) is None
    assert _image_filter_from_header({"FILTER": "   "}) is None
    assert _image_filter_from_header({"FILTER": " V "}) == "V"


# ---------------------------------------------------------------------------
# Detected-source matching
# ---------------------------------------------------------------------------

def test_matching_requires_a_positive_tolerance():
    with pytest.raises(ValueError, match="Positive catalog source match tolerance"):
        _match_detected_sources(
            [_catalog_source(0, 12.0, 13.5)],
            [SourceExtractionData(id="d0", x=10.0, y=10.0)],
            wcs=_wcs(), header={}, data=np.zeros((4, 4)), source_match_tol=0,
        )


def test_no_detected_sources_passes_catalog_sources_through_untouched():
    catalog = [_catalog_source(0, 12.0, 13.5)]
    assert _match_detected_sources(
        catalog, [], wcs=_wcs(), header={}, data=np.zeros((4, 4)), source_match_tol=5,
    ) is catalog


def test_pixel_mode_needs_a_wcs_when_catalog_has_only_sky_coordinates():
    with pytest.raises(ValueError, match="Missing WCS"):
        _match_detected_sources(
            [_catalog_source(0, 12.0, 13.5)],
            [SourceExtractionData(id="d0", x=10.0, y=10.0)],
            wcs=None, header={}, data=np.zeros((4, 4)), source_match_tol=5,
        )


def test_sky_only_mode_uses_an_explicit_angular_tolerance_without_wcs():
    w = _wcs()
    ra_deg, dec_deg = w.all_pix2world(500.0, 500.0, 1)
    ra_hours = float(ra_deg) / 15.0

    catalog = [_catalog_source(0, ra_hours, float(dec_deg))]
    detected = [
        SourceExtractionData(id="d0", x=500.0, y=500.0, ra_hours=ra_hours, dec_degs=float(dec_deg))
    ]

    matched = _match_detected_sources(
        catalog, detected, wcs=None, header={}, data=np.zeros((4, 4)),
        source_match_tol=5.0, source_match_tol_arcsec=5.0,
    )
    assert len(matched) == 1
    assert matched[0].catalog_name == "APASS"


def test_matching_is_mutual_nearest_neighbour():
    """Two detections near one catalog star yield exactly one match.

    The reverse query is what makes this a mutual match. Without it, both
    detections would claim the same catalog star and the zero-point solve would
    see the same reference magnitude twice, tightening the fit on a duplicate.
    """
    w = _wcs()
    ra_deg, dec_deg = w.all_pix2world(500.0, 500.0, 1)
    ra_hours, dec = float(ra_deg) / 15.0, float(dec_deg)

    # Second detection is offset by ~1 arcsec in dec — inside tolerance, but
    # farther from the catalog star than the first.
    detected = [
        SourceExtractionData(id="d0", x=500.0, y=500.0, ra_hours=ra_hours, dec_degs=dec),
        SourceExtractionData(id="d1", x=502.0, y=500.0, ra_hours=ra_hours, dec_degs=dec + 1 / 3600),
    ]
    matched = _match_detected_sources(
        [_catalog_source(0, ra_hours, dec)], detected,
        wcs=None, header={}, data=np.zeros((4, 4)),
        source_match_tol=10.0, source_match_tol_arcsec=10.0,
    )
    assert len(matched) == 1
    assert matched[0].id == "cat-0"


def test_unmatchable_sources_raise_rather_than_returning_empty():
    """An empty match set is a failed calibration, not a zero-source solve."""
    with pytest.raises(RuntimeError, match="Could not match any detected sources"):
        _match_detected_sources(
            [_catalog_source(0, 1.0, 1.0)],
            [SourceExtractionData(id="d0", x=5.0, y=5.0, ra_hours=20.0, dec_degs=-80.0)],
            wcs=None, header={}, data=np.zeros((4, 4)),
            source_match_tol=1.0, source_match_tol_arcsec=1.0,
        )


def test_matched_source_takes_catalog_identity_and_detected_geometry():
    """The merge is directional: catalog wins on identity, detection on position.

    A match returns a ``CatalogSource``, which has no ``filter`` /
    ``telescope`` / ``exp_length`` / FWHM fields at all — hence the explicit
    exclude list at the merge site. That is why ``perform_field_calibration``
    has to restore FILTER from the header afterwards in
    ``use_provided_photometry`` mode: the information is not dropped by
    oversight, it has nowhere to go.
    """
    w = _wcs()
    ra_deg, dec_deg = w.all_pix2world(500.0, 500.0, 1)
    ra_hours, dec = float(ra_deg) / 15.0, float(dec_deg)

    detected = [
        SourceExtractionData(
            id="detected-id", x=500.0, y=500.0, ra_hours=ra_hours, dec_degs=dec,
            filter="V", telescope="Prompt5", exp_length=90.0, fwhm_x=3.2, fwhm_y=3.1,
        )
    ]
    matched = _match_detected_sources(
        [_catalog_source(0, ra_hours, dec)], detected,
        wcs=None, header={}, data=np.zeros((4, 4)),
        source_match_tol=5.0, source_match_tol_arcsec=5.0,
    )[0]

    assert isinstance(matched, CatalogSource)
    assert matched.id == "cat-0"
    assert matched.catalog_name == "APASS"
    assert matched.x == pytest.approx(500.0)
    assert matched.mags["V"].value == pytest.approx(14.0)

    for dropped in ("filter", "telescope", "exp_length", "fwhm_x", "fwhm_y", "theta"):
        assert dropped not in CatalogSource.model_fields


def test_catalog_sources_without_file_id_are_offered_to_every_file():
    """A query answered once for a stack must match all of its frames."""
    w = _wcs()
    ra_deg, dec_deg = w.all_pix2world(500.0, 500.0, 1)
    ra_hours, dec = float(ra_deg) / 15.0, float(dec_deg)

    detected = [
        SourceExtractionData(id="d0", file_id=1, x=500.0, y=500.0, ra_hours=ra_hours, dec_degs=dec),
        SourceExtractionData(id="d1", file_id=2, x=500.0, y=500.0, ra_hours=ra_hours, dec_degs=dec),
    ]
    matched = _match_detected_sources(
        [_catalog_source(0, ra_hours, dec)], detected,
        wcs=None, header={}, data=np.zeros((4, 4)),
        source_match_tol=5.0, source_match_tol_arcsec=5.0,
    )
    assert sorted(m.file_id for m in matched) == [1, 2]


def test_pixel_matching_without_wcs_preserves_the_pixel_tolerance():
    catalog = [CatalogSource(id="near", x=10.9, y=10), CatalogSource(id="far", x=10, y=20)]
    matched = _match_detected_sources(
        catalog, [SourceExtractionData(id="det", x=10, y=10)],
        wcs=None, header={}, data=np.zeros((30, 30)), source_match_tol=1,
    )
    assert [source.id for source in matched] == ["near"]


def test_wcs_matching_prefers_measured_pixels_over_supplied_sky_coordinates():
    wcs = _wcs()
    ra, dec = wcs.all_pix2world([500, 510], [500, 500], 1)
    detected = SourceExtractionData(id="det", x=500, y=500,
        ra_hours=float(ra[1] / 15), dec_degs=float(dec[1]))
    matched = _match_detected_sources(
        [_catalog_source(0, float(ra[0] / 15), float(dec[0])),
         _catalog_source(1, float(ra[1] / 15), float(dec[1]))], [detected],
        wcs=wcs, header={}, data=np.zeros((1027, 1056)), source_match_tol=1,
    )
    assert [source.id for source in matched] == ["cat-0"]
    assert (matched[0].x, matched[0].y) == (500, 500)


@pytest.mark.parametrize("crval", [(0, 0), (179, 89.99), (179, -89.99)])
def test_wcs_matching_projects_sky_only_detections_at_origin_one(crval):
    wcs = _wcs(crpix=(10, 10), crval=crval)
    ra, dec = wcs.all_pix2world([10, 10.8], [10, 10], 1)
    matched = _match_detected_sources(
        [_catalog_source(0, float(ra[0] / 15), float(dec[0]))],
        [SourceExtractionData(id="det", ra_hours=float(ra[1] / 15), dec_degs=float(dec[1]))],
        wcs=wcs, header={}, data=np.zeros((20, 20)), source_match_tol=1,
    )
    assert [source.id for source in matched] == ["cat-0"]
    assert matched[0].x == pytest.approx(10.8, abs=1e-8)
    assert matched[0].y == pytest.approx(10, abs=1e-8)


# ---------------------------------------------------------------------------
# Calibration-source collection
# ---------------------------------------------------------------------------

def _phot(source_id, mag, *, filter="V"):
    return PhotometryData(id=source_id, mag=mag, mag_error=0.02, filter=filter)


def test_collect_resolves_reference_magnitudes_through_the_filter_lookup():
    catalog = [_catalog_source(0, 1.0, 2.0, mags={"V": Mag(value=15.5, error=0.03)})]
    catalog[0].id = "s0"

    collected = _collect_calibration_sources(
        [_phot("s0", 13.0)], catalog,
        catalog_filter_lookup={"APASS": {}}, custom_filter_lookup=None,
    )
    assert len(collected) == 1
    assert collected[0].ref_mag == pytest.approx(15.5)
    assert collected[0].ref_mag_error == pytest.approx(0.03)
    assert collected[0].catalog_name == "APASS"


def test_collect_prefers_a_ref_mag_already_on_the_catalog_source():
    """A backend that already resolved the band must not be second-guessed."""
    catalog = [_catalog_source(0, 1.0, 2.0, mags={"V": Mag(value=15.5)})]
    catalog[0].id = "s0"
    catalog[0].ref_mag = 99.0

    collected = _collect_calibration_sources(
        [_phot("s0", 13.0)], catalog,
        catalog_filter_lookup={"APASS": {}}, custom_filter_lookup=None,
    )
    assert collected[0].ref_mag == pytest.approx(99.0)


def test_collect_drops_photometry_with_no_matching_catalog_row():
    catalog = [_catalog_source(0, 1.0, 2.0)]
    catalog[0].id = "s0"
    assert _collect_calibration_sources(
        [_phot("unmatched", 13.0)], catalog,
        catalog_filter_lookup=None, custom_filter_lookup=None,
    ) == []


def test_collect_drops_sources_whose_filter_cannot_be_resolved_in_strict_mode():
    """Strict parity turns an unresolvable filter into a dropped source.

    With the fallback on, the same source would be kept and calibrated against
    V — the exact silent substitution ``strict_filter_parity`` exists to stop.
    """
    catalog = [_catalog_source(0, 1.0, 2.0, mags={"V": Mag(value=15.5)})]
    catalog[0].id = "s0"
    phot = [_phot("s0", 13.0, filter="Zeta")]

    assert _collect_calibration_sources(
        phot, catalog, catalog_filter_lookup={"APASS": {}},
        custom_filter_lookup=None, allow_preferred_band_fallback=False,
    ) == []

    lenient = _collect_calibration_sources(
        [_phot("s0", 13.0, filter="Zeta")], catalog,
        catalog_filter_lookup={"APASS": {}}, custom_filter_lookup=None,
        allow_preferred_band_fallback=True,
    )
    assert len(lenient) == 1
    assert lenient[0].ref_mag == pytest.approx(15.5)


def test_collect_infers_the_catalog_name_when_exactly_one_is_configured():
    """A single-catalog run may leave ``catalog_name`` off its sources."""
    catalog = [CatalogSource(id="s0", mags={"V": Mag(value=15.5)})]
    collected = _collect_calibration_sources(
        [_phot("s0", 13.0)], catalog,
        catalog_filter_lookup={"APASS": {}}, custom_filter_lookup=None,
    )
    assert collected[0].catalog_name == "APASS"


# ---------------------------------------------------------------------------
# End to end on a real frame
# ---------------------------------------------------------------------------

def test_perform_field_calibration_end_to_end_on_a_real_frame(frame_image):
    """Calibrate a real frame using only supplied scientific inputs.

    Catalog sources are synthesised at the sky positions of sources actually
    detected in the frame, with reference magnitudes offset by a known constant,
    so the recovered zero point must come back as that constant. Everything
    between — WCS construction, source matching, aperture photometry, ref-mag
    resolution, Chauvenet-rejected solve, header write-back — is the real code
    path, and nothing touches the network.
    """
    from algorithms.photometry.photometry import run_photometry
    from algorithms.photometry.source_extraction import run_source_extraction
    from algorithms.photometry.schemas import (
        SourceExtractionSettings as PhotExtractionSettings,
    )
    from algorithms.photometry.source_extraction import build_wcs_from_header

    data, header = frame_image("ngc3628")
    header = header.copy()
    data = np.array(data)

    detected, _, _ = run_source_extraction(
        data, header, PhotExtractionSettings(), file_id=1
    )
    assert len(detected) > 10, "fixture frame should yield a workable detection list"
    # Source extraction leaves `id` unset; the calibration path keys photometry
    # back to catalog rows by id, so give each detection a stable one.
    for i, source in enumerate(detected):
        source.id = f"det-{i}"

    # A known zero point: catalog mag = instrumental mag + 21.0. The
    # instrumental magnitudes are whatever aperture photometry measures, so the
    # solve has to recover 21.0 from the frame's own flux scale.
    #
    # apcorr_tol=0.0 here matches what field calibration forces internally (see
    # test_calibration_photometry_forces_apcorr_tol_to_zero). With the default
    # 1e-4 the reference magnitudes would carry an aperture correction the
    # calibration photometry does not, and the recovered zero point would sit
    # ~0.1 mag off — which is precisely the legacy-parity drift that override
    # exists to prevent.
    ZERO_POINT = 21.0
    phot = run_photometry(
        data, header, detected, FieldCalPhotometrySettings(a=5.0, apcorr_tol=0.0)
    )
    by_id = {p.id: p for p in phot if p.mag is not None}
    assert len(by_id) > 10

    # Catalog magnitudes carry ~0.02 mag of scatter, matching a real APASS
    # column. This exercises an estimable empirical zero-point uncertainty;
    # the zero-scatter boundary has its own numerical regression.
    rng = np.random.default_rng(20260811)
    catalog_sources = [
        CatalogSource(
            id=f"cat-{i}",
            catalog_name="APASS",
            ra_hours=source.ra_hours,
            dec_degs=source.dec_degs,
            mags={
                "V": Mag(
                    value=by_id[source.id].mag + ZERO_POINT + float(rng.normal(0, 0.02)),
                    error=0.02,
                )
            },
        )
        for i, source in enumerate(detected)
        if source.id in by_id and source.ra_hours is not None
    ]
    assert len(catalog_sources) > 10

    zero_point, result = perform_field_calibration(
        header, data,
        wcs=build_wcs_from_header(header),
        file_id=1,
        field_cal_settings=PhotometricCalibrationSettings(
            catalogs=["APASS"], source_match_tol=3.0, variable_check_tol=0,
        ),
        photometry_settings=FieldCalPhotometrySettings(a=5.0),
        catalog_sources=catalog_sources,
        detected_sources=detected,
    )

    assert zero_point == pytest.approx(ZERO_POINT, abs=0.02)
    assert result.zero_point_slop < 0.1
    assert result.rej_percent < 50
    assert len(result.phot_results) > 10

    # The solve writes its result back into the header it was handed.
    assert header["PHOT_M0"] == pytest.approx(ZERO_POINT, abs=0.02)
    assert header["PHOT_CAL"] == "APASS"


def test_calibration_photometry_forces_apcorr_tol_to_zero(monkeypatch):
    """LEGACY AFTERGLOW PARITY — the caller's ``apcorr_tol`` must not survive.

    ``field_cal.py`` copies the photometry settings with ``apcorr_tol = 0.0``
    before measuring calibration stars, because the aperture-photometry kernel
    gates its aperture-correction pass on ``apcorr_tol > 0``. Letting the
    default 1e-4 through switches aperture correction on and the zero point
    drifts away from legacy Afterglow. The source comment says "DO NOT CLEAN
    UP"; this asserts it.
    """
    seen: list[float] = []

    def spy_run_photometry(data, header, sources, settings, **kw):
        seen.append(settings.apcorr_tol)
        return [
            PhotometryData(id=s.id, mag=13.0 + i * 0.1, mag_error=0.02, filter="V")
            for i, s in enumerate(sources)
        ]

    w = _wcs()
    ra_deg, dec_deg = w.all_pix2world(500.0, 500.0, 1)
    ra_hours, dec = float(ra_deg) / 15.0, float(dec_deg)

    monkeypatch.setattr("algorithms.fieldcal.field_cal.run_photometry", spy_run_photometry)

    catalog_sources = [
        CatalogSource(
            id=f"cat-{i}", catalog_name="APASS",
            ra_hours=ra_hours + i * 1e-4, dec_degs=dec,
            mags={"V": Mag(value=34.0 + i * 0.101, error=0.02)},
        )
        for i in range(6)
    ]
    detected = [
        SourceExtractionData(
            id=f"d{i}", x=float(w.all_world2pix((ra_hours + i*1e-4)*15, dec, 1)[0]),
            y=float(w.all_world2pix((ra_hours + i*1e-4)*15, dec, 1)[1]),
            ra_hours=ra_hours + i * 1e-4, dec_degs=dec, filter="V",
        )
        for i in range(6)
    ]

    perform_field_calibration(
        {"FILTER": "V"}, np.zeros((1027, 1056), dtype=np.float32),
        wcs=w,
        field_cal_settings=PhotometricCalibrationSettings(
            catalogs=["APASS"], source_match_tol=5.0, variable_check_tol=0,
        ),
        # A caller-supplied non-zero tolerance that must be overridden.
        photometry_settings=FieldCalPhotometrySettings(a=5.0, apcorr_tol=1e-4),
        catalog_sources=catalog_sources,
        detected_sources=detected,
    )

    assert seen == [0.0]


@pytest.mark.parametrize("mag_only", [False, True])
def test_calibration_snr_constraints_use_flux_ratio_or_exact_magnitude_inverse(mag_only):
    rows = [CatalogSource(
        id=str(i), mag=-5 - i * .2, mag_error=2.5 * np.log10(1 + 1 / snr),
        flux=None if mag_only else 1000, flux_error=None if mag_only else 1000 / snr,
        ref_mag=15 - i * .2 + i * .005, ref_mag_error=.02,
    ) for i, snr in enumerate([9.9, 10.1, 10.3, 10.4, 11.1])]
    _, result = perform_field_calibration(
        {"FILTER": "V"}, np.zeros((10, 10)), catalog_sources=rows,
        use_provided_photometry=True,
        field_cal_settings=PhotometricCalibrationSettings(min_snr=10, max_snr=11),
    )
    assert [row.id for row in result.phot_results] == ["1", "2", "3"]


@pytest.mark.parametrize("flux,flux_error,mag_error", [
    (100, 0, .01), (100, -1, .01), (100, None, None),
    (None, None, None), (None, None, 0), (None, None, -.01),
])
def test_calibration_snr_constraints_reject_unusable_measurement_uncertainty(flux, flux_error, mag_error):
    rows = [CatalogSource(id=str(i), flux=flux, flux_error=flux_error,
        mag=-5 + i * .1, mag_error=mag_error, ref_mag=15 + i * .101, ref_mag_error=.02)
        for i in range(3)]
    with pytest.raises(RuntimeError, match="All sources violate SNR constraints"):
        perform_field_calibration(
            {"FILTER": "V"}, np.zeros((10, 10)), catalog_sources=rows,
            use_provided_photometry=True,
        )


@pytest.mark.parametrize("flux", [0, -100])
def test_calibration_rejects_nonpositive_flux_even_with_finite_magnitude_and_open_snr(flux):
    rows = [CatalogSource(id=str(i), flux=flux, flux_error=10,
        mag=-5 + i * .1, mag_error=.01, ref_mag=15 + i * .101, ref_mag_error=.02)
        for i in range(3)]
    with pytest.raises(RuntimeError, match="No catalog sources could be photometered"):
        perform_field_calibration(
            {"FILTER": "V"}, np.zeros((10, 10)), catalog_sources=rows,
            use_provided_photometry=True,
            field_cal_settings=PhotometricCalibrationSettings(min_snr=0),
        )


def test_matched_detector_positions_are_not_projected_or_proper_motion_shifted_again(monkeypatch):
    from datetime import datetime
    from algorithms.photometry.source_extraction import get_source_xy

    wcs = _wcs(crpix=(20, 20), crval=(180, 0), scale=1 / 3600)
    epoch, old_epoch = datetime(2026, 1, 1), datetime(2016, 1, 1)
    seconds = (epoch - old_epoch).total_seconds()
    xy = [(10, 20), (20, 20), (30, 20)]
    ra, dec = wcs.all_pix2world(*np.transpose(xy), 1)
    catalog = [CatalogSource(id=str(i), ra_hours=float(r / 15), dec_degs=float(d - 10 / 3600),
        pm_epoch=old_epoch, pm_sky=(10 / 3600) / seconds, pm_pos_angle_sky=0,
        ref_mag=15 + i * .101, ref_mag_error=.02) for i, (r, d) in enumerate(zip(ra, dec))]
    detected = [SourceExtractionData(id=f"det{i}", x=x, y=y,
        ra_hours=float(r / 15), dec_degs=float(d + 3 / 3600))
        for i, ((x, y), r, d) in enumerate(zip(xy, ra, dec))]
    measured_positions = []

    def measure(data, header, sources, settings, **kwargs):
        measured_positions.extend(get_source_xy(source, epoch, kwargs["wcs"]) for source in sources)
        return [PhotometryData(id=source.id, mag=-5 + i * .1, mag_error=.02, filter="V")
                for i, source in enumerate(sources)]

    monkeypatch.setattr("algorithms.fieldcal.field_cal.run_photometry", measure)
    perform_field_calibration(
        {"FILTER": "V", "DATE-OBS": "2026-01-01T00:00:00"}, np.zeros((40, 40)),
        wcs=wcs, catalog_sources=catalog, detected_sources=detected,
        field_cal_settings=PhotometricCalibrationSettings(source_match_tol=.1, variable_check_tol=0),
    )
    np.testing.assert_allclose(measured_positions, xy, atol=1e-8)


def test_calibration_forwards_extracted_rms_and_retains_annular_background(monkeypatch):
    image = np.zeros((40, 40))
    rms = np.full_like(image, 4)
    detected = [SourceExtractionData(id=str(i), x=10 + i * 10, y=20) for i in range(3)]
    catalog = [CatalogSource(id=str(i), x=10 + i * 10, y=20,
        ref_mag=15 + i * .101, ref_mag_error=.02) for i in range(3)]
    seen = []

    def extract(*args, **kwargs):
        return detected, np.full_like(image, 50), rms

    def measure(data, header, sources, settings, **kwargs):
        seen.append((kwargs["background"], kwargs["background_rms"]))
        return [PhotometryData(id=source.id, mag=-5 + i * .1, mag_error=.02, filter="V")
                for i, source in enumerate(sources)]

    monkeypatch.setattr("algorithms.fieldcal.field_cal.run_source_extraction", extract)
    monkeypatch.setattr("algorithms.fieldcal.field_cal.run_photometry", measure)
    perform_field_calibration(
        {"FILTER": "V"}, image, catalog_sources=catalog,
        extraction_settings=SourceExtractionSettings(),
    )
    assert len(seen) == 1
    assert seen[0][0] is None
    assert seen[0][1] is rms
