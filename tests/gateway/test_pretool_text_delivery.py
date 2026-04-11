import sys
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
    return MessageEvent(
        text=text,
        source=_make_source(),
        message_id="m1",
    )


def _make_runner(session_entry: SessionEntry):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    adapter = MagicMock()
    adapter.send = AsyncMock()
    adapter.stop_typing = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=False)
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = session_entry
    runner.session_store.load_transcript.return_value = []
    runner.session_store.has_any_sessions.return_value = True
    runner.session_store.append_to_transcript = MagicMock()
    runner.session_store.rewrite_transcript = MagicMock()
    runner.session_store.update_session = MagicMock()
    runner._running_agents = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._session_db = MagicMock()
    runner._session_db.get_session_title.return_value = None
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
    return runner


@pytest.mark.asyncio
async def test_handle_message_includes_current_turn_pretool_text_in_response(
    monkeypatch,
):
    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_runner(session_entry)
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.commands",
        SimpleNamespace(
            GATEWAY_KNOWN_COMMANDS=frozenset(), resolve_command=lambda _cmd: None
        ),
    )
    runner.session_store.load_transcript.return_value = [
        {
            "role": "assistant",
            "content": "Old pre-tool text",
            "tool_calls": [{"function": {"name": "memory"}}],
        }
    ]
    runner._run_agent = AsyncMock(
        return_value={
            "final_response": "Here is the result.",
            "messages": [
                {
                    "role": "assistant",
                    "content": "Old pre-tool text",
                    "tool_calls": [{"function": {"name": "memory"}}],
                },
                {"role": "user", "content": "hello"},
                {
                    "role": "assistant",
                    "content": "Let me check that for you.",
                    "tool_calls": [{"function": {"name": "session_search"}}],
                },
                {"role": "tool", "content": "{}"},
                {"role": "assistant", "content": "Here is the result."},
            ],
            "tools": [],
            "history_offset": 1,
            "last_prompt_tokens": 80,
        }
    )

    result = await runner._handle_message(_make_event("hello"))

    assert result == "Let me check that for you.\n\nHere is the result."


@pytest.mark.asyncio
async def test_handle_message_does_not_duplicate_matching_pretool_text(monkeypatch):
    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_runner(session_entry)
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.commands",
        SimpleNamespace(
            GATEWAY_KNOWN_COMMANDS=frozenset(), resolve_command=lambda _cmd: None
        ),
    )
    runner._run_agent = AsyncMock(
        return_value={
            "final_response": "All set.",
            "messages": [
                {"role": "user", "content": "hello"},
                {
                    "role": "assistant",
                    "content": "All set.",
                    "tool_calls": [{"function": {"name": "memory"}}],
                },
                {"role": "tool", "content": "{}"},
                {"role": "assistant", "content": "All set."},
            ],
            "tools": [],
            "history_offset": 0,
            "last_prompt_tokens": 80,
        }
    )

    result = await runner._handle_message(_make_event("hello"))

    assert result == "All set."


@pytest.mark.asyncio
async def test_handle_message_strips_hidden_reasoning_from_pretool_text(monkeypatch):
    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_runner(session_entry)
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.commands",
        SimpleNamespace(
            GATEWAY_KNOWN_COMMANDS=frozenset(), resolve_command=lambda _cmd: None
        ),
    )
    runner._run_agent = AsyncMock(
        return_value={
            "final_response": "Visible final answer.",
            "messages": [
                {"role": "user", "content": "hello"},
                {
                    "role": "assistant",
                    "content": "<think>internal only</think>Visible pre-tool text.",
                    "tool_calls": [{"function": {"name": "memory"}}],
                },
                {"role": "tool", "content": "{}"},
                {"role": "assistant", "content": "Visible final answer."},
            ],
            "tools": [],
            "history_offset": 0,
            "last_prompt_tokens": 80,
        }
    )

    result = await runner._handle_message(_make_event("hello"))

    assert result == "Visible pre-tool text.\n\nVisible final answer."
    assert "internal only" not in result


@pytest.mark.asyncio
async def test_handle_message_uses_text_blocks_for_pretool_content(monkeypatch):
    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_runner(session_entry)
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.commands",
        SimpleNamespace(
            GATEWAY_KNOWN_COMMANDS=frozenset(), resolve_command=lambda _cmd: None
        ),
    )
    runner._run_agent = AsyncMock(
        return_value={
            "final_response": "Structured final answer.",
            "messages": [
                {"role": "user", "content": "hello"},
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Visible structured pre-tool text."}
                    ],
                    "tool_calls": [{"function": {"name": "memory"}}],
                },
                {"role": "tool", "content": "{}"},
                {"role": "assistant", "content": "Structured final answer."},
            ],
            "tools": [],
            "history_offset": 0,
            "last_prompt_tokens": 80,
        }
    )

    result = await runner._handle_message(_make_event("hello"))

    assert result == "Visible structured pre-tool text.\n\nStructured final answer."


@pytest.mark.asyncio
async def test_handle_message_dedupes_pretool_text_when_reasoning_display_enabled(
    monkeypatch,
):
    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_runner(session_entry)
    runner._show_reasoning = True
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.commands",
        SimpleNamespace(
            GATEWAY_KNOWN_COMMANDS=frozenset(), resolve_command=lambda _cmd: None
        ),
    )
    runner._run_agent = AsyncMock(
        return_value={
            "final_response": "All set.",
            "last_reasoning": "internal reasoning",
            "messages": [
                {"role": "user", "content": "hello"},
                {
                    "role": "assistant",
                    "content": "All set.",
                    "tool_calls": [{"function": {"name": "memory"}}],
                },
                {"role": "tool", "content": "{}"},
                {"role": "assistant", "content": "All set."},
            ],
            "tools": [],
            "history_offset": 0,
            "last_prompt_tokens": 80,
        }
    )

    result = await runner._handle_message(_make_event("hello"))

    assert result.count("All set.") == 1
    assert "internal reasoning" in result


@pytest.mark.asyncio
async def test_handle_message_ignores_stale_pretool_text_when_history_offset_resets(
    monkeypatch,
):
    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_runner(session_entry)
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.commands",
        SimpleNamespace(
            GATEWAY_KNOWN_COMMANDS=frozenset(), resolve_command=lambda _cmd: None
        ),
    )
    runner._run_agent = AsyncMock(
        return_value={
            "final_response": "Fresh final answer.",
            "messages": [
                {"role": "user", "content": "older question"},
                {
                    "role": "assistant",
                    "content": "Old pre-tool text that should not leak.",
                    "tool_calls": [{"function": {"name": "memory"}}],
                },
                {"role": "tool", "content": "{}"},
                {"role": "assistant", "content": "Older final answer."},
                {"role": "user", "content": "new question"},
                {
                    "role": "assistant",
                    "content": "Fresh pre-tool text.",
                    "tool_calls": [{"function": {"name": "session_search"}}],
                },
                {"role": "tool", "content": "{}"},
                {"role": "assistant", "content": "Fresh final answer."},
            ],
            "tools": [],
            "history_offset": 0,
            "last_prompt_tokens": 80,
        }
    )

    result = await runner._handle_message(_make_event("hello"))

    assert result == "Fresh pre-tool text.\n\nFresh final answer."
    assert "Old pre-tool text" not in result
