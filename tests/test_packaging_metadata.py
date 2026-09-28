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
    assert all(u.startswith("https://github.com/SkynetRTN/MARS") for u in urls.values())


def test_runtime_dependencies_are_bounded_ranges_not_a_freeze():
    """An exact pin on every package, test tools included, clashed with the
    rest of a user's environment. Runtime dependencies are what MARS imports,
    bounded with ~=; exact versions belong to uv.lock."""
    deps = _PROJECT["dependencies"] + sum(_PROJECT["optional-dependencies"].values(), [])
    for dep in deps:
        assert "==" not in dep and "~=" in dep, dep
    names = {dep.split()[0].split("~=")[0].lower() for dep in deps}
    assert not names & {"pytest", "mock", "packaging", "twine"}, names


def test_pytest_is_a_development_dependency_only():
    import tomllib

    pyproject = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert any(d.startswith("pytest") for d in pyproject["dependency-groups"]["dev"])


def test_the_readme_uses_absolute_urls_pypi_can_render():
    """PyPI renders README.md with no repository to resolve a relative path
    against: the banner showed as a broken image, and relative links 404."""
    import re

    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    relative_images = re.findall(r'(?:src|srcset)="(?!https://)([^"]+)"', readme)
    relative_links = [
        target
        for target in re.findall(r"\]\(([^)\s]+)\)", readme)
        if not re.match(r"(https?:|mailto:|#)", target)
    ]
    assert relative_images == [] and relative_links == [], (relative_images, relative_links)
