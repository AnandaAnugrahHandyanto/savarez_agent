"""Tests for Telegram message reactions tied to processing lifecycle hooks."""

import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType, ProcessingOutcome
from gateway.session import SessionSource


def _make_adapter(**extra_env):
    from gateway.platforms.telegram import TelegramAdapter

    adapter = object.__new__(TelegramAdapter)
    adapter.platform = Platform.TELEGRAM
    adapter.config = PlatformConfig(enabled=True, token="fake-token")
    adapter._bot = AsyncMock()
    adapter._bot.set_message_reaction = AsyncMock()
    return adapter


def _make_event(chat_id: str = "123", message_id: str = "456") -> MessageEvent:
    return MessageEvent(
        text="hello",
        message_type=MessageType.TEXT,
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id=chat_id,
            chat_type="private",
            user_id="42",
            user_name="TestUser",
        ),
        message_id=message_id,
    )


# ── _reactions_enabled ───────────────────────────────────────────────


def test_reactions_disabled_by_default(monkeypatch):
    """Telegram reactions should be disabled by default."""
    monkeypatch.delenv("TELEGRAM_REACTIONS", raising=False)
    adapter = _make_adapter()
    assert adapter._reactions_enabled() is False


def test_reactions_enabled_when_set_true(monkeypatch):
    """Setting TELEGRAM_REACTIONS=true enables reactions."""
    monkeypatch.setenv("TELEGRAM_REACTIONS", "true")
    adapter = _make_adapter()
    assert adapter._reactions_enabled() is True


def test_reactions_enabled_with_1(monkeypatch):
    """TELEGRAM_REACTIONS=1 enables reactions."""
    monkeypatch.setenv("TELEGRAM_REACTIONS", "1")
    adapter = _make_adapter()
    assert adapter._reactions_enabled() is True


def test_reactions_disabled_with_false(monkeypatch):
    """TELEGRAM_REACTIONS=false disables reactions."""
    monkeypatch.setenv("TELEGRAM_REACTIONS", "false")
    adapter = _make_adapter()
    assert adapter._reactions_enabled() is False


def test_reactions_disabled_with_0(monkeypatch):
    """TELEGRAM_REACTIONS=0 disables reactions."""
    monkeypatch.setenv("TELEGRAM_REACTIONS", "0")
    adapter = _make_adapter()
    assert adapter._reactions_enabled() is False


def test_reactions_disabled_with_no(monkeypatch):
    """TELEGRAM_REACTIONS=no disables reactions."""
    monkeypatch.setenv("TELEGRAM_REACTIONS", "no")
    adapter = _make_adapter()
    assert adapter._reactions_enabled() is False


# ── _set_reaction ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_reaction_calls_bot_api(monkeypatch):
    """_set_reaction should call bot.set_message_reaction with correct args."""
    monkeypatch.setenv("TELEGRAM_REACTIONS", "true")
    adapter = _make_adapter()

    result = await adapter._set_reaction("123", "456", "\U0001f440")

    assert result is True
    adapter._bot.set_message_reaction.assert_awaited_once_with(
        chat_id=123,
        message_id=456,
        reaction="\U0001f440",
    )


@pytest.mark.asyncio
async def test_set_reaction_returns_false_without_bot(monkeypatch):
    """_set_reaction should return False when bot is not available."""
    monkeypatch.setenv("TELEGRAM_REACTIONS", "true")
    adapter = _make_adapter()
    adapter._bot = None

    result = await adapter._set_reaction("123", "456", "\U0001f440")
    assert result is False


@pytest.mark.asyncio
async def test_set_reaction_handles_api_error_gracefully(monkeypatch):
    """API errors during reaction should not propagate."""
    monkeypatch.setenv("TELEGRAM_REACTIONS", "true")
    adapter = _make_adapter()
    adapter._bot.set_message_reaction = AsyncMock(side_effect=RuntimeError("no perms"))

    result = await adapter._set_reaction("123", "456", "\U0001f440")
    assert result is False


# ── on_processing_start ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_on_processing_start_adds_eyes_reaction(monkeypatch):
    """Processing start should add eyes reaction when enabled."""
    monkeypatch.setenv("TELEGRAM_REACTIONS", "true")
    adapter = _make_adapter()
    event = _make_event()

    await adapter.on_processing_start(event)

    adapter._bot.set_message_reaction.assert_awaited_once_with(
        chat_id=123,
        message_id=456,
        reaction="\U0001f440",
    )


@pytest.mark.asyncio
async def test_on_processing_start_skipped_when_disabled(monkeypatch):
    """Processing start should not react when reactions are disabled."""
    monkeypatch.delenv("TELEGRAM_REACTIONS", raising=False)
    adapter = _make_adapter()
    event = _make_event()

    await adapter.on_processing_start(event)

    adapter._bot.set_message_reaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_processing_start_handles_missing_ids(monkeypatch):
    """Should handle events without chat_id or message_id gracefully."""
    monkeypatch.setenv("TELEGRAM_REACTIONS", "true")
    adapter = _make_adapter()
    event = MessageEvent(
        text="hello",
        message_type=MessageType.TEXT,
        source=SimpleNamespace(chat_id=None),
        message_id=None,
    )

    await adapter.on_processing_start(event)

    adapter._bot.set_message_reaction.assert_not_awaited()


# ── on_processing_complete ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_on_processing_complete_success(monkeypatch):
    """Successful processing should set thumbs-up reaction."""
    monkeypatch.setenv("TELEGRAM_REACTIONS", "true")
    adapter = _make_adapter()
    event = _make_event()

    await adapter.on_processing_complete(event, ProcessingOutcome.SUCCESS)

    adapter._bot.set_message_reaction.assert_awaited_once_with(
        chat_id=123,
        message_id=456,
        reaction="\U0001f44d",
    )


@pytest.mark.asyncio
async def test_on_processing_complete_failure(monkeypatch):
    """Failed processing should set thumbs-down reaction."""
    monkeypatch.setenv("TELEGRAM_REACTIONS", "true")
    adapter = _make_adapter()
    event = _make_event()

    await adapter.on_processing_complete(event, ProcessingOutcome.FAILURE)

    adapter._bot.set_message_reaction.assert_awaited_once_with(
        chat_id=123,
        message_id=456,
        reaction="\U0001f44e",
    )


@pytest.mark.asyncio
async def test_on_processing_complete_skipped_when_disabled(monkeypatch):
    """Processing complete should not react when reactions are disabled."""
    monkeypatch.delenv("TELEGRAM_REACTIONS", raising=False)
    adapter = _make_adapter()
    event = _make_event()

    await adapter.on_processing_complete(event, ProcessingOutcome.SUCCESS)

    adapter._bot.set_message_reaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_processing_complete_cancelled_clears_reaction(monkeypatch):
    """Cancelled processing should clear the in-progress reaction.

    Without this clear, the 👀 reaction lingers on the user's message
    indefinitely (until another agent run swaps it for 👍/👎). On a
    ``/stop`` that ends a session, that reaction never gets cleaned up.
    """
    monkeypatch.setenv("TELEGRAM_REACTIONS", "true")
    adapter = _make_adapter()
    event = _make_event()

    await adapter.on_processing_complete(event, ProcessingOutcome.CANCELLED)

    # set_message_reaction with reaction=None clears all reactions on the
    # message (Bot API documented semantics; equivalent to Bot API 10.0's
    # deleteMessageReaction but works on PTB 22.6 already).
    adapter._bot.set_message_reaction.assert_awaited_once_with(
        chat_id=123,
        message_id=456,
        reaction=None,
    )


@pytest.mark.asyncio
async def test_on_processing_complete_cancelled_skipped_when_disabled(monkeypatch):
    """Cancelled processing should not call the API when reactions are off."""
    monkeypatch.delenv("TELEGRAM_REACTIONS", raising=False)
    adapter = _make_adapter()
    event = _make_event()

    await adapter.on_processing_complete(event, ProcessingOutcome.CANCELLED)

    adapter._bot.set_message_reaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_clear_reactions_handles_api_error_gracefully(monkeypatch):
    """API errors during clear should not propagate."""
    monkeypatch.setenv("TELEGRAM_REACTIONS", "true")
    adapter = _make_adapter()
    adapter._bot.set_message_reaction = AsyncMock(side_effect=RuntimeError("no perms"))

    result = await adapter._clear_reactions("123", "456")
    assert result is False


@pytest.mark.asyncio
async def test_clear_reactions_returns_false_without_bot(monkeypatch):
    """_clear_reactions should return False when bot is not available."""
    adapter = _make_adapter()
    adapter._bot = None

    result = await adapter._clear_reactions("123", "456")
    assert result is False


@pytest.mark.asyncio
async def test_handle_reaction_update_persists_and_dispatches(monkeypatch):
    """Incoming Telegram reactions should be persisted and routed to the agent."""
    adapter = _make_adapter()
    adapter.handle_message = AsyncMock()
    adapter._bot = SimpleNamespace(id=999999)

    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            platform_message_id TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE telegram_reaction_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            platform TEXT,
            chat_id TEXT,
            message_id TEXT,
            thread_id TEXT,
            reactor_user_id TEXT,
            reactor_user_name TEXT,
            actor_chat_id TEXT,
            timestamp REAL,
            reaction_json TEXT,
            old_reaction_json TEXT,
            new_reaction_json TEXT,
            raw_update_json TEXT,
            actor_chat_name TEXT,
            old_reaction TEXT,
            new_reaction TEXT,
            raw_update TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO messages(session_id, platform_message_id) VALUES (?, ?)",
        ("sess-1", "521"),
    )
    conn.commit()

    origin = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1003804726892",
        chat_type="group",
        user_id="114091409",
        user_name="lililililililil",
    )
    session_entry = SimpleNamespace(session_id="sess-1", origin=origin)
    adapter._session_store = SimpleNamespace(
        _db=SimpleNamespace(_conn=conn),
        list_sessions=lambda: [session_entry],
    )

    reaction = SimpleNamespace(
        chat=SimpleNamespace(id=-1003804726892),
        message_id=521,
        date=datetime.now(timezone.utc),
        old_reaction=[],
        new_reaction=[{"type": "emoji", "emoji": "🤬"}],
        user=SimpleNamespace(
            id=114091409,
            full_name="lililililililil",
            username=None,
            first_name=None,
        ),
        actor_chat=None,
        message_thread_id=None,
    )
    update = SimpleNamespace(message_reaction=reaction)

    await adapter._handle_reaction_update(update, context=SimpleNamespace())

    adapter.handle_message.assert_awaited_once()
    event = adapter.handle_message.await_args.args[0]
    assert event.text == "reaction:added:🤬"
    assert event.message_id == "521"
    assert event.source == origin

    row = conn.execute(
        "SELECT platform, chat_id, message_id, reactor_user_name, reaction_json, new_reaction_json FROM telegram_reaction_events"
    ).fetchone()
    assert row == (
        "telegram",
        "-1003804726892",
        "521",
        "lililililililil",
        '[{"type": "emoji", "emoji": "🤬"}]',
        '[{"type": "emoji", "emoji": "🤬"}]',
    )


# ── config.py bridging ───────────────────────────────────────────────


def test_config_bridges_telegram_reactions(monkeypatch, tmp_path):
    """gateway/config.py bridges telegram.reactions to TELEGRAM_REACTIONS env var."""
    import yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "telegram": {
            "reactions": True,
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # Use setenv (not delenv) so monkeypatch registers cleanup even when
    # the var doesn't exist yet — load_gateway_config will overwrite it.
    monkeypatch.setenv("TELEGRAM_REACTIONS", "")

    from gateway.config import load_gateway_config
    load_gateway_config()

    import os
    assert os.getenv("TELEGRAM_REACTIONS") == "true"


def test_config_reactions_env_takes_precedence(monkeypatch, tmp_path):
    """Env var should take precedence over config.yaml for reactions."""
    import yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "telegram": {
            "reactions": True,
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_REACTIONS", "false")

    from gateway.config import load_gateway_config
    load_gateway_config()

    import os
    assert os.getenv("TELEGRAM_REACTIONS") == "false"
