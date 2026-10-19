"""Real SDK download helpers against offline bounded streaming responses."""

from pathlib import Path
from types import SimpleNamespace

from astropy.table import Table
from astroquery.mast import ObservationsClass
from astroquery.casda import CasdaClass
import pytest

from tools.downloads import (DownloadLimit, bounded_transfer, check_mast_paths,
                             check_products, MAX_PRODUCTS, MAX_DOWNLOAD_BYTES)


class Response:
    def __init__(self, chunks, headers=None):
        self.chunks = chunks
        self.headers = {} if headers is None else headers
        self.closed = False
        self.visited = 0

    @property
    def content(self):
        raise AssertionError("Download must stream, never access response.content")

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        assert size == 64 * 1024
        for chunk in self.chunks:
            self.visited += 1
            yield chunk

    def close(self):
        self.closed = True


def session(response):
    def request(method, url, **kwargs):
        assert kwargs["stream"] is True
        assert 0 < kwargs["timeout"] <= 30
        return response
    return SimpleNamespace(request=request)


@pytest.mark.parametrize("headers", [{}, {"content-length": "1"}])
def test_actual_stream_not_headers_bounds_bytes_and_removes_partial(tmp_path, headers):
    provider = ObservationsClass()
    response = Response([b"a" * 6, b"b" * 6, b"never read"], headers)
    provider._session = session(response)
    with bounded_transfer(provider, tmp_path, max_bytes=10):
        with pytest.raises(DownloadLimit, match="decoded stream"):
            provider._download_file("https://example.test/data", tmp_path / "frame.fits", verbose=False)
    assert response.closed and response.visited == 2
    assert list(tmp_path.iterdir()) == []


def test_declared_size_is_rejected_before_reading_or_creating_a_file(tmp_path):
    provider = ObservationsClass()
    response = Response([b"never read"], {"content-length": "11"})
    provider._session = session(response)
    with bounded_transfer(provider, tmp_path, max_bytes=10):
        with pytest.raises(DownloadLimit, match="remaining"):
            provider._download_file("https://example.test/data", tmp_path / "frame.fits")
    assert response.closed and response.visited == 0
    assert list(tmp_path.iterdir()) == []


def test_shared_budget_counts_every_file_and_preserves_completed_files(tmp_path):
    provider = ObservationsClass()
    response = Response([b"a" * 6])
    provider._session = session(response)
    original = provider._download_file.__func__
    cloud = provider._cloud_connection = object()
    with bounded_transfer(provider, tmp_path, max_bytes=10):
        assert provider._cloud_connection is None
        provider._download_file("https://example.test/a", tmp_path / "a.fits")
        with pytest.raises(DownloadLimit):
            provider._download_file("https://example.test/b", tmp_path / "b.fits")
    assert provider._download_file.__func__ is original
    assert provider._cloud_connection is cloud
    assert (tmp_path / "a.fits").read_bytes() == b"a" * 6
    assert not (tmp_path / "b.fits").exists()


def test_sdk_mast_manifest_uses_capped_http_even_with_cloud_enabled(tmp_path):
    provider = ObservationsClass()
    response = Response([b"FITS placeholder"])
    provider._session = session(response)
    products = Table({"obs_collection": ["TESS"], "obs_id": ["obs"],
                      "productFilename": ["frame.fits"], "dataURI": ["mast:TESS/product/frame.fits"]})
    check_mast_paths(products)
    with bounded_transfer(provider, tmp_path):
        manifest = provider._download_files(products, str(tmp_path), verbose=False)
    assert manifest["Status"][0] == "COMPLETE"
    assert Path(manifest["Local Path"][0]).read_bytes() == b"FITS placeholder"
    assert response.closed


@pytest.mark.parametrize("url", ["https://example.test/%2e%2e%2fescape.fits",
                                 "https://example.test/%2Ftmp%2Fescape.fits"])
def test_casda_decoded_filename_cannot_escape_root(tmp_path, url):
    provider = CasdaClass()
    provider._session = SimpleNamespace(request=lambda *a, **k: pytest.fail("path validation must precede HTTP"))
    with bounded_transfer(provider, tmp_path):
        with pytest.raises(DownloadLimit, match="escapes"):
            provider.download_files([url], savedir=str(tmp_path))


def test_existing_operator_file_is_not_overwritten(tmp_path):
    provider = CasdaClass()
    existing = tmp_path / "frame.fits"
    existing.write_bytes(b"operator")
    with bounded_transfer(provider, tmp_path):
        with pytest.raises(DownloadLimit, match="overwrite"):
            provider.download_files(["https://example.test/frame.fits"], savedir=str(tmp_path))
    assert existing.read_bytes() == b"operator"


def test_product_and_declared_byte_caps_do_not_silently_slice_tables():
    with pytest.raises(DownloadLimit, match="products"):
        check_products(Table({"id": list(range(MAX_PRODUCTS + 1))}))
    with pytest.raises(DownloadLimit, match="sizes"):
        check_products(Table({"size": [MAX_DOWNLOAD_BYTES + 1]}), size_column="size")
    check_products(Table({"size": [12]}), size_column="size")


@pytest.mark.parametrize("value", ["..", "/tmp", "a/b", "a\\b", "C:drive"])
def test_mast_metadata_is_checked_before_sdk_mkdir(value):
    products = Table({"obs_collection": [value], "obs_id": ["obs"], "productFilename": ["frame.fits"]})
    with pytest.raises(DownloadLimit):
        check_mast_paths(products)


def test_mast_over_budget_still_reports_full_metadata(tmp_path, monkeypatch):
    from tools import artifacts, mast
    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path / "artifacts")
    obs = Table({"obsid": [1]})
    products = Table({"id": list(range(MAX_PRODUCTS + 1))})
    monkeypatch.setattr(mast.Observations, "query_object", lambda *a, **k: obs)
    monkeypatch.setattr(mast.Observations, "get_unique_product_list", lambda *a, **k: products)
    monkeypatch.setattr(mast.Observations, "download_products", lambda *a, **k: pytest.fail("over-budget download reached SDK"))
    result = mast.search_mast("offline", download=True)
    assert result.status == "partial" and result.count == 1
    assert result.errors[0].code == "resource_limit"
    assert len(result.artifacts) == 2


def test_casda_over_budget_is_refused_before_login_or_staging(tmp_path, monkeypatch):
    from tools import artifacts, casda
    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path / "artifacts")
    table = Table({"id": list(range(MAX_PRODUCTS + 1))})
    fake = SimpleNamespace(query_region=lambda *a, **k: table,
                           filter_out_unreleased=lambda t: t,
                           login=lambda *a, **k: pytest.fail("over-budget staging reached login"))
    monkeypatch.setattr(casda, "Casda", lambda: fake)
    result = casda.search_casda(ra_deg=1, dec_deg=2, download=True)
    assert result.status == "partial" and result.count == MAX_PRODUCTS + 1
    assert result.errors[0].code == "resource_limit"
