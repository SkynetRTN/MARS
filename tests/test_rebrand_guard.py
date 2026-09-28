"""R3's guard: the project is MARS, and "Kepler" survives only where it must.

``docs/working/mars-rebrand.md`` §5 (R3). A case-insensitive search of the
code trees may find ``kepler`` only in the places below. Each is there on
purpose, and none is the project's name for itself:

- a handful of lines that name the old name on purpose (``OLD_NAME_LINES``);
  the deprecation shims that honoured it for ``0.1.0rc3`` are gone (§6.3);
- published names that must keep their bytes: the data bundles' archives,
  their ``ARCHIVE_PREFIX``, and the ``.kepler-bundle.json`` marker a fetched
  bundle carries (§3);
- the repository's first name, which still redirects and must stay unused;
- the **Kepler mission**, and the astronomy named after Kepler himself
  ("Keplerian" orbits, Kepler's laws). A tool that queries the telescope's
  data must be able to say so. Add the form it needs to :data:`MISSION`,
  never a path.

The documentation joined this scope in R4. A **record** -- a dated plan,
analysis or report -- says what was true when it was written, and keeps the
old names under a dated note (``RECORDS``); a current document may name them
only to describe the upgrade from Kepler.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

#: What is searched: the whole repository but its binary data.
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
    ".github",
    ".claude",
    "pyproject.toml",
)

#: Whole files that must name the old name: this guard, which quotes it.
SHIMS = frozenset({"tests/test_rebrand_guard.py"})

#: Records, kept as written under a dated note (docs/working/mars-rebrand.md
#: §2), and the rebrand plan itself.
RECORDS = frozenset(
    {
        "docs/working/mars-rebrand.md",
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

#: Published names that keep their bytes, wherever they are mentioned.
PUBLISHED = (
    r"kepler-(?:optical|isochrones)-(?:[0-9a-f]{12}|<sha12>)\.tar",
    r'ARCHIVE_PREFIX = "kepler-"',
    r"\.kepler-bundle\.json",
    r"archon774/kepler\b",
    # Retired before the rename; named only where its retirement is recorded.
    r"kepler-astro-query",
)

#: The checkout's directory until R6 renamed it /home/claude/mars. Allowed
#: only in the files that quote it as a record -- extraction provenance and a
#: live run's output -- never globally: nothing may depend on it any more.
OLD_CHECKOUT = r"/home/claude/Kepler\b"
QUOTES_OLD_CHECKOUT = frozenset({"docs/extraction.md", "tools/bench/graders/answer.py"})

#: The telescope and the astronomer, not the project.
MISSION = (
    r"\bKeplerian\b",
    r"\bKepler's (?:laws?|equation)\b",
    r"\bKepler(?:/K2)? (?:space telescope|mission|spacecraft|Input Catalog)\b",
    r"\bKIC ?\d+",
    r"\bKOI-?\d+",
)

#: Whole sections of a current document that describe the upgrade from
#: Kepler, by file and heading; the section ends at the next heading.
UPGRADE_SECTIONS = {"docs/installing.md": "### Upgrading from Kepler"}

#: Single lines that name the old name on purpose, by file.
OLD_NAME_LINES = {
    "docs/working/README.md": r"Renaming Kepler to MARS",
    "tools/config.py": r"^#: fetched by Kepler and moved into",
    "tools/mcp/__main__.py": r"project called ``kepler``",
    "tests/test_mcp_surface.py": r"pip install 'kepler\[mcp\]'",
}

_ALLOWED = re.compile("|".join(PUBLISHED + MISSION))

#: The name however it is spaced: the console's wordmark was "K E P L E R",
#: which a plain search for "kepler" never saw.
_NAME = re.compile(r"k[\s._-]*e[\s._-]*p[\s._-]*l[\s._-]*e[\s._-]*r", re.IGNORECASE)


def _hits() -> list[tuple[str, int, str]]:
    result = subprocess.run(
        ["git", "grep", "-I", "-n", "-i", "-E", _NAME.pattern.replace("\\s", "[:space:]"), "--", *SCOPE],
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


def _section_lines(path: str, heading: str) -> range:
    """1-based line numbers of the section, its heading included."""
    lines = (_REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
    heading_index = lines.index(heading)
    end_index = next(
        (i for i in range(heading_index + 1, len(lines)) if lines[i].startswith("#")),
        len(lines),
    )
    return range(heading_index + 1, end_index + 1)


def _unexplained(path: str, text: str, number: int = 0) -> bool:
    if path in SHIMS or path in RECORDS or path.startswith(RECORD_TREES):
        return False
    if path in UPGRADE_SECTIONS and number in _section_lines(path, UPGRADE_SECTIONS[path]):
        return False
    reference = OLD_NAME_LINES.get(path)
    if reference and re.search(reference, text):
        return False
    if path in QUOTES_OLD_CHECKOUT:
        text = re.sub(OLD_CHECKOUT, "", text)
    return _NAME.search(_ALLOWED.sub("", text)) is not None


@pytest.mark.skipif(
    shutil.which("git") is None or not (_REPO_ROOT / ".git").exists(),
    reason="needs a git checkout",
)
def test_kepler_appears_only_where_it_must():
    unexplained = [
        f"{path}:{number}: {text.strip()}"
        for path, number, text in _hits()
        if _unexplained(path, text, number)
    ]
    assert unexplained == [], "\n".join(unexplained)


def test_the_mission_stays_nameable():
    for text in (
        "light curves from the Kepler space telescope",
        "the Kepler/K2 mission archive",
        "KIC 8462852",
        "Keplerian orbital position",
        "solving Kepler's equation",
    ):
        assert not _unexplained("tools/future_mission_tool.py", text), text
    assert _unexplained("tools/future_mission_tool.py", "Kepler's astronomy tools")
    assert _unexplained("tools/tui/widgets/header.py", 'WORDMARK = "K E P L E R"')


def test_the_old_checkout_path_is_allowed_only_where_it_is_quoted():
    quoted = "`/home/claude/Kepler/algorithms/lightcurve/`"
    assert not _unexplained("docs/extraction.md", quoted)
    assert _unexplained("tools/config.py", 'ROOT = "/home/claude/Kepler/data"')
    assert _unexplained("docs/installing.md", quoted)


def test_no_new_top_level_package():
    """§6.2: the namespace move is its own track, so nothing new joins
    ``tools`` and ``algorithms`` at the top level in the meantime."""
    import tomllib

    pyproject = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["include"] == [
        "tools*",
        "algorithms*",
    ]


def test_every_old_name_line_still_matches_something():
    """A stale entry would let a new mention through unexamined."""
    hits = _hits()
    for path, pattern in OLD_NAME_LINES.items():
        assert any(p == path and re.search(pattern, t) for p, _, t in hits), path
