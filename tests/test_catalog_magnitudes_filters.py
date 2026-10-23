"""M2: real band identities and production filter-routing precedence."""

import pytest
from astropy.table import Table

from algorithms.catalogs import CATALOGS
from algorithms.fieldcal.ref_mag import resolve_ref_mag_for_filter
from algorithms.query.registry import CATALOGS as QUERYABLE
from algorithms.query.selection import catalog_supports_filter, select_catalogs_for_filter
from tools.catalogs import resolve_reference_band


def resolve(catalog, image_filter, mags, **kwargs):
    return resolve_ref_mag_for_filter(
        catalog_name=catalog, image_filter=image_filter, cs_mags=mags,
        allow_preferred_band_fallback=False, **kwargs,
    )


@pytest.mark.parametrize("image_filter", ["R", " R ", "Halpha", "H_alpha", "Halpha "])
def test_apass_uses_the_production_r_expression_in_every_entry_point(image_filter):
    mags = {"B": 15.2, "V": 14.6, "gprime": 14.9, "rprime": 14.4, "iprime": 14.25}
    # Independent evaluation of the existing expression: 14.4 - .2936*.15 - .1439.
    assert resolve("APASS", image_filter, mags)[0] == pytest.approx(14.21206)
    assert catalog_supports_filter("APASS", image_filter)
    report = resolve_reference_band("APASS", image_filter)
    assert report.supported
    assert report.kind == "expression"
    assert report.reference == "rprime - 0.2936*(rprime - iprime) - 0.1439"


@pytest.mark.parametrize("image_filter", ["g'", " g′ ", "g’", "gp"])
def test_prime_aliases_compose_whitespace_and_quote_normalization(image_filter):
    assert catalog_supports_filter("APASS", image_filter)
    assert resolve("APASS", image_filter, {"gprime": 14.9}) == (14.9, None)


@pytest.mark.parametrize("image_filter", ["Open", "Clear", "Lum"])
@pytest.mark.parametrize("catalog", ["APASS", "Landolt", "Stetson", "StetsonGlobs"])
def test_production_unfiltered_mapping_also_works_in_strict_resolution(catalog, image_filter):
    assert catalog_supports_filter(catalog, image_filter)
    assert resolve(catalog, image_filter, {"V": 14.6}) == (14.6, None)


@pytest.mark.parametrize("image_filter,expected", [
    ("R", 14.21206), ("I", 13.7959), ("U", 15.049), ("V", 14.607),
])
def test_sdss_standard_band_transforms_outrank_case_only_native_matches(image_filter, expected):
    mags = {"u": 15.7, "g": 14.9, "r": 14.4, "i": 14.25, "z": 14.1}
    assert resolve("SDSS", image_filter, mags)[0] == pytest.approx(expected)
    report = resolve_reference_band("SDSS", image_filter)
    assert report.supported and report.kind == "expression"


@pytest.mark.parametrize("catalog,image_filter,mags", [
    ("SkyMapper", "V", {"v": 13.0, "g": 12.0}),
    ("SkyMapper", "U", {"u": 13.0, "g": 12.0}),
    ("PanSTARRS", "R", {"r": 12.0, "i": 11.0}),
    ("Tycho", "V", {"BT": 13.0, "VT": 12.0}),
    ("USNO", "B", {"Bphot": 12.0}),
    ("UCAC", "B", {"Open": 12.0, "Rphot": 13.0}),
])
def test_a_named_photometric_system_never_falls_back_to_another(catalog, image_filter, mags):
    assert not catalog_supports_filter(catalog, image_filter)
    assert not resolve_reference_band(catalog, image_filter).supported
    for permissive in (False, True):
        assert resolve_ref_mag_for_filter(
            catalog_name=catalog, image_filter=image_filter, cs_mags=mags,
            allow_preferred_band_fallback=permissive,
        ) == (None, None)


def test_ucac_open_band_does_not_claim_every_filter():
    assert catalog_supports_filter("UCAC", "Open")
    assert not catalog_supports_filter("UCAC", "MysteryBand")
    assert select_catalogs_for_filter(["UCAC", "APASS"], "B") == ["APASS"]


@pytest.mark.parametrize("name,columns,native", [
    ("2MASS", {"_2MASS": ["x"], "RAJ2000": [15.0], "DEJ2000": [1.0],
               "Jmag": [12.0], "Hmag": [11.7], "Kmag": [11.5], "Bmag": [18.0], "Rmag": [17.0]},
     {"Bopt": 18.0, "Ropt": 17.0}),
    ("UCAC", {"SrcIDgaia": [123], "RAJ2000": [15.0], "DEJ2000": [1.0],
              "f.mag": [12.0], "Rmag": [17.0]}, {"Open": 12.0, "Rphot": 17.0}),
    ("Tycho", {"TYC1": [1], "TYC2": [2], "TYC3": [1], "RAmdeg": [15.0], "DEmdeg": [1.0],
               "BTmag": [13.0], "VTmag": [12.0]}, {"BT": 13.0, "VT": 12.0}),
    ("USNO", {"USNO-B1.0": ["x"], "RAJ2000": [15.0], "DEJ2000": [1.0],
              "B1mag": [18.0], "B2mag": [16.0], "R1mag": [17.0], "R2mag": [15.0]},
     {"Bphot": 17.0, "Rphot": 16.0}),
])
def test_query_mapping_labels_native_systems_without_recomputing_them(name, columns, native):
    source, = QUERYABLE[name].table_to_sources(Table(columns))
    for band, value in native.items():
        assert source.mags[band].value == value
    assert not {"B", "V", "R"} & source.mags.keys()
    for band in native:
        assert resolve(source.catalog_name, band, source.mags)[0] == native[band]


def test_2mass_optical_transform_uses_jk_instead_of_photographic_b():
    assert resolve("2MASS", "B", {"Bopt": 18.0, "J": 12.0, "K": 11.5})[0] == pytest.approx(14.3295625)


def test_native_colours_and_zero_magnitudes_survive_query_mapping():
    table = Table({"Star": ["x"], "RAJ2000": ["01 00 00"], "DEJ2000": ["+01 00 00"],
                   "Vmag": [0.0], "e_Vmag": [0.0], "B-V": [0.0], "U-B": [0.0],
                   "V-R": [0.0], "R-I": [0.0], "V-I": [0.0]})
    source, = QUERYABLE["Landolt"].table_to_sources(table)
    for band in ("U", "B", "V", "R", "I", "B_V"):
        assert source.mags[band].value == 0.0
    assert source.mags["V"].error == 0.0


def test_native_survey_case_does_not_trigger_a_standard_transform():
    assert resolve("SDSS", "r", {"r": 14.4, "i": 14.25}) == (14.4, None)
    assert resolve("Landolt", "B_V", {"B_V": 0.5, "BV": 99.0}) == (0.5, None)


def test_explicit_prime_alias_override_precedes_generic_prime_spelling():
    assert resolve("APASS", "g'", {"gprime": 14.9, "V": 14.6},
                   custom_filter_lookup={"APASS": {"g'": "V"}}) == (14.6, None)


def test_lookup_overrides_work_for_registry_keys_and_source_names():
    custom = {"Stetson": {"Custom": "V - 1"}}
    assert resolve("StetsonGlobs", "Custom", {"V": 14.6}, custom_filter_lookup=custom) == (13.6, None)
    assert catalog_supports_filter("StetsonGlobs", "Custom", custom_filter_lookup=custom)


@pytest.mark.parametrize("catalog", ["SkyMapper", "SDSS"])
@pytest.mark.parametrize("image_filter", ["g'", " g′ ", "gp", "g_p", "g_'", "g_′", "G'"])
def test_standard_prime_spellings_reach_the_retained_survey_transform(catalog, image_filter):
    mags = {"g": 14.9, "r": 14.4}
    expected = 14.988 if catalog == "SkyMapper" else 14.9018
    assert catalog_supports_filter(catalog, image_filter)
    assert resolve(catalog, image_filter, mags)[0] == pytest.approx(expected)
    assert resolve_reference_band(catalog, image_filter).kind == "expression"


@pytest.mark.parametrize("catalog,image_filter,code", [
    ("APASS", "Halpha", "broadband_reference"),
    ("APASS", "H_alpha", "broadband_reference"),
    ("SDSS", "Halpha", "broadband_reference"),
    ("APASS", "I", "approximate_transform"),
    ("SkyMapper", "gprime", "approximate_transform"),
    ("2MASS", "B", "approximate_transform"),
    ("UCAC", "Open", "nonstandard_passband"),
])
def test_retained_approximations_are_disclosed_without_changing_formulas(catalog, image_filter, code):
    report = resolve_reference_band(catalog, image_filter)
    assert report.supported
    assert code in {warning.code for warning in report.warnings}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_a_nonfinite_catalog_magnitude_cannot_become_a_reference(value):
    assert resolve("APASS", "V", {"V": value}) == (None, None)


def test_pipeline_custom_alias_map_wins_without_mutating_the_supplied_map():
    from algorithms.catalogs.schemas import CatalogSource
    from algorithms.fieldcal.field_cal import _collect_calibration_sources
    from algorithms.fieldcal.schemas import PhotometryData

    mapping = {"StetsonGlobs": {"Open": "V"}}
    results = _collect_calibration_sources(
        [PhotometryData(id="x", filter="Open")],
        [CatalogSource(id="x", catalog_name="StetsonGlobs", mags={"V": {"value": 14.6}})],
        catalog_filter_lookup=mapping, custom_filter_lookup={"Stetson": {"Open": "V - 1"}},
    )
    assert results[0].ref_mag == 13.6
    assert mapping == {"StetsonGlobs": {"Open": "V"}}


def test_narrowband_calibration_reports_its_broadband_reference(frame_path, tmp_path):
    from astropy.io import fits
    from tools.photometry import calibrate_zeropoint

    data, header = fits.getdata(frame_path("ngc5128_b"), header=True)
    header["FILTER"] = "Halpha"
    path = tmp_path / "halpha.fits"
    fits.writeto(path, data, header)
    result = calibrate_zeropoint(path, catalog_fixture="full_response", compare_to="ngc5128_b_002")
    assert result.errors == []
    assert result.zero_point is not None
    assert "broadband_reference" in {warning.code for warning in result.warnings}


def test_narrowband_magnitude_label_describes_relative_calibration():
    from types import SimpleNamespace
    from tools.photometry_pipeline import ZeroPointResolution, magnitude_label_for

    zero_point = ZeroPointResolution(value=20.0, source="field-cal", verified=True,
        calibration_sources=[SimpleNamespace(catalog_name="APASS", filter="Halpha")])
    assert magnitude_label_for(zero_point) == "relative magnitude (broadband reference)"


@pytest.mark.parametrize("catalog,image_filter,mags", [
    ("SkyMapper", "V_", {"v": 13.0, "g": 12.0}),
    ("SkyMapper", "_V", {"v": 13.0, "g": 12.0}),
    ("SkyMapper", "U_", {"u": 13.0, "g": 12.0}),
    ("PanSTARRS", "R_", {"r": 13.0, "i": 12.0}),
])
def test_transcription_noise_cannot_bypass_single_letter_system_identity(catalog, image_filter, mags):
    assert not catalog_supports_filter(catalog, image_filter)
    assert not resolve_reference_band(catalog, image_filter).supported
    for permissive in (False, True):
        assert resolve_ref_mag_for_filter(
            catalog_name=catalog, image_filter=image_filter, cs_mags=mags,
            allow_preferred_band_fallback=permissive,
        ) == (None, None)


@pytest.mark.parametrize("image_filter,expected", [
    ("HALPHA", 14.21206), ("halpha", 14.21206), ("H_ALPHA", 14.21206),
    ("h_alpha", 14.21206), ("HBETA", 14.9), ("hbeta", 14.9),
])
def test_known_multiletter_aliases_never_enter_the_unknown_filter_fallback(image_filter, expected):
    from tools.catalogs import reference_band_unavailable

    assert catalog_supports_filter("APASS", image_filter)
    report = resolve_reference_band("APASS", image_filter)
    assert report.supported
    assert "broadband_reference" in {warning.code for warning in report.warnings}
    assert reference_band_unavailable("APASS", image_filter) is None
    for fallback in (False, True):
        actual, _ = resolve_ref_mag_for_filter(
            catalog_name="APASS", image_filter=image_filter,
            cs_mags={"V": 14.6, "gprime": 14.9, "rprime": 14.4, "iprime": 14.25},
            allow_preferred_band_fallback=fallback,
        )
        assert actual == pytest.approx(expected)


@pytest.mark.parametrize("source_name", ["Stetson", "StetsonGlobs"])
@pytest.mark.parametrize("reverse", [False, True])
def test_conflicting_alias_overrides_have_the_same_priority_in_pipeline_and_resolver(source_name, reverse):
    from algorithms.catalogs.schemas import CatalogSource
    from algorithms.fieldcal.field_cal import _collect_calibration_sources
    from algorithms.fieldcal.schemas import PhotometryData

    overrides = {"StetsonGlobs": {"Open": "V - 1"}, "Stetson": {"Open": "V - 2"}}
    if reverse:
        overrides = dict(reversed(list(overrides.items())))
    expected = 13.6 if source_name == "StetsonGlobs" else 12.6
    assert resolve(source_name, "Open", {"V": 14.6}, custom_filter_lookup=overrides) == (expected, None)
    result, = _collect_calibration_sources(
        [PhotometryData(id="x", filter="Open")],
        [CatalogSource(id="x", catalog_name=source_name, mags={"V": {"value": 14.6}})],
        catalog_filter_lookup={"StetsonGlobs": {"Open": "V"}}, custom_filter_lookup=overrides,
    )
    assert result.ref_mag == expected
