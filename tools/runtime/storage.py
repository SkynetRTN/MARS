"""Private managed call trees; never adopt or clean an operator's data tree."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import time
import uuid

OWNER_FILE = ".mars-runtime.json"
CALL_FILE = ".mars-call.json"
OWNER = {"owner": "MARS", "version": 1}


def private_write(path: Path, value: dict) -> None:
    stage = path.with_suffix(".part")
    with stage.open("w", encoding="utf-8") as handle:
        os.chmod(stage, 0o600)
        json.dump(value, handle)
    stage.replace(path)


def managed_root(root: Path, *, create: bool = True) -> Path:
    """Create one dedicated owned namespace; refuse symlinks or unowned trees."""
    root = root.expanduser().resolve() / ".mars-runtime"
    if not create and not root.exists() and not root.is_symlink():
        return root
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=False)
    except FileExistsError:
        if root.is_symlink() or not root.is_dir():
            raise ValueError("MARS runtime namespace must be a real directory.")
        marker = root / OWNER_FILE
        if marker.is_symlink() or marker.stat().st_size > 4096:
            raise ValueError("Runtime namespace has no valid ownership marker.")
        if json.loads(marker.read_text()) != OWNER:
            raise ValueError("Refusing to adopt an unowned runtime namespace.")
    else:
        private_write(root / OWNER_FILE, OWNER)
    return root


def tree_size(root: Path, *, max_files: int) -> int:
    """Bounded traversal of an owned tree; reject links and special files."""
    total = count = 0
    if not root.exists():
        return 0
    if root.is_symlink():
        raise ValueError("Runtime tree contains a symlink.")
    pending = [root]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                count += 1
                if count > max_files:
                    raise ValueError("Runtime tree exceeds its file/entry budget.")
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    pending.append(Path(entry.path))
                elif stat.S_ISREG(info.st_mode):
                    total += info.st_size
                else:
                    raise ValueError("Runtime tree contains a link or special file.")
    return total


def create_call(root: Path, *, identifier: str | None = None) -> Path:
    identifier = uuid.uuid4().hex if identifier is None else identifier
    if len(identifier) != 32 or any(char not in "0123456789abcdef" for char in identifier):
        raise ValueError("Invalid runtime call identifier.")
    path = root / identifier
    path.mkdir(mode=0o700, exist_ok=False)
    private_write(path / CALL_FILE, {"owner": "MARS", "id": identifier,
                                   "created": time.time(), "state": "running", "pid": os.getpid()})
    return path


def finish_call(path: Path, state: str) -> None:
    marker = path / CALL_FILE
    record = json.loads(marker.read_text())
    private_write(marker, {**record, "state": state})


def cleanup(root: Path, *, days: float = 30, apply: bool = False) -> list[Path]:
    """Dry-run by default; explicit apply removes only expired marked calls.

    Never touches bundles, operator inputs, or old/unmarked artifacts/downloads.
    Running calls and trees with symlinks/special files are conservatively kept.
    """
    if not 1 <= days <= 3650:
        raise ValueError("Retention must be between 1 and 3650 days.")
    root = managed_root(root, create=False)
    if not root.exists():
        return []
    cutoff = time.time() - days * 86400
    selected = []
    with os.scandir(root) as entries:
        for index, entry in enumerate(entries):
            if index >= 10_000:
                raise ValueError("Runtime retention inventory exceeds its entry budget.")
            name = entry.name
            if len(name) != 32 or any(char not in "0123456789abcdef" for char in name):
                continue
            path = Path(entry.path)
            marker = path / CALL_FILE
            if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                continue
            try:
                if marker.is_symlink() or marker.stat().st_size > 4096:
                    continue
                record = json.loads(marker.read_text())
                if (record.get("owner") != "MARS" or record.get("id") != name
                        or record.get("state") not in {"complete", "failed", "cancelled"}
                        or record.get("created", float("inf")) >= cutoff):
                    continue
                tree_size(path, max_files=10_000)
            except (OSError, ValueError, TypeError):
                continue
            selected.append(path)
    # Validate the complete selection before any deletion; no recursive root
    # deletion and no resolution of paths copied from a call's marker.
    if apply:
        for path in selected:
            shutil.rmtree(path)
    return selected


def cleanup_main(argv: list[str]) -> int:
    """No SDK, no root creation, explicit apply. Use the server's root policy."""
    import argparse
    from tools.mcp.roots import user_artifact_dir

    parser = argparse.ArgumentParser(prog="mars-mcp cleanup")
    parser.add_argument("--days", type=float, default=30,
                        help="Keep finished calls for this many days (1–3650; default 30).")
    parser.add_argument("--apply", action="store_true", help="Delete listed expired owned calls; default is dry-run.")
    options = parser.parse_args(argv)
    artifact_root = Path(os.environ.get("MARS_ARTIFACT_DIR", "").strip() or user_artifact_dir())
    os.environ["MARS_ARTIFACT_DIR"] = str(artifact_root.expanduser().resolve())
    from tools import config
    try:
        selected = []
        # Validate inventories at both roots before any requested deletion.
        for root in dict.fromkeys((artifact_root, config.FITS_DOWNLOAD_DIR)):
            selected.extend(cleanup(root, days=options.days))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if options.apply:
        for path in selected:
            shutil.rmtree(path)
    print("Applied cleanup:" if options.apply else "Dry-run (use --apply to delete):")
    for path in selected:
        print(path)
    print(f"{len(selected)} expired owned call tree(s); running/unmarked/operator data retained.")
    return 0
