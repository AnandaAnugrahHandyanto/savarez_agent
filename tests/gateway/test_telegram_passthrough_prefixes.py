"""Tests for the TELEGRAM_PASSTHROUGH_PREFIXES env-var slash whitelist in
gateway/run.py.

Drives the real ``GatewayRunner._handle_message`` path with a stub session
store so we exercise the actual env-var check inserted at the dispatch
site. Uses the same ``object.__new__`` runner construction pattern as
test_slash_access_dispatch.py.

Coverage targets:
  - Backward compat: env var unset → unknown command still returns the
    standard ``Unknown command `/foo`...`` notice.
  - Match (with leading slash): ``TELEGRAM_PASSTHROUGH_PREFIXES="/foo"`` +
    ``/foo`` from user → notice is NOT returned (request falls through to
    the agent dispatch path, which we stub).
  - Match (without leading slash): same as above but with
    ``TELEGRAM_PASSTHROUGH_PREFIXES="foo"``.
  - Case insensitive: ``/FOO`` matches when env lists ``foo``.
  - Multiple comma-separated entries with surrounding whitespace.
  - Non-matching token with env var set: still returns the standard notice.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource


def _make_source(
    *,
    platform: Platform = Platform.TELEGRAM,
    user_id: str = "user1",
    chat_type: str = "dm",
    chat_id: str = "c1",
) -> SessionSource:
    return SessionSource(
        platform=platform,
        user_id=user_id,
        chat_id=chat_id,
        user_name=f"name-{user_id}",
        chat_type=chat_type,
    )


def _make_event(text: str, source: SessionSource) -> MessageEvent:
    return MessageEvent(text=text, source=source, message_id="m1")


def _make_runner(*, platform: Platform = Platform.TELEGRAM):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={
            platform: PlatformConfig(
                enabled=True,
                token="***",
                extra={},
            )
        }
    )
    adapter = MagicMock()
    adapter.send = AsyncMock()
    runner.adapters = {platform: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(
        emit=AsyncMock(),
        emit_collect=AsyncMock(return_value=[]),
        loaded_hooks=False,
    )
    runner.session_store = MagicMock()
    session_entry = SessionEntry(
        session_key="agent:main:telegram:dm:c1",
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=platform,
        chat_type="dm",
        total_tokens=0,
    )
    runner.session_store.get_or_create_session.return_value = session_entry
    runner.session_store.load_transcript.return_value = []
    runner.session_store.has_any_sessions.return_value = True
    runner.session_store.append_to_transcript = MagicMock()
    runner.session_store.rewrite_transcript = MagicMock()
    runner.session_store.update_session = MagicMock()
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._session_run_generation = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._session_sources = {}
    runner._session_db = MagicMock()
    runner._session_db.get_session_title.return_value = None
    runner._session_db.get_session.return_value = None
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
    # Stub the agent path so passthrough fall-through returns a sentinel
    # we can detect (instead of attempting a real agent run, which would
    # require the full plugin stack).
    runner._handle_message_with_agent = AsyncMock(return_value="<agent-dispatch>")
    runner._begin_session_run_generation = lambda *_a, **_kw: 1
    runner._is_telegram_topic_root_lobby = lambda *_a, **_kw: False
    return runner


# ---------------------------------------------------------------------------
# Backward compat — env var unset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_command_returns_notice_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("TELEGRAM_PASSTHROUGH_PREFIXES", raising=False)
    runner = _make_runner()
    result = await runner._handle_message(
        _make_event("/totallymadeup", _make_source())
    )
    assert result is not None
    assert "Unknown command `/totallymadeup`" in result


@pytest.mark.asyncio
async def test_unknown_command_returns_notice_when_env_var_empty(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PASSTHROUGH_PREFIXES", "")
    runner = _make_runner()
    result = await runner._handle_message(
        _make_event("/totallymadeup", _make_source())
    )
    assert result is not None
    assert "Unknown command `/totallymadeup`" in result


# ---------------------------------------------------------------------------
# Match — env-var-listed token is passed through to the agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_passthrough_with_leading_slash_in_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PASSTHROUGH_PREFIXES", "/customcmd")
    runner = _make_runner()
    result = await runner._handle_message(
        _make_event("/customcmd hello", _make_source())
    )
    # The unknown-command notice MUST NOT be returned — the fall-through
    # should reach the (stubbed) agent dispatch.
    assert "Unknown command" not in (result or "")


@pytest.mark.asyncio
async def test_passthrough_without_leading_slash_in_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PASSTHROUGH_PREFIXES", "customcmd")
    runner = _make_runner()
    result = await runner._handle_message(
        _make_event("/customcmd hello", _make_source())
    )
    assert "Unknown command" not in (result or "")


@pytest.mark.asyncio
async def test_passthrough_match_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PASSTHROUGH_PREFIXES", "customcmd")
    runner = _make_runner()
    result = await runner._handle_message(
        _make_event("/CUSTOMCMD hello", _make_source())
    )
    assert "Unknown command" not in (result or "")


@pytest.mark.asyncio
async def test_passthrough_handles_multiple_comma_separated_entries(monkeypatch):
    monkeypatch.setenv(
        "TELEGRAM_PASSTHROUGH_PREFIXES", " /foo , bar ,/baz "
    )
    runner = _make_runner()
    for cmd in ("/foo", "/bar", "/baz"):
        result = await runner._handle_message(
            _make_event(f"{cmd} hi", _make_source())
        )
        assert "Unknown command" not in (result or ""), (
            f"{cmd} should be passed through"
        )


# ---------------------------------------------------------------------------
# Non-matching token with env var set — still returns notice
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_matching_token_still_returns_notice(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PASSTHROUGH_PREFIXES", "foo,bar")
    runner = _make_runner()
    result = await runner._handle_message(
        _make_event("/somethingelse", _make_source())
    )
    assert result is not None
    assert "Unknown command `/somethingelse`" in result


# ---------------------------------------------------------------------------
# event.text must NOT be mutated by passthrough — the agent receives the
# original message with the leading slash intact.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_passthrough_preserves_leading_slash_in_event_text(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PASSTHROUGH_PREFIXES", "customcmd")
    runner = _make_runner()
    event = _make_event("/customcmd hello world", _make_source())
    await runner._handle_message(event)
    # The agent stub was called; event.text must still start with the
    # leading slash because SOUL.md / system prompt branches rely on it.
    assert event.text.startswith("/customcmd"), (
        f"event.text was mutated: {event.text!r}"
    )
