"""Filter-aware catalog selection: ``algorithms/query/selection.py``.

Selection narrows the configured catalog list to catalogs that can actually
produce a reference magnitude for the image's filter, before anything is
queried. Two properties matter and both are asserted here:

* it must share effective mappings, spelling and bounded alias traversal with
  reference-magnitude calculation;
* it must **never return an empty list**. A blank filter or a wholly
  incompatible configuration returns the input unchanged, because dropping every
  catalog turns a recoverable situation into a failed calibration.

Modelled on ``skynet .../tests/runners/test_catalog_query.py``'s
``TestCatalogSupportsFilter`` / ``TestSelectCatalogsForFilter``.
"""

from __future__ import annotations

import logging

import pytest

from algorithms.catalogs import CATALOGS
from algorithms.query.selection import (
    _expression_deps,
    _filter_token_candidates,
    _lookup_resolves,
    catalog_supports_filter,
    normalize_filter_token,
    select_catalogs_for_filter,
)

ALL_CATALOG_NAMES = sorted(CATALOGS)


# ---------------------------------------------------------------------------
# Expression dependency extraction
# ---------------------------------------------------------------------------

def test_expression_deps_reads_band_names_off_the_compiled_code():
    assert _expression_deps("r - 0.2936*(r - i)") == {"r", "i"}
    assert _expression_deps("B") == {"B"}


def test_math_builtins_are_not_mistaken_for_bands():
    """``sqrt``/``log10``/``abs``/``exp``/``log`` are functions, not columns.

    Without this exclusion, any transform using one would be judged to depend on
    a band no catalog has, and the catalog would be dropped from selection.
    """
    assert _expression_deps("sqrt(g) + log10(r) + abs(i) + exp(z) + log(y)") == {
        "g", "r", "i", "z", "y"
    }


def test_uncompilable_expression_resolves_nothing_rather_than_raising():
    """Selection is advisory; a malformed transform must not crash a query."""
    for broken in ("r - ", "*(", "1 +"):
        assert _expression_deps(broken) == set()


# ---------------------------------------------------------------------------
# Token candidates
# ---------------------------------------------------------------------------

def test_original_casing_is_tried_first():
    """SkyMapper's ``v`` and Johnson ``V`` are different bands.

    Lower-casing before trying the original would silently pick the wrong one.
    """
    assert _filter_token_candidates("V")[0] == "V"
    assert _filter_token_candidates("Halpha")[0] == "Halpha"


def test_violet_and_johnson_tokens_do_not_offer_case_variants():
    candidates = _filter_token_candidates("v")
    assert candidates[0] == "v"
    assert "V" not in candidates


def test_padded_input_never_yields_the_bare_upper_case_token():
    """CAT-01: whitespace must not bypass the V/v passband distinction."""
    assert _filter_token_candidates(" v ") == [" v ", "v"]
    assert "V" not in _filter_token_candidates(" v ")


def test_typographic_apostrophes_normalise_to_ascii():
    for variant in ("g′", "g’"):
        assert "g'" in _filter_token_candidates(variant)


def test_normalize_filter_token_strips_and_blanks_to_none():
    assert normalize_filter_token(" V ") == "V"
    assert normalize_filter_token("   ") is None
    assert normalize_filter_token("") is None
    assert normalize_filter_token(None) is None


# ---------------------------------------------------------------------------
# Two levels of indirection, and no more
# ---------------------------------------------------------------------------

def test_lookup_resolves_a_direct_band():
    assert _lookup_resolves("V", {"V", "B"}, {})


def test_lookup_resolves_one_alias_hop():
    assert _lookup_resolves("gp", {"gprime"}, {"gp": "gprime"})


def test_lookup_resolves_an_expression_over_bands():
    assert _lookup_resolves("r - 0.29*(r - i)", {"r", "i"}, {})


def test_lookup_resolves_an_alias_to_an_expression():
    """PanSTARRS's real chain: ``g'`` -> ``gprime`` -> an expression over g, r.

    ``_lookup_resolves`` is called with the lookup *value*, not the filter name —
    ``catalog_supports_filter`` has already done ``lookup.get(token)``. So the
    starting point here is ``gprime``, and the one permitted extra hop lands on
    the expression.
    """
    lookup = {"g'": "gprime", "gprime": "0.94*g + 0.06*r"}
    assert _lookup_resolves("gprime", {"g", "r"}, lookup)


def test_lookup_chains_match_numeric_resolution_and_detect_cycles():
    lookup = {"a": "b", "b": "c", "c": "V"}
    assert _lookup_resolves("a", {"V"}, lookup)
    assert not _lookup_resolves("a", {"V"}, {"a": "b", "b": "a"})
    assert not _lookup_resolves("a", {"V"}, {"a": "missing"})


def test_expression_needs_every_referenced_band():
    assert not _lookup_resolves("r - 0.29*(r - i)", {"r"}, {})


# ---------------------------------------------------------------------------
# catalog_supports_filter
# ---------------------------------------------------------------------------

def test_direct_band_support():
    assert catalog_supports_filter("APASS", "B")
    assert catalog_supports_filter("APASS", "V")


def test_support_via_a_colour_transform():
    """APASS answers an R-band image without carrying R at all."""
    assert "R" not in CATALOGS["APASS"].mags
    assert catalog_supports_filter("APASS", "R")


def test_ucac_native_open_does_not_substitute_for_other_filters():
    assert catalog_supports_filter("UCAC", "Open")
    assert not catalog_supports_filter("UCAC", "V")
    assert not catalog_supports_filter("UCAC", "SomeFilterNobodyHasHeardOf")


def test_ocl_filters_are_supported_by_the_v_capable_catalogs():
    for name in ("APASS", "Landolt", "Stetson"):
        for ocl in ("Open", "Clear", "Lum"):
            assert catalog_supports_filter(name, ocl), f"{name}/{ocl}"


def test_2mass_serves_optical_filters_through_jhk_colour_transforms():
    """2MASS is near-infrared but declares BVRI transforms over ``J - K``.

    Easy to assume a JHK catalog cannot answer a V-band frame; it can, through
    a cubic in ``J - K``. Selection therefore keeps 2MASS for optical filters,
    and that is correct. What it must not claim is a band with no transform.
    """
    assert {"J", "H", "K"} <= set(CATALOGS["2MASS"].mags)
    for optical in ("B", "V", "R", "I"):
        assert catalog_supports_filter("2MASS", optical), optical
    assert catalog_supports_filter("2MASS", "J")
    assert not catalog_supports_filter("2MASS", "OIII")
    assert not catalog_supports_filter("2MASS", "z'")


def test_unknown_catalog_returns_false_rather_than_raising():
    """Selection is advisory; the runner validates names with a clear error."""
    assert not catalog_supports_filter("NoSuchCatalog", "V")


def test_custom_filter_lookup_can_add_support():
    """A deployment can teach a catalog a filter MARS ships no transform for."""
    assert not catalog_supports_filter("2MASS", "OIII")
    assert catalog_supports_filter(
        "2MASS", "OIII", custom_filter_lookup={"2MASS": {"OIII": "J"}}
    )


def test_custom_lookup_for_another_catalog_is_ignored():
    assert not catalog_supports_filter(
        "2MASS", "OIII", custom_filter_lookup={"APASS": {"OIII": "J"}}
    )


# ---------------------------------------------------------------------------
# select_catalogs_for_filter
# ---------------------------------------------------------------------------

def test_selection_keeps_configured_priority_order():
    """Survivors keep their configured order — it is the query try-order."""
    configured = ["Landolt", "APASS", "PanSTARRS"]
    assert select_catalogs_for_filter(configured, "V") == ["Landolt", "APASS"]


def test_selection_drops_incompatible_catalogs():
    selected = select_catalogs_for_filter(["APASS", "2MASS"], "OIII")
    assert selected == ["APASS"]


def test_blank_filter_returns_the_list_unchanged():
    """Nothing to match on, so nothing is dropped."""
    configured = ["APASS", "2MASS"]  # 2MASS cannot serve OIII, but is kept
    for blank in (None, "", "   "):
        assert select_catalogs_for_filter(configured, blank) == configured


def test_no_compatible_catalog_falls_back_to_the_full_list(caplog):
    """A total mismatch returns everything and logs a warning.

    Dropping every catalog would turn a recoverable configuration disagreement
    into a failed calibration, so the full list is tried instead.
    """
    with caplog.at_level(logging.WARNING, logger="algorithms.query.selection"):
        selected = select_catalogs_for_filter(["2MASS"], "OIII")

    assert selected == ["2MASS"]
    assert any("No configured catalog supports filter" in r.message for r in caplog.records)


def test_selection_never_returns_an_empty_list():
    """The invariant, swept across every catalog and a spread of filters."""
    for image_filter in ("V", "B", "R", "I", "Halpha", "OIII", "Open", "Lum",
                         "g'", "rp", "J", "Nonsense", " "):
        selected = select_catalogs_for_filter(ALL_CATALOG_NAMES, image_filter)
        assert selected, image_filter
        assert set(selected) <= set(ALL_CATALOG_NAMES)


def test_selection_returns_a_copy_not_the_caller_list():
    configured = ["APASS", "2MASS"]
    result = select_catalogs_for_filter(configured, None)
    assert result is not configured
    result.append("mutated")
    assert configured == ["APASS", "2MASS"]


def test_unknown_names_in_the_configured_list_are_dropped_not_fatal():
    assert select_catalogs_for_filter(["APASS", "NoSuchCatalog"], "V") == ["APASS"]


# ---------------------------------------------------------------------------
# Agreement with reference-magnitude resolution
# ---------------------------------------------------------------------------

APASS_MAGS = {band: {"value": 15.0, "error": 0.02} for band in CATALOGS["APASS"].mags}


@pytest.mark.parametrize(
    "image_filter", ["V", "B", "R", "I", "Halpha", "OIII", "SII",
                     "g'", "r'", "i'", "gp", "rp", "ip"]
)
def test_selection_agrees_with_ref_mag_resolution_for_apass(image_filter):
    """Anything selection keeps APASS for, strict resolution must also serve.

    Both modules read the same effective ``CATALOGS`` mapping. This sweep is what catches them drifting further apart: a
    catalog kept by selection but rejected by resolution produces a frame that
    fails calibration with the unhelpful message "No calibration sources matched
    catalog magnitudes".

    OCL spellings are also checked in the dedicated test below.
    """
    from algorithms.fieldcal.ref_mag import resolve_ref_mag_for_filter

    if not catalog_supports_filter("APASS", image_filter):
        pytest.skip(f"selection does not keep APASS for {image_filter!r}")

    resolved, _ = resolve_ref_mag_for_filter(
        image_filter=image_filter, catalog_name="APASS", cs_mags=APASS_MAGS,
        allow_preferred_band_fallback=False,
    )
    assert resolved is not None, (
        f"selection keeps APASS for {image_filter!r} but strict resolution "
        f"returns None — the two registries have drifted"
    )


@pytest.mark.parametrize("image_filter", ("Open", "Clear", "Lum"))
def test_unfiltered_selection_and_strict_resolution_use_the_same_map(image_filter):
    from algorithms.fieldcal.ref_mag import resolve_ref_mag_for_filter

    assert catalog_supports_filter("APASS", image_filter)
    for fallback in (False, True):
        value, _ = resolve_ref_mag_for_filter(
            image_filter=image_filter, catalog_name="APASS", cs_mags=APASS_MAGS,
            allow_preferred_band_fallback=fallback,
        )
        assert value == pytest.approx(15.0)


def test_ocl_report_trials_more_filters_than_the_fallback_can_reach(ocl_filter_report):
    """The recorded OCL policy is a three-way trial, not a fixed preference.

    Skynet's report trials V, rprime and R per frame and keeps whichever gives
    the lowest slop — and rprime wins for 3 of the 9 frames it processed. The
    preferred-band fallback always answers V, so it reproduces the recorded
    choice for 6 of them and silently differs on the rest.
    """
    metadata = ocl_filter_report["metadata"]
    assert metadata["trial_filters"] == ["V", "rprime", "R"]
    assert "lowest" in metadata["selection_rule"]

    counts = ocl_filter_report["summary"]["best_filter_counts"]
    assert counts["V"] == 6
    assert counts["rprime"] == 3
    assert counts["V"] + counts["rprime"] + counts["R"] < metadata["total_files"]
