"""R3's guard: the project is MARS, and "Kepler" survives only where it must.

``docs/working/mars-rebrand.md`` §5 (R3). A case-insensitive search of the
code trees may find ``kepler`` only in the places below. Each is there on
purpose, and none is the project's name for itself:

- the deprecation shims and their tests, removed in the release after
  ``0.1.0rc3`` (§6.3), and the handful of lines elsewhere that name them;
- published names that must keep their bytes: the data bundles' archives,
  their ``ARCHIVE_PREFIX``, and the ``.kepler-bundle.json`` marker a fetched
  bundle carries (§3);
- the repository's first name, which still redirects and must stay unused;
- the **Kepler mission**. A tool that queries the telescope's data must be
  able to say so. Add the form it needs to :data:`MISSION`, never a path.

The documentation joins this scope in R4.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

#: What is searched: everything that is not prose documentation.
SCOPE = (
    "tools",
    "tests",
    "algorithms",
    "benchmarks",
    "skills",
    "data",
    ".github",
    ".claude",
    "pyproject.toml",
)

#: Whole files that exist to handle the old name.
SHIMS = frozenset(
    {
        "tools/aliases.py",
        "tools/compat.py",
        "tests/test_aliases.py",
        "tests/test_compat.py",
        "tests/test_rebrand_guard.py",
    }
)

#: Published names that keep their bytes, wherever they are mentioned.
PUBLISHED = (
    r"kepler-(?:optical|isochrones)-[0-9a-f]{12}\.tar",
    r'ARCHIVE_PREFIX = "kepler-"',
    r"\.kepler-bundle\.json",
    r"archon774/kepler\b",
)

#: The telescope, not the project.
MISSION = (
    r"\bKepler(?:/K2)? (?:space telescope|mission|spacecraft|Input Catalog)\b",
    r"\bKIC ?\d+",
    r"\bKOI-?\d+",
)

#: Single lines outside the shims that name them, by file.
SHIM_REFERENCES = {
    "pyproject.toml": r'^kepler(?:-bench|-mcp)? = "tools\.aliases:',
    "tools/config.py": r"^# Kepler's KEPLER_\* names",
    "tools/mcp/__main__.py": r"project called ``kepler``",
    "tools/mcp/selftest.py": r"# KEPLER_\* too",
    "tools/paths.py": r"find the ``kepler``",
    "tests/test_bench_tasks.py": r'"KEPLER_MAX_FRAMES"',
    "tests/test_mcp_surface.py": r"pip install 'kepler\[mcp\]'",
    "tests/test_tool_registry_coverage.py": (
        r"deprecated kepler, kepler-mcp and kepler-bench|KEPLER_\* variables and the kepler home"
    ),
}

_ALLOWED = re.compile("|".join(PUBLISHED + MISSION))


def _hits() -> list[tuple[str, int, str]]:
    result = subprocess.run(
        ["git", "grep", "-I", "-n", "-i", "kepler", "--", *SCOPE],
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


def _unexplained(path: str, text: str) -> bool:
    if path in SHIMS:
        return False
    reference = SHIM_REFERENCES.get(path)
    if reference and re.search(reference, text):
        return False
    return re.search("kepler", _ALLOWED.sub("", text), re.IGNORECASE) is not None


@pytest.mark.skipif(
    shutil.which("git") is None or not (_REPO_ROOT / ".git").exists(),
    reason="needs a git checkout",
)
def test_kepler_appears_only_where_it_must():
    unexplained = [
        f"{path}:{number}: {text.strip()}"
        for path, number, text in _hits()
        if _unexplained(path, text)
    ]
    assert unexplained == [], "\n".join(unexplained)


def test_the_mission_stays_nameable():
    for text in (
        "light curves from the Kepler space telescope",
        "the Kepler/K2 mission archive",
        "KIC 8462852",
    ):
        assert not _unexplained("tools/future_mission_tool.py", text), text
    assert _unexplained("tools/future_mission_tool.py", "Kepler's astronomy tools")


def test_no_new_top_level_package():
    """§6.2: the namespace move is its own track, so nothing new joins
    ``tools`` and ``algorithms`` at the top level in the meantime."""
    import tomllib

    pyproject = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["include"] == [
        "tools*",
        "algorithms*",
    ]


def test_every_shim_reference_still_matches_something():
    """A stale entry would let a new mention through unexamined."""
    hits = _hits()
    for path, pattern in SHIM_REFERENCES.items():
        assert any(p == path and re.search(pattern, t) for p, _, t in hits), path
