"""MARS is GPL-3.0-only, copyright the Skynet Robotic Telescope Network.

The terms must agree wherever they are read from -- the licence file, the
package metadata PyPI shows, and the README -- or the distribution misstates
them.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_the_project_declares_gpl_3_only_with_its_licence_file():
    project = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["license"] == "GPL-3.0-only"
    assert project["license-files"] == ["LICENSE"]
    assert project["authors"] == [{"name": "Skynet Robotic Telescope Network"}]
    # PEP 639: a licence expression replaces the licence classifiers, and
    # setuptools refuses a project that declares both.
    assert not any(c.startswith("License ::") for c in project.get("classifiers", []))


def test_the_licence_file_is_the_gpl_version_3():
    text = (_REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.lstrip().startswith("GNU GENERAL PUBLIC LICENSE")
    assert "Version 3, 29 June 2007" in text
    assert "END OF TERMS AND CONDITIONS" in text


def test_the_readme_states_the_copyright_holder_and_licence():
    readme = (_REPO_ROOT / "README.md").read_text(encoding="utf-8")
    section = readme[readme.index("## License"):]
    assert "Copyright (C) 2026 Skynet Robotic Telescope Network." in section
    assert "`GPL-3.0-only`" in section
