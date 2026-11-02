"""The release's ``.mcpb`` packer (``.github/scripts/pack_extension.py``).

It replaces ``mcpb pack`` so no npm code produces what users install, so it
must pack what ``mcpb pack`` would: the extension's files minus
``.mcpbignore`` and its listed patterns, deterministically.
"""

from __future__ import annotations

import importlib.util
import shutil
import zipfile

import pytest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_EXT = _ROOT / "installers" / "claude-desktop"
_SCRIPT = _ROOT / ".github" / "scripts" / "pack_extension.py"
_spec = importlib.util.spec_from_file_location("pack_extension", _SCRIPT)
pack_extension = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pack_extension)

#: What ``mcpb pack`` 2.1.2 packed from this folder (checked 2026-10-23).
_PACKED = ["icon.png", "manifest.json", "pyproject.toml", "src/server.py", "uv.lock"]


def _copy(tmp_path: Path) -> Path:
    source = tmp_path / "ext"
    shutil.copytree(_EXT, source)
    return source


def test_packs_what_mcpb_pack_packs_and_skips_ignored_files(tmp_path):
    source = _copy(tmp_path)
    (source / "src" / "__pycache__").mkdir(exist_ok=True)
    (source / "src" / "__pycache__" / "server.cpython-313.pyc").write_bytes(b"x")
    (source / ".venv" / "lib").mkdir(parents=True)
    (source / ".venv" / "lib" / "site.py").write_text("x")

    output = tmp_path / "mars.mcpb"
    pack_extension.pack(source, output)

    with zipfile.ZipFile(output) as archive:
        assert sorted(archive.namelist()) == _PACKED
        for name in _PACKED:
            assert archive.read(name) == (_EXT / name).read_bytes()


def test_what_mcpb_pack_always_leaves_out_is_never_packed(tmp_path):
    """A local pack must not ship a key: mcpb's own excludes apply whatever
    .mcpbignore says (EXCLUDE_PATTERNS, @anthropic-ai/mcpb 2.1.2)."""

    source = _copy(tmp_path)
    (source / ".env").write_text("ADS_DEV_KEY=not-a-real-key")
    (source / ".env.production").write_text("x")
    (source / ".DS_Store").write_bytes(b"x")
    (source / "src" / ".DS_Store").write_bytes(b"x")
    (source / "mars-old.mcpb").write_bytes(b"x")
    (source / "debug.log").write_text("x")
    (source / ".git").mkdir()
    (source / ".git" / "config").write_text("x")
    (source / "node_modules" / ".cache").mkdir(parents=True)
    (source / "node_modules" / ".cache" / "x").write_text("x")

    names = sorted(p.as_posix() for p in pack_extension.packed_files(source))

    assert names == _PACKED


def test_the_archive_is_deterministic(tmp_path):
    first, second = tmp_path / "a.mcpb", tmp_path / "b.mcpb"
    pack_extension.pack(_copy(tmp_path), first)
    pack_extension.pack(_EXT, second)
    assert first.read_bytes() == second.read_bytes()


def test_comments_and_anchored_directories_are_honoured(tmp_path):
    source = _copy(tmp_path)
    ignore = source / ".mcpbignore"
    ignore.write_text(
        ignore.read_text() + "# local only, not a pattern\nsrc/tests/\n", encoding="utf-8"
    )
    (source / "src" / "tests").mkdir()
    (source / "src" / "tests" / "test_x.py").write_text("x")
    (source / "local").write_text("kept: the comment is not a pattern")
    (source / "tests").mkdir()
    (source / "tests" / "kept.py").write_text("x")

    names = [p.as_posix() for p in pack_extension.packed_files(source)]

    assert "src/tests/test_x.py" not in names
    assert "local" in names
    assert "tests/kept.py" in names


def test_a_negation_is_refused_rather_than_ignored(tmp_path):
    source = _copy(tmp_path)
    ignore = source / ".mcpbignore"
    ignore.write_text(ignore.read_text() + "!README.md\n", encoding="utf-8")

    with pytest.raises(ValueError, match="negation"):
        pack_extension.packed_files(source)
