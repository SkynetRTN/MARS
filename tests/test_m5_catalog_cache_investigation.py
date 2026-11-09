"""M5 CAT-17/26 investigation: current behavior, with no provider network.

Geometry witnesses are specified independently
of MARS clipping. SDK checks retain the installed astroquery request/cache path
and replace only its HTTP session or the filesystem operation being tested.
"""

from datetime import timedelta
import builtins
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.units import arcmin, deg
import astroquery.query as sdk_query
from requests import Request, Response

from algorithms.query import cache, config, vizier
from algorithms.query.registry import CATALOGS
from algorithms.query.runner import query_catalogs


def _capture_region(monkeypatch, name):
    """Capture the backend's actual provider boundary, without emulating it."""
    catalog = CATALOGS[name]
    received = []
    if name == "SDSS":
        def transport(ra, dec, region, limit):
            received.append((ra, dec, region))
            return []

        monkeypatch.setattr(catalog, "_query_sql_region", transport)
    else:
        def transport(ra, dec, constraints, limit, **region):
            dimensions = ((region["width"], region["height"])
                          if "width" in region else region["radius"])
            received.append((ra, dec, dimensions))
            return []

        monkeypatch.setattr(catalog, "query_region", transport)
    return catalog, received


def test_constructed_catalog_uses_enabled_setting_despite_false_class_attribute(monkeypatch):
    monkeypatch.delenv("VIZIER_CACHE_ENABLED", raising=False)
    settings = config.QuerySettings()
    assert vizier.VizierCatalog.cache is False
    assert settings.VIZIER_CACHE_ENABLED is True
    monkeypatch.setattr(vizier, "settings", settings)
    assert type(CATALOGS["APASS"])().cache is True
    assert type(CATALOGS["SDSS"])().cache is True
    assert type(CATALOGS["APASS"])(cache=False).cache is False


@pytest.mark.parametrize("name", ["APASS", "SDSS"])
@pytest.mark.parametrize("dec,height,direction", [
    (20.0013, 2.0, 1), (-20.0013, 2.0, -1), (89.999, 0.2, -1), (-89.999, 0.2, 1),
])
def test_cached_public_box_preserves_original_latitude_edge(
    name, dec, height, direction, monkeypatch,
):
    """Exact grid-multiple dimensions grow to compensate for centre motion."""
    catalog, received = _capture_region(monkeypatch, name)
    # On the meridian, rectangular latitude extent is unambiguous even near
    # the poles. Stay 0.06 arcsec inside the edge away from the rounded centre.
    witness_dec = dec + direction * (height / 120 - 0.001 / 60)
    assert abs(witness_dec - dec) * 60 < height / 2
    for enabled in (False, True):
        monkeypatch.setattr(catalog, "cache", enabled)
        assert query_catalogs([name], ra_hours=1.0, dec_degs=dec,
                              width_arcmins=2.0, height_arcmins=height) == []
    (_, exact_dec, exact_dimensions), (_, snapped_dec, dimensions) = received
    assert exact_dec == dec
    assert abs(witness_dec - exact_dec) * 60 < exact_dimensions[1].to_value(arcmin) / 2
    assert dimensions[1].to_value(arcmin) >= height
    assert abs(witness_dec - snapped_dec) * 60 < dimensions[1].to_value(arcmin) / 2


@pytest.mark.parametrize("name", ["APASS", "SDSS"])
@pytest.mark.parametrize("ra_deg", [0.0013, 359.9987])
def test_cached_public_equatorial_box_preserves_edge_at_ra_seam(
    name, ra_deg, monkeypatch,
):
    catalog, received = _capture_region(monkeypatch, name)
    monkeypatch.setattr(catalog, "cache", True)
    # At the equator, angular width equals longitude width. Specify the edge
    # directly rather than asking MARS's box clipper what should be included.
    direction = 1 if ra_deg < 180 else -1
    witness_ra = (ra_deg + direction * (1.0 - 0.001) / 60) % 360
    original_distance = abs((witness_ra - ra_deg + 180) % 360 - 180) * 60
    assert original_distance < 1.0
    assert query_catalogs([name], ra_hours=ra_deg / 15, dec_degs=0,
                          width_arcmins=2.0, height_arcmins=2.0) == []
    snapped_ra, _, dimensions = received[0]
    assert snapped_ra == 0.0
    assert dimensions[0].to_value(arcmin) >= 2.0
    snapped_distance = abs((witness_ra - snapped_ra * 15 + 180) % 360 - 180) * 60
    assert snapped_distance < dimensions[0].to_value(arcmin) / 2


@pytest.mark.parametrize("name", ["APASS", "SDSS"])
@pytest.mark.parametrize("ra_deg,dec", [
    (15.0013, 20.0013), (359.9987, 0.0013), (0.0013, 89.999), (15.0013, -89.999),
])
def test_public_cached_cone_encloses_independent_edge_witnesses(
    name, ra_deg, dec, monkeypatch,
):
    catalog, received = _capture_region(monkeypatch, name)
    monkeypatch.setattr(catalog, "cache", True)
    original = SkyCoord(ra_deg, dec, unit=deg)
    # Radius is an exact cache-grid multiple; the old size-only rounding has
    # no slack to compensate for moving the centre. Sample all bearings just
    # inside that original cap, including near the seam and both poles.
    witnesses = original.directional_offset_by(np.arange(0, 360, 10) * deg,
                                              (1.2 - 1e-5) * arcmin)
    assert np.all(original.separation(witnesses).arcmin < 1.2)
    assert query_catalogs([name], ra_hours=ra_deg / 15, dec_degs=dec,
                          radius_arcmins=1.2) == []
    ra, latitude, radius = received[0]
    assert np.all(SkyCoord(ra * 15, latitude, unit=deg).separation(witnesses).arcmin
                  <= radius.to_value(arcmin))


def _response(method, url, payload=None):
    response = Response()
    response.status_code = 200
    response.url = url
    response.request = Request(method, url).prepare()
    response._content = payload or (
        b'<?xml version="1.0"?><VOTABLE version="1.3" '
        b'xmlns="http://www.ivoa.net/xml/VOTable/v1.3"><RESOURCE/></VOTABLE>'
    )
    return response


@pytest.fixture
def sdk_cache(tmp_path, monkeypatch):
    """Use real installed SDK cache machinery, confined to this temp tree."""
    directory = tmp_path / "Vizier"
    directory.mkdir()
    monkeypatch.setattr(cache, "vizier_cache_dir", lambda: str(directory))
    client = vizier.VizierClass(catalog="II/336/apass9")
    client.cache_location = directory
    requests = []

    def transport(method, url, **kwargs):
        requests.append((method, url, kwargs))
        return _response(method, url)

    monkeypatch.setattr(client._session, "request", transport)
    return client, directory, requests


def _sdk_region(client, *, enabled=True):
    return client.query_region(SkyCoord(15, 20, unit=deg), radius=1 * arcmin,
                               catalog="II/336/apass9", cache=enabled)


@pytest.mark.parametrize("fault", ["permission", "corrupt_pickle"])
def test_installed_sdk_read_failure_refetches_and_replaces_cache(sdk_cache, monkeypatch, fault):
    client, directory, requests = sdk_cache
    assert not _sdk_region(client)
    entry, = directory.glob("*.pickle")
    with monkeypatch.context() as scope:
        if fault == "corrupt_pickle":
            entry.write_bytes(b"not a pickle")
        else:
            def denied_read(path, mode, *args, **kwargs):
                if Path(path) == entry and mode == "rb":
                    raise PermissionError("injected cache read failure")
                return builtins.open(path, mode, *args, **kwargs)

            scope.setattr(sdk_query, "open", denied_read, raising=False)
        assert not _sdk_region(client)
    assert len(requests) == 2
    assert not _sdk_region(client)  # The replacement really is readable.
    assert len(requests) == 2


def test_installed_sdk_write_failure_leaves_provider_result_usable(sdk_cache, monkeypatch):
    client, directory, requests = sdk_cache
    failed_writes = []

    def denied_write(path, mode, *args, **kwargs):
        if Path(path).parent == directory and mode == "wb":
            failed_writes.append(path)
            raise OSError("injected cache disk-full failure")
        return builtins.open(path, mode, *args, **kwargs)

    monkeypatch.setattr(sdk_query, "open", denied_write, raising=False)
    assert not _sdk_region(client)
    assert not _sdk_region(client)
    assert len(requests) == len(failed_writes) == 2
    assert list(directory.glob("*.pickle")) == []


def test_installed_sdk_eviction_failure_is_nonfatal(sdk_cache, monkeypatch):
    client, directory, requests = sdk_cache
    assert not _sdk_region(client)
    entry, = directory.glob("*.pickle")
    original_unlink = Path.unlink
    failures = []

    def denied_unlink(path, *args, **kwargs):
        if path == entry:
            failures.append(path)
            raise PermissionError("injected cache eviction failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", denied_unlink)
    assert client._last_query.remove_cache_file(client.cache_location) is None
    assert failures == [entry]
    assert entry.exists()
    assert not _sdk_region(client)  # Still a valid cached response.
    assert len(requests) == 1


@pytest.fixture
def sdss_error_cache(sdk_cache, monkeypatch):
    """Keep SDSS's direct eviction path and the installed SDK request intact."""
    from algorithms.query.sdss import MARSSDSS

    _, vizier_directory, _ = sdk_cache
    directory = vizier_directory.parent / "SDSS"
    client = MARSSDSS()
    client.cache_location = directory
    answers = iter([
        b"<html><title>SkyServer maintenance</title></html>",
        b"objID,ra,dec,u,err_u,g,err_g,r,err_r,i,err_i,z,err_z\n"
        b"1,180,0.5,15,0.01,14,0.01,13.5,0.01,13.3,0.01,13.2,0.01\n",
    ])
    requests = []

    def transport(method, url, **kwargs):
        requests.append((method, url, kwargs))
        return _response(method, url, next(answers))

    monkeypatch.setattr(client._session, "request", transport)
    return client, directory, requests


def test_sdss_direct_eviction_refetches_html_and_caches_valid_csv(sdss_error_cache):
    from algorithms.query.sdss import _query_sql

    client, directory, requests = sdss_error_cache
    sql = "SELECT TOP 1 objID,ra,dec,g FROM Star"
    rows = _query_sql(client, sql, data_release=17, cache=True)
    assert list(rows["objID"]) == [1]
    assert list(rows["g"]) == [14.0]
    assert len(requests) == 2
    assert len(list(directory.glob("*.pickle"))) == 1
    cached = _query_sql(client, sql, data_release=17, cache=True)
    assert list(cached["objID"]) == [1]
    assert len(requests) == 2


def test_sdss_direct_eviction_permission_fault_still_recovers_html(
    sdss_error_cache, monkeypatch,
):
    """An undeletable service-error entry triggers one uncached retry."""
    from algorithms.query.sdss import _query_sql

    client, directory, requests = sdss_error_cache
    sql = "SELECT TOP 1 objID,ra,dec,g FROM Star"
    original_unlink = Path.unlink
    failed_evictions = []

    def denied_unlink(path, *args, **kwargs):
        if path.parent == directory and path.suffix == ".pickle":
            failed_evictions.append(path)
            raise PermissionError("injected SDSS direct cache eviction failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", denied_unlink)
    rows = _query_sql(client, sql, data_release=17, cache=True)
    assert len(failed_evictions) == 1
    assert failed_evictions[0].exists()
    assert list(rows["objID"]) == [1]
    assert len(requests) == 2


def test_installed_sdk_cache_directory_fault_allows_automatic_fallback(
    sdk_cache, monkeypatch,
):
    """A failed cache directory creation does not prevent the provider call."""
    client, directory, requests = sdk_cache
    directory.rmdir()  # Model an unavailable cache directory that needs creation.
    original_mkdir = Path.mkdir

    def denied_mkdir(path, *args, **kwargs):
        if path == directory:
            raise PermissionError("injected cache directory permission failure")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", denied_mkdir)
    assert not _sdk_region(client)
    assert len(requests) == 1
    assert not _sdk_region(client, enabled=False)
    assert len(requests) == 2


@pytest.mark.parametrize("fault", ["listing", "stat", "unlink"])
def test_pruning_filesystem_fault_does_not_break_installed_sdk_request(
    sdk_cache, monkeypatch, fault,
):
    client, directory, requests = sdk_cache
    expired = directory / "expired.pickle"
    expired.write_bytes(b"expired")
    os.utime(expired, (0, 0))
    original_glob = cache.glob

    def listing(pattern):
        if fault == "listing":
            raise PermissionError("injected pruning listing failure")
        return original_glob(pattern)

    def stat(path):
        if Path(path) == expired and fault == "stat":
            raise PermissionError("injected pruning stat failure")
        return os.stat(path)

    def unlink(path):
        if Path(path) == expired and fault == "unlink":
            raise PermissionError("injected pruning unlink failure")
        return os.unlink(path)

    monkeypatch.setattr(cache, "glob", listing)
    monkeypatch.setattr(cache, "os", SimpleNamespace(path=os.path, stat=stat, unlink=unlink))
    assert not _sdk_region(client)
    assert len(requests) == 1
    assert expired.exists()
    assert len(list(directory.glob("*.pickle"))) == 2


def test_every_sdk_write_scans_vizier_entries_including_non_vizier_writes(sdk_cache, monkeypatch):
    """CAT-26 policy/work characterization, not an asserted performance defect."""
    from algorithms.query.sdss import MARSSDSS

    client, directory, requests = sdk_cache
    for index in range(4):
        (directory / f"existing-{index}.pickle").write_bytes(b"live")
    scans, stat_calls = [], []
    original_glob = cache.glob

    def listing(pattern):
        entries = original_glob(pattern)
        scans.append(len(entries))
        return entries

    def stat(path):
        stat_calls.append(path)
        return os.stat(path)

    monkeypatch.setattr(cache, "glob", listing)
    monkeypatch.setattr(cache, "os", SimpleNamespace(path=os.path, stat=stat, unlink=os.unlink))
    url = "https://example.invalid/offline-cache-test"
    for index in range(2):
        client._request("GET", url, params={"case": index}, cache=True)
    sdss = MARSSDSS()
    sdss.cache_location = directory.parent / "SDSS"
    monkeypatch.setattr(sdss._session, "request", lambda method, url, **kwargs: _response(method, url))
    sdss._request("GET", url, params={"case": 2}, cache=True)
    assert scans == [4, 5, 6]
    assert len(stat_calls) == 15
    assert all(Path(path).parent == directory for path in stat_calls)
    assert len(list((directory.parent / "SDSS").glob("*.pickle"))) == 1
    client._request("GET", url, params={"case": 0}, cache=True)
    assert scans == [4, 5, 6]  # A cache hit does no pruning work.
    assert len(requests) == 2


@pytest.mark.parametrize("days,error", [(float("nan"), ValueError), (float("inf"), OverflowError)])
def test_unsafe_nonfinite_retention_config_raises_outside_write_suppression(
    sdk_cache, monkeypatch, days, error,
):
    """A separate configuration limitation, not an ordinary cache I/O fault."""
    client, _, requests = sdk_cache
    monkeypatch.setattr(config.settings, "VIZIER_CACHE_AGE_DAYS", days)
    with pytest.raises(error):
        _sdk_region(client)
    assert len(requests) == 1
    assert not _sdk_region(client, enabled=False)
    assert len(requests) == 2


def test_cache_suppression_installation_is_idempotent():
    installed = sdk_query.AstroQuery, sdk_query.to_cache
    cache.install_cache_error_suppression(max_age=timedelta(days=1))
    assert (sdk_query.AstroQuery, sdk_query.to_cache) == installed
