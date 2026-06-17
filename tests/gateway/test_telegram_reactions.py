"""Tests for Telegram message reactions tied to processing lifecycle hooks."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType, ProcessingOutcome
from gateway.session import SessionSource


def _make_adapter(**extra_config):
    from gateway.platforms.telegram import TelegramAdapter

    adapter = object.__new__(TelegramAdapter)
    adapter.platform = Platform.TELEGRAM
    adapter.config = PlatformConfig(enabled=True, token="fake-token", extra=extra_config)
    adapter._message_handler = None
    adapter._bot = AsyncMock()
    adapter._bot.id = 999
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


def _reaction_obj(emoji: str):
    return SimpleNamespace(emoji=emoji)


def _make_reaction_update(
    *,
    user_id: int = 42,
    is_bot: bool = False,
    chat_id: int = -1001,
    chat_type: str = "supergroup",
    message_id: int = 456,
    old_reaction=None,
    new_reaction=None,
    update_id: int = 9999,
):
    return SimpleNamespace(
        update_id=update_id,
        message_reaction=SimpleNamespace(
            user=SimpleNamespace(id=user_id, is_bot=is_bot, first_name="Tester"),
            chat=SimpleNamespace(id=chat_id, type=chat_type),
            message_id=message_id,
            old_reaction=[_reaction_obj(e) for e in (old_reaction or [])],
            new_reaction=[_reaction_obj(e) for e in (new_reaction or [])],
        ),
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


# ── inbound user reaction feedback ───────────────────────────────────


def test_reaction_feedback_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TELEGRAM_REACTION_FEEDBACK", raising=False)
    adapter = _make_adapter()
    assert adapter._reaction_feedback_enabled() is False


def test_reaction_feedback_enabled_when_set_true(monkeypatch):
    monkeypatch.setenv("TELEGRAM_REACTION_FEEDBACK", "true")
    adapter = _make_adapter()
    assert adapter._reaction_feedback_enabled() is True


def test_reaction_feedback_env_takes_precedence_over_extra(monkeypatch):
    monkeypatch.setenv("TELEGRAM_REACTION_FEEDBACK", "false")
    adapter = _make_adapter(reaction_feedback=True)
    assert adapter._reaction_feedback_enabled() is False


def test_reaction_feedback_can_be_enabled_from_extra(monkeypatch):
    monkeypatch.delenv("TELEGRAM_REACTION_FEEDBACK", raising=False)
    adapter = _make_adapter(reaction_feedback=True)
    assert adapter._reaction_feedback_enabled() is True


@pytest.mark.asyncio
async def test_handle_message_reaction_records_authorized_feedback(monkeypatch, tmp_path):
    """Authorized reactions to known Hermes-sent messages become feedback events."""
    import json

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_REACTION_FEEDBACK", "true")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "42")
    monkeypatch.delenv("GATEWAY_ALLOW_ALL_USERS", raising=False)

    from gateway import reaction_feedback

    reaction_feedback.record_sent_message(
        platform="telegram",
        chat_id="-1001",
        thread_id="777",
        message_id="456",
        content="assistant text",
        metadata={"session_id": "sess-1", "session_key": "telegram:-1001:777"},
    )
    adapter = _make_adapter()

    await adapter._handle_message_reaction(
        _make_reaction_update(new_reaction=["👍"]),
        SimpleNamespace(),
    )

    events = [
        json.loads(line)
        for line in reaction_feedback.events_path().read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert len(events) == 1
    assert events[0]["route"] == {"chat_id": "-1001", "thread_id": "777", "message_id": "456"}
    assert events[0]["reaction"]["semantic"] == "useful"
    assert events[0]["target"]["known"] is True
    assert events[0]["target"]["session_id"] == "sess-1"


@pytest.mark.asyncio
async def test_handle_message_reaction_ignores_unknown_target(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_REACTION_FEEDBACK", "true")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "42")
    monkeypatch.delenv("GATEWAY_ALLOW_ALL_USERS", raising=False)

    from gateway import reaction_feedback

    adapter = _make_adapter()

    await adapter._handle_message_reaction(
        _make_reaction_update(user_id=42, new_reaction=["👎"]),
        SimpleNamespace(),
    )

    assert not reaction_feedback.events_path().exists()


@pytest.mark.asyncio
async def test_handle_message_reaction_ignores_unauthorized_user(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_REACTION_FEEDBACK", "true")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "777")
    monkeypatch.delenv("GATEWAY_ALLOW_ALL_USERS", raising=False)

    from gateway import reaction_feedback

    reaction_feedback.record_sent_message(
        platform="telegram",
        chat_id="-1001",
        message_id="456",
        content="assistant text",
    )
    adapter = _make_adapter()

    await adapter._handle_message_reaction(
        _make_reaction_update(user_id=42, new_reaction=["👎"]),
        SimpleNamespace(),
    )

    assert not reaction_feedback.events_path().exists()


@pytest.mark.asyncio
async def test_handle_message_reaction_ignores_bot_actor(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_REACTION_FEEDBACK", "true")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "42")

    from gateway import reaction_feedback

    reaction_feedback.record_sent_message(
        platform="telegram",
        chat_id="-1001",
        message_id="456",
        content="assistant text",
    )
    adapter = _make_adapter()

    await adapter._handle_message_reaction(
        _make_reaction_update(user_id=42, is_bot=True, new_reaction=["👎"]),
        SimpleNamespace(),
    )

    assert not reaction_feedback.events_path().exists()


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


def test_config_bridges_telegram_reaction_feedback(monkeypatch, tmp_path):
    """gateway/config.py bridges telegram.reaction_feedback to TELEGRAM_REACTION_FEEDBACK."""
    import yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "telegram": {
            "reaction_feedback": True,
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_REACTION_FEEDBACK", "")

    from gateway.config import load_gateway_config
    load_gateway_config()

    import os
    assert os.getenv("TELEGRAM_REACTION_FEEDBACK") == "true"


def test_config_reaction_feedback_env_takes_precedence(monkeypatch, tmp_path):
    """Env var should take precedence over config.yaml for reaction feedback."""
    import yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "telegram": {
            "reaction_feedback": True,
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_REACTION_FEEDBACK", "false")

    from gateway.config import load_gateway_config
    load_gateway_config()

    import os
    assert os.getenv("TELEGRAM_REACTION_FEEDBACK") == "false"
