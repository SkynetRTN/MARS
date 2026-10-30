"""Follow-up review: alias selection and actual reference provenance."""

import pytest
from astropy.io import fits

from algorithms.catalogs.schemas import CatalogSource, Mag
from algorithms.fieldcal.ref_mag import resolve_ref_mag_for_filter
from algorithms.query.selection import catalog_supports_filter, select_catalogs_for_filter


@pytest.mark.parametrize("key,source_name,band", [
    ("Stetson", "StetsonGlobs", "V"), ("Tycho", "Tycho2", "BT"),
    ("UCAC", "UCAC5", "Open"), ("USNO", "USNOB1", "Bphot"),
])
def test_source_name_overrides_also_apply_when_selecting_registry_keys(key, source_name, band):
    override = {source_name: {"Halpha": band}}
    for name in (key, source_name):
        assert catalog_supports_filter(name, "Halpha", custom_filter_lookup=override)
        assert resolve_ref_mag_for_filter(
            catalog_name=name, image_filter="Halpha", cs_mags={band: 14.6},
            custom_filter_lookup=override, allow_preferred_band_fallback=False,
        ) == (14.6, None)
    assert select_catalogs_for_filter([key, "APASS"], "Halpha", custom_filter_lookup=override) == [key, "APASS"]


def test_source_name_override_keeps_the_preferred_catalog_in_the_real_query_runner(monkeypatch):
    from algorithms.query.registry import CATALOGS
    from algorithms.query.runner import query_catalogs

    calls = []
    wanted = CatalogSource(id="preferred", catalog_name="StetsonGlobs", ra_hours=1.0,
                           dec_degs=2.0, mags={"V": Mag(value=14.6)})

    def query_stetson(*args, **kwargs):
        calls.append("Stetson")
        return [wanted]

    def query_apass(*args, **kwargs):
        calls.append("APASS")
        return [CatalogSource(id="fallback", catalog_name="APASS")]

    monkeypatch.setattr(CATALOGS["Stetson"], "query_circ", query_stetson)
    monkeypatch.setattr(CATALOGS["APASS"], "query_circ", query_apass)
    rows = query_catalogs(
        ["Stetson", "APASS"], ra_hours=1.0, dec_degs=2.0, radius_arcmins=1.0,
        image_filter="Halpha", custom_filter_lookup={"StetsonGlobs": {"Halpha": "V"}},
        stop_on_success=True,
    )
    assert [row.id for row in rows] == ["preferred"]
    assert calls == ["Stetson"]


@pytest.mark.parametrize("method,image_filter,catalog,unwanted_code", [
    ("provided", "Halpha", "ManualHalpha", "broadband_reference"),
    ("direct", "Halpha", "ManualHalpha", "broadband_reference"),
    ("provided", "I", "APASS", "approximate_transform"),
])
def test_supplied_native_references_are_not_described_as_unperformed_transforms(
    method, image_filter, catalog, unwanted_code, frame_path, tmp_path,
):
    from tools.fieldcal_reference import replay_catalog_sources
    from tools.photometry import calibrate_zeropoint

    data, header = fits.getdata(frame_path("ngc5128_b"), header=True)
    header["FILTER"] = image_filter
    path = tmp_path / "provided_reference.fits"
    fits.writeto(path, data, header)
    rows = replay_catalog_sources("ngc5128_b_002")
    for row in rows:
        row.catalog_name = catalog
        if method == "direct":
            row.mags = {image_filter: Mag(value=row.ref_mag, error=row.ref_mag_error)}
            row.ref_mag = row.ref_mag_error = None
        else:
            row.mags = {}
    result = calibrate_zeropoint(path, catalog_sources=rows)
    assert result.errors == []
    assert result.zero_point is not None
    assert unwanted_code not in {warning.code for warning in result.warnings}


@pytest.mark.parametrize("provided", [False, True])
def test_narrowband_labels_follow_the_route_through_the_public_photometry_pipeline(
    provided, frame_path, tmp_path, monkeypatch,
):
    from tools.fieldcal_reference import replay_catalog_sources, replay_variable_sources
    from tools.photometry import run_photometry_on_target
    from algorithms.query import runner

    data, header = fits.getdata(frame_path("ngc5128_b"), header=True)
    header["FILTER"] = "Halpha"
    path = tmp_path / "routing_only.fits"
    fits.writeto(path, data, header)

    def query_catalogs(names, **kwargs):
        if names == ["VSX"]:
            return replay_variable_sources("ngc5128_b_002")
        assert names == ["APASS"]
        return replay_catalog_sources("ngc5128_b_002", fixture="selected_rows" if provided else "full_response")

    monkeypatch.setattr(runner, "query_catalogs", query_catalogs)
    result = run_photometry_on_target(path, use_field_cal=True, catalogs=["APASS"], output_dir=tmp_path)
    assert result.errors == []
    assert result.zero_point_source == "field-cal"
    assert result.zero_point.zero_point is not None
    if provided:
        assert result.magnitude_label == "calibrated magnitude"
        assert "broadband_reference" not in {warning.code for warning in result.warnings}
    else:
        assert result.magnitude_label == "relative magnitude (broadband reference)"
        assert "broadband_reference" in {warning.code for warning in result.warnings}
        assert "broadband_reference" in {warning.code for warning in result.zero_point.warnings}


@pytest.mark.parametrize("catalog,image_filter,mags,lookup,expected,warnings", [
    ("APASS", "I", {"V": 14.6}, {"I": "V"}, 14.6, set()),
    ("SkyMapper", "Halpha", {"g": 14.9}, {"Halpha": "gprime"}, 14.988,
     {"broadband_reference", "approximate_transform"}),
    ("USNO", "Halpha", {"R1": 14.6}, {"Halpha": "R1"}, 14.6, {"broadband_reference"}),
    ("Landolt", "Halpha", {"V": 14.6, "V_R": 0.4}, {"Halpha": "V - V_R"}, 14.2,
     {"broadband_reference"}),
])
def test_warnings_describe_the_used_custom_target_not_the_default_for_the_filter(
    catalog, image_filter, mags, lookup, expected, warnings,
):
    from algorithms.fieldcal.field_cal import _collect_calibration_sources
    from algorithms.fieldcal.schemas import PhotometryData
    from tools.catalogs import calibration_reference_warnings

    routes = {}
    sources = _collect_calibration_sources(
        [PhotometryData(id="x", filter=image_filter)],
        [CatalogSource(id="x", catalog_name=catalog, mags={band: Mag(value=value) for band, value in mags.items()})],
        catalog_filter_lookup=None, custom_filter_lookup={catalog: lookup}, reference_routes=routes,
    )
    assert sources[0].ref_mag == pytest.approx(expected)
    assert {warning.code for warning in calibration_reference_warnings(sources, routes)} == warnings


@pytest.mark.parametrize("proxy_first", [False, True])
@pytest.mark.parametrize("proxy_error", [0.0, 0.03])
def test_rejected_broadband_proxy_does_not_change_the_surviving_native_scale(proxy_first, proxy_error):
    import numpy as np
    from algorithms.fieldcal.field_cal import perform_field_calibration
    from algorithms.fieldcal.schemas import PhotometryData, PhotometricCalibrationSettings
    from tools.catalogs import calibration_reference_warnings
    from tools.photometry_pipeline import ZeroPointResolution, magnitude_label_for

    catalog = []
    measured = []
    for index in range(10):
        native = 14.0 + index * 0.1
        source_id = f"native-{index}"
        catalog.append(CatalogSource(id=source_id, catalog_name="ManualHalpha", x=10 + 4*index, y=20,
                                     mags={"Halpha": Mag(value=native)}))
        measured.append(PhotometryData(id=source_id, x=10 + 4*index, y=20,
                                      mag=native - 20 + (0.01 if index % 2 else -0.01), mag_error=0.03))
    proxy = CatalogSource(id="rejected-proxy", catalog_name="APASS", x=10, y=40,
                          mags={"rprime": Mag(value=14.0), "iprime": Mag(value=14.0)})
    proxy_measurement = PhotometryData(id="rejected-proxy", x=10, y=40, mag=-100, mag_error=proxy_error)
    catalog.insert(0 if proxy_first else len(catalog), proxy)
    measured.insert(0 if proxy_first else len(measured), proxy_measurement)
    for index, (row, measurement) in enumerate(zip(catalog, measured)):
        row.ra_hours = measurement.ra_hours = 1.0 + index / 3600
        row.dec_degs = measurement.dec_degs = 2.0
    zero_point, result = perform_field_calibration(
        fits.Header({"FILTER": "Halpha"}), np.zeros((64, 64)), catalog_sources=catalog,
        detected_sources=measured, use_provided_photometry=True,
        field_cal_settings=PhotometricCalibrationSettings(catalogs=["APASS", "ManualHalpha"],
                                                         variable_check_tol=0, min_snr=0),
    )
    assert zero_point == pytest.approx(20.0, abs=1e-10)
    assert result.rej_percent == pytest.approx(100/11)
    # Candidate rows remain available to the existing diagnostic plot.
    assert len(result.phot_results) == 11
    assert calibration_reference_warnings(result.phot_results, result._reference_routes) == []
    assert magnitude_label_for(ZeroPointResolution(
        value=zero_point, source="field-cal", verified=True, calibration_sources=result.phot_results,
        reference_routes=result._reference_routes,
    )) == "calibrated magnitude"
