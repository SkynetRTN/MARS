"""M3 pulsar controls (``docs/working/master-continuation-plan.md``).

Background subtraction, plot labels, background and size controls existed in
Python but not in the registered schemas, while the guidance told callers to
"vary back_scale" on a tool that has no such parameter. This pins which
controls are public, that the schemas say so, that a registered caller cannot
reach the rest, and that the guidance matches. The decision and its reasons
are in ``docs/pulsar-tool-pipeline.md`` ("Public and Python-only controls").
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import tools.pulsar as pulsar
from tools.llm.validation import index_schemas, validate_tool_call
from tools.registry import TOOL_SCHEMAS

ROOT = Path(__file__).resolve().parents[1]

#: The supported public controls, per tool.
PUBLIC = {
    "load_pulsar_lightcurve": {"path", "back_scale", "subtract_background", "output_name"},
    "compute_pulsar_periodogram": {"path", "start", "stop", "steps", "freq_mode", "channel", "output_name"},
    "fold_pulsar_lightcurve": {"path", "period_s", "bins", "phase", "display_period", "output_name"},
    "sonify_pulsar": {"path", "period_s", "bins", "speed", "stereo", "audio_seconds", "seed", "output_name"},
    "plot_pulsar": {"path", "kind", "title", "show_hidden_series", "output_name"},
}

#: Python-only controls: accepted by the functions, refused from a registered caller.
PYTHON_ONLY = {
    "compute_pulsar_periodogram": {"back_scale", "subtract_background"},
    "fold_pulsar_lightcurve": {"cal", "back_scale", "subtract_background"},
    "sonify_pulsar": {"phase", "cal", "back_scale", "subtract_background", "max_input_seconds", "sample_rate"},
    "plot_pulsar": {"x_label", "y_label", "back_scale", "subtract_background", "dpi", "figsize"},
}


def _schema(name: str) -> dict:
    return next(tool for tool in TOOL_SCHEMAS if tool["name"] == name)


@pytest.mark.parametrize("name", sorted(PUBLIC))
def test_the_public_controls_are_exactly_the_registered_ones(name):
    assert set(_schema(name)["input_schema"]["properties"]) == PUBLIC[name]


@pytest.mark.parametrize("name", sorted(PYTHON_ONLY))
def test_python_only_controls_stay_in_python_and_out_of_reach(name):
    signature = set(inspect.signature(getattr(pulsar, name)).parameters)
    assert PYTHON_ONLY[name] <= signature
    index = index_schemas(TOOL_SCHEMAS)
    required = {"path": "x", "period_s": 1.0}
    base = {key: required[key] for key in _schema(name)["input_schema"].get("required", [])}
    for control in PYTHON_ONLY[name]:
        fault = validate_tool_call(name, {**base, control: 1}, index)
        assert fault is not None and control in fault.detail, control


def test_every_python_parameter_is_classified():
    # A new parameter must be decided on, not left hidden by accident.
    server_side = {"subdir", "directory"}
    for name in PUBLIC:
        signature = set(inspect.signature(getattr(pulsar, name)).parameters)
        assert signature - server_side == PUBLIC[name] | PYTHON_ONLY.get(name, set()), name


# --- guidance matches the schemas ------------------------------------------------


def _guidance_texts() -> dict[str, str]:
    from tools.agent.prompt import SYSTEM_PROMPT

    texts = {"prompt": SYSTEM_PROMPT}
    for path in (ROOT / "tools/skill/source").rglob("*.md"):
        texts[str(path.relative_to(ROOT))] = path.read_text(encoding="utf-8")
    for tool in TOOL_SCHEMAS:
        if "pulsar" in tool["name"]:
            texts[tool["name"]] = tool["description"]
    return texts


def test_guidance_never_asks_for_back_scale_where_it_is_not_accepted():
    # back_scale is public on load_pulsar_lightcurve only: any advice to vary
    # it must say to rerun that stage.
    for where, text in _guidance_texts().items():
        for paragraph in text.split("\n\n"):
            if "back_scale" in paragraph.replace("\n", " ") and "vary" in paragraph.lower():
                assert "load_pulsar_lightcurve" in paragraph or "at load" in paragraph, (where, paragraph[:200])


def test_the_sonify_schema_no_longer_offers_background_controls():
    description = _schema("sonify_pulsar")["description"]
    assert "load_pulsar_lightcurve" in description


# --- an ignored background setting is reported ----------------------------------


@pytest.fixture(scope="module")
def artifact(tmp_path_factory):
    import tools.artifacts as artifacts_module

    scan = pulsar.resolve_pulsar_scan("B0329+54").path
    original = artifacts_module.ARTIFACT_DIR
    artifacts_module.ARTIFACT_DIR = tmp_path_factory.mktemp("artifacts")
    try:
        loaded = pulsar.load_pulsar_lightcurve(scan)
        assert loaded.errors == []
        yield loaded.artifact.path, scan
    finally:
        artifacts_module.ARTIFACT_DIR = original


CALLS = {
    "compute_pulsar_periodogram": lambda path, **kw: pulsar.compute_pulsar_periodogram(path, steps=200, **kw),
    "fold_pulsar_lightcurve": lambda path, **kw: pulsar.fold_pulsar_lightcurve(path, 0.714, **kw),
    "sonify_pulsar": lambda path, **kw: pulsar.sonify_pulsar(path, period_s=0.714, audio_seconds=0.5, **kw),
    "plot_pulsar": lambda path, **kw: pulsar.plot_pulsar(path, **kw),
}


@pytest.mark.parametrize("name", sorted(CALLS))
@pytest.mark.parametrize("settings", [{"back_scale": 6.0}, {"subtract_background": False}])
def test_background_settings_on_an_artifact_are_reported_as_ignored(artifact, artifact_dir, name, settings):
    path, _scan = artifact
    result = CALLS[name](path, **settings)
    assert result.errors == []
    (warning,) = [w for w in result.warnings if w.code == "background_settings_ignored"]
    assert "load_pulsar_lightcurve" in warning.message


@pytest.mark.parametrize("name", sorted(CALLS))
def test_default_background_settings_on_an_artifact_warn_nothing(artifact, artifact_dir, name):
    path, _scan = artifact
    result = CALLS[name](path)
    assert "background_settings_ignored" not in {w.code for w in result.warnings}


def test_background_settings_on_a_raw_scan_are_applied_not_reported(artifact, artifact_dir):
    _path, scan = artifact
    result = pulsar.compute_pulsar_periodogram(scan, steps=200, back_scale=6.0)
    assert "background_settings_ignored" not in {w.code for w in result.warnings}
