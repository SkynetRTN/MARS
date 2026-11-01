#!/usr/bin/env python3
"""Generate the architecture figures for ``docs/architecture-layers.md``.

Three figures, each drawn once and rendered in three palettes:

- ``light`` and ``dark`` -- the committed SVG pairs. The repository renders
  theme-aware assets as a ``-light``/``-dark`` pair behind a ``<picture>``
  element, not as one file with an internal ``prefers-color-scheme`` query:
  GitHub picks between the two from *its own* theme setting, which an SVG's
  internal media query cannot see.
- ``print`` -- greyscale and set in CMU Serif, to sit beside the Skynet 2
  pathway figure in a proposal. Written only with ``--print DIR``, as SVG,
  PDF and a 600-dpi PNG, and never committed.

Every count a figure prints is measured from this checkout when it is drawn
(:func:`measure`), never typed in, so a re-run picks up any change that moves
one. Measuring imports the registry, so run it in the project environment:

    uv run python docs/assets/architecture/make.py
    uv run python docs/assets/architecture/make.py --print ~/figures

Labels are fitted against CMU Serif's own metrics, and the run fails if one
overflows its box or uses a glyph the face lacks; each SVG embeds a subset of
the face (:func:`embedded_faces`). Without the CMU fonts installed the check
and the embedding are skipped with a warning. The ``print`` exports need
``rsvg-convert`` (librsvg) on PATH.

The figures are sized for a 6.5-inch column: one SVG unit is
6.5 in / 1000 = 0.468 pt in print, so the smallest label (16 units) prints
at 7.5 pt. Cut detail before shrinking type below that.
"""

from __future__ import annotations

import argparse
import ast
import collections
import inspect
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PRINT_WIDTH_IN = 6.5
FONT_DIR = Path("/usr/share/fonts/cm-unicode")
SERIF = '"CMU Serif", "Latin Modern Roman", "Computer Modern Serif", Georgia, "Times New Roman", serif'

PALETTES = {
    "light": {
        "bg": "#FFFFFF", "lane": "#F1F5F4", "box": "#FFFFFF",
        "ink": "#0F1619", "ink2": "#46565D", "rule": "#AEBBB9", "line": "#56656B",
        "accent": "#0C6B78", "accentSoft": "#E1F0F1",
        "warn": "#A8500C", "warnSoft": "#F7EADF",
    },
    "dark": {
        "bg": "#0D1117", "lane": "#151E23", "box": "#0D1117",
        "ink": "#E7EDEB", "ink2": "#A8B8BD", "rule": "#3A4D55", "line": "#8EA0A6",
        "accent": "#4FBECA", "accentSoft": "#0E3238",
        "warn": "#DE9A52", "warnSoft": "#38281A",
    },
    # Matches the proposal's Figure 6: grey lanes, white boxes, black type.
    # Emphasis is carried by weight and fill, never by colour alone.
    "print": {
        "bg": "#FFFFFF", "lane": "#EDEDED", "box": "#FFFFFF",
        "ink": "#000000", "ink2": "#333333", "rule": "#8A8A8A", "line": "#3F3F3F",
        "accent": "#000000", "accentSoft": "#DCDCDC",
        "warn": "#000000", "warnSoft": "#F4F4F4",
    },
}

# Text classes: (font file, size in SVG units, CSS weight/style, colour key).
TEXT = {
    "t": ("cmunrm.otf", 17.5, "", "ink"),
    "tb": ("cmunbx.otf", 17.5, "font-weight: bold;", "ink"),
    "ts": ("cmunrm.otf", 16, "", "ink2"),
    "ti": ("cmunti.otf", 16, "font-style: italic;", "ink2"),
    "tl": ("cmunti.otf", 17, "font-style: italic;", "ink2"),
    "tw": ("cmunti.otf", 16, "font-style: italic;", "warn"),
}
LINE_HEIGHT = {"t": 21, "tb": 21, "ts": 19, "ti": 19, "tl": 20, "tw": 19}

STYLE = """{faces}
  text {{ font-family: {serif}; }}
  .bg {{ fill: {bg}; }}
  .lane {{ fill: {lane}; }}
  .box {{ fill: {box}; stroke: {rule}; stroke-width: 1.2; }}
  .boxA {{ fill: {accentSoft}; stroke: {accent}; stroke-width: 1.4; }}
  .boxD {{ fill: {box}; stroke: {line}; stroke-width: 1.3; stroke-dasharray: 5 3; }}
  .boxW {{ fill: {warnSoft}; stroke: {warn}; stroke-width: 1.4; }}
  .boxAD {{ fill: {accentSoft}; stroke: {accent}; stroke-width: 1.4; stroke-dasharray: 5 3; }}
  .frame {{ fill: none; stroke: {accent}; stroke-width: 1.4; }}
  .ln {{ fill: none; stroke: {line}; stroke-width: 1.3; }}
  .lnA {{ fill: none; stroke: {accent}; stroke-width: 1.6; }}
  .lnD {{ fill: none; stroke: {line}; stroke-width: 1.2; stroke-dasharray: 4 3; }}
  .lnW {{ fill: none; stroke: {warn}; stroke-width: 1.8; stroke-dasharray: 9 5; }}
  .hd {{ fill: {line}; }}
  .hdA {{ fill: {accent}; }}
  .halo {{ paint-order: stroke; stroke: {bg}; stroke-width: 5; stroke-linejoin: round; }}
  .haloL {{ paint-order: stroke; stroke: {lane}; stroke-width: 5; stroke-linejoin: round; }}
{text_classes}"""

HEAD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{pw}" height="{ph}" role="img" aria-labelledby="t d">
<title id="t">{title}</title>
<desc id="d">{alt}</desc>
<style>{style}</style>
<defs>
  <marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="hd" d="M0,1 L10,5 L0,9 z"/></marker>
  <marker id="aA" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="hdA" d="M0,1 L10,5 L0,9 z"/></marker>
</defs>
<rect class="bg" x="0" y="0" width="{w}" height="{h}"/>
"""


# --- Measurement ------------------------------------------------------------


def _count_markers(tag: str) -> int:
    """``EXTRACTED:``/``PORTED:`` markers under ``algorithms/``.

    Most are ``# EXTRACTED: was <symbol>`` comments, some sit in docstrings;
    a backticked mention (a header saying changes are "marked `EXTRACTED:`")
    is a reference to the convention, not a marker.
    """

    pattern = re.compile(rf"(?<!`)\b{tag}:")
    return sum(
        len(pattern.findall(path.read_text(encoding="utf-8")))
        for path in (ROOT / "algorithms").rglob("*.py")
    )


def _count_test_functions() -> int:
    count = 0
    for path in (ROOT / "tests").rglob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        count += sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        )
    return count


def _sweep() -> dict[str, object]:
    """The recorded benchmark sweep, from its generated report."""

    import json

    report = json.loads((ROOT / "docs" / "benchmarking" / "report.json").read_text())
    header = report["header"]
    repeats = {run["repeats"] for run in header["runs"]}
    assert len(repeats) == 1, f"mixed repeat counts: {repeats}"
    board = sorted(report["boards"]["correctness"], key=lambda row: row["rank"])
    return {
        "sessions": header["sessions"],
        "tasks": len({key.split("\x00")[0] for key in report["by_task"]}),
        "repeats": repeats.pop(),
        "backends": len(report["matrix"]),
        "correct": [round(100 * row["value"]) for row in board],
        "intervals": [[round(100 * bound) for bound in row["interval"]] for row in board],
    }


def measure() -> dict[str, object]:
    """Every number the figures print, read from the checkout."""

    from tools import downloads
    from tools.agent.engine import run_session
    from tools.bench.plane import TOOL_CLASSES
    from tools.mcp.groups import GROUPS, tools_in_groups
    from tools.registry import TOOL_SCHEMAS

    classes = collections.Counter(TOOL_CLASSES.values())
    groups = {group.name: len(tools_in_groups([group.name])) for group in GROUPS}
    assert sum(groups.values()) == len(TOOL_SCHEMAS), "groups must partition the registry"
    return {
        "tools": len(TOOL_SCHEMAS),
        "groups": groups,
        "local": classes["local"],
        "remote": classes["remote"],
        "mixed": classes["mixed"],
        "max_turns": inspect.signature(run_session).parameters["max_turns"].default,
        "extracted": _count_markers("EXTRACTED"),
        "ported": _count_markers("PORTED"),
        "tests": _count_test_functions(),
        "frames": len(list((ROOT / "data" / "optical").glob("*.fits"))),
        "scans": len(list((ROOT / "data" / "pulsar").glob("*.cal.txt"))),
        "max_products": downloads.MAX_PRODUCTS,
        "max_mib": downloads.MAX_DOWNLOAD_BYTES // 1024**2,
        "max_seconds": downloads.MAX_TRANSFER_SECONDS,
        "solves": sum(1 for p in (ROOT / "data" / "fieldcal" / "zp_solutions").iterdir() if p.is_dir()),
        "ci_pythons": re.search(
            r"python: \[([^\]]*)\]", (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        ).group(1).replace('"', "").split(", "),
        "sweep": _sweep(),
    }


# --- Drawing ----------------------------------------------------------------


class _Metrics:
    """CMU Serif advance widths, for the overflow check."""

    def __init__(self) -> None:
        self.fonts = {}
        self.cmaps = {}
        try:
            from fontTools.ttLib import TTFont
            from PIL import ImageFont
        except ImportError:  # pragma: no cover - both ship with matplotlib
            return
        for cls, (filename, size, _, _) in TEXT.items():
            path = FONT_DIR / filename
            if path.exists():
                # Measure at 10x and scale back: sub-unit sizes stay exact.
                self.fonts[cls] = (ImageFont.truetype(str(path), size * 10), 10.0)
                if filename not in self.cmaps:
                    self.cmaps[filename] = TTFont(path).getBestCmap()

    @property
    def available(self) -> bool:
        return len(self.fonts) == len(TEXT)

    def width(self, text: str, cls: str) -> float:
        font, scale = self.fonts[cls]
        return font.getlength(text) / scale


METRICS = _Metrics()


@dataclass
class Canvas:
    width: int
    height: int
    parts: list[str] = field(default_factory=list)
    overflows: list[str] = field(default_factory=list)
    #: Characters drawn per font file, for the embedded subsets.
    used: dict[str, set[str]] = field(default_factory=lambda: collections.defaultdict(set))

    def _use(self, text: str, cls: str) -> None:
        filename = TEXT[cls][0]
        self.used[filename].update(text)
        if METRICS.available:
            missing = sorted({ch for ch in text if ord(ch) not in METRICS.cmaps[filename]})
            if missing:
                # A fallback font would draw these, at other metrics.
                self.overflows.append(f"{text!r}: {filename} has no glyph for {missing}")

    def _check(self, text: str, cls: str, room: float, where: str) -> None:
        if METRICS.available and METRICS.width(text, cls) > room:
            self.overflows.append(
                f"{where}: {text!r} is {METRICS.width(text, cls):.0f} wide, room {room:.0f}"
            )

    def text(self, x, y, s, cls="t", anchor="start", halo=None, room=None):
        self._use(s, cls)
        if room is not None:
            self._check(s, cls, room, f"text at ({x},{y})")
        extra = f' class="{cls}' + (f" {halo}" if halo else "") + '"'
        self.parts.append(
            f'<text{extra} x="{x}" y="{y}" text-anchor="{anchor}">{escape(s)}</text>'
        )

    def lane(self, y, h, label):
        self.parts.append(f'<rect class="lane" x="0" y="{y}" width="{self.width}" height="{h}"/>')
        cx, cy = 17, y + h / 2
        self._use(label, "tl")
        self._check(label, "tl", h - 8, f"lane {label!r}")
        self.parts.append(
            f'<text class="tl" x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="central" '
            f'transform="rotate(-90 {cx} {cy})">{escape(label)}</text>'
        )

    def box(self, x, y, w, h, lines, kind="box", align="middle", pad=10):
        """A box with centred lines; ``lines`` is ``[(text, class), ...]``."""

        self.parts.append(f'<rect class="{kind}" x="{x}" y="{y}" width="{w}" height="{h}" rx="2"/>')
        heights = [LINE_HEIGHT[cls] for _, cls in lines]
        block = sum(heights)
        if block > h - 6:
            self.overflows.append(f"box at ({x},{y}): {len(lines)} lines need {block}, room {h - 6}")
        baseline = y + (h - block) / 2
        tx = {"middle": x + w / 2, "start": x + pad}[align]
        for (s, cls), lh in zip(lines, heights):
            baseline += lh
            self._use(s, cls)
            self._check(s, cls, w - 2 * pad, f"box at ({x},{y})")
            self.parts.append(
                f'<text class="{cls}" x="{tx}" y="{baseline - lh * 0.27:.1f}" '
                f'text-anchor="{align}">{escape(s)}</text>'
            )

    def arrow(self, *points, kind="ln", both=False):
        d = " ".join(("M" if i == 0 else "L") + f" {x} {y}" for i, (x, y) in enumerate(points))
        head = "aA" if kind == "lnA" else "a"
        start = f' marker-start="url(#{head})"' if both else ""
        self.parts.append(f'<path class="{kind}" d="{d}"{start} marker-end="url(#{head})"/>')

    def line(self, *points, kind="ln"):
        d = " ".join(("M" if i == 0 else "L") + f" {x} {y}" for i, (x, y) in enumerate(points))
        self.parts.append(f'<path class="{kind}" d="{d}"/>')

    def panel(self, x, w, label):
        """A full-height band with an italic heading, for side-by-side panels."""

        self.parts.append(f'<rect class="lane" x="{x}" y="0" width="{w}" height="{self.height}"/>')
        self.text(x + 20, 26, label, "tl", room=w - 40)

    def raw(self, s):
        self.parts.append(s)


# --- Fig. 1 -- MARS as built ------------------------------------------------


def fig1(m: dict) -> tuple[Canvas, str, str]:
    c = Canvas(1000, 702)
    g = m["groups"]

    # Lanes.
    c.lane(0, 86, "Callers")
    c.lane(90, 214, "Agent layer")
    c.lane(308, 122, "Tools")
    c.lane(434, 132, "Algorithms")
    c.lane(570, 132, "Data")

    # Callers.
    c.box(44, 14, 218, 58, [("mars console", "t"), ("students, researchers", "ts")])
    c.box(278, 14, 218, 58, [("mars-bench", "t"), ("recorded, graded runs", "ts")])
    c.box(620, 14, 186, 58, [("Python, notebooks", "t"), ("no model in the path", "ts")])
    c.box(812, 14, 180, 58, [("MCP clients", "t"), ("Claude Code, any host", "ts")])

    # The loop.
    c.raw('<rect class="frame" x="44" y="100" width="560" height="194" rx="3"/>')
    c.text(58, 124, "One bounded, recorded loop", "tb", room=280)
    c.text(590, 124, f"at most {m['max_turns']} turns", "ts", anchor="end", room=140)
    c.arrow((153, 72), (153, 100))
    c.arrow((387, 72), (387, 100))

    c.text(58, 150, "each turn: stop check \u2192 user notes \u2192 model call \u2192 fault log",
           "ti", room=530)
    c.text(58, 176, "each call, before it runs:", "ti", room=530)
    gates = [
        ("schema check", "no extra args", 116),
        ("stop check", "user can halt", 104),
        ("approval", "slow \u00b7 keyed \u00b7 writes", 156),
        ("repeat cache", "reuses a result", 0),
    ]
    x = 58
    for i, (title, sub, w) in enumerate(gates):
        w = w or (594 - x)
        c.box(x, 186, w, 48, [(title, "t"), (sub, "ts")], kind="boxA", pad=6)
        if i < len(gates) - 1:
            c.arrow((x + w, 210), (x + w + 14, 210), kind="lnA")
        x += w + 14

    c.box(58, 242, 422, 46, [
        ("session record: every argument,", "ts"),
        ("decision and result, saved per call", "ts"),
    ])
    c.arrow((560, 234), (560, 320), kind="lnA")
    c.text(552, 270, "dispatch", "ti", anchor="end", room=64)

    # Model port, beside the loop.
    c.box(628, 100, 160, 162, [
        ("Model port", "t"),
        ("provider-neutral", "ti"),
        ("Anthropic", "ts"),
        ("OpenAI-compatible", "ts"),
        ("Gemini", "ts"),
        ("Ollama (local)", "ts"),
    ])
    c.arrow((604, 152), (628, 152), both=True)

    # MCP server.
    c.box(812, 100, 180, 112, [
        ("MCP server", "t"),
        ("strict schema check:", "ts"),
        ("undeclared arguments", "ts"),
        ("never reach a tool", "ts"),
    ])
    c.arrow((902, 72), (902, 100))
    c.arrow((830, 212), (830, 336), (808, 336))
    c.arrow((798, 72), (798, 320))

    # Trust boundary between the model side and the software side.
    c.line((36, 306), (1000, 306), kind="lnW")
    c.text(992, 296, "a model\u2019s request crosses only as a schema-valid call", "tw",
           anchor="end", halo="haloL", room=370)

    # Tools.
    c.box(44, 320, 764, 32, [(
        f"Tool surface: {m['tools']} typed tools \u00b7 {m['local']} local \u00b7 "
        f"{m['remote']} remote \u00b7 {m['mixed']} mixed \u00b7 stateless per call", "t")])
    groups = [
        ("Optical", "optical", 44, 200),
        ("Time series", "timeseries", 260, 132),
        ("HR diagram", "hr", 408, 132),
        ("Radio", "radio", 556, 108),
        ("Databases", "databases", 680, 128),
    ]
    for label, key, x, w in groups:
        c.box(x, 364, w, 54, [(label, "t"), (f"{g[key]} tools", "ts")])

    # What comes back.
    c.box(840, 320, 152, 98, [
        ("Structured result", "t"), ("status, preview,", "ts"), ("warnings,", "ts"),
        ("artifact paths", "ts")])
    c.arrow((808, 391), (840, 391))
    c.line((916, 418), (916, 446), kind="lnD")
    c.box(840, 446, 152, 108, [
        ("Artifacts", "t"), ("tables, plots,", "ts"), ("audio, downloads", "ts"),
        ("under fixed roots", "ti")])

    # Algorithms.
    c.box(44, 446, 272, 108, [
        ("Skynet and Afterglow extractions", "t"),
        ("plate solving, source extraction,", "ts"),
        ("photometry, zero point, catalogs", "ts"),
        (f"{m['extracted']} inline EXTRACTED markers", "ti"),
    ], pad=6)
    c.box(332, 446, 224, 108, [
        ("Astromancer ports", "t"),
        ("pulsar, variable star,", "ts"),
        ("HR-diagram fit", "ts"),
        (f"{m['ported']} inline PORTED markers", "ti"),
    ])
    c.box(572, 446, 112, 108, [
        ("First-party", "t"), ("radio source", "ts"), ("identification,", "ts"),
        ("spectral index", "ts")], pad=6)
    for x in (144, 354, 474, 628):
        c.arrow((x, 418), (x, 446))

    # Data and services: every algorithm reads through one bus; the database
    # tools reach their services directly.
    c.line((172, 554), (172, 568), (640, 568))
    c.line((446, 554), (446, 568))
    c.line((640, 554), (640, 568))
    for x in (172, 446, 640):
        c.arrow((x, 568), (x, 582))
    c.arrow((744, 418), (744, 582))
    c.box(44, 582, 272, 108, [
        ("In the installed package", "t"),
        (f"{m['scans']} Green Bank 20 m pulsar scans", "ts"),
        (f"{m['solves']} recorded zero-point solves", "ts"),
        ("Afterglow reference outputs", "ts"),
    ], pad=6)
    c.box(332, 582, 272, 108, [
        ("Optional data bundles", "t"),
        (f"{m['frames']} PROMPT/Skynet optical frames", "ts"),
        ("Girardi isochrone grid", "ts"),
        ("size and SHA-256 pinned", "ti"),
    ], pad=6)
    c.box(620, 582, 372, 108, [
        ("Remote services", "t"),
        ("SIMBAD \u00b7 NED \u00b7 VizieR \u00b7 ADS \u00b7 SDSS", "ts"),
        ("MAST \u00b7 ATNF \u00b7 CASDA \u00b7 MPC", "ts"),
        (f"downloads capped: {m['max_products']} products, {m['max_mib']} MiB, "
         f"{m['max_seconds']} s", "ti"),
    ])

    title = "MARS as built: the model proposes, tested software computes"
    alt = (
        "Five horizontal lanes. Callers (the mars console, the mars-bench benchmark, "
        "Python scripts and MCP clients) enter at the top. The console and the benchmark "
        f"drive one bounded loop of at most {m['max_turns']} turns, which checks every "
        "proposed tool call against its schema, a stop request, an approval policy and a "
        "repeat-call cache before dispatching it, and records every call in a session "
        "record. MCP clients reach the tools through a server that applies a strict schema "
        "check. A dashed trust boundary separates the model side from the software side. "
        f"Below it, a surface of {m['tools']} typed tools in five groups calls algorithms "
        "extracted from the Skynet pipeline and Afterglow, ported from Astromancer, or "
        "first-party, which read the data installed with the package, checksum-pinned "
        "optional bundles and remote astronomy "
        "services. Results return as structured results and artifacts."
    )
    return c, title, alt


# --- Fig. 2 -- the proposed Aim 2 loop --------------------------------------
#
# Proposed work, drawn as proposed: a dashed outline is to be built under the
# award; a solid one exists in MARS today or is Skynet 2, funded by NSF ATI.
# The Skynet 2 boxes are the proposal's own Figure 6, collapsed into one lane,
# under its own names.


def fig2(m: dict) -> tuple[Canvas, str, str]:
    c = Canvas(1000, 484)

    c.lane(0, 118, "User")
    c.lane(122, 130, "MARS")
    c.lane(256, 130, "Skynet 2")
    c.lane(390, 94, "Facility")

    # User.
    c.box(44, 16, 226, 86, [
        ("Scientific objective", "t"), ("e.g. measure a variable", "ts"),
        ("star’s period to 1%", "ts")])
    c.box(300, 16, 200, 86, [
        ("Review, clarify,", "t"), ("approve", "t"), ("the plan and each", "ts"),
        ("consequential action", "ts")], kind="boxAD")
    c.box(632, 16, 180, 86, [
        ("Interpretation", "t"), ("result with its evidence,", "ts"),
        ("or the limiting", "ts"), ("requirement", "ts")], pad=6)
    c.text(836, 34, "Proposed", "tb", room=156)
    c.raw('<rect class="boxD" x="836" y="48" width="26" height="14"/>')
    c.text(870, 60, "built in Aim 2", "ts", room=122)
    c.raw('<rect class="box" x="836" y="74" width="26" height="14"/>')
    c.text(870, 86, "existing", "ts", room=122)
    c.arrow((632, 59), (500, 59))
    c.text(566, 52, "follow-up", "ti", anchor="middle", halo="haloL", room=120)

    # MARS.
    c.box(44, 138, 226, 98, [
        ("Measurement", "t"), ("requirements", "t"), ("cadence, baseline,", "ts"),
        ("precision, bands", "ts")], kind="boxD")
    c.box(286, 138, 160, 98, [
        ("Observing and", "t"), ("analysis plan", "t"), ("for the user", "ti"),
        ("to inspect", "ti")], kind="boxD")
    c.box(462, 138, 154, 98, [
        ("Observation", "t"), ("request", "t"), ("via a constrained", "ts"),
        ("interface", "ts")], kind="boxD", pad=6)
    c.box(632, 138, 180, 98, [
        ("Adequacy check", "t"), ("operational success", "ts"), ("vs. scientific", "ts"),
        ("adequacy", "ts")], kind="boxD")
    c.box(828, 138, 164, 98, [
        ("Analysis", "t"), ("existing MARS tools:", "ti"), ("photometry, zero", "ts"),
        ("point, periodograms", "ts")], pad=6)

    c.arrow((157, 102), (157, 138))
    c.arrow((270, 187), (286, 187))
    c.arrow((366, 138), (366, 102))
    c.arrow((482, 102), (482, 138), kind="lnA")
    c.arrow((828, 187), (812, 187))
    c.arrow((722, 138), (722, 102))

    # Skynet 2: Figure 6's service lane.
    c.box(44, 272, 402, 98, [
        ("Registered instrument capabilities", "t"),
        ("filters, response curves, field of view,", "ts"),
        ("measured sensitivity", "ts"),
        ("App State and UNCG facilities added in Aim 1", "ti")])
    c.box(462, 272, 154, 98, [
        ("Access control", "t"), ("& capability", "t"), ("matching", "t")], pad=6)
    c.box(628, 272, 96, 98, [("Scheduler", "t")], pad=6)
    c.box(736, 272, 110, 98, [("SkyNode", "t"), ("gateway", "t")], pad=6)
    c.box(858, 272, 134, 98, [("Data storage,", "t"), ("pipeline & QA", "t")], pad=6)

    c.arrow((157, 272), (157, 236))
    c.text(165, 258, "registered capabilities", "ti", halo="haloL", room=180)
    c.arrow((539, 236), (539, 272))
    c.arrow((616, 321), (628, 321))
    c.arrow((724, 321), (736, 321))
    c.arrow((925, 272), (925, 236))
    c.text(917, 258, "data, QA", "ti", anchor="end", halo="haloL", room=80)

    # Facility.
    c.text(44, 430, "Facility selection, scheduling and execution stay with", "ti", room=500)
    c.text(44, 450, "Skynet 2, funded by NSF ATI.", "ti", room=500)
    c.box(560, 404, 140, 64, [("Local operator", "t"), ("control", "t")], pad=6)
    c.box(716, 404, 150, 64, [("SkyNode", "t"), ("at each telescope", "ts")], pad=6)
    c.line((700, 436), (716, 436), kind="lnD")
    c.arrow((791, 370), (791, 404))
    c.text(799, 392, "tasks", "ti", room=50)
    c.arrow((866, 436), (925, 436), (925, 370))
    c.text(917, 392, "raw assets", "ti", anchor="end", room=80)

    title = "Proposed (Aim 2): from scientific intent to evidence through MARS and Skynet 2"
    alt = (
        "A proposed workflow in four lanes: user, MARS, Skynet 2 and facility. A user "
        "states a scientific objective. MARS, using the capabilities registered in "
        "Skynet 2, turns it into measurement requirements and an observing-and-analysis "
        "plan, which the user reviews and approves; only then does MARS send an "
        "observation request through a constrained interface. Skynet 2 performs access "
        "control and capability matching, scheduling and dispatch through the SkyNode "
        "gateway to SkyNode at each telescope, under local operator control, and returns "
        "data and quality assessment. MARS analyses the data with its existing tools and "
        "checks scientific adequacy separately from operational success; the user receives "
        "the result with its evidence, or the limiting requirement and a follow-up for "
        "review. Dashed outlines are to be built under Aim 2; solid outlines exist: MARS "
        "today, and Skynet 2, funded by NSF ATI, which keeps facility selection, scheduling "
        "and execution."
    )
    return c, title, alt


# --- Fig. 3 -- validation -----------------------------------------------------


def fig3(m: dict) -> tuple[Canvas, str, str]:
    sw = m["sweep"]
    c = Canvas(1000, 618)
    c.panel(0, 492, "Provenance: is it the same algorithm?")
    c.panel(508, 492, "Evaluation: does a model use it correctly?")

    rows = [40, 150, 260, 370, 480]
    h = 88
    lx, lw = 20, 452
    rx, rw = 528, 452

    # Left: where the algorithms came from, and what holds them there.
    c.box(lx, rows[0], 216, h, [
        ("Skynet and Afterglow", "t"), ("production Python", "ts"),
        ("plate solving to zero point", "ti")])
    c.box(lx + 236, rows[0], 216, h, [
        ("Astromancer", "t"), ("TypeScript", "ts"), ("pulsar, variable star, HR fit", "ti")])
    c.box(lx, rows[1], lw, h, [
        ("Extracted and ported, not rewritten", "t"),
        ("upstream files and line ranges recorded", "ts"),
        (f"{m['extracted']} EXTRACTED and {m['ported']} PORTED markers in the code", "ts"),
        ("deliberate corrections tested against independent references", "ti")])
    c.box(lx, rows[2], lw, h, [
        ("Preservation tests", "t"),
        (f"{m['tests']:,} test functions; offline and keyless by default", "ts"),
        ("parity with recorded upstream output, known bugs included", "ts"),
        (f"{m['frames']} real frames, {m['solves']} recorded zero-point solves", "ti")])
    pythons = " and ".join(m["ci_pythons"])
    c.box(lx, rows[3], lw, h, [
        ("Continuous integration", "t"),
        (f"Python {pythons}, against the lockfile", "ts"),
        ("secret scan over the tree and its full history", "ts"),
        ("workflow audit; actions pinned to commit hashes", "ti")])
    c.box(lx, rows[4], lw, h, [
        ("Release", "t"),
        ("TestPyPI → byte-compared install → PyPI", "ts"),
        ("trusted publishing: no stored upload token", "ts"),
        ("SHA-256 sums; data bundles pinned by size and hash", "ti")])
    for x in (lx + 108, lx + 344):
        c.arrow((x, rows[0] + h), (x, rows[1]))
    for top in rows[1:4]:
        c.arrow((lx + lw / 2, top + h), (lx + lw / 2, top + 110))

    # Right: the benchmark today, and what Aim 3 adds.
    c.box(rx, rows[0], rw, h, [
        ("Task", "t"),
        ("a scientific prompt, and an answer key of what", "ts"),
        ("must and must not be claimed", "ts")])
    c.box(rx, rows[1], rw, h, [
        ("Run, recorded", "t"),
        ("the console’s loop, unchanged; every call recorded", "ts"),
        (f"tool plane: {m['local']} live · {m['remote']} replayed · "
         f"{m['mixed']} decided per call", "ts"),
        ("astronomy services replayed from recorded fixtures", "ti")])
    c.box(rx, rows[2], rw, h, [
        ("Graded separately from running", "t"),
        ("answer, efficiency, trajectory, protocol", "ts"),
        ("deterministic checks; no model grades a model", "ts"),
        ("a corrected check re-grades without re-running", "ti")])
    top, second = sw["intervals"][0], sw["intervals"][1]
    overlap = "overlap" if top[0] <= second[1] and second[0] <= top[1] else "separate"
    c.box(rx, rows[3], rw, h, [
        ("September 2026 sweep, before attribution checks", "t"),
        (f"{sw['sessions']} sessions: {sw['tasks']} tasks × {sw['repeats']} repeats "
         f"× {sw['backends']} models", "ts"),
        ("correct: " + ", ".join(f"{v}%" for v in sw["correct"])
         + " of scored sessions", "ts"),
        (f"95% intervals for the top two {overlap}", "ti")])
    c.box(rx, rows[4], rw, 120, [
        ("Aim 3, proposed", "t"),
        ("real Skynet 2 observations as validation cases", "ts"),
        ("each failure traced to instrument capability,", "ts"),
        ("observing execution, analysis or AI interpretation", "ts"),
        ("a warranted request for human help scores as success", "ti")], kind="boxD")
    for top_y in rows[:4]:
        c.arrow((rx + rw / 2, top_y + h), (rx + rw / 2, top_y + 110))

    title = "Validation: provenance and preservation testing, and the benchmark"
    alt = (
        "Two panels. Left, provenance: algorithms extracted from the Skynet pipeline and "
        "Afterglow and ported from Astromancer, with upstream files and line ranges "
        "recorded and "
        f"{m['extracted']} EXTRACTED and {m['ported']} PORTED markers, and deliberate "
        f"corrections tested against independent references; {m['tests']:,} test functions "
        "pin parity with recorded upstream output, known bugs included; continuous integration "
        f"on Python {pythons} against the lockfile with secret scanning and a workflow "
        "audit; and a release path from TestPyPI through a byte-compared install to PyPI by "
        "trusted publishing. Right, evaluation: tasks with answer keys run through the same "
        "loop with astronomy services replayed, graded deterministically and separately from "
        f"running; the September 2026 sweep of {sw['sessions']} sessions scored "
        + ", ".join(f"{v}%" for v in sw["correct"])
        + " correct. A dashed box marks Aim 3's proposed extension to real Skynet 2 "
        "observations, with failures traced to instrument, execution, analysis or AI "
        "interpretation."
    )
    return c, title, alt


FIGURES = [
    ("fig-1-mars-as-built", fig1),
    ("fig-2-aim-2-proposed", fig2),
    ("fig-3-validation", fig3),
]


# --- Output -----------------------------------------------------------------


# The three CMU Serif faces the figures use: (file, CSS weight, CSS style).
FACES = (
    ("cmunrm.otf", "normal", "normal"),
    ("cmunbx.otf", "bold", "normal"),
    ("cmunti.otf", "normal", "italic"),
)
EMBEDDED = "MARS Figure Serif"


def embedded_faces(canvas: Canvas) -> str:
    """``@font-face`` rules carrying a WOFF subset of each face, inline.

    A browser showing the SVG as an image loads no external font, so without
    these a reader without CMU Serif gets Georgia or similar, about a tenth
    wider -- enough to push labels into their box edges. A data URI is not
    external, so the figure renders in the face it was fitted to everywhere.
    CMU Serif is under the SIL Open Font License, which permits embedding.
    librsvg ignores ``@font-face`` and uses the installed fonts instead.
    """

    if not METRICS.available:
        return ""
    import base64
    import io

    import logging

    from fontTools import subset
    from fontTools.ttLib import TTFont

    logging.getLogger("fontTools").setLevel(logging.ERROR)
    rules = []
    for filename, weight, style in FACES:
        chars = "".join(sorted(canvas.used.get(filename, ())))
        if not chars:
            continue
        # A recalculated head.modified would make every run's bytes differ
        # and every regeneration a diff.
        font = TTFont(FONT_DIR / filename, recalcTimestamp=False)
        options = subset.Options()
        options.flavor = "woff"
        subsetter = subset.Subsetter(options)
        subsetter.populate(text=chars)
        subsetter.subset(font)
        buffer = io.BytesIO()
        font.save(buffer)
        data = base64.b64encode(buffer.getvalue()).decode("ascii")
        rules.append(
            f'\n  @font-face {{ font-family: "{EMBEDDED}"; font-weight: {weight}; '
            f'font-style: {style}; src: url(data:font/woff;base64,{data}) format("woff"); }}'
        )
    return "".join(rules)


def render(canvas: Canvas, title: str, alt: str, theme: str) -> str:
    palette = PALETTES[theme]
    text_classes = "\n".join(
        f"  .{cls} {{ font-size: {size}px; {css} fill: {palette[colour]}; }}"
        for cls, (_, size, css, colour) in TEXT.items()
    )
    faces = embedded_faces(canvas)
    serif = f'"{EMBEDDED}", {SERIF}' if faces else SERIF
    style = STYLE.format(serif=serif, faces=faces, text_classes=text_classes, **palette)
    if theme == "print":
        pw = f"{PRINT_WIDTH_IN}in"
        ph = f"{PRINT_WIDTH_IN * canvas.height / canvas.width:.3f}in"
    else:
        pw, ph = canvas.width, canvas.height
    head = HEAD.format(
        w=canvas.width, h=canvas.height, pw=pw, ph=ph,
        title=escape(title), alt=escape(alt), style=style,
    )
    return head + "\n".join(canvas.parts) + "\n</svg>\n"


def export_print(svg_path: Path) -> None:
    rsvg = shutil.which("rsvg-convert")
    if rsvg is None:
        sys.exit("--print needs rsvg-convert (librsvg) on PATH")
    stem = svg_path.with_suffix("")
    subprocess.run([rsvg, "-f", "pdf", "-o", f"{stem}.pdf", str(svg_path)], check=True)
    subprocess.run(
        [rsvg, "-f", "png", "-d", "600", "-p", "600", "-o", f"{stem}.png", str(svg_path)],
        check=True,
    )
    # rsvg-convert writes no resolution into the PNG, and Word then assumes
    # 96 dpi and inserts it six times too large. Record the 600 dpi it has.
    from PIL import Image

    with Image.open(f"{stem}.png") as image:
        image.load()
    image.save(f"{stem}.png", dpi=(600, 600))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--print", dest="print_dir", type=Path,
                        help="also write greyscale print SVG, PDF and 600-dpi PNG here")
    args = parser.parse_args()

    if not METRICS.available:
        print(f"warning: CMU Serif not found under {FONT_DIR}; "
              "labels not fitted, face not embedded", file=sys.stderr)
    m = measure()
    failed = False
    for name, draw in FIGURES:
        canvas, title, alt = draw(m)
        for problem in canvas.overflows:
            print(f"{name}: {problem}", file=sys.stderr)
            failed = True
        for theme in ("light", "dark"):
            path = OUT / f"{name}-{theme}.svg"
            path.write_text(render(canvas, title, alt, theme), encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
        if args.print_dir:
            args.print_dir.mkdir(parents=True, exist_ok=True)
            path = args.print_dir / f"{name}.svg"
            path.write_text(render(canvas, title, alt, "print"), encoding="utf-8")
            export_print(path)
            print(f"wrote {path.with_suffix('')}.{{svg,pdf,png}}")
    if failed:
        sys.exit("labels overflow; widen the box or cut the text")


if __name__ == "__main__":
    main()
