"""Finite streamed archive transfers, shared by MAST and CASDA.

Wrap only the selected provider instance, not requests or astroquery globally.
The SDK still owns authentication, product selection and manifests. Its cloud,
resume and unbounded ``response.content`` shortcuts are deliberately disabled.
"""

from contextlib import contextmanager
import math
import os
from pathlib import Path
import time
import uuid

MAX_PRODUCTS = 32
MAX_DOWNLOAD_BYTES = 512 * 1024**2
MAX_TRANSFER_SECONDS = 600


class DownloadLimit(ValueError):
    """A visible refusal, never silently truncate products or bytes."""


def check_products(products, *, size_column=None):
    if len(products) > MAX_PRODUCTS:
        raise DownloadLimit(f"Download has {len(products)} products; limit is {MAX_PRODUCTS}. Narrow the query/filters; no products downloaded.")
    if size_column and size_column in products.colnames:
        total = 0
        for size in products[size_column]:
            # Missing metadata is not permission for an unbounded transfer:
            # the actual decoded stream remains capped regardless of headers.
            try:
                value = float(size)
            except (TypeError, ValueError):
                continue
            if math.isfinite(value) and value >= 0:
                total += value
        if total > MAX_DOWNLOAD_BYTES:
            raise DownloadLimit("Declared product sizes exceed the 512 MiB download budget; narrow the filters.")


def check_mast_paths(products):
    # astroquery creates these directories before invoking its HTTP helper.
    # Refuse provider metadata capable of creating paths outside the root.
    for column in ("obs_collection", "obs_id", "productFilename"):
        for value in products[column]:
            value = str(value)
            if not value or value in {".", ".."} or any(c in value for c in "/\\:\x00"):
                raise DownloadLimit(f"Unsafe MAST download path component in {column}.")


@contextmanager
def bounded_transfer(provider, root: Path, *, max_files=MAX_PRODUCTS,
                     max_bytes=MAX_DOWNLOAD_BYTES, timeout_s=MAX_TRANSFER_SECONDS):
    """Bound actual decoded bytes across a batch, before writing each chunk.

    Existing files are never overwritten or treated as an unverified cache.
    Failed files remain unadvertised and their owned staging file is removed.
    Root/path ownership assumes the documented trusted single local user.
    """
    root = Path(root).resolve()
    deadline = time.monotonic() + timeout_s
    total = files = 0
    saved = provider.__dict__.get("_download_file")
    cloud = getattr(provider, "_cloud_connection", None)
    has_cloud = hasattr(provider, "_cloud_connection")

    def download(url, local_filepath, timeout=None, auth=None, method="GET", **kwargs):
        nonlocal total, files
        files += 1
        if files > max_files:
            raise DownloadLimit("Archive download file-count budget exceeded.")
        path = Path(local_filepath)
        if (os.name != "nt" and "\\" in str(path)) or "\x00" in str(path):
            raise DownloadLimit("Unsafe archive download filename.")
        path = path.resolve()
        if not path.is_relative_to(root) or path == root:
            raise DownloadLimit("Archive download path escapes its configured root.")
        if path.exists():
            raise DownloadLimit("Refusing to overwrite an existing archive download; choose a fresh download directory.")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DownloadLimit("Archive transfer deadline exceeded.")
        response = None
        stage = path.with_name(f".{path.name}.{uuid.uuid4().hex}.part")
        # Consume SDK-specific options here, not as HTTP request parameters.
        for option in ("continuation", "cache", "head_safe", "verbose"):
            kwargs.pop(option, None)
        try:
            response = provider._session.request(method, url, timeout=min(30, remaining),
                                                 stream=True, auth=auth, **kwargs)
            response.raise_for_status()
            length = response.headers.get("content-length")
            if length is not None and int(length) > max_bytes - total:
                raise DownloadLimit("Archive response exceeds the remaining download byte budget.")
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with stage.open("xb") as handle:
                os.chmod(stage, 0o600)
                for chunk in response.iter_content(64 * 1024):
                    if time.monotonic() >= deadline:
                        raise DownloadLimit("Archive transfer deadline exceeded.")
                    if len(chunk) > max_bytes - total:
                        raise DownloadLimit("Archive decoded stream exceeds the download byte budget.")
                    total += len(chunk)
                    handle.write(chunk)
            # Exclusive creation preserves an operator file even if it appeared
            # since validation. No filesystem-adversary/sandbox claim is made.
            os.link(stage, path)
            return str(path)
        finally:
            if response is not None:
                response.close()
            stage.unlink(missing_ok=True)

    provider._download_file = download
    if has_cloud:
        provider._cloud_connection = None
    try:
        yield
    finally:
        if saved is None:
            del provider._download_file
        else:
            provider._download_file = saved
        if has_cloud:
            provider._cloud_connection = cloud
