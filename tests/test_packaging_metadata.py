"""What PyPI shows for skynet-mars, kept consistent with what the package does.

The release workflow publishes to TestPyPI and PyPI (docs/releasing.md); these
pin the metadata that an index displays and a resolver reads, so an edit to
``requires-python`` or the CI matrix cannot leave the classifiers claiming
something else.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PROJECT = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def test_the_distribution_is_skynet_mars():
    assert _PROJECT["name"] == "skynet-mars"


def test_the_python_classifiers_start_at_the_requires_python_floor():
    floor = re.fullmatch(r">=3\.(\d+)", _PROJECT["requires-python"])
    assert floor, _PROJECT["requires-python"]
    versions = sorted(
        int(m.group(1))
        for c in _PROJECT["classifiers"]
        if (m := re.fullmatch(r"Programming Language :: Python :: 3\.(\d+)", c))
    )
    assert versions and versions[0] == int(floor.group(1))
    assert versions == list(range(versions[0], versions[-1] + 1)), "a gap in the claimed versions"


def test_every_python_the_classifiers_claim_is_tested_in_ci():
    ci = (_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for c in _PROJECT["classifiers"]:
        if m := re.fullmatch(r"Programming Language :: Python :: (3\.\d+)", c):
            assert f'"{m.group(1)}"' in ci, f"CI never runs Python {m.group(1)}"


def test_the_project_urls_point_at_the_repository():
    urls = _PROJECT["urls"]
    assert {"Homepage", "Repository", "Issues"} <= set(urls)
    assert all(u.startswith("https://github.com/archon774/MARS") for u in urls.values())
