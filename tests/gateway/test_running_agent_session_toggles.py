"""Regression tests: safe slash commands dispatch mid-agent-run.

When an agent is running, the gateway's running-agent guard must not execute
unsafe slash commands mid-turn. Safe control-plane commands dispatch directly;
unsafe commands are treated like ordinary busy follow-ups so the user gets the
queue/interrupt/steer controls instead of a dead-end warning.

A small allowlist bypasses that and actually dispatches:

  * /model — shows the picker or stores a session model override for the next
    model call/turn without stopping the active request.
  * /yolo — toggles the session yolo flag; useful to pre-approve a
    pending approval prompt without waiting for the agent to finish.
  * /verbose — cycles the per-platform tool-progress display mode;
    affects the ongoing stream.

Commands whose handlers say "takes effect on next message" go through busy
follow-up handling by design:

  * /fast — writes config.yaml only
  * /reasoning — writes config.yaml only

These tests lock in both behaviors so the allowlist doesn't silently
grow or shrink.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource, build_session_key


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )


def _make_event(text: str) -> MessageEvent:
    return MessageEvent(text=text, source=_make_source(), message_id="m1")


def _make_runner():
    """Minimal GatewayRunner with an active running agent for this session."""
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    adapter = MagicMock()
    adapter.send = AsyncMock()
    adapter._send_with_retry = AsyncMock(
        return_value=SimpleNamespace(success=True, message_id="ack-1")
    )
    adapter._pending_messages = {}
    adapter.config = SimpleNamespace(extra={})
    adapter.platform = Platform.TELEGRAM
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=False)

    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = session_entry
    runner.session_store.load_transcript.return_value = []
    runner.session_store.has_any_sessions.return_value = True
    runner.session_store.append_to_transcript = MagicMock()
    runner.session_store.rewrite_transcript = MagicMock()
    runner.session_store.update_session = MagicMock()
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._busy_input_mode = "interrupt"
    runner._busy_text_mode = "queue"
    runner._busy_ack_ts = {}
    runner._pending_followups = {}
    runner._tool_bubble_msg_ids = {}
    runner._busy_control_bubble_ids = {}
    runner._busy_ack_tool_bubble_defer_seconds = 0.0
    runner._draining = False
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._session_db = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._show_reasoning = False
    runner._service_tier = None
    runner._is_user_authorized = lambda _source: True
    runner._set_session_env = lambda _context: None
    runner._should_send_voice_reply = lambda *_args, **_kwargs: False
    runner._send_voice_reply = AsyncMock()
    runner._capture_gateway_honcho_if_configured = lambda *args, **kwargs: None
    runner._emit_gateway_run_progress = AsyncMock()

    # Simulate agent actively running for this session so the guard fires.
    # Note: the stale-eviction branch calls agent.get_activity_summary() and
    # compares seconds_since_activity against HERMES_AGENT_TIMEOUT. Return a
    # dict with recent activity so the eviction path doesn't clear our
    # fake running agent before the toggle guard runs.
    import time
    sk = build_session_key(_make_source())
    agent_mock = MagicMock()
    agent_mock.get_activity_summary.return_value = {
        "seconds_since_activity": 0.0,
        "last_activity_desc": "api_call",
        "api_call_count": 1,
        "max_iterations": 60,
    }
    runner._running_agents[sk] = agent_mock
    runner._running_agents_ts[sk] = time.time()
    return runner


@pytest.mark.asyncio
async def test_model_dispatches_mid_run(monkeypatch):
    """/model mid-run must show the picker/list, not tell user to /stop."""
    runner = _make_runner()
    runner._handle_model_command = AsyncMock(return_value="model picker")

    result = await runner._handle_message(_make_event("/model"))

    runner._handle_model_command.assert_awaited_once()
    assert result == "model picker"
    assert "wait or /stop first" not in (result or "")
    assert "can't run mid-turn" not in (result or "")


@pytest.mark.asyncio
async def test_yolo_dispatches_mid_run(monkeypatch):
    """/yolo mid-run must dispatch to its handler, not hit the catch-all."""
    runner = _make_runner()
    runner._handle_yolo_command = AsyncMock(return_value="⚡ YOLO mode **ON** for this session")

    result = await runner._handle_message(_make_event("/yolo"))

    runner._handle_yolo_command.assert_awaited_once()
    assert result == "⚡ YOLO mode **ON** for this session"
    assert "can't run mid-turn" not in (result or "")


@pytest.mark.asyncio
async def test_verbose_dispatches_mid_run(monkeypatch):
    """/verbose mid-run must dispatch to its handler, not hit the catch-all."""
    runner = _make_runner()
    runner._handle_verbose_command = AsyncMock(return_value="tool progress: new")

    result = await runner._handle_message(_make_event("/verbose"))

    runner._handle_verbose_command.assert_awaited_once()
    assert result == "tool progress: new"
    assert "can't run mid-turn" not in (result or "")


@pytest.mark.asyncio
async def test_fast_routes_to_busy_controls_mid_run():
    """/fast mid-run must not execute immediately or hard-block.

    It is an intentional follow-up. Route through normal busy handling so
    Telegram/Discord can show queue/interrupt/stop controls.
    """
    runner = _make_runner()
    runner._handle_fast_command = AsyncMock(
        side_effect=AssertionError("/fast should not dispatch mid-run")
    )
    sk = build_session_key(_make_source())

    result = await runner._handle_message(_make_event("/fast"))

    runner._handle_fast_command.assert_not_awaited()
    assert result is None
    assert "fast" in runner.adapters[Platform.TELEGRAM]._pending_messages[sk].text
    runner.adapters[Platform.TELEGRAM]._send_with_retry.assert_awaited_once()
    content = runner.adapters[Platform.TELEGRAM]._send_with_retry.call_args.kwargs["content"]
    assert "Interrupting current task" in content
    assert "can't run mid-turn" not in content


@pytest.mark.asyncio
async def test_reasoning_routes_to_busy_controls_mid_run():
    """/reasoning mid-run follows the same busy path as user text."""
    runner = _make_runner()
    runner._handle_reasoning_command = AsyncMock(
        side_effect=AssertionError("/reasoning should not dispatch mid-run")
    )
    sk = build_session_key(_make_source())

    result = await runner._handle_message(_make_event("/reasoning high"))

    runner._handle_reasoning_command.assert_not_awaited()
    assert result is None
    assert runner.adapters[Platform.TELEGRAM]._pending_messages[sk].text == "/reasoning high"
    runner.adapters[Platform.TELEGRAM]._send_with_retry.assert_awaited_once()
    content = runner.adapters[Platform.TELEGRAM]._send_with_retry.call_args.kwargs["content"]
    assert "Interrupting current task" in content
    assert "can't run mid-turn" not in content


@pytest.mark.parametrize("command_text", ["/model", "/model openai/gpt-5.5", "/undo", "/retry"])
@pytest.mark.asyncio
async def test_unsafe_slash_commands_route_to_busy_controls_mid_run(command_text):
    """Session/config slash commands typed mid-run become busy follow-ups."""
    runner = _make_runner()
    sk = build_session_key(_make_source())

    result = await runner._handle_message(_make_event(command_text))

    assert result is None
    assert runner.adapters[Platform.TELEGRAM]._pending_messages[sk].text == command_text
    runner.adapters[Platform.TELEGRAM]._send_with_retry.assert_awaited_once()
    content = runner.adapters[Platform.TELEGRAM]._send_with_retry.call_args.kwargs["content"]
    assert "Interrupting current task" in content
    assert "can't run mid-turn" not in content


@pytest.mark.asyncio
async def test_btw_dispatches_mid_run():
    """/btw mid-run must dispatch to /background's handler, not hit the catch-all.

    /btw is an alias of /background (see hermes_cli/commands.py). Typing
    /btw mid-turn must spawn a parallel background task — that's the whole
    point of the command. Before the mid-turn bypass was added for
    /background, /btw fell through to the "Agent is running — wait or
    /stop first" catch-all, making it useless in exactly the scenario it
    was designed for. The alias and the bypass together make it work.
    """
    runner = _make_runner()
    runner._handle_background_command = AsyncMock(
        return_value='🚀 Background task started: "what module owns titles?"'
    )

    result = await runner._handle_message(_make_event("/btw what module owns titles?"))

    runner._handle_background_command.assert_awaited_once()
    assert result is not None
    assert "can't run mid-turn" not in result
