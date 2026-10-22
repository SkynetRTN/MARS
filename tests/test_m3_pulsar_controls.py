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
import re
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

#: Words that make a paragraph advice to change back_scale.
_RETUNE = re.compile(r"\b(vary|varying|retune|retry|different|change|try)\b", re.IGNORECASE)


def _guidance_texts() -> dict[str, str]:
    from tools.agent.prompt import SYSTEM_PROMPT

    texts = {"prompt": SYSTEM_PROMPT}
    for path in [*(ROOT / "tools/skill/source").rglob("*.md"),
                 ROOT / "docs/pulsar-tool-pipeline.md", ROOT / "CLAUDE.md"]:
        texts[str(path.relative_to(ROOT))] = path.read_text(encoding="utf-8")
    for tool in TOOL_SCHEMAS:
        if "pulsar" in tool["name"]:
            texts[tool["name"]] = tool["description"]
    for name in ("compute_pulsar_periodogram", "fold_pulsar_lightcurve", "sonify_pulsar", "plot_pulsar"):
        texts[f"{name} docstring"] = inspect.getdoc(getattr(pulsar, name))
    return texts


def test_retune_advice_for_back_scale_always_names_the_stage_that_takes_it():
    # back_scale is public on load_pulsar_lightcurve only: advice to change it
    # anywhere must say to rerun that stage.
    offenders = []
    for where, text in _guidance_texts().items():
        for paragraph in re.split(r"\n\s*\n", text):
            flat = " ".join(paragraph.split())
            if "back_scale" in flat and _RETUNE.search(flat) and not (
                "load_pulsar_lightcurve" in flat or "at load" in flat
            ):
                offenders.append((where, flat[:160]))
    assert offenders == []


def test_the_sonify_schema_no_longer_offers_background_controls():
    description = _schema("sonify_pulsar")["description"]
    assert "load_pulsar_lightcurve" in description


# --- an ignored background setting is reported, truthfully ------------------------


@pytest.fixture(scope="module")
def artifacts_root(tmp_path_factory):
    import tools.artifacts as artifacts_module

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(artifacts_module, "ARTIFACT_DIR", tmp_path_factory.mktemp("artifacts"))
        yield artifacts_module.ARTIFACT_DIR


@pytest.fixture(scope="module")
def scan():
    return pulsar.resolve_pulsar_scan("B0329+54").path


@pytest.fixture(scope="module")
def artifact(artifacts_root, scan):
    loaded = pulsar.load_pulsar_lightcurve(scan)
    assert loaded.errors == []
    return loaded.artifact.path


@pytest.fixture(scope="module")
def unsubtracted_artifact(artifacts_root, scan):
    loaded = pulsar.load_pulsar_lightcurve(scan, subtract_background=False, output_name="raw_baseline")
    assert loaded.errors == []
    return loaded.artifact.path


CALLS = {
    "compute_pulsar_periodogram": lambda path, **kw: pulsar.compute_pulsar_periodogram(path, steps=200, **kw),
    "fold_pulsar_lightcurve": lambda path, **kw: pulsar.fold_pulsar_lightcurve(path, 0.714, **kw),
    "sonify_pulsar": lambda path, **kw: pulsar.sonify_pulsar(path, period_s=0.714, audio_seconds=0.5, **kw),
    "plot_pulsar": lambda path, **kw: pulsar.plot_pulsar(path, **kw),
    "load_pulsar_lightcurve": lambda path, **kw: pulsar.load_pulsar_lightcurve(path, **kw),
}


def _ignored(result):
    return [w.message for w in result.warnings if w.code == "background_settings_ignored"]


@pytest.mark.parametrize("name", sorted(CALLS))
@pytest.mark.parametrize("settings", [{"back_scale": 6.0}, {"subtract_background": False}])
def test_a_setting_the_artifact_does_not_record_is_reported(artifact, name, settings):
    result = CALLS[name](artifact, **settings)
    assert result.errors == []
    (message,) = _ignored(result)
    assert "back_scale=3 s" in message  # what the artifact actually records
    # Never circular: it asks for the raw scan, not a rerun with the artifact.
    assert "Pass the raw scan to load_pulsar_lightcurve" in message


@pytest.mark.parametrize("name", sorted(CALLS))
def test_settings_matching_the_artifact_are_not_reported(artifact, name):
    # Was a false positive: back_scale equal to what the artifact records.
    assert _ignored(CALLS[name](artifact, back_scale=3.0, subtract_background=True)) == []
    assert _ignored(CALLS[name](artifact)) == []


def test_an_explicit_default_differing_from_the_artifact_is_reported(artifacts_root, scan):
    # Was a false negative: back_scale=3.0 asked of an artifact loaded at 6.0.
    loaded = pulsar.load_pulsar_lightcurve(scan, back_scale=6.0, output_name="wide_baseline")
    (message,) = _ignored(pulsar.compute_pulsar_periodogram(loaded.artifact.path, steps=200, back_scale=3.0))
    assert "back_scale=6 s" in message


def test_the_message_describes_an_unsubtracted_artifact_truthfully(unsubtracted_artifact):
    (message,) = _ignored(pulsar.compute_pulsar_periodogram(unsubtracted_artifact, steps=200, back_scale=6.0))
    assert "written without background subtraction" in message
    assert _ignored(pulsar.fold_pulsar_lightcurve(unsubtracted_artifact, 0.714, subtract_background=False)) == []


def test_a_periodogram_artifact_is_not_attributed_to_stage_one(artifact):
    periodogram = pulsar.compute_pulsar_periodogram(artifact, steps=200)
    (message,) = _ignored(pulsar.plot_pulsar(periodogram.artifact.path, back_scale=6.0))
    assert "periodogram or folded artifact" in message
    assert "load_pulsar_lightcurve wrote" not in message


def test_background_settings_on_a_raw_scan_are_applied_not_reported(artifacts_root, scan):
    result = pulsar.compute_pulsar_periodogram(scan, steps=200, back_scale=6.0)
    assert _ignored(result) == []
