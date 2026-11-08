"""Offline M5 investigation of CAT-21/25/32, not corrected behavior.

Tests named ``characterizes_bug`` pin an observed defect. Other tests distinguish
retained wire policy, optional identifiers, and the scope of same-row dedup.
Provider responses stop at SDK seams; mapping, geometry and solvers remain real.
"""

from __future__ import annotations

import json
import math
from types import SimpleNamespace
import warnings

import numpy as np
import pytest
from astropy.table import MaskedColumn, Table
from astropy.wcs import WCS
from pydantic import ValidationError

from algorithms.catalogs.schemas import CatalogSource, Mag
from algorithms.fieldcal.field_cal import (
    _normalize_catalog_sources,
    perform_field_calibration,
)
from algorithms.fieldcal.ref_mag import resolve_ref_mag_for_filter
from algorithms.query import simbad
from algorithms.query.geometry import remove_duplicate_sources
from algorithms.query.registry import CATALOGS
from algorithms.query.runner import query_catalogs
from algorithms.query.vizier import VizierClass
from tools.calibration import solve_zeropoint_from_measurements
from tools.resolve import resolve_target


def _simbad_response(monkeypatch, otype, *, ra=0.0, dec=0.0):
    table = Table({"main_id": ["test object"], "ra": [ra], "dec": [dec], "otype": [otype]})
    calls = []

    def query_object(name, **kwargs):
        calls.append((name, kwargs))
        return table

    monkeypatch.setattr(simbad, "_simbad", SimpleNamespace(query_object=query_object))
    return calls


@pytest.mark.parametrize("otype", ["*", "G"])
def test_cat21_characterizes_bug_common_machine_types_lose_public_labels(monkeypatch, otype):
    # Current SIMBAD otype is the machine code, distinct from its otyp.label.
    # https://docs.astropy.org/projects/astroquery/en/stable/simbad/simbad_evolution.html#object-types
    calls = _simbad_response(monkeypatch, otype)
    result = resolve_target(" Test Object ")
    assert result.status == "ok" and result.count == 1
    assert result.preview[0]["object_type"] == ""
    assert result.preview[0]["ra_deg"] == result.preview[0]["dec_deg"] == 0.0
    assert calls == [("test object", {"wildcard": False})]


@pytest.mark.parametrize("otype,label", [("Star", "Star"), ("Galaxy", "Galaxy")])
def test_cat21_retained_long_vocabulary_keys_produce_public_prose(monkeypatch, otype, label):
    # Controls for the retained dictionary, not a claim that modern otype
    # returns these long labels in place of the machine codes above.
    _simbad_response(monkeypatch, otype)
    assert resolve_target("test object").preview[0]["object_type"] == label


def test_cat21_characterizes_bug_unknown_code_is_erased_instead_of_raw_fallback(monkeypatch):
    # catalogs.simbad promises a raw-code fallback; ResolvedTarget instead
    # documents the implementation's empty-string policy. This test pins that
    # observable mismatch without treating an unknown code as no match.
    _simbad_response(monkeypatch, "future_code_not_in_mars")
    result = resolve_target("test object")
    assert result.status == "ok" and result.errors == []
    assert result.preview[0]["object_type"] == ""


def test_cat21_a_deliberately_empty_vocabulary_label_is_not_a_missing_match(monkeypatch):
    _simbad_response(monkeypatch, "Possible_As*")
    result = resolve_target("test object")
    assert result.status == "ok" and result.preview[0]["object_type"] == ""


def test_cat21_masked_position_is_skipped_while_real_zero_position_survives(monkeypatch):
    table = Table({
        "main_id": ["origin", "masked"], "otype": ["Star", "Star"],
        "ra": MaskedColumn([0.0, 10.0], mask=[False, True]), "dec": [0.0, 0.0],
    })
    monkeypatch.setattr(simbad, "_simbad", SimpleNamespace(query_object=lambda *a, **k: table))
    result = resolve_target("two candidates")
    assert result.count == 1 and result.preview[0]["object_name"] == "origin"


@pytest.mark.parametrize("value", [None, math.nan, math.inf, -math.inf])
def test_cat25_retained_null_wire_policy_does_not_change_reference_eligibility(value):
    original = Mag(value=value, error=0.03)
    dumped = original.model_dump()
    assert dumped == {"value": None, "error": 0.03}
    assert json.loads(original.model_dump_json()) == dumped
    restored = Mag.model_validate(dumped)
    assert restored.value is None and restored.error == 0.03
    if value is not None:
        assert not math.isfinite(original.value)  # serialization does not mutate the model
    for mags in ({"V": original}, {"V": restored}, {"V": dumped}):
        assert resolve_ref_mag_for_filter(
            image_filter="V", catalog_name="APASS", cs_mags=mags,
        ) == (None, None)
    source = CatalogSource(id="ref", catalog_name="APASS", mags={"V": original})
    measurement = {"id": "ref", "filter": "V", "mag": -6.0, "mag_error": 0.02}
    for supplied in (source, json.loads(source.model_dump_json())):
        result = solve_zeropoint_from_measurements([measurement], [supplied])
        assert result.source_count == 0 and result.zero_point is None
        assert [error.code for error in result.errors] == ["no_usable_sources"]


@pytest.mark.parametrize("error", [None, math.nan, math.inf, -math.inf, 0.0, 0.03])
def test_cat25_finite_magnitude_keeps_eligibility_and_zero_error_across_serialization(error):
    magnitude = Mag(value=0.0, error=error)
    expected_error = error if error is not None and math.isfinite(error) else None
    for mags in ({"V": magnitude}, {"V": magnitude.model_dump()}):
        assert resolve_ref_mag_for_filter(
            image_filter="V", catalog_name="APASS", cs_mags=mags,
        ) == (0.0, expected_error)


def test_cat25_a_finite_public_solution_is_identical_after_catalog_json_roundtrip():
    sources = [CatalogSource(
        id=str(i), catalog_name="APASS", mags={"V": Mag(value=ref, error=0.02)},
    ) for i, ref in enumerate([12.8, 14.0, 15.2])]
    measurements = [{"id": str(i), "filter": "V", "mag": mag, "mag_error": 0.03}
                    for i, mag in enumerate([-7.0, -6.0, -5.0])]
    direct = solve_zeropoint_from_measurements(measurements, sources)
    serialized = solve_zeropoint_from_measurements(
        measurements, [json.loads(source.model_dump_json()) for source in sources],
    )
    assert direct.errors == [] and direct.source_count == 3
    assert direct.zero_point == pytest.approx(20.0)
    assert direct.zero_point_error_mag > 0
    assert direct.model_dump() == serialized.model_dump()


def _identity_table(identifier=None, *, ra=0.0, dec=0.0):
    table = Table({"RAJ2000": [ra], "DEJ2000": [dec], "Vmag": [12.0], "e_Vmag": [0.02]})
    if identifier is not None:
        table["recno"] = [identifier]
    return table


def _offline_regions(monkeypatch, tables):
    responses, calls = iter(tables), []

    def query_region(client, coordinate, **kwargs):
        calls.append((coordinate, kwargs))
        return [next(responses)]

    monkeypatch.setattr(VizierClass, "query_region", query_region)
    return calls


def _wcs(ra=0.0):
    wcs = WCS(naxis=2)
    wcs.wcs.crval = [ra, 0.0]
    wcs.wcs.crpix = [16.5, 16.5]
    wcs.wcs.cdelt = [-0.01, 0.01]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.array_shape = (32, 32)
    return wcs


@pytest.mark.parametrize("identifier,normalized_id", [(None, None), (0, "0"), (42, "42")])
def test_cat32_bound_apass_optional_or_integer_identifiers_reach_fieldcal_normalization(
    monkeypatch, identifier, normalized_id,
):
    # recno is conditional input: current II/336 metadata has no such column.
    # This tests mapping behavior, not a provider stability guarantee.
    calls = _offline_regions(monkeypatch, [_identity_table(identifier)])
    (source,) = CATALOGS["APASS"].query_circ(0.0, 0.0, 1.0)
    assert source.ra_hours == source.dec_degs == 0.0
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Pydantic serializer warnings:", category=UserWarning)
        (normalized,) = _normalize_catalog_sources([source], file_id=7)
    assert normalized.id == normalized_id and normalized.file_id == 7
    assert len(calls) == 1 and "recno" in CATALOGS["APASS"]._columns


@pytest.mark.parametrize("first_id,second_id,expected_count", [
    (None, None, 1), (0, 0, 1), (42, 42, 1), (42, 420, 2), (None, 42, 2),
])
def test_cat32_real_multi_image_runner_deduplicates_only_equal_row_identities(
    monkeypatch, first_id, second_id, expected_count,
):
    # A changed ordinal is a conditional re-ingest-like experiment, not proof
    # of a live APASS change or a promise of persistent astrophysical identity.
    calls = _offline_regions(monkeypatch, [_identity_table(first_id), _identity_table(second_id)])
    sources = query_catalogs(["APASS"], wcs=[_wcs(), _wcs(0.001)])
    assert len(calls) == 2 and len(sources) == expected_count
    assert all(source.ra_hours == source.dec_degs == 0.0 for source in sources)


def test_cat32_equal_id_at_distinct_positions_is_not_merged_by_the_multi_image_runner(monkeypatch):
    _offline_regions(monkeypatch, [_identity_table(42), _identity_table(42, ra=0.01)])
    sources = query_catalogs(["APASS"], wcs=[_wcs(), _wcs(0.001)])
    assert len(sources) == 2 and sources[0].ra_hours != sources[1].ra_hours


def test_cat32_catalog_blind_helper_is_not_used_to_cross_deduplicate_runner_results(monkeypatch):
    table = _identity_table()
    table["rmag"] = [12.0]
    # Both catalogs lack an id in this experiment, including PanSTARRS, so
    # identical triples would collide if the runner merged before deduping.
    _offline_regions(monkeypatch, [table.copy() for _ in range(4)])
    sources = query_catalogs(["APASS", "PanSTARRS"], wcs=[_wcs(), _wcs(0.001)])
    assert [source.catalog_name for source in sources] == ["APASS", "PanSTARRS"]
    assert len(remove_duplicate_sources(list(sources))) == 1


def test_cat32_characterizes_conditional_masked_optional_id_rejection(monkeypatch):
    # APASS does not currently serve recno. If an optional integer id is
    # present but masked, its sentinel is not normalized like an absent id.
    table = _identity_table()
    table["recno"] = MaskedColumn([42], mask=[True])
    _offline_regions(monkeypatch, [table])
    sources = CATALOGS["APASS"].query_circ(0.0, 0.0, 1.0)
    assert len(sources) == 1 and np.ma.is_masked(sources[0].id)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Pydantic serializer warnings:", category=UserWarning)
        with pytest.raises(ValidationError, match="Input should be a valid string") as caught:
            perform_field_calibration({}, np.zeros((4, 4)), wcs=_wcs(), catalog_sources=sources)
    assert caught.value.errors()[0]["loc"] == ("id",)
