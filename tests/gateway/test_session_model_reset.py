"""Tests that /new (and its /reset alias) clears session-scoped overrides."""
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
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    adapter = MagicMock()
    adapter.send = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=False)
    runner._session_model_overrides = {}
    runner._session_reasoning_overrides = {}
    runner._pending_model_notes = {}
    runner._gateway_message_mode_overrides = {}
    runner._background_tasks = set()

    session_key = build_session_key(_make_source())
    session_entry = SessionEntry(
        session_key=session_key,
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = session_entry
    runner.session_store.reset_session.return_value = session_entry
    runner.session_store._entries = {session_key: session_entry}
    runner.session_store._generate_session_key.return_value = session_key
    runner._running_agents = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._session_db = None
    runner._agent_cache_lock = None  # disables _evict_cached_agent lock path
    runner._is_user_authorized = lambda _source: True
    runner._format_session_info = lambda: ""

    return runner


@pytest.mark.asyncio
async def test_new_command_clears_session_model_override():
    """/new must remove the session-scoped model override for that session."""
    runner = _make_runner()
    session_key = build_session_key(_make_source())

    # Simulate a prior /model switch stored as a session override
    runner._session_model_overrides[session_key] = {
        "model": "gpt-4o",
        "provider": "openai",
        "api_key": "***",
        "base_url": "",
        "api_mode": "openai",
    }
    runner._session_reasoning_overrides[session_key] = {"enabled": True, "effort": "high"}
    runner._pending_model_notes[session_key] = "[Note: switched to gpt-4o.]"

    await runner._handle_reset_command(_make_event("/new"))

    assert session_key not in runner._session_model_overrides
    assert session_key not in runner._session_reasoning_overrides
    assert session_key not in runner._pending_model_notes


@pytest.mark.asyncio
async def test_new_command_clears_sticky_gateway_message_mode():
    """/new is a conversation boundary and must return follow-ups to default routing."""
    runner = _make_runner()
    session_key = build_session_key(_make_source())
    runner._gateway_message_mode_overrides[session_key] = "lite"

    await runner._handle_reset_command(_make_event("/new"))

    assert session_key not in runner._gateway_message_mode_overrides


@pytest.mark.asyncio
async def test_new_command_resets_active_scoped_gateway_message_mode():
    """/new in a sticky lane resets that lane, not an unrelated base session."""
    runner = _make_runner()
    base_source = _make_source()
    scoped_source = SessionSource(
        platform=base_source.platform,
        user_id=base_source.user_id,
        chat_id=base_source.chat_id,
        user_name=base_source.user_name,
        chat_type=base_source.chat_type,
        session_scope="lite",
    )
    base_key = build_session_key(base_source)
    scoped_key = build_session_key(scoped_source)
    scoped_entry = SessionEntry(
        session_key=scoped_key,
        session_id="sess-lite",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner.session_store._entries[scoped_key] = scoped_entry
    runner.session_store.reset_session.side_effect = lambda key: runner.session_store._entries.get(key)
    runner._gateway_message_mode_overrides[base_key] = "lite"
    runner._session_model_overrides[scoped_key] = {
        "model": "gpt-4o",
        "provider": "openai",
        "api_key": "***",
        "base_url": "",
        "api_mode": "openai",
    }

    await runner._handle_reset_command(_make_event("/new"))

    runner.session_store.reset_session.assert_called_once_with(scoped_key)
    assert base_key not in runner._gateway_message_mode_overrides
    assert scoped_key not in runner._session_model_overrides


@pytest.mark.asyncio
async def test_new_command_no_override_is_noop():
    """/new with no prior model override must not raise."""
    runner = _make_runner()
    session_key = build_session_key(_make_source())

    assert session_key not in runner._session_model_overrides
    assert session_key not in runner._session_reasoning_overrides

    await runner._handle_reset_command(_make_event("/new"))

    assert session_key not in runner._session_model_overrides
    assert session_key not in runner._session_reasoning_overrides


@pytest.mark.asyncio
async def test_new_command_only_clears_own_session():
    """/new must only clear the override for the session that triggered it."""
    runner = _make_runner()
    session_key = build_session_key(_make_source())
    other_key = "other_session_key"

    runner._session_model_overrides[session_key] = {
        "model": "gpt-4o",
        "provider": "openai",
        "api_key": "sk-test",
        "base_url": "",
        "api_mode": "openai",
    }
    runner._session_model_overrides[other_key] = {
        "model": "claude-sonnet-4-6",
        "provider": "anthropic",
        "api_key": "***",
        "base_url": "",
        "api_mode": "anthropic",
    }
    runner._session_reasoning_overrides[session_key] = {"enabled": True, "effort": "high"}
    runner._session_reasoning_overrides[other_key] = {"enabled": True, "effort": "low"}
    runner._pending_model_notes[session_key] = "[Note: switched to gpt-4o.]"
    runner._pending_model_notes[other_key] = "[Note: switched to claude-sonnet-4-6.]"

    await runner._handle_reset_command(_make_event("/new"))

    assert session_key not in runner._session_model_overrides
    assert other_key in runner._session_model_overrides
    assert session_key not in runner._session_reasoning_overrides
    assert other_key in runner._session_reasoning_overrides
    assert session_key not in runner._pending_model_notes
    assert other_key in runner._pending_model_notes

@pytest.mark.asyncio
async def test_deny_all_requires_exact_argument(monkeypatch):
    """`/deny allow` must not be parsed as `/deny all` by substring match."""
    runner = _make_runner()
    session_key = build_session_key(_make_source())
    calls = []

    def fake_find_blocking_approval_session_key(key):
        assert key == session_key
        return session_key

    def fake_resolve_gateway_approval(key, choice, *, resolve_all=False):
        calls.append((key, choice, resolve_all))
        return 1

    monkeypatch.setattr(
        "tools.approval.find_blocking_approval_session_key",
        fake_find_blocking_approval_session_key,
    )
    monkeypatch.setattr("tools.approval.resolve_gateway_approval", fake_resolve_gateway_approval)

    await runner._handle_deny_command(_make_event("/deny allow"))
    await runner._handle_deny_command(_make_event("/deny all"))

    assert calls == [
        (session_key, "deny", False),
        (session_key, "deny", True),
    ]

@pytest.mark.asyncio
async def test_yolo_targets_scoped_pending_approval_without_sticky_mode():
    """Plain `/yolo` should target a scoped lane that owns the pending approval."""
    from tools.approval import disable_session_yolo, is_session_yolo_enabled

    runner = _make_runner()
    base_key = build_session_key(_make_source())
    scoped_key = f"{base_key}:mode:ops"
    runner._pending_approvals[scoped_key] = object()

    try:
        await runner._handle_yolo_command(_make_event("/yolo"))

        assert is_session_yolo_enabled(scoped_key) is True
        assert is_session_yolo_enabled(base_key) is False
    finally:
        disable_session_yolo(scoped_key)
        disable_session_yolo(base_key)

@pytest.mark.asyncio
async def test_new_command_treats_sticky_dev_as_unscoped_session():
    """`dev` mode has no session_scope, so `/new` must reset the base session."""
    runner = _make_runner()
    base_key = build_session_key(_make_source())
    runner._gateway_message_mode_overrides[base_key] = "dev"

    await runner._handle_reset_command(_make_event("/new"))

    runner.session_store.reset_session.assert_called_once_with(base_key)
    assert base_key not in runner._gateway_message_mode_overrides

def test_scoped_session_key_resolver_treats_dev_as_unscoped():
    """Active dev route must not fabricate a `:mode:dev` session key."""
    runner = _make_runner()
    base_key = build_session_key(_make_source())
    runner._gateway_message_mode_overrides[base_key] = "dev"

    assert runner._scoped_session_key_for_command(base_key) == base_key
