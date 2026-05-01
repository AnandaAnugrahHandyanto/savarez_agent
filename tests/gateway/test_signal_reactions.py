"""Tests for Signal message reactions tied to processing lifecycle hooks."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType, ProcessingOutcome
from gateway.platforms.signal import SignalAdapter
from gateway.session import SessionSource


def _make_adapter(**extra_env):
    adapter = object.__new__(SignalAdapter)
    adapter.platform = Platform.SIGNAL
    adapter.config = PlatformConfig(enabled=True)
    adapter.account = "+15551234567"
    adapter.send_reaction = AsyncMock()
    adapter.remove_reaction = AsyncMock()
    # Mock the auth gate — returns True by default so reaction tests for
    # authorized users pass.  Individual tests can set it to False to
    # verify that reactions are skipped for unauthorized users.
    adapter._is_user_authorized = lambda source: True
    for k, v in extra_env.items():
        setattr(adapter, k, v)
    return adapter


def _make_event(chat_id: str = "group:abc123", sender: str = "+15559876543") -> MessageEvent:
    """Build a MessageEvent carrying the raw_message dict that Signal hooks
    expect (sender + timestamp_ms)."""
    return MessageEvent(
        text="hello",
        message_type=MessageType.TEXT,
        source=SessionSource(
            platform=Platform.SIGNAL,
            chat_id=chat_id,
            chat_type="group",
            user_id="42",
            user_name="TestUser",
        ),
        raw_message={"sender": sender, "timestamp_ms": 1700000000000},
        message_id="msg-456",
    )


# ── _reactions_enabled ───────────────────────────────────────────────


def test_reactions_disabled_by_default(monkeypatch):
    """Signal reactions should be disabled by default."""
    monkeypatch.delenv("SIGNAL_REACTIONS", raising=False)
    adapter = _make_adapter()
    assert adapter._reactions_enabled() is False


def test_reactions_enabled_when_set_true(monkeypatch):
    """Setting SIGNAL_REACTIONS=true enables reactions."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "true")
    adapter = _make_adapter()
    assert adapter._reactions_enabled() is True


def test_reactions_enabled_with_1(monkeypatch):
    """SIGNAL_REACTIONS=1 enables reactions."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "1")
    adapter = _make_adapter()
    assert adapter._reactions_enabled() is True


def test_reactions_disabled_with_false(monkeypatch):
    """SIGNAL_REACTIONS=false disables reactions."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "false")
    adapter = _make_adapter()
    assert adapter._reactions_enabled() is False


def test_reactions_disabled_with_0(monkeypatch):
    """SIGNAL_REACTIONS=0 disables reactions."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "0")
    adapter = _make_adapter()
    assert adapter._reactions_enabled() is False


def test_reactions_disabled_with_no(monkeypatch):
    """SIGNAL_REACTIONS=no disables reactions."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "no")
    adapter = _make_adapter()
    assert adapter._reactions_enabled() is False


# ── send_reaction ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_reaction_calls_rpc_correctly(monkeypatch):
    """send_reaction should call _rpc('sendReaction', ...) with correct args."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "true")
    adapter = _make_adapter(send_reaction=None)  # don't replace — test the real method
    adapter._rpc = AsyncMock(return_value={"ok": True})

    # For a DM chat (phone number, not group: prefix)
    result = await SignalAdapter.send_reaction(
        adapter, "+15559876543", "👀", "+15559876543", 1700000000000,
    )

    assert result is True
    adapter._rpc.assert_awaited_once_with("sendReaction", {
        "account": "+15551234567",
        "emoji": "👀",
        "targetAuthor": "+15559876543",
        "targetTimestamp": 1700000000000,
        "recipient": ["+15559876543"],
    })


@pytest.mark.asyncio
async def test_send_reaction_routes_to_group_correctly(monkeypatch):
    """send_reaction should use groupId for group: chat_ids."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "true")
    adapter = _make_adapter(send_reaction=None)
    adapter._rpc = AsyncMock(return_value={"ok": True})

    result = await SignalAdapter.send_reaction(
        adapter, "group:abc123", "👀", "+15559876543", 1700000000000,
    )

    assert result is True
    adapter._rpc.assert_awaited_once_with("sendReaction", {
        "account": "+15551234567",
        "emoji": "👀",
        "targetAuthor": "+15559876543",
        "targetTimestamp": 1700000000000,
        "groupId": "abc123",
    })


@pytest.mark.asyncio
async def test_send_reaction_returns_false_on_rpc_failure(monkeypatch):
    """send_reaction should return False when _rpc returns None (failure)."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "true")
    adapter = _make_adapter(send_reaction=None)
    adapter._rpc = AsyncMock(return_value=None)

    result = await SignalAdapter.send_reaction(
        adapter, "+15559876543", "👀", "+15559876543", 1700000000000,
    )

    assert result is False


# ── _extract_reaction_target ─────────────────────────────────────────


def test_extract_reaction_target_returns_sender_and_ts():
    """Should extract (sender, timestamp_ms) from a properly-formed event."""
    adapter = _make_adapter()
    event = _make_event(sender="+15559876543")

    target = adapter._extract_reaction_target(event)

    assert target == ("+15559876543", 1700000000000)


def test_extract_reaction_target_none_when_raw_message_missing():
    """Should return None when raw_message is not a dict."""
    adapter = _make_adapter()
    event = _make_event()
    event.raw_message = None

    assert adapter._extract_reaction_target(event) is None


def test_extract_reaction_target_none_when_raw_message_not_dict():
    """Should return None when raw_message is a non-dict type."""
    adapter = _make_adapter()
    event = _make_event()
    event.raw_message = "just a string"

    assert adapter._extract_reaction_target(event) is None


def test_extract_reaction_target_none_when_sender_missing():
    """Should return None when raw_message dict lacks a sender."""
    adapter = _make_adapter()
    event = _make_event()
    event.raw_message = {"timestamp_ms": 1700000000000}

    assert adapter._extract_reaction_target(event) is None


def test_extract_reaction_target_none_when_timestamp_missing():
    """Should return None when raw_message dict lacks timestamp_ms."""
    adapter = _make_adapter()
    event = _make_event()
    event.raw_message = {"sender": "+1555"}

    assert adapter._extract_reaction_target(event) is None


# ── on_processing_start ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_on_processing_start_adds_eyes_reaction(monkeypatch):
    """Processing start should send a 👀 reaction when enabled."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "true")
    adapter = _make_adapter()
    event = _make_event()

    await adapter.on_processing_start(event)

    adapter.send_reaction.assert_awaited_once_with(
        "group:abc123", "👀", "+15559876543", 1700000000000,
    )


@pytest.mark.asyncio
async def test_on_processing_start_skipped_when_disabled(monkeypatch):
    """Processing start should not react when reactions are disabled."""
    monkeypatch.delenv("SIGNAL_REACTIONS", raising=False)
    adapter = _make_adapter()
    event = _make_event()

    await adapter.on_processing_start(event)

    adapter.send_reaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_processing_start_skipped_when_target_missing(monkeypatch):
    """Should not call send_reaction when raw_message lacks sender/timestamp."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "true")
    adapter = _make_adapter()
    event = _make_event()
    event.raw_message = None

    await adapter.on_processing_start(event)

    adapter.send_reaction.assert_not_awaited()


# ── on_processing_complete ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_on_processing_complete_success(monkeypatch):
    """Successful processing should remove 👀 then send ✅."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "true")
    adapter = _make_adapter()
    event = _make_event()

    await adapter.on_processing_complete(event, ProcessingOutcome.SUCCESS)

    adapter.remove_reaction.assert_awaited_once_with(
        "group:abc123", "+15559876543", 1700000000000,
    )
    adapter.send_reaction.assert_awaited_once_with(
        "group:abc123", "✅", "+15559876543", 1700000000000,
    )


@pytest.mark.asyncio
async def test_on_processing_complete_failure(monkeypatch):
    """Failed processing should remove 👀 then send ❌."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "true")
    adapter = _make_adapter()
    event = _make_event()

    await adapter.on_processing_complete(event, ProcessingOutcome.FAILURE)

    adapter.remove_reaction.assert_awaited_once_with(
        "group:abc123", "+15559876543", 1700000000000,
    )
    adapter.send_reaction.assert_awaited_once_with(
        "group:abc123", "❌", "+15559876543", 1700000000000,
    )


@pytest.mark.asyncio
async def test_on_processing_complete_skipped_when_disabled(monkeypatch):
    """Processing complete should not react when reactions are disabled."""
    monkeypatch.delenv("SIGNAL_REACTIONS", raising=False)
    adapter = _make_adapter()
    event = _make_event()

    await adapter.on_processing_complete(event, ProcessingOutcome.SUCCESS)

    adapter.send_reaction.assert_not_awaited()
    adapter.remove_reaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_processing_complete_cancelled_keeps_in_progress_reaction(monkeypatch):
    """Expected cancellation should not replace the in-progress 👀 reaction."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "true")
    adapter = _make_adapter()
    event = _make_event()

    await adapter.on_processing_complete(event, ProcessingOutcome.CANCELLED)

    adapter.send_reaction.assert_not_awaited()
    adapter.remove_reaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_processing_complete_skipped_when_target_missing(monkeypatch):
    """Should not call send/remove_reaction when raw_message lacks the target."""
    monkeypatch.setenv("SIGNAL_REACTIONS", "true")
    adapter = _make_adapter()
    event = _make_event()
    event.raw_message = None

    await adapter.on_processing_complete(event, ProcessingOutcome.SUCCESS)

    adapter.send_reaction.assert_not_awaited()
    adapter.remove_reaction.assert_not_awaited()


# ── config.py bridging ───────────────────────────────────────────────


def test_config_bridges_signal_reactions(monkeypatch, tmp_path):
    """gateway/config.py bridges signal.reactions to SIGNAL_REACTIONS env var."""
    import yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "signal": {
            "reactions": True,
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("SIGNAL_REACTIONS", "")

    from gateway.config import load_gateway_config
    load_gateway_config()

    import os
    assert os.getenv("SIGNAL_REACTIONS") == "true"


def test_config_reactions_env_takes_precedence(monkeypatch, tmp_path):
    """Env var should take precedence over config.yaml for reactions."""
    import yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "signal": {
            "reactions": True,
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("SIGNAL_REACTIONS", "false")

    from gateway.config import load_gateway_config
    load_gateway_config()

    import os
    assert os.getenv("SIGNAL_REACTIONS") == "false"

