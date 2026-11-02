#!/usr/bin/env python3
"""Generate the architecture figures for ``docs/architecture-layers.md``.

Five figures, each drawn once and rendered in three palettes:

- ``light`` and ``dark`` -- the committed SVG pairs. The repository renders
  theme-aware assets as a ``-light``/``-dark`` pair behind a ``<picture>``
  element, not as one file with an internal ``prefers-color-scheme`` query:
  GitHub picks between the two from *its own* theme setting, which an SVG's
  internal media query cannot see.
- ``print`` -- greyscale, for documents outside the repository; Fig. 5
  prints in its light colours. Written only with ``--print DIR``, as SVG,
  PDF and a 600-dpi PNG, and never committed.

Every count a figure prints is measured from this checkout when it is drawn
(:func:`measure`), never typed in, so a re-run picks up any change that moves
one. Measuring imports the registry, so run it in the project environment:

    uv run python docs/assets/architecture/make.py
    uv run python docs/assets/architecture/make.py --print ~/figures

Labels are fitted against the metrics of the face they are set in, CMU Serif
or Typewriter, and the run fails if one overflows its box or uses a glyph the
face lacks; each SVG embeds a subset of its faces (:func:`embedded_faces`).
Without those fonts installed the check and the embedding are skipped with a
warning. The ``print`` exports need ``rsvg-convert`` (librsvg) on PATH.

The figures are sized for a 6.5-inch column: one SVG unit is
6.5 in / 1000 = 0.468 pt in print, so a 15-unit label prints at 7 pt and
Fig. 4's 13-unit edge labels at 6.1 pt. Cut detail before shrinking type
further.
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
        "lane2": "#E4EBEA", "soft": "#8C9A9E",
    },
    "dark": {
        "bg": "#0D1117", "lane": "#151E23", "box": "#0D1117",
        "ink": "#E7EDEB", "ink2": "#A8B8BD", "rule": "#3A4D55", "line": "#8EA0A6",
        "accent": "#4FBECA", "accentSoft": "#0E3238",
        "warn": "#DE9A52", "warnSoft": "#38281A",
        "lane2": "#1D2930", "soft": "#5E7178",
    },
    # Grey lanes, white boxes, black type. Emphasis is carried by weight and
    # fill, never by colour alone.
    "print": {
        "bg": "#FFFFFF", "lane": "#EDEDED", "box": "#FFFFFF",
        "ink": "#000000", "ink2": "#333333", "rule": "#8A8A8A", "line": "#3F3F3F",
        "accent": "#000000", "accentSoft": "#DCDCDC",
        "warn": "#000000", "warnSoft": "#F4F4F4",
        "lane2": "#E0E0E0", "soft": "#8A8A8A",
    },
    # Fig. 4's print: neutral greys, black type, grey feedback.
    "mono": {
        "bg": "#FFFFFF", "lane": "#F5F5F5", "lane2": "#EBEBEB", "box": "#FFFFFF",
        "ink": "#000000", "ink2": "#737373", "rule": "#737373", "line": "#404040",
        "soft": "#9A9A9A", "accent": "#000000", "accentSoft": "#DCDCDC",
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
    # Code: identifiers as the source spells them.
    "tm": ("cmuntt.otf", 15, 'font-family: "MARS Figure Mono", "CMU Typewriter Text", '
           'ui-monospace, Menlo, Consolas, monospace;', "ink"),
    "tmA": ("cmuntt.otf", 15, 'font-family: "MARS Figure Mono", "CMU Typewriter Text", '
            'ui-monospace, Menlo, Consolas, monospace;', "accent"),
    # Fig. 4: names upright, data italic, edge labels small, feedback grey.
    "n": ("cmunrm.otf", 15, "", "ink"),
    "ni": ("cmunti.otf", 15, "font-style: italic;", "ink"),
    "ne": ("cmunrm.otf", 13, "", "ink"),
    "ng": ("cmunrm.otf", 13, "", "ink2"),
    "nf": ("cmunti.otf", 14, "font-style: italic;", "ink2"),
    "nl": ("cmunti.otf", 15, "font-style: italic;", "ink2"),
}
LINE_HEIGHT = {"t": 21, "tb": 21, "ts": 19, "ti": 19, "tl": 20, "tw": 19,
               "tm": 18, "tmA": 18, "n": 17, "ni": 17, "ne": 15, "ng": 15, "nf": 16, "nl": 17}

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
  .lnR {{ fill: none; stroke: {line}; stroke-width: 1.2; stroke-dasharray: 5 3; }}
  .act {{ fill: {accentSoft}; stroke: {accent}; stroke-width: 1; }}
  .frag {{ fill: none; stroke: {line}; stroke-width: 1; }}
  .fragTab {{ fill: {lane}; stroke: {line}; stroke-width: 1; }}
  .card {{ fill: {box}; stroke: {rule}; stroke-width: 1.2; }}
  .cardHead {{ fill: {lane}; stroke: {rule}; stroke-width: 1.2; }}
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


def _engine() -> dict[str, object]:
    """The agent engine's own vocabulary, as the code declares it."""

    import dataclasses
    import typing

    from tools.agent import approval, events, policy
    from tools.llm import base, types
    from tools.models import ToolResult
    from tools.runtime.limits import CallLimits

    limits = CallLimits()
    return {
        "faults": typing.get_args(types.FaultType),
        "stop_reasons": typing.get_args(types.StopReason),
        "dialects": typing.get_args(base.SchemaDialect),
        "risk_tags": typing.get_args(policy.RiskTag),
        "decisions": tuple(d.value for d in approval.Decision),
        "statuses": typing.get_args(ToolResult.model_fields["status"].annotation),
        "events": tuple(t.__name__ for t in typing.get_args(events.Event)),
        "http_timeout_s": base.BaseHTTPBackend._timeout_s,
        "call_timeout_s": limits.timeout_s,
        "call_memory_gib": limits.memory_bytes // 1024**3,
        "call_reply_mib": limits.reply_bytes // 1024**2,
        "call_download_mib": limits.download_bytes // 1024**2,
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
        "engine": _engine(),
    }


# --- Drawing ----------------------------------------------------------------


class _Metrics:
    """Advance widths of every face the figures use, for the overflow check."""

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
    #: Text classes drawn: only these are written into the figure's style.
    classes: set[str] = field(default_factory=set)
    #: CSS only this figure needs, formatted with the palette like STYLE.
    style: str = ""

    def _use(self, text: str, cls: str) -> None:
        filename = TEXT[cls][0]
        self.classes.add(cls)
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

    def lane(self, y, h, label, kind="lane", cls="tl"):
        """A full-width band, its label rotated; a newline splits the label.

        Every label of two or more lines starts in the same column, so a third
        line steps right rather than pushing the first off the canvas.
        """

        self.parts.append(f'<rect class="{kind}" x="0" y="{y}" width="{self.width}" height="{h}"/>')
        lines = label.split("\n")
        for i, line in enumerate(lines):
            cx, cy = 17, y + h / 2
            if len(lines) > 1:
                cx += round((i - 0.5) * LINE_HEIGHT[cls], 1)
            self._use(line, cls)
            self._check(line, cls, h - 8, f"lane {line!r}")
            self.parts.append(
                f'<text class="{cls}" x="{cx}" y="{cy}" text-anchor="middle" '
                f'dominant-baseline="central" transform="rotate(-90 {cx} {cy})">'
                f'{escape(line)}</text>'
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
# The Skynet 2 boxes are Skynet 2's own control and data pathway, collapsed
# into one lane, under its own names.


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


# --- Fig. 5 -- the agent engine, one turn at a time --------------------------
#
# The engine on its own, drawn the way a design document would: a sequence
# diagram of one turn, with the calls named as the code names them, and the
# vocabularies the loop speaks in beside it. Every identifier and enumeration
# is read from the code (:func:`_engine`); nothing here is proposed work.


def _wrap_words(words, width_chars: int, sep: str = "  ") -> list[str]:
    lines, line = [], ""
    for word in words:
        candidate = f"{line}{sep}{word}" if line else word
        if len(candidate) > width_chars and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def fig5(m: dict) -> tuple[Canvas, str, str]:
    e = m["engine"]
    c = Canvas(1000, 688)

    # --- The sequence diagram. ------------------------------------------------
    X = {"caller": 44, "loop": 172, "checks": 348, "tools": 440, "record": 530, "model": 622}
    heads = (("caller", "Caller", 76), ("loop", "Agent loop", 108), ("checks", "Checks", 84),
             ("tools", "Tools", 84), ("record", "Record", 84), ("model", "Model port", 96))
    top, bottom = 44, 566
    for key, label, w in heads:
        x = X[key]
        c.line((x, top), (x, bottom), kind="lnD")
        c.box(x - w / 2, 12, w, 32, [(label, "t")], pad=4)
    # The loop's activation bar: it holds control for the whole session.
    c.raw(f'<rect class="act" x="{X["loop"] - 5}" y="62" width="10" height="{548 - 62}"/>')

    def frame(x0, y0, x1, y1, guard):
        c.raw(f'<rect class="frag" x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}"/>')
        c.raw(f'<path class="fragTab" d="M {x0} {y0} H {x0 + 44} V {y0 + 14} L {x0 + 38} {y0 + 20} '
              f'H {x0} Z"/>')
        c.text(x0 + 6, y0 + 15, "loop", "tm", room=40)
        # The guard sits clear of the loop's activation bar.
        c.text(X["loop"] + 14, y0 + 15, f"[{guard}]", "ti", halo="halo", room=x1 - X["loop"] - 20)

    def call(y, a, b, label, accent=False, back=False):
        xa, xb = X[a] + (5 if a == "loop" else 0), X[b] - (5 if b == "loop" else 0)
        if xb < xa:
            xa, xb = X[a] - (5 if a == "loop" else 0), X[b] + (5 if b == "loop" else 0)
        kind = "lnR" if back else ("lnA" if accent else "ln")
        c.arrow((xa, y), (xb, y), kind=kind)
        left = min(xa, xb) + 6
        c.text(left, y - 6, label, "tmA" if accent else "tm", halo="halo",
               room=abs(xb - xa) - 8)

    def self_call(y, label, accent=False):
        x = X["loop"] + 5
        c.arrow((x, y - 8), (x + 24, y - 8), (x + 24, y + 6), (x, y + 6),
                kind="lnA" if accent else "ln")
        c.text(x + 32, y + 4, label, "tmA" if accent else "tm", halo="halo", room=420)

    def note(x, y, text, room):
        c.text(x, y, text, "ti", halo="halo", room=room)

    call(76, "caller", "loop", "run_session(…)")
    frame(20, 88, 660, 496, f"each turn, at most {m['max_turns']}")
    self_call(124, "should_stop()  pending_input()")
    call(154, "loop", "model", "complete(messages, tools, system, max_tokens)")
    call(182, "model", "loop", "ModelResponse(stop_reason, tool_calls, faults)", back=True)
    frame(108, 198, 652, 462, "each proposed tool call")
    call(234, "loop", "checks", "validate_tool_call()", accent=True)
    call(260, "checks", "loop", "fault | None", back=True)
    note(X["checks"] + 8, 258, "a fault: error result, tool not called", 300)
    call(288, "loop", "checks", "approver(proposed)", accent=True)
    call(314, "checks", "loop", "Decision", back=True)
    note(X["checks"] + 8, 312, "deny or stop: refused result", 300)
    self_call(342, "make_cache_key(name, args): hit reuses", accent=True)
    call(372, "loop", "tools", "functions[name](**args)", accent=True)
    call(398, "tools", "loop", "ToolResult", back=True)
    call(426, "loop", "record", "record_tool_call()  save()", accent=True)
    call(450, "loop", "caller", "yield", back=True)
    self_call(480, "append ToolResultBlock(is_error)")
    call(518, "loop", "record", "save(outcome)")
    call(542, "loop", "caller", "yield", back=True)
    c.text(X["caller"] - 24, 562, "SessionFinished.outcome: " + " | ".join(
        ("end_turn", "max_turns", "interrupted", "error")), "tm", halo="halo", room=620)

    # The event stream every caller reads.
    c.text(20, 596, f"yielded to the caller as it happens ({len(e['events'])} event types):",
           "ti", room=620)
    for i, line in enumerate(_wrap_words(e["events"], 78)):
        c.text(20, 616 + i * 18, line, "tm", room=640)

    # --- The vocabularies, as specification cards. ----------------------------
    cards = (
        ("Model port", [
            ("complete(messages, tools, system)", "tm"),
            ("dialects: " + ", ".join(e["dialects"][:1]) + ",", "tm"),
            (", ".join(e["dialects"][1:]), "tm"),
            # The OpenAI, Gemini and Ollama adapters; Anthropic's goes through its SDK.
            (f"httpx: TLS on, no redirects, {e['http_timeout_s']:g} s timeout", "ts"),
        ]),
        ("Protocol faults", [(line, "tm") for line in _wrap_words(e["faults"], 37)]),
        ("Approval", [
            ("risk tags: " + " | ".join(e["risk_tags"]), "tm"),
            ("Decision: " + " | ".join(e["decisions"]), "tm"),
            ("headless default: deny any tagged call", "ts"),
        ]),
        ("ToolResult", [
            ("status: " + "|".join(e["statuses"]), "tm"),
            ("count, preview[], columns", "tm"),
            ("artifacts[ArtifactRef]", "tm"),
            ("warnings[], errors[ToolError]", "tm"),
        ]),
        ("MCP path: mars-mcp over stdio", [
            ("additionalProperties: false", "tm"),
            ("run_call(): owned worker per call", "tm"),
            (f"limits: {e['call_timeout_s']:g} s, {e['call_memory_gib']} GiB, "
             f"{e['call_reply_mib']} MiB reply", "tm"),
        ]),
        ("Evaluation: mars-bench", [
            (f"{m['local']} live | {m['remote']} replayed | {m['mixed']} per call", "tm"),
            ("graders: answer, efficiency,", "tm"),
            ("trajectory, protocol", "tm"),
            ("no model grades a model; keys.lock", "ts"),
        ]),
    )
    y = 12
    for title, lines in cards:
        h = 30 + 18 * len(lines) + 8
        c.raw(f'<rect class="card" x="680" y="{y}" width="312" height="{h}" rx="2"/>')
        c.raw(f'<rect class="cardHead" x="680" y="{y}" width="312" height="26" rx="2"/>')
        c.text(690, y + 19, title, "tb", room=292)
        for i, (text, cls) in enumerate(lines):
            c.text(690, y + 46 + 18 * i, text, cls, room=296)
        y += h + 8
    if y - 8 > c.height - 4:
        c.overflows.append(f"cards end at {y - 8}, below the canvas ({c.height})")

    title = "The MARS agent engine: one turn, as the code runs it"
    alt = (
        "A sequence diagram of one agent turn across six lifelines: caller, agent loop, "
        "checks, tools, record and model. The caller calls run_session; for each turn, at "
        f"most {m['max_turns']}, the loop checks should_stop and pending_input, calls "
        "complete on the model port and receives a ModelResponse; for each proposed tool "
        "call it calls validate_tool_call, then the approver, then make_cache_key, then the "
        "tool function, which returns a ToolResult; it records the call and saves the "
        "manifest, and appends a ToolResultBlock for the next turn. The session ends with "
        "SessionFinished, whose outcome is end_turn, max_turns, interrupted or error. "
        f"Beside it, specification cards list the model port's schema dialects, the "
        f"{len(e['faults'])} protocol fault types, the approval risk tags and decisions, "
        "the ToolResult envelope, the MCP path's strict validation and owned worker per "
        "call, and the benchmark's tool plane and graders."
    )
    return c, title, alt


# --- Fig. 4 -- the agent loop -------------------------------------------------
#
# Drawn the way a system's control-and-data pathway is drawn: swimlanes, each
# component named and nothing more, data in dashed italic boxes, feedback in
# grey. The providers, tool groups and turn limit are read from the code.

LOOP_STYLE = """
  .lane2 {{ fill: {lane2}; }}
  .gBox {{ fill: {box}; stroke: {rule}; stroke-width: 1; }}
  .gData {{ fill: {box}; stroke: {soft}; stroke-width: 1; stroke-dasharray: 4 3; }}
  .gGroup {{ fill: none; stroke: {soft}; stroke-width: 1; }}
  .gLn {{ fill: none; stroke: {line}; stroke-width: 1.3; }}
  .gFb {{ fill: none; stroke: {soft}; stroke-width: 1.1; }}
  .gDash {{ fill: none; stroke: {soft}; stroke-width: 1.1; stroke-dasharray: 4 3; }}
  .gHd {{ fill: {line}; }}
  .gHdS {{ fill: {soft}; }}
"""

# Display names, keyed by the factory's provider prefix.
PROVIDER_NAMES = {"anthropic": "Anthropic", "openai": "OpenAI", "gemini": "Gemini",
                  "ollama": "Ollama"}
# What each MCP tool group does, keyed by group name.
GROUP_NAMES = {
    "databases": ("Catalogs &", "Archives"),
    "optical": ("Photometry &", "Plate Solving"),
    "timeseries": ("Pulsar &", "Variable Stars"),
    "hr": ("HR Diagrams &", "Isochrones"),
    "radio": ("Radio", "Sources"),
}


def _rounded(points, r=5) -> str:
    """Path data for an orthogonal polyline with its corners rounded."""

    def toward(p, q, k):
        dx, dy = q[0] - p[0], q[1] - p[1]
        n = abs(dx) + abs(dy)
        return f"{p[0] + dx / n * k:g} {p[1] + dy / n * k:g}"

    d = [f"M {points[0][0]:g} {points[0][1]:g}"]
    for a, p, b in zip(points, points[1:], points[2:]):
        k = min(r, (abs(p[0] - a[0]) + abs(p[1] - a[1])) / 2,
                (abs(b[0] - p[0]) + abs(b[1] - p[1])) / 2)
        d.append(f"L {toward(p, a, k)} Q {p[0]:g} {p[1]:g} {toward(p, b, k)}")
    d.append(f"L {points[-1][0]:g} {points[-1][1]:g}")
    return " ".join(d)


def fig_loop(m: dict) -> tuple[Canvas, str, str]:
    from tools.llm.factory import RECOGNIZED_PROVIDERS

    assert set(RECOGNIZED_PROVIDERS) == set(PROVIDER_NAMES), "name every provider"
    assert set(m["groups"]) == set(GROUP_NAMES), "name every tool group"

    c = Canvas(1000, 440)
    c.style = LOOP_STYLE
    c.raw('<defs>' + "".join(
        f'<marker id="{k}" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" '
        f'markerWidth="7.5" markerHeight="7.5" orient="auto-start-reverse">'
        f'<path class="{cls}" d="M0,0.8 L10,5 L0,9.2 L2.6,5 z"/></marker>'
        for k, cls in (("g", "gHd"), ("gS", "gHdS"))) + '</defs>')

    def flow(*points, kind="gLn", head=True, start=False):
        marker = "g" if kind == "gLn" else "gS"
        ends = (f' marker-start="url(#{marker})"' if start else "") + (
            f' marker-end="url(#{marker})"' if head else "")
        c.raw(f'<path class="{kind}" d="{_rounded(points)}"{ends}/>')

    def name(x, y, w, h, *lines, kind="gBox", cls="n"):
        c.box(x, y, w, h, [(s, cls) for s in lines], kind=kind, pad=5)

    def on_line(x, y, s, under, room):
        """A label set into a line, the line broken around it."""

        w = METRICS.width(s, "nf") if METRICS.available else 7 * len(s)
        c.raw(f'<rect class="{under}" x="{x - w / 2 - 6:.1f}" y="{y - 7}" '
              f'width="{w + 12:.1f}" height="14"/>')
        c.text(x, y + 4, s, "nf", anchor="middle", room=room)

    c.lane(28, 146, "User", cls="nl")
    c.lane(176, 96, "MARS\nAgent", kind="lane2", cls="nl")
    c.lane(296, 54, "Model", cls="nl")
    c.lane(352, 88, "Validated\nScientific\nTools", cls="nl")

    # User: three ways in, one conversation; the answer, three ways out.
    for y, lines in ((35, ("MARS", "Console")), (80, ("Python", "API")),
                     (125, ("Benchmark", "Harness"))):
        name(52, y, 86, 40, *lines)
    name(160, 79, 136, 42, "Conversation", "(question, results)", kind="gData", cls="ni")
    flow((138, 55), (176, 55), (176, 79))
    flow((138, 100), (160, 100))
    flow((138, 145), (176, 145), (176, 121))
    name(432, 110, 84, 40, "Researcher", "Approval", kind="gData")
    name(745, 79, 90, 42, "Answer and", "Artifacts", kind="gData", cls="ni")
    for y, lines in ((35, ("MARS", "Console")), (80, ("Python", "API")),
                     (125, ("Benchmark", "Graders"))):
        name(872, y, 96, 40, *lines)
    flow((835, 100), (854, 100), (854, 55), (872, 55))
    flow((854, 100), (872, 100))
    flow((854, 100), (854, 145), (872, 145))

    # The agent: every proposed call passes each box in turn.
    chain = ((230, 80, ("Model", "Port")), (332, 80, ("Schema", "Validation")),
             (434, 80, ("Approval", "Policy")), (536, 64, ("Call", "Cache")),
             (622, 80, ("Tool", "Dispatch")))
    for x, w, lines in chain:
        name(x, 210, w, 40, *lines)
    for (x0, w0, _), (x1, _, _) in zip(chain, chain[1:]):
        flow((x0 + w0, 230), (x1, 230))
    # What the record keeps, from AgentSession.to_manifest.
    c.box(750, 201, 186, 58, [("Session Record", "n"), ("(calls, arguments, outputs,", "ni"),
                              ("decisions, artifacts)", "ni")], kind="gBox", pad=5)
    flow((270, 121), (270, 210))
    flow((790, 201), (790, 121))
    flow((474, 150), (474, 210), kind="gDash", start=True)
    c.text(480, 167, "risk-tagged calls", "ne", room=150)
    # A call that fails its schema or is refused goes back as an error, unrun.
    flow((448, 210), (448, 194), (372, 194), kind="gDash", head=False)
    flow((372, 210), (372, 100), (296, 100), kind="gDash")
    c.text(334, 95, "errors", "ng", anchor="middle", room=70)

    # Results rise from the tools and go straight on to the conversation; the
    # session record takes a copy on the way. Feedback, as the pathway figures
    # draw it: grey, labelled in the line.
    flow((726, 366), (726, 230), (750, 230))
    c.text(732, 289, "structured results + artifact paths", "ne", room=230)
    flow((726, 230), (726, 44), (260, 44), (260, 79), kind="gFb")
    on_line(493, 44, f"tool results return to the model for the next turn "
                     f"(default limit: {m['max_turns']})", "lane", room=420)
    flow((790, 79), (790, 14), (40, 14), (40, 100), (52, 100), kind="gFb")
    flow((40, 55), (52, 55), kind="gFb")
    on_line(415, 14, "answers and saved sessions inform follow-up questions", "bg", room=700)

    # Model: any of the providers behind one port.
    c.raw('<rect class="gGroup" x="96" y="302" width="348" height="42" rx="3"/>')
    for i, provider in enumerate(PROVIDER_NAMES.values()):
        name(102 + i * 86, 308, 78, 30, provider)
    flow((258, 250), (258, 302))
    flow((282, 302), (282, 250))
    c.text(252, 289, "messages, tool schemas", "ne", anchor="end", room=140)
    c.text(288, 289, "proposed calls", "ne", room=120)

    # Tools: the groups, and the observing interface proposed for Skynet 2.
    c.raw('<rect class="gGroup" x="242" y="366" width="745" height="60" rx="3"/>')
    for i, group in enumerate(m["groups"]):
        name(248 + i * 123, 374, 118, 44, *GROUP_NAMES[group])
    c.box(863, 374, 118, 44, [("Skynet 2", "n"), ("(proposed)", "ni")], kind="gData", pad=5)
    flow((662, 250), (662, 366))
    c.text(656, 289, "validated call", "ne", anchor="end", room=120)

    groups = ", ".join(" ".join(GROUP_NAMES[g]).replace("& ", "and ").lower()
                       for g in m["groups"])
    title = "The MARS agent loop: from a question, through a language model and checked tool calls, to an answer"
    alt = (
        "A swimlane diagram in four lanes: user, MARS agent, model and validated scientific "
        "tools. A question "
        "enters from the MARS console, the Python API or the benchmark harness and becomes "
        "the conversation. The agent's model port sends the messages and tool schemas to "
        f"one of {len(PROVIDER_NAMES)} model providers ("
        + ", ".join(PROVIDER_NAMES.values()) + ") and receives proposed tool calls. Each "
        "call passes schema validation, an approval policy that asks a researcher before "
        "risk-tagged calls, and a repeat-call cache, then tool dispatch runs it on one of "
        f"{m['tools']} tools in {len(m['groups'])} groups ({groups}); a Skynet 2 observing "
        "interface is shown as proposed. A call that fails validation or is refused returns "
        "to the conversation as an error without running. Structured results and artifact "
        "paths return from the tools to the conversation for the model's next turn, by "
        f"default at most {m['max_turns']}, and are copied on the way into the session record, which "
        "keeps the calls, arguments, outputs, decisions and artifacts. The answer and artifacts go to the console, the Python caller "
        "and the benchmark graders; answers and saved sessions inform follow-up questions."
    )
    return c, title, alt


# (file stem, drawing function, palette of the --print export). The diagrams
# print in greyscale; the engine keeps its colour.
FIGURES = [
    ("fig-1-mars-as-built", fig1, "print"),
    ("fig-2-aim-2-proposed", fig2, "print"),
    ("fig-3-validation", fig3, "print"),
    ("fig-4-agent-loop", fig_loop, "mono"),
    ("fig-5-agent-engine", fig5, "light"),
]


# --- Output -----------------------------------------------------------------


# The CMU faces the figures use: (file, embedded family, CSS weight, style).
EMBEDDED = "MARS Figure Serif"
FACES = (
    ("cmunrm.otf", EMBEDDED, "normal", "normal"),
    ("cmunbx.otf", EMBEDDED, "bold", "normal"),
    ("cmunti.otf", EMBEDDED, "normal", "italic"),
    ("cmuntt.otf", "MARS Figure Mono", "normal", "normal"),
)


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
    for filename, family, weight, style in FACES:
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
            f'\n  @font-face {{ font-family: "{family}"; font-weight: {weight}; '
            f'font-style: {style}; src: url(data:font/woff;base64,{data}) format("woff"); }}'
        )
    return "".join(rules)


def render(canvas: Canvas, title: str, alt: str, theme: str, *, for_print: bool = False) -> str:
    palette = PALETTES[theme]
    text_classes = "\n".join(
        f"  .{cls} {{ font-size: {size}px; {css} fill: {palette[colour]}; }}"
        for cls, (_, size, css, colour) in TEXT.items()
        if cls in canvas.classes
    )
    faces = embedded_faces(canvas)
    serif = f'"{EMBEDDED}", {SERIF}' if faces else SERIF
    style = STYLE.format(serif=serif, faces=faces, text_classes=text_classes, **palette)
    if canvas.style:
        style += canvas.style.format(**palette)
    if for_print:
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
                        help="also write a print SVG, PDF and 600-dpi PNG of each here")
    args = parser.parse_args()

    if not METRICS.available:
        print("warning: a figure font is not installed; "
              "labels not fitted, faces not embedded", file=sys.stderr)
    m = measure()
    failed = False
    for name, draw, print_palette in FIGURES:
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
            path.write_text(render(canvas, title, alt, print_palette, for_print=True),
                            encoding="utf-8")
            export_print(path)
            print(f"wrote {path.with_suffix('')}.{{svg,pdf,png}}")
    if failed:
        sys.exit("labels overflow; widen the box or cut the text")


if __name__ == "__main__":
    main()
