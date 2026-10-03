"""The project is MARS, and its earlier name appears nowhere in the repository.

A case-insensitive search of every tracked text file, however the name is
spaced, finds only the astronomy named after the astronomer: the space
telescope and its mission, "Keplerian" orbits, Kepler's laws. A tool that
queries the telescope's data must be able to say so. Add the form it needs to
:data:`MISSION`, never a path or a file.

The earlier name is spelled in pieces here (:data:`_OLD`) so that this file
carries it no more than any other.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

#: The earlier name, in pieces.
_OLD = "kep" + "ler"

#: Where the repository's own name is checked (the last test).
SCOPE = (
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    ".gitleaks.toml",
    "docs",
    "tools",
    "tests",
    "algorithms",
    "benchmarks",
    "skills",
    "data",
    "installers",
    ".github",
    ".claude",
    "pyproject.toml",
)

#: Dated records -- plans, analyses, reports -- that may keep the repository
#: names they were written with (see the last test).
RECORDS = frozenset(
    {
        "docs/archive/mcp-tool-surface.md",
        "docs/archive/model-backends.md",
        "docs/archive/optical-tools.md",
        "docs/analysis/algorithm-remediation-plan.md",
        "docs/analysis/applicable-designs.md",
        "docs/benchmarking/report.md",
        "docs/benchmarking/report.json",
        "docs/benchmarking/results.md",
        "docs/superpowers/plans/2026-09-14-tui-artifact-rendering.md",
    }
)
RECORD_TREES = ("docs/benchmarking/figures/",)

#: The telescope and the astronomer, not the project.
_ASTRONOMER = _OLD.capitalize()
MISSION = (
    rf"\b{_ASTRONOMER}ian\b",
    rf"\b{_ASTRONOMER}'s (?:laws?|equation)\b",
    rf"\b{_ASTRONOMER}(?:/K2)? (?:space telescope|mission|spacecraft|Input Catalog)\b",
    r"\bKIC ?\d+",
    r"\bKOI-?\d+",
)

_ALLOWED = re.compile("|".join(MISSION))

#: The name however it is spaced: a wordmark spelled with spaces between the
#: letters is invisible to a plain search.
_NAME = re.compile(r"[\s._-]*".join(_OLD), re.IGNORECASE)


def _hits() -> list[tuple[str, int, str]]:
    result = subprocess.run(
        # The whole tracked tree, not SCOPE: uv.lock, LICENSE and the dotfiles
        # at the top level are where an old distribution name would come back.
        ["git", "grep", "-I", "-n", "-i", "-E", _NAME.pattern.replace("\\s", "[:space:]"), "--", "."],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        pytest.skip(f"git grep failed: {result.stderr.strip()}")
    hits = []
    for line in result.stdout.splitlines():
        path, number, text = line.split(":", 2)
        hits.append((path, int(number), text))
    return hits


def _names_the_project(text: str) -> bool:
    return _NAME.search(_ALLOWED.sub("", text)) is not None


@pytest.mark.skipif(
    shutil.which("git") is None or not (_REPO_ROOT / ".git").exists(),
    reason="needs a git checkout",
)
def test_the_earlier_name_appears_nowhere():
    named = [f"{path}:{number}: {text.strip()}" for path, number, text in _hits() if _names_the_project(text)]
    assert named == [], "\n".join(named)


@pytest.mark.skipif(
    shutil.which("git") is None or not (_REPO_ROOT / ".git").exists(),
    reason="needs a git checkout",
)
def test_no_tracked_path_carries_the_earlier_name():
    result = subprocess.run(["git", "ls-files"], cwd=_REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.skip(f"git ls-files failed: {result.stderr.strip()}")
    assert [path for path in result.stdout.splitlines() if _NAME.search(path)] == []


def test_the_mission_stays_nameable():
    for text in (
        "light curves from the Kepler space telescope",
        "the Kepler/K2 mission archive",
        "KIC 8462852",
        "Keplerian orbital position",
        "solving Kepler's equation",
    ):
        assert not _names_the_project(text), text
    old = _ASTRONOMER
    assert _names_the_project(f"{old}'s astronomy tools")
    assert _names_the_project(f"pip install '{_OLD}[mcp]'")
    assert _names_the_project(f".{_OLD}-bundle.json")
    assert _names_the_project(f'WORDMARK = "{" ".join(_OLD.upper())}"')
    assert _names_the_project(f"/home/claude/{old}/artifacts")


def test_no_new_top_level_package():
    """The namespace move is its own track, so nothing new joins ``tools``
    and ``algorithms`` at the top level in the meantime."""
    import tomllib

    pyproject = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["include"] == [
        "tools*",
        "algorithms*",
    ]


def test_the_repository_is_skynetrtn_mars_outside_the_records():
    """The repository is ``SkynetRTN/MARS`` (renamed and transferred to the
    Skynet organisation 2026-09-28); the distribution stays ``skynet-mars``.
    Its earlier names only redirect, until someone creates a repository under
    one, so nothing current may point at them. Records keep the names they
    were written with, and ``tools/mcp/bundles.py`` names them to say exactly
    that."""
    result = subprocess.run(
        ["git", "grep", "-n", "-E", r"archon774/(skynet-mars|mars-suite|MARS)\b", "--", *SCOPE],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        pytest.skip(f"git grep failed: {result.stderr.strip()}")
    stale = [
        line
        for line in result.stdout.splitlines()
        if line.split(":", 1)[0] not in RECORDS | {"tools/mcp/bundles.py"}
        and not line.split(":", 1)[0].startswith(RECORD_TREES)
    ]
    assert stale == [], "\n".join(stale)
