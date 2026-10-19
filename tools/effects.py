"""Shared local effects and AUD-01's explicit private-artifact consent policy.

Routine artifacts are deliberately exempt from agent write confirmation.
Downloads and input mutation are not. MCP hints describe effects, not consent:
an exempt artifact writer is still not read-only.
"""

NO_LOCAL_WRITE = frozenset({
    "resolve_target", "get_paper_abstract", "list_vizier_catalogs",
    "list_optical_frames", "resolve_optical_frame", "describe_image_wcs",
    "list_photometry_targets", "list_photometric_catalogs",
    "resolve_reference_band", "list_artifacts", "describe_artifact",
    "list_zeropoint_references", "load_zeropoint_reference",
    "compare_zeropoint_to_reference", "replay_field_calibration",
    "solve_zeropoint_from_measurements", "list_pulsar_scans",
    "resolve_pulsar_scan", "list_variable_star_fixtures",
    "resolve_variable_star_fixture", "get_literature_cluster_params",
    "calibrate_zeropoint",
})

CONSENT_ARTIFACT_WRITERS = frozenset({"sonify_pulsar", "plot_pulsar", "plot_field_sed"})

# Closed inventory: a new writer must be reviewed, not silently exempted.
PRIVATE_ARTIFACT_EXEMPTIONS = frozenset({
    "search_simbad", "search_simbad_measurements", "search_simbad_bibliography",
    "search_ads", "get_citing_papers", "get_referenced_papers", "build_literature_review",
    "search_ned", "search_vizier", "search_atnf", "search_mast", "search_mpc", "search_casda",
    "extract_photometry_from_fits", "crossmatch_gaia", "crossmatch_gaia_by_position",
    "select_cluster_members", "fit_and_compare_hr_diagram", "run_full_hr_pipeline",
    "run_full_hr_pipeline_from_catalog", "load_pulsar_lightcurve",
    "compute_pulsar_periodogram", "fold_pulsar_lightcurve", "run_photometry_on_target",
    "identify_radio_sources", "analyze_source_spectrum", "solve_astrometry",
    "load_variable_star_lightcurve", "compute_variable_star_periodogram",
    "fold_variable_star_lightcurve",
})

DOWNLOAD_FLAGS = {"search_mast": "download", "search_casda": "download"}
WRITE_FLAGS = {"solve_astrometry": "write_header"}
WRITES_OUTSIDE_ARTIFACTS = {"download": False, "write_header": True}


def artifact_write_requires_consent(name: str) -> bool:
    """Unknown/unreviewed tools fail closed; exemption is only by inventory."""
    return name not in NO_LOCAL_WRITE and name not in PRIVATE_ARTIFACT_EXEMPTIONS
