import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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
    from gateway.run import GatewayRunner

    source = _make_source()
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    adapter = MagicMock()
    adapter.send = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(
        emit=AsyncMock(),
        emit_collect=AsyncMock(return_value=[]),
        loaded_hooks=False,
    )
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = SessionEntry(
        session_key=build_session_key(source),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner.session_store.load_transcript.return_value = []
    runner.session_store.has_any_sessions.return_value = True
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._session_run_generation = {}
    runner._session_db = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._show_reasoning = False
    runner._is_user_authorized = lambda _source: True
    runner._set_session_env = lambda _context: None
    runner._should_send_voice_reply = lambda *_args, **_kwargs: False
    runner._send_voice_reply = AsyncMock()
    runner._capture_gateway_honcho_if_configured = lambda *args, **kwargs: None
    runner._emit_gateway_run_progress = AsyncMock()
    runner._is_telegram_topic_root_lobby = lambda _source: False
    runner._should_send_telegram_lobby_reminder = lambda _source: False
    return runner


def test_telegram_ulw_plugin_payload_forwards_to_agent(monkeypatch):
    payload = {
        "display": "Started LazyHermes Ultrawork run: /tmp/lazyhermes-run",
        "agent_message": "inspect this folder",
        "run_dir": "/tmp/lazyhermes-run",
    }
    seen = {}

    async def _capture(event, source, _quick_key, _run_generation):
        seen["text"] = event.text
        return "FORWARDED"

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "hermes_cli.plugins.get_plugin_command_handler",
        lambda name: (lambda _args: payload) if name == "ulw-loop" else None,
    )

    runner = _make_runner()
    runner._handle_message_with_agent = _capture

    result = asyncio.run(runner._handle_message(_make_event("/ulw_loop inspect this folder")))

    assert result == "FORWARDED"
    assert seen["text"] == "inspect this folder"


def test_telegram_ulw_plan_plugin_forwards_goal_bootstrap(monkeypatch):
    payload = {
        "display": "Created LazyHermes plan: /tmp/plan.md\nForwarding goal bootstrap to Hermes agent now.",
        "agent_message": "global rollout\n\n<lazyhermes-goal-instruction>\nFirst call get_goal.\n</lazyhermes-goal-instruction>",
        "plan": "/tmp/plan.md",
    }
    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "hermes_cli.plugins.get_plugin_command_handler",
        lambda name: (lambda _args: payload) if name == "ulw-plan" else None,
    )

    seen = {}

    async def _capture(event, source, _quick_key, _run_generation):
        seen["text"] = event.text
        return "FORWARDED"

    runner = _make_runner()
    runner._handle_message_with_agent = _capture

    result = asyncio.run(runner._handle_message(_make_event("/ulw_plan global rollout")))

    assert result == "FORWARDED"
    assert "First call get_goal" in seen["text"]
