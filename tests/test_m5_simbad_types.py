"""Public SIMBAD resolution preserves machine-type meaning and unknown codes."""

from types import SimpleNamespace

import numpy as np
import pytest
from astropy.table import MaskedColumn, Table

from algorithms.query import simbad
from tools.resolve import resolve_target


@pytest.mark.parametrize("code, label", [
    ("*", "Star"), ("G", "Galaxy"),
    ("Star", "Star"), ("Galaxy", "Galaxy"),
    ("future_type", "future_type"),
    ("Unknown", "Unknown"), ("Possible_As*", ""),
    (b"*", "Star"), (b"G", "Galaxy"), (b"future_type", "future_type"),
    (" G ", "Galaxy"), (None, ""),
])
def test_public_resolution_keeps_meaningful_type_without_changing_coordinates(
    monkeypatch, code, label,
):
    table = Table({
        "main_id": ["reference"], "ra": [0.0], "dec": [-12.5],
        "otype": np.array([code], dtype=object),
    })
    calls = []

    def query_object(name, **kwargs):
        calls.append((name, kwargs))
        return table

    monkeypatch.setattr(simbad, "_simbad", SimpleNamespace(query_object=query_object))
    result = resolve_target(" Reference ")

    assert result.status == "ok" and result.errors == [] and result.count == 1
    assert result.preview[0]["object_type"] == label
    assert result.preview[0]["ra_deg"] == 0.0
    assert result.preview[0]["dec_deg"] == -12.5
    assert calls == [("reference", {"wildcard": False})]


def test_masked_type_does_not_discard_an_otherwise_usable_match(monkeypatch):
    table = Table({"main_id": ["reference"], "ra": [0.0], "dec": [0.0]})
    table["otype"] = MaskedColumn(["G"], mask=[True])
    monkeypatch.setattr(
        simbad, "_simbad", SimpleNamespace(query_object=lambda *a, **k: table),
    )
    result = resolve_target("reference")

    assert result.status == "ok" and result.count == 1
    assert result.preview[0]["object_type"] == ""
