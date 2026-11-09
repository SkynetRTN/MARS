"""Cache faults must preserve real SDK requests, parsing and later recovery."""

import builtins
from io import BytesIO
from pathlib import Path

import astroquery.query as sdk_query
from astroquery.exceptions import RemoteServiceError
from astropy.coordinates import SkyCoord
from astropy.units import arcmin, deg
import pytest
from requests import ConnectionError, HTTPError, Request, Response

from algorithms.query import cache
from algorithms.query.sdss import MARSSDSS, _query_sql
from algorithms.query.vizier import ProviderResponseError, VizierClass


_SQL = "SELECT TOP 1 objID,ra,dec,g FROM Star"
_HTML = b"<html><title>SkyServer maintenance</title></html>"
_CSV = b"objID,ra,dec,g\n1,180,0.5,14\n"
_VOTABLE = (
    b'<?xml version="1.0"?><VOTABLE version="1.3" '
    b'xmlns="http://www.ivoa.net/xml/VOTable/v1.3"><RESOURCE/></VOTABLE>'
)


def _client(provider, directory, monkeypatch, answers=None):
    """Replace only HTTP; preserve SDK cache keys, files and table parsers."""
    client = VizierClass(catalog="II/336/apass9") if provider == "vizier" else MARSSDSS()
    client.cache_location = directory
    requests = []
    replies = iter(answers) if answers is not None else None

    def transport(method, url, **kwargs):
        requests.append((method, url, kwargs))
        payload = next(replies) if replies is not None else (_VOTABLE if provider == "vizier" else _CSV)
        if isinstance(payload, BaseException):
            raise payload
        response = Response()
        response.status_code = 200
        response.url = url
        response.request = Request(method, url).prepare()
        response._content = payload
        response.raw = BytesIO(payload)
        return response

    monkeypatch.setattr(client._session, "request", transport)
    monkeypatch.setattr(cache, "vizier_cache_dir", lambda: str(directory))
    return client, requests


def _fetch(provider, client, *, enabled=True):
    if provider == "vizier":
        rows = client.query_region(SkyCoord(15, 20, unit=deg), radius=1 * arcmin,
                                   catalog="II/336/apass9", cache=enabled)
        assert not rows
    else:
        rows = _query_sql(client, _SQL, data_release=17, cache=enabled)
        assert list(rows["objID"]) == [1]
        assert list(rows["g"]) == [14.0]


def _deny_directory(monkeypatch, directory, error):
    original = Path.mkdir

    def mkdir(path, *args, **kwargs):
        if path == directory:
            raise error("cache directory unavailable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mkdir)


@pytest.mark.parametrize("provider", ["vizier", "sdss"])
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("error", [PermissionError, OSError])
def test_cache_directory_failure_refetches_and_recovers(
    tmp_path, monkeypatch, provider, explicit, error,
):
    directory = tmp_path / "explicit"
    client, requests = _client(provider, directory, monkeypatch)
    if not explicit:
        client._cache_location = None
        monkeypatch.setattr(sdk_query.paths, "get_cache_dir", lambda **kwargs: str(tmp_path))
        directory = tmp_path / "astroquery" / client.name
        monkeypatch.setattr(cache, "vizier_cache_dir", lambda: str(directory))
    with monkeypatch.context() as scope:
        _deny_directory(scope, directory, error)
        _fetch(provider, client)
        _fetch(provider, client)
        assert len(requests) == 2
        assert not directory.exists()
    _fetch(provider, client)
    _fetch(provider, client)
    assert len(requests) == 3  # A later write repairs the cache; next call hits it.
    assert client.cache_location == directory
    assert len(list(directory.glob("*.pickle"))) == 1


def test_directory_suppression_preserves_global_and_explicit_cache_controls(tmp_path, monkeypatch):
    directory = tmp_path / "cache"
    client, requests = _client("sdss", directory, monkeypatch)
    url = "https://example.invalid/cache-control"
    with sdk_query.cache_conf.set_temp("cache_active", False):
        client._request("GET", url)
        client._request("GET", url)
        assert not directory.exists()
        client._request("GET", url, cache=True)
        client._request("GET", url, cache=True)
        assert len(requests) == 3
    with sdk_query.cache_conf.set_temp("cache_active", True):
        client._request("GET", url)
        client._request("GET", url, cache=False)
        assert len(requests) == 4


@pytest.mark.parametrize("provider", ["vizier", "sdss"])
def test_default_cache_discovery_permission_error_falls_back_and_recovers(tmp_path, monkeypatch, provider):
    client, requests = _client(provider, tmp_path / "unused", monkeypatch)
    client._cache_location = None
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv("ASTROPY_CACHE_DIR", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    legacy = tmp_path / ".astropy" / "cache"
    original_stat = Path.stat
    failures = []

    def denied_stat(path, *args, **kwargs):
        if path == legacy:
            failures.append(path)
            raise PermissionError("default cache discovery denied")
        return original_stat(path, *args, **kwargs)

    with monkeypatch.context() as scope:
        scope.setattr(Path, "stat", denied_stat)
        _fetch(provider, client)
        _fetch(provider, client)
        assert len(requests) == 2
        assert failures  # Real Astropy discovery reached the denied legacy path.
    _fetch(provider, client)
    _fetch(provider, client)
    assert len(requests) == 3
    assert len(list(client.cache_location.glob("*.pickle"))) == 1


@pytest.mark.parametrize("failure", [ConnectionError("offline"), HTTPError("HTTP 503"),
                                     OSError("provider I/O failure"), KeyboardInterrupt()])
def test_directory_failure_never_swallows_or_retries_provider_errors(tmp_path, monkeypatch, failure):
    directory = tmp_path / "cache"
    client, requests = _client("sdss", directory, monkeypatch, [failure])
    _deny_directory(monkeypatch, directory, PermissionError)
    with pytest.raises(type(failure)) as caught:
        _query_sql(client, _SQL, data_release=17, cache=True)
    assert caught.value is failure
    assert len(requests) == 1


def test_directory_failure_does_not_replay_a_post(tmp_path, monkeypatch):
    directory = tmp_path / "cache"
    client, requests = _client("sdss", directory, monkeypatch)
    _deny_directory(monkeypatch, directory, OSError)
    response = client._request("POST", "https://example.invalid/action",
                               data={"action": "once"}, cache=True)
    assert response.content == _CSV
    assert len(requests) == 1
    assert requests[0][0] == "POST"
    assert requests[0][2]["data"] == {"action": "once"}


@pytest.mark.parametrize("explicit_savedir", [False, True])
def test_directory_suppression_preserves_requested_save_errors(tmp_path, monkeypatch, explicit_savedir):
    directory = tmp_path / "cache"
    client, requests = _client("sdss", directory, monkeypatch)
    _deny_directory(monkeypatch, directory, PermissionError)
    destination = (tmp_path / "downloads") if explicit_savedir else directory

    def denied_save(path, mode, *args, **kwargs):
        if Path(path) == destination / "response.csv":
            raise PermissionError("save destination is read-only")
        return builtins.open(path, mode, *args, **kwargs)

    monkeypatch.setattr(sdk_query, "open", denied_save, raising=False)
    with pytest.raises(PermissionError, match="save destination"):
        client._request("GET", "https://example.invalid/response.csv", save=True,
                        savedir=str(destination) if explicit_savedir else "", cache=True)
    assert len(requests) == 1


def _deny_eviction(monkeypatch, directory, error=PermissionError):
    original = Path.unlink

    def unlink(path, *args, **kwargs):
        if path.parent == directory and path.suffix == ".pickle":
            raise error("cache entry cannot be removed")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)


@pytest.mark.parametrize("error", [PermissionError, OSError])
def test_sdss_undeletable_html_is_bypassed_on_each_call(tmp_path, monkeypatch, error):
    directory = tmp_path / "SDSS"
    client, requests = _client("sdss", directory, monkeypatch, [_HTML, _CSV, _CSV])
    _deny_eviction(monkeypatch, directory, error)
    _fetch("sdss", client)
    _fetch("sdss", client)
    assert len(requests) == 3  # Initial HTML, then one uncached CSV per call.
    entry, = directory.glob("*.pickle")
    assert _HTML in entry.read_bytes()  # The stale entry really remains.


def test_sdss_vanished_error_entry_is_repaired_with_cache_enabled(tmp_path, monkeypatch):
    directory = tmp_path / "SDSS"
    client, requests = _client("sdss", directory, monkeypatch, [_HTML, _CSV])
    original = Path.unlink
    removals = []

    def raced_unlink(path, *args, **kwargs):
        if path.parent == directory and path.suffix == ".pickle":
            original(path, missing_ok=True)  # Another worker removed it first.
            removals.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", raced_unlink)
    _fetch("sdss", client)
    _fetch("sdss", client)
    assert len(removals) == 1
    assert len(requests) == 2  # Refetch repaired the entry instead of bypassing it.
    assert len(list(directory.glob("*.pickle"))) == 1


@pytest.mark.parametrize("undeletable", [False, True])
def test_sdss_persistent_html_raises_service_error_after_one_retry(tmp_path, monkeypatch, undeletable):
    directory = tmp_path / "SDSS"
    client, requests = _client("sdss", directory, monkeypatch, [_HTML] * 4)
    if undeletable:
        _deny_eviction(monkeypatch, directory)
    for attempt in range(2):
        with pytest.raises(RemoteServiceError, match="maintenance"):
            _query_sql(client, _SQL, data_release=17, cache=True)
        assert len(requests) == (2 + attempt if undeletable else 2 * (attempt + 1))


@pytest.mark.parametrize("reply,error", [
    (b"error_message: request refused", RemoteServiceError),
    (b"objID,ra,dec\nnot-an-objid,180,0.5\n", ProviderResponseError),
])
def test_sdss_undeletable_entry_preserves_parser_error_distinctions(tmp_path, monkeypatch, reply, error):
    directory = tmp_path / "SDSS"
    client, requests = _client("sdss", directory, monkeypatch, [_HTML, reply, reply])
    _deny_eviction(monkeypatch, directory)
    for _ in range(2):
        with pytest.raises(error):
            _query_sql(client, _SQL, data_release=17, cache=True)
    assert len(requests) == 3


def test_sdss_uncached_html_has_no_automatic_retry(tmp_path, monkeypatch):
    directory = tmp_path / "SDSS"
    client, requests = _client("sdss", directory, monkeypatch, [_HTML])
    with pytest.raises(RemoteServiceError, match="maintenance"):
        _query_sql(client, _SQL, data_release=17, cache=False)
    assert len(requests) == 1
    assert not directory.exists()


def test_sdss_failed_eviction_does_not_retry_a_provider_network_error(tmp_path, monkeypatch):
    directory = tmp_path / "SDSS"
    failure = ConnectionError("offline during HTML recovery")
    client, requests = _client("sdss", directory, monkeypatch, [_HTML, failure])
    _deny_eviction(monkeypatch, directory)
    with pytest.raises(ConnectionError) as caught:
        _query_sql(client, _SQL, data_release=17, cache=True)
    assert caught.value is failure
    assert len(requests) == 2
