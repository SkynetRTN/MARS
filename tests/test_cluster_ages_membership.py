"""M2: cluster age units, identifier joins and measured zero proper motion."""

import math

import numpy as np
import pandas as pd
import pytest
from astropy.table import Table, QTable

from algorithms.hrdiagram_py import legacy
from tools import hr_diagram


@pytest.mark.parametrize("table_type", [Table, QTable])
def test_astropy_mixin_masks_are_not_ages_or_members(table_type):
    from astropy.utils.masked import Masked

    table = table_type({"age": Masked(np.array([9., 8.]), mask=[True, False]),
                        "pm_ra": Masked(np.array([0., 3.]), mask=[True, False]),
                        "pm_dec": [0., 4.]})
    rows = [dict(row) for row in table]
    assert legacy.get_mwsc_age_distribution(rows) == [100.]
    sources = [{"fsr": row} for row in rows]
    selected = legacy.update_cluster_field_sources(sources, {})
    assert selected == {"fsr": sources[1:], "not_fsr": sources[:1]}
    assert legacy.get_velocity_dispersion(sources, 0., 0.) == pytest.approx(5 / math.sqrt(2))


@pytest.mark.parametrize("component", ["pm_ra", "pm_dec"])
def test_masked_motion_is_missing_even_when_its_backing_value_is_finite(component):
    from astropy.utils.masked import Masked

    source = {"fsr": {"pm_ra": 0., "pm_dec": 0.}}
    source["fsr"][component] = Masked(np.array(42.), mask=True)
    assert legacy.update_cluster_field_sources([source], {})["fsr"] == []
    with pytest.raises(ValueError, match="paired"):
        legacy.get_velocity_dispersion([source], 0., 0.)


def test_age_histogram_keeps_old_clusters_in_myr():
    clusters = [{"age": age} for age in [9., 7., None, 10.1, 8., 10.]]
    assert legacy.get_mwsc_age_distribution(clusters) == pytest.approx([
        10., 100., 1_000., 10_000., 12_589.254117941662,
    ])


def test_age_histogram_retains_the_13_8_gyr_window_without_overflow():
    clusters = [{"age": age} for age in [
        None, math.nan, math.inf, -math.inf, 1000., -1000.,
        math.log10(14e9), math.log10(12.5e9), 9.,
    ]]
    assert legacy.get_mwsc_age_distribution(clusters) == pytest.approx([1_000., 12_500.])


@pytest.mark.parametrize("dtype", [np.int32, np.int64, np.uint64])
def test_age_histogram_accepts_integer_catalogue_arrays_without_wrapping(dtype):
    clusters = [{"age": age} for age in np.array([9, 0, 5, 6], dtype=dtype)]
    assert legacy.get_mwsc_age_distribution(clusters) == pytest.approx([1e-6, .1, 1., 1000.])


def _fsr(identifier, pm_ra=0., pm_dec=0.):
    return {"id": identifier, "pm_ra": pm_ra, "pm_dec": pm_dec, "distance": 1.}


@pytest.mark.parametrize("order", [
    ["1", "10", "2"], ["2", "1", "10"], ["10", "2", "1"],
])
def test_fsr_join_matches_every_identifier_independent_of_sort_order(order):
    sources = [{"id": identifier, "fsr": None} for identifier in order]
    rows = [_fsr("2", 2.), _fsr("10", 10.), _fsr("1", 1.)]
    result = legacy.append_fsr_results(sources, rows)
    assert result is sources
    assert [source["id"] for source in result] == order
    assert [source["fsr"]["pm_ra"] for source in result] == [float(identifier) for identifier in order]
    assert [row["id"] for row in rows] == ["2", "10", "1"]


def test_fsr_identifiers_are_opaque_and_unmatched_sources_are_retained():
    identifiers = ["01", "1", 2**53 + 1, 2**53, "Gaia-opaque"]
    sources = [{"id": identifier, "fsr": None} for identifier in identifiers]
    previous = {"pm_ra": 7., "pm_dec": 8., "distance": 9.}
    sources.append({"id": "unmatched", "fsr": previous})
    rows = [_fsr(identifier, index + 1.) for index, identifier in enumerate(identifiers)]
    legacy.append_fsr_results(sources, rows[::-1] + [_fsr("unknown")])
    assert [source["fsr"]["pm_ra"] for source in sources[:-1]] == [1., 2., 3., 4., 5.]
    assert sources[-1]["fsr"] is previous


def test_duplicate_fsr_results_keep_the_first_match():
    sources = [{"id": "1", "fsr": None}]
    legacy.append_fsr_results(sources, [_fsr("1", 1.), _fsr("1", 2.)])
    assert sources[0]["fsr"]["pm_ra"] == 1.


def _selection(ra=(-1., 1.), dec=(-1., 1.)):
    return {
        "distance": {"min": .5, "max": 1.5},
        "pm_ra": {"min": ra[0], "max": ra[1]},
        "pm_dec": {"min": dec[0], "max": dec[1]},
    }


@pytest.mark.parametrize("motion", [(0., 0.), (0., .5), (.5, 0.)])
@pytest.mark.parametrize("bounded", [False, True])
def test_zero_motion_is_a_measurement_inside_the_selection(motion, bounded):
    source = {"id": "zero", "fsr": _fsr("zero", *motion)}
    selection = _selection() if bounded else {"distance": None, "pm_ra": None, "pm_dec": None}
    result = legacy.update_cluster_field_sources([source], selection)
    assert result == {"fsr": [source], "not_fsr": []}


@pytest.mark.parametrize("bounded", [False, True])
@pytest.mark.parametrize("component", ["pm_ra", "pm_dec"])
def test_missing_or_nonfinite_motion_is_not_a_measured_zero(bounded, component):
    sources = [
        {"id": str(index), "fsr": {**_fsr(str(index)), component: value}}
        for index, value in enumerate([None, math.nan, math.inf, -math.inf])
    ]
    selection = _selection() if bounded else {"distance": None, "pm_ra": None, "pm_dec": None}
    result = legacy.update_cluster_field_sources(sources, selection)
    assert result == {"fsr": [], "not_fsr": sources}


@pytest.mark.parametrize("ra, dec, motion", [
    ((0., 0.), (-1., 1.), (0., .5)),
    ((-1., 1.), (0., 0.), (.5, 0.)),
    ((0., 0.), (0., 0.), (0., 0.)),
])
def test_zero_width_motion_selection_is_a_closed_line_or_point(ra, dec, motion):
    inside = {"id": "inside", "fsr": _fsr("inside", *motion)}
    outside = {"id": "outside", "fsr": _fsr("outside", 2., 2.)}
    result = legacy.update_cluster_field_sources([inside, outside], _selection(ra, dec))
    assert result == {"fsr": [inside], "not_fsr": [outside]}


def test_ellipse_includes_boundary_but_excludes_rectangle_corners_without_mutation():
    sources = [
        {"id": str(index), "fsr": _fsr(str(index), *motion)}
        for index, motion in enumerate([(1., 0.), (.6, .8), (1., 1.), (0., -1.)])
    ]
    original = [dict(source, fsr=dict(source["fsr"])) for source in sources]
    result = legacy.update_cluster_field_sources(sources, _selection())
    assert [source["id"] for source in result["fsr"]] == ["0", "1", "3"]
    assert [source["id"] for source in result["not_fsr"]] == ["2"]
    assert sources == original


@pytest.mark.parametrize("component", ["pm_ra", "pm_dec"])
@pytest.mark.parametrize("bounds", [(.1, .3), (1.2, 1.6)])
@pytest.mark.parametrize("line", [False, True])
def test_decimal_endpoints_are_inclusive_and_adjacent_outside_values_are_rejected(component, bounds, line):
    other_bounds = (0., 0.) if line else (-1., 1.)
    selection = _selection(bounds, other_bounds) if component == "pm_ra" else _selection(other_bounds, bounds)
    points = [bounds[0], bounds[1], math.nextafter(bounds[0], -math.inf), math.nextafter(bounds[1], math.inf)]
    sources = [
        {"id": str(index), "fsr": {**_fsr(str(index)), component: value}}
        for index, value in enumerate(points)
    ]
    result = legacy.update_cluster_field_sources(sources, selection)
    assert [source["id"] for source in result["fsr"]] == ["0", "1"]
    assert [source["id"] for source in result["not_fsr"]] == ["2", "3"]


def test_join_and_partition_keep_zero_motion_id_10():
    sources = [{"id": identifier, "fsr": None} for identifier in ["1", "10", "2"]]
    legacy.append_fsr_results(sources, [_fsr("2", 4., 4.), _fsr("10"), _fsr("1", .5, .5)])
    result = legacy.update_cluster_field_sources(sources, _selection())
    assert [source["id"] for source in result["fsr"]] == ["1", "10"]
    assert [source["id"] for source in result["not_fsr"]] == ["2"]


def test_registered_membership_preserves_zero_motion_in_written_artifact(tmp_path, artifact_dir, monkeypatch):
    path = tmp_path / "matched.ecsv"
    Table.from_pandas(pd.DataFrame({
        "id": ["zero", "one-zero", "outside", "missing"],
        "parallax": [2.] * 4, "parallax_error": [.01] * 4,
        "pmra": [0., 0., 10., math.nan], "pmdec": [0., .1, 0., 0.],
        "pmra_error": [.01] * 4, "pmdec_error": [.01] * 4,
    })).write(path, format="ascii.ecsv")
    monkeypatch.setattr(hr_diagram, "_fetch_literature_params", lambda _: {
        "parallax_mas": 2., "distance_kpc": .5, "pmra_mas_yr": 0., "pmdec_mas_yr": 0.,
    })
    result = hr_diagram.select_cluster_members(str(path), "synthetic")
    assert result.status == "ok"
    assert result.count == 2
    saved = Table.read(result.artifact.path)
    assert list(saved["id"]) == ["zero", "one-zero"]
