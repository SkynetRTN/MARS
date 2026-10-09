"""PUL-06: a failed local scan does not abort discovery or resolution."""

from pathlib import Path

import pytest

from tools import pulsar
from tools.models import PulsarScan, PulsarScanList


@pytest.mark.parametrize("failure", [PermissionError, FileNotFoundError])
def test_scan_listing_keeps_readable_scans(tmp_path, monkeypatch, failure):
    good = tmp_path / "good.txt"
    good.write_text("# SRC_NAME = B0329+54\n0 1 2 3\n")
    bad = tmp_path / "bad.txt"
    bad.touch()
    original = pulsar._scan_summary

    def summarize(path, directory=None):
        if Path(path) == bad:
            raise failure("injected scan read failure")
        return original(path, directory)

    monkeypatch.setattr(pulsar, "_scan_summary", summarize)
    listing = pulsar.list_pulsar_scans(tmp_path)
    assert listing.errors == []
    assert listing.count == 1
    assert [scan.path for scan in listing.scans] == [str(good)]
    warning = next(w for w in listing.warnings if w.code == "scan_unreadable")
    assert "bad.txt" in warning.message

    resolved = pulsar.resolve_pulsar_scan("B0329+54", tmp_path)
    assert isinstance(resolved, PulsarScan)
    assert resolved.path == str(good)
    assert any(w.code == "scan_unreadable" for w in resolved.warnings)


@pytest.mark.parametrize("failure", [PermissionError, FileNotFoundError])
def test_explicit_scan_read_failure_is_structured(tmp_path, monkeypatch, failure):
    source = tmp_path / "scan.txt"
    source.touch()

    def summarize(*args, **kwargs):
        raise failure("injected scan read failure")

    monkeypatch.setattr(pulsar, "_scan_summary", summarize)
    result = pulsar.resolve_pulsar_scan(str(source), tmp_path)
    assert isinstance(result, PulsarScanList)
    assert [e.code for e in result.errors] == ["read_failed"]
    assert result.count == 0
    assert "scan.txt" in result.errors[0].message


def test_scan_stat_failure_is_structured(tmp_path, monkeypatch):
    source = tmp_path / "scan.txt"
    source.write_text("# SRC_NAME = B0329+54\n0 1 2 3\n")
    original = Path.stat
    opened = False
    original_open = Path.open

    def open_file(path, *args, **kwargs):
        nonlocal opened
        if path == source:
            opened = True
        return original_open(path, *args, **kwargs)

    def stat(path, *args, **kwargs):
        if path == source and opened:
            raise FileNotFoundError("scan disappeared after its header was read")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_file)
    monkeypatch.setattr(Path, "stat", stat)
    result = pulsar.resolve_pulsar_scan(str(source), tmp_path)
    assert isinstance(result, PulsarScanList)
    assert [e.code for e in result.errors] == ["read_failed"]


def test_scan_header_has_a_finite_read_budget(tmp_path):
    source = tmp_path / "header.txt"
    source.write_text("#" + "x" * 70_000 + "\n0 1 2 3\n")
    result = pulsar.resolve_pulsar_scan(str(source), tmp_path)
    assert isinstance(result, PulsarScanList)
    assert [e.code for e in result.errors] == ["parse_error"]


@pytest.mark.parametrize("lines, accepted", [(256, True), (257, False)])
def test_scan_header_line_budget_boundary(tmp_path, lines, accepted):
    source = tmp_path / "header.txt"
    source.write_text("# metadata\n" * lines + "0 1 2 3\n")
    result = pulsar.resolve_pulsar_scan(str(source), tmp_path)
    if accepted:
        assert isinstance(result, PulsarScan)
    else:
        assert isinstance(result, PulsarScanList)
        assert [e.code for e in result.errors] == ["parse_error"]


def test_directory_stat_failure_is_structured(tmp_path, monkeypatch):
    original = Path.stat

    def stat(path, *args, **kwargs):
        if path == tmp_path:
            raise PermissionError("injected root permission failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    result = pulsar.list_pulsar_scans(tmp_path)
    assert [e.code for e in result.errors] == ["read_failed"]
    assert result.count == 0


def test_disappearing_scan_after_discovery_is_a_warning(tmp_path, monkeypatch):
    source = tmp_path / "vanished.txt"
    source.touch()
    original = Path.stat

    def stat(path, *args, **kwargs):
        if path == source:
            raise FileNotFoundError("injected disappearance after discovery")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    result = pulsar.list_pulsar_scans(tmp_path)
    assert result.errors == []
    assert result.count == 0
    assert any(w.code == "scan_unreadable" for w in result.warnings)


def test_directory_read_failure_is_not_a_successful_empty_listing(tmp_path, monkeypatch):
    original = Path.iterdir

    def iterate(path):
        if path == tmp_path:
            raise PermissionError("injected directory read failure")
        return original(path)

    monkeypatch.setattr(Path, "iterdir", iterate)
    result = pulsar.list_pulsar_scans(tmp_path)
    assert [e.code for e in result.errors] == ["read_failed"]
    assert result.count == 0
