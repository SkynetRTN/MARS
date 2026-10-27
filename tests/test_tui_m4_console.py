"""M4's console fixes: accurate first-launch and failure messages, the five
commands that had no handler, keyboard approvals, and tool calls that report
their own status instead of a tick."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from textual.widgets import Button, Static

from tools.agent.approval import Decision
from tools.agent.events import ToolCallProposed
from tools.agent.policy import SessionPolicy
from tools.agent.prompt import SYSTEM_PROMPT
from tools.llm.base import BackendUnavailableError
from tools.llm.types import Message, TextBlock
from tools.tui import backends
from tools.tui.app import ApprovalModal, MARSApp
from tools.tui.commands import COMMANDS
from tools.tui.widgets.tool_node import ToolNode, _duration
from tools.tui.widgets.transcript import Transcript


def _run(coroutine):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        executor = loop._default_executor
        if executor is not None:
            executor.shutdown(wait=True)
        loop.close()


def _rendered(app: MARSApp) -> str:
    transcript = app.query_one("#transcript", Transcript)
    return "\n".join(str(entry.render()) for entry in transcript.query(Static))


async def _type(pilot, text: str) -> None:
    for character in text:
        await pilot.press("space" if character == " " else character)
    await pilot.press("enter")
    await pilot.pause()


# ---------------------------------------------------------------------------
# First launch: where the key goes depends on how MARS was installed


def test_an_installed_copy_is_not_told_to_edit_a_repository_env(monkeypatch):
    monkeypatch.setattr(backends, "is_checkout", lambda: False)

    message = backends.unavailable_message(
        "anthropic/claude-sonnet-5", BackendUnavailableError("ANTHROPIC_API_KEY")
    )

    assert ".env" not in message
    assert "repository" not in message
    assert "ANTHROPIC_API_KEY" in message
    assert "`mars --backend ollama`" in message


def test_a_checkout_is_still_pointed_at_its_env_file(monkeypatch):
    monkeypatch.setattr(backends, "is_checkout", lambda: True)

    message = backends.unavailable_message(
        "anthropic/claude-sonnet-5", BackendUnavailableError("ANTHROPIC_API_KEY")
    )

    assert ".env" in message


def test_inside_the_console_the_local_model_is_offered_as_a_command(monkeypatch):
    monkeypatch.setattr(backends, "is_checkout", lambda: False)

    message = backends.unavailable_message(
        "anthropic/claude-sonnet-5",
        BackendUnavailableError("ANTHROPIC_API_KEY"),
        "ollama/qwen3:8b",
    )

    assert "`/backend ollama`" in message
    assert "mars --backend" not in message
    assert message.endswith("Still on ollama/qwen3:8b.")


def test_a_missing_default_model_names_how_to_pick_another_at_launch():
    """The default Ollama tag may not exist off Apple Silicon; the launcher
    has no picker, so the message has to say what to type."""

    exc = backends.ModelNotInstalled(
        "ollama/qwen3.8:27b-mlx", "qwen3.8:27b-mlx", ("llama3.1:8b",)
    )

    message = backends.unavailable_message("ollama/qwen3.8:27b-mlx", exc)

    assert "llama3.1:8b" in message
    assert "`mars --backend ollama/llama3.1:8b`" in message
    assert "`ollama pull qwen3.8:27b-mlx`" in message


def test_ollama_not_installed_says_where_to_get_it(monkeypatch):
    """A daemon that does not answer may not exist: `ollama serve` alone is
    then a command the person does not have."""

    monkeypatch.setattr(backends.shutil, "which", lambda name: None)

    message = backends.unavailable_message(
        "ollama/qwen3:8b", BackendUnavailableError("OLLAMA_BASE_URL")
    )

    assert "Ollama is not installed here" in message
    assert "https://ollama.com" in message


# ---------------------------------------------------------------------------
# A failure mid-turn names its cause and a next step


class _StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__("request echoed back: secret-ish detail")
        self.status_code = status_code


class _ResponseError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__("raw provider text")
        self.response = SimpleNamespace(status_code=status_code)


class ReadTimeout(Exception):
    pass


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (_StatusError(401), "check its API key"),
        (_ResponseError(404), "ollama pull"),
        (_StatusError(429), "rate-limiting"),
        (_StatusError(503), "server error (HTTP 503)"),
        (ReadTimeout(), "did not answer in time"),
        (ConnectionRefusedError(), "Could not reach"),
        (KeyError("x"), "unexpected KeyError"),
    ],
)
def test_failure_message_names_the_cause_without_the_exception_text(exc, expected):
    message = backends.failure_message(exc, "ollama/qwen3:8b")

    assert expected in message
    assert "Send your question again" in message
    assert "secret-ish" not in message
    assert "raw provider text" not in message


def test_failure_message_claims_a_saved_session_only_when_there_is_one():
    assert "is saved" in backends.failure_message(KeyError(), saved=True)
    assert "is saved" not in backends.failure_message(KeyError(), saved=False)


def test_failure_message_reuses_the_unavailable_wording(monkeypatch):
    monkeypatch.setattr(backends, "is_checkout", lambda: False)

    message = backends.failure_message(
        BackendUnavailableError("OLLAMA_BASE_URL"), "ollama/qwen3:8b"
    )

    assert "ollama serve" in message
    assert "Send your question again" in message


def test_a_key_lost_mid_session_is_told_the_in_console_command(monkeypatch):
    monkeypatch.setattr(backends, "is_checkout", lambda: False)

    message = backends.failure_message(
        BackendUnavailableError("ANTHROPIC_API_KEY"), "anthropic/claude-sonnet-5"
    )

    assert "`/backend ollama`" in message
    assert "mars --backend" not in message


def test_a_spec_at_the_start_of_a_failure_keeps_its_case():
    message = backends.failure_message(_StatusError(401), "ollama/llama3.1")

    assert message.startswith("ollama/llama3.1 refused")
    assert backends.failure_message(KeyError()).startswith("The session stopped")


# ---------------------------------------------------------------------------
# Tool calls show their own status


def _finished(result: dict) -> str:
    # The fields finish() sets, without the repaint that needs a running app.
    node = ToolNode.__new__(ToolNode)
    node.state = "finished"
    node.cache_hit = False
    node.result = result
    node.duration_ms = 12.0
    status, details = node._summary()
    return f"{status}{details}"


def test_a_tool_that_returned_an_error_is_not_ticked():
    summary = _finished(
        {
            "status": "error",
            "errors": [{"code": "dependency_missing", "message": "No ADS API token configured."}],
        }
    )

    assert summary.startswith("✗")
    assert "No ADS API token configured." in summary


def test_only_an_ok_result_gets_the_tick():
    assert _finished({"status": "ok"}).startswith("✓")
    assert _finished({"status": "not_found"}).startswith("∅")
    partial = _finished(
        {"status": "partial", "warnings": [{"code": "x", "message": "row limit hit"}]}
    )
    assert partial.startswith("!")
    assert "row limit hit" in partial


def test_long_durations_read_in_seconds_and_minutes():
    assert _duration(250) == "250 ms"
    assert _duration(14_200) == "14.2 s"
    assert _duration(285_000) == "4 min 45 s"


# ---------------------------------------------------------------------------
# Every listed command has a handler


def test_every_registered_command_has_a_handler():
    missing = [c.name for c in COMMANDS if not callable(getattr(MARSApp, c.handler, None))]

    assert missing == []


def test_status_names_the_backend_and_session():
    async def scenario() -> None:
        app = MARSApp(backend=SimpleNamespace(spec="stub/model"))
        async with app.run_test() as pilot:
            await _type(pilot, "/status")
            rendered = _rendered(app)
            assert "Backend: stub/model" in rendered
            assert "Session: none yet" in rendered
            assert app.engine_starts == 0

    _run(scenario())


def test_tools_lists_every_tool_and_describes_one():
    from tools.registry import TOOL_SCHEMAS

    async def scenario() -> None:
        app = MARSApp(backend=object())
        async with app.run_test() as pilot:
            await _type(pilot, "/tools")
            rendered = _rendered(app)
            assert f"{len(TOOL_SCHEMAS)} tools" in rendered
            assert "* plot_pulsar" in rendered
            assert "+ search_mast" in rendered
            assert "+ solve_astrometry" in rendered
            await _type(pilot, "/tools search_simbad")
            assert "Parameters:" in _rendered(app)
            await _type(pilot, "/tools nope")
            assert "Unknown tool: nope" in _rendered(app)

    _run(scenario())


def test_prompt_shows_the_system_prompt():
    async def scenario() -> None:
        app = MARSApp(backend=object())
        async with app.run_test() as pilot:
            await _type(pilot, "/prompt")
            assert SYSTEM_PROMPT.strip().splitlines()[0] in _rendered(app)

    _run(scenario())


def test_approve_shows_and_resets_allow_always():
    async def scenario() -> None:
        app = MARSApp(backend=object())
        async with app.run_test() as pilot:
            app.policy._always_allowed.add(("plot_pulsar", frozenset({"writes"})))
            await _type(pilot, "/approve")
            assert "Always allowed now: plot_pulsar" in _rendered(app)
            await _type(pilot, "/approve reset")
            assert app.policy.always_allowed == frozenset()
            assert "Approvals reset" in _rendered(app)

    _run(scenario())


def test_new_clears_the_conversation_without_restarting():
    async def scenario() -> None:
        app = MARSApp(backend=object())
        async with app.run_test() as pilot:
            app._history = (Message(role="user", blocks=(TextBlock(text="M31?"),)),)
            app.artifact_count = 3
            app.query_one("#transcript", Transcript).append_notice("old entry")
            await _type(pilot, "/new")
            assert app._history == ()
            assert app.artifact_count == 0
            rendered = _rendered(app)
            assert "old entry" not in rendered
            assert "New conversation." in rendered

    _run(scenario())


def test_new_refuses_while_a_session_is_running(monkeypatch):
    async def scenario() -> None:
        app = MARSApp(backend=object())
        async with app.run_test() as pilot:
            monkeypatch.setattr(app, "_session_running", lambda: True)
            app._history = (Message(role="user", blocks=(TextBlock(text="M31?"),)),)
            app.new_session(())
            await pilot.pause()
            assert app._history != ()
            assert "still running" in _rendered(app)

    _run(scenario())


def test_session_policy_reset_forgets_allow_always():
    policy = SessionPolicy(lambda proposed: Decision.ALLOW_ALWAYS)
    policy.approve(ToolCallProposed("c1", "plot_pulsar", {}))

    assert {name for name, _ in policy.always_allowed} == {"plot_pulsar"}
    policy.reset()
    assert policy.always_allowed == frozenset()


# ---------------------------------------------------------------------------
# Approvals from the keyboard


@pytest.mark.parametrize(
    ("keys", "expected"),
    [
        (("n",), Decision.DENY),
        (("escape",), Decision.DENY),
        (("enter",), Decision.DENY),
        (("left", "left", "enter"), Decision.ALLOW),
        (("left", "enter"), Decision.ALLOW_ALWAYS),
    ],
)
def test_the_approval_modal_answers_from_the_keyboard(monkeypatch, keys, expected):
    monkeypatch.setattr(ApprovalModal, "GRACE_S", 0.0)
    decisions: list[Decision | None] = []

    async def scenario() -> None:
        app = MARSApp(backend=object())
        async with app.run_test() as pilot:
            modal = ApprovalModal(ToolCallProposed("c1", "plot_pulsar", {}))
            app.push_screen(modal, decisions.append)
            await pilot.pause()
            assert app.focused is modal.query_one("#deny", Button)
            await pilot.press(*keys)
            await pilot.pause()

    _run(scenario())

    assert decisions == [expected]


def test_no_letter_allows_a_call(monkeypatch):
    """The rest of a sentence typed for the prompt lands in the dialog: the
    `a` in "galaxy" once allowed a call always."""

    monkeypatch.setattr(ApprovalModal, "GRACE_S", 0.0)
    decisions: list[Decision | None] = []

    async def scenario() -> None:
        app = MARSApp(backend=object())
        async with app.run_test() as pilot:
            modal = ApprovalModal(ToolCallProposed("c1", "plot_pulsar", {}))
            app.push_screen(modal, decisions.append)
            await pilot.pause()
            await pilot.press(*"what does this galaxy look like")
            await pilot.pause()
            assert app.screen is modal

    _run(scenario())

    assert decisions == []


def test_a_deny_is_never_held_back_by_the_grace_period():
    decisions: list[Decision | None] = []

    async def scenario() -> None:
        app = MARSApp(backend=object())
        async with app.run_test() as pilot:
            modal = ApprovalModal(ToolCallProposed("c1", "plot_pulsar", {}))
            app.push_screen(modal, decisions.append)
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

    _run(scenario())

    assert decisions == [Decision.DENY]


def test_an_allow_as_the_approval_opens_is_ignored():
    """The prompt is live during a turn: an Enter meant for a note must not
    approve a call whose dialog appeared under it, even with Allow focused."""

    decisions: list[Decision | None] = []

    async def scenario() -> None:
        app = MARSApp(backend=object())
        async with app.run_test() as pilot:
            modal = ApprovalModal(ToolCallProposed("c1", "plot_pulsar", {}))
            app.push_screen(modal, decisions.append)
            await pilot.pause()
            await pilot.press("left", "left", "enter")
            await pilot.pause()
            assert app.screen is modal

    _run(scenario())

    assert decisions == []


def test_a_tool_listing_line_says_what_the_tool_does():
    from tools.tui.app import _first_sentence

    assert _first_sentence("Stage 0. Resolve an optical frame by name or path.") == (
        "Stage 0. Resolve an optical frame by name or path."
    )
    assert _first_sentence(
        "Search VizieR tables, e.g. a catalog by its name. More here."
    ) == "Search VizieR tables, e.g. a catalog by its name."
    assert len(_first_sentence("word " * 100)) <= 140


def test_a_truncated_ollama_prompt_says_how_to_widen_the_window():
    message = backends.failure_message(
        BackendUnavailableError("OLLAMA_CONTEXT_LENGTH"), "ollama/qwen3:0.6b"
    )

    assert "OLLAMA_CONTEXT_LENGTH=32768 ollama serve" in message


def test_an_ollama_timeout_says_what_ran_out():
    message = backends.failure_message(
        BackendUnavailableError("OLLAMA_TIMEOUT_S"), "ollama/qwen3:0.6b"
    )

    assert "did not finish a turn within OLLAMA_TIMEOUT_S" in message
