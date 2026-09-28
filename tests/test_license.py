"""MARS is GPL-3.0-only, and says so wherever a licence is read from.

The Astromancer ports make the whole work GPL-3.0 (README.md, License). A
distribution that declared no licence, or a different one from the file it
ships, would misstate the terms on PyPI.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_the_project_declares_gpl_3_only_with_its_licence_file():
    project = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["license"] == "GPL-3.0-only"
    assert project["license-files"] == ["LICENSE"]
    # PEP 639: a licence expression replaces the licence classifiers, and
    # setuptools refuses a project that declares both.
    assert not any(c.startswith("License ::") for c in project.get("classifiers", []))


def test_the_licence_file_is_the_gpl_version_3():
    text = (_REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.lstrip().startswith("GNU GENERAL PUBLIC LICENSE")
    assert "Version 3, 29 June 2007" in text
    assert "END OF TERMS AND CONDITIONS" in text
