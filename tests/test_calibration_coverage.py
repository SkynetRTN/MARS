"""M2 coverage disclosures reach successful and failed public tool calls."""

import pytest


@pytest.mark.parametrize("tool", ["calibrate", "photometry"])
@pytest.mark.parametrize("failed", [False, True])
def test_coverage_notices_survive_the_public_calibration_boundary(tool, failed, frame_path, tmp_path, monkeypatch):
    from algorithms.query.coverage import note_query_issue
    from algorithms.query import runner
    from tools.fieldcal_reference import replay_catalog_sources, replay_variable_sources
    from tools.photometry import calibrate_zeropoint, run_photometry_on_target

    def query(names, **kwargs):
        if names == ["VSX"]:
            return replay_variable_sources("ngc5128_b_002")
        note_query_issue("catalog_rows_capped", "APASS: raw response reached its row limit.")
        if failed:
            raise TimeoutError("test provider timeout")
        return replay_catalog_sources("ngc5128_b_002")

    monkeypatch.setattr(runner, "query_catalogs", query)
    if tool == "calibrate":
        result = calibrate_zeropoint(frame_path("ngc5128_b"), catalogs=["APASS"])
        assert bool(result.errors) == failed
    else:
        result = run_photometry_on_target(frame_path("ngc5128_b"), catalogs=["APASS"],
                                         use_field_cal=True, output_dir=tmp_path)
        assert result.errors == []
        assert (result.zero_point_source == "field-cal") != failed
    assert "catalog_rows_capped" in {warning.code for warning in result.warnings}
    if not failed:
        assert "calibration_sufficiency_unverified" in {warning.code for warning in result.warnings}
        if tool == "photometry":
            assert "catalog_rows_capped" in {warning.code for warning in result.zero_point.warnings}


def test_offline_supplied_calibration_does_not_claim_sample_sufficiency(frame_path):
    from tools.photometry import calibrate_zeropoint

    result = calibrate_zeropoint(frame_path("ngc5128_b"), catalog_fixture="selected_rows",
                                compare_to="ngc5128_b_002")
    assert result.errors == []
    assert "calibration_sufficiency_unverified" in {warning.code for warning in result.warnings}
    assert "catalog_rows_capped" not in {warning.code for warning in result.warnings}


def test_reported_calibration_star_count_uses_exact_solver_survivors(frame_image, monkeypatch):
    from algorithms.query import runner
    from tools.fieldcal_reference import replay_catalog_sources, replay_variable_sources
    from tools.photometry_pipeline import compute_field_cal_zero_point

    def query(names, **kwargs):
        if names == ["VSX"]:
            return replay_variable_sources("ngc5128_b_002")
        return replay_catalog_sources("ngc5128_b_002")

    monkeypatch.setattr(runner, "query_catalogs", query)
    data, header = frame_image("ngc5128_b")
    value, diagnostics, error, result = compute_field_cal_zero_point(header.copy(), data.copy(), catalogs=["APASS"])
    assert value is not None and error is None
    assert diagnostics["num_calibration_stars"] == len(result._reference_routes)
    assert diagnostics["num_calibration_candidates"] == len(result.phot_results)
    assert diagnostics["num_calibration_stars"] == 29
    assert diagnostics["num_calibration_candidates"] == 35


@pytest.mark.parametrize("tool", ["calibrate", "photometry"])
def test_raw_provider_cap_and_priority_stop_reach_tools_through_real_query_mapping(
    tool, frame_path, tmp_path, monkeypatch,
):
    from astroquery.vizier.core import VizierClass
    from algorithms.query.registry import CATALOGS
    from tools.config import BUNDLED_DATA_DIR
    from tools.fieldcal_reference import _read_response
    from tools.photometry import calibrate_zeropoint, run_photometry_on_target

    directory = BUNDLED_DATA_DIR / "fieldcal" / "zp_solutions" / "ngc5128_b_002"
    tables = {CATALOGS[name].vizier_catalog: _read_response(directory, name)[1]
              for name in ("APASS", "VSX")}
    monkeypatch.setattr(CATALOGS["APASS"], "row_limit", 132)

    def transport(client, *args, **kwargs):
        name = client.catalog[0] if isinstance(client.catalog, list) else client.catalog
        return [tables[name]]

    monkeypatch.setattr(VizierClass, "query_region", transport)
    if tool == "calibrate":
        result = calibrate_zeropoint(frame_path("ngc5128_b"), catalogs=["APASS", "Stetson"])
    else:
        result = run_photometry_on_target(frame_path("ngc5128_b"), catalogs=["APASS", "Stetson"],
                                         use_field_cal=True, output_dir=tmp_path)
        assert result.zero_point_source == "field-cal"
        assert result.zero_point.source_count > 0
    assert result.errors == []
    codes = {warning.code for warning in result.warnings}
    assert {"catalog_rows_capped", "catalog_fallback_not_exhausted",
            "calibration_sufficiency_unverified"} <= codes


def test_failed_variable_star_crosscheck_is_disclosed(frame_path, monkeypatch):
    from algorithms.query import runner
    from tools.fieldcal_reference import replay_catalog_sources
    from tools.photometry import calibrate_zeropoint

    def query(names, **kwargs):
        if names == ["VSX"]:
            raise TimeoutError("variable catalog timeout")
        return replay_catalog_sources("ngc5128_b_002")

    monkeypatch.setattr(runner, "query_catalogs", query)
    result = calibrate_zeropoint(frame_path("ngc5128_b"), catalogs=["APASS"])
    assert result.errors == []
    assert "catalog_query_incomplete" in {warning.code for warning in result.warnings}


def test_error_only_vsx_response_is_disclosed_through_actual_sdk_parsing(frame_path, monkeypatch):
    from io import BytesIO
    from astroquery.vizier import VizierClass
    from requests import Response
    from algorithms.query.registry import CATALOGS
    from tools.config import BUNDLED_DATA_DIR
    from tools.fieldcal_reference import _read_response
    from tools.photometry import calibrate_zeropoint

    directory = BUNDLED_DATA_DIR / "fieldcal" / "zp_solutions" / "ngc5128_b_002"
    buffer = BytesIO()
    table = _read_response(directory, "APASS")[1]
    table.rename_columns(table.colnames, [name.replace("'", "_") for name in table.colnames])
    table.write(buffer, format="votable")
    reference_response = buffer.getvalue()
    variable_error = b'<?xml version="1.0"?><VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3"><RESOURCE/><INFO name="QUERY_STATUS" value="ERROR">(pipe) Request has been interrupted</INFO></VOTABLE>'

    def transport(client, *args, **kwargs):
        response = Response()
        response.status_code = 200
        catalog = client.catalog[0] if isinstance(client.catalog, list) else client.catalog
        response._content = variable_error if catalog == CATALOGS["VSX"].vizier_catalog else reference_response
        return response

    monkeypatch.setattr(VizierClass, "_request", transport)
    result = calibrate_zeropoint(frame_path("ngc5128_b"), catalogs=["APASS"])
    assert result.errors == []
    assert result.zero_point is not None
    incomplete = [warning.message for warning in result.warnings if warning.code == "catalog_query_incomplete"]
    assert any("VSX" in message and "interrupted" in message for message in incomplete)


@pytest.mark.parametrize("tool", ["measurements", "replay"])
def test_direct_and_recorded_fits_disclose_sufficiency_and_count_only_survivors(tool):
    from tools.calibration import solve_zeropoint_from_measurements
    from tools.fieldcal_reference import load_zeropoint_reference, replay_field_calibration

    if tool == "measurements":
        reference = load_zeropoint_reference("ngc5128_b_002")
        solution = solve_zeropoint_from_measurements(reference.measurements, [])
    else:
        replay = replay_field_calibration("ngc5128_b_002")
        assert replay.errors == []
        assert replay.num_matched == 35
        solution = replay.solution
        assert "calibration_sufficiency_unverified" in {warning.code for warning in replay.warnings}
    assert solution.errors == []
    assert solution.source_count == 29
    assert "calibration_sufficiency_unverified" in {warning.code for warning in solution.warnings}


@pytest.mark.parametrize("count", [1, 2])
def test_direct_fit_without_a_positive_finite_uncertainty_is_not_a_calibration(count):
    from tools.calibration import solve_zeropoint_from_measurements

    result = solve_zeropoint_from_measurements(
        [{"mag": 14 + index, "ref_mag": 16 + index} for index in range(count)], [],
    )
    assert result.zero_point is None
    assert "no_solution" in {error.code for error in result.errors}
