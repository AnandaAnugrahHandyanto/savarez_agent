"""Tests for the Telegram outbound reply-context cache.

When ``telegram.extra.rich_messages`` is enabled, final replies are sent via
``sendRichMessage``. That payload carries the agent text in a ``rich_message``
structure and no legacy ``text`` field, so a user replying to such a message
arrives with ``message.reply_to_message.text`` / ``.caption`` empty and the
adapter has nothing to quote. The adapter therefore remembers a bounded,
TTL-expiring snippet of what it sent, keyed by ``(chat_id, message_id)``, and
falls back to it in ``_build_message_event`` so ``reply_to_text`` is restored.

This brings rich-message replies (and rich cron announcements) to parity with
legacy text replies, which already round-trip through ``reply_to_message.text``.

The ``telegram`` package is mocked by ``tests/gateway/conftest.py``, so these
tests construct a real ``TelegramAdapter`` and wire a mock bot.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import PlatformConfig
from gateway.platforms.base import MessageType, SendResult
from gateway.platforms.telegram import TelegramAdapter


def _make_adapter(extra=None):
    """Build a TelegramAdapter with a mock bot wired for both send paths."""
    config = PlatformConfig(
        enabled=True,
        token="fake-token",
        extra={"rich_messages": True, **(extra or {})},
    )
    adapter = TelegramAdapter(config)
    bot = MagicMock()
    # AsyncMock makes inspect.iscoroutinefunction(...) True so the adapter's
    # rich-capability probe is satisfied (real Bot.do_api_request is async).
    bot.do_api_request = AsyncMock(return_value=SimpleNamespace(message_id=123))
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
    bot.send_chat_action = AsyncMock()
    bot.send_message_draft = AsyncMock(return_value=True)
    adapter._bot = bot
    return adapter


def _make_reply_message(
    *,
    reply_to_id=123,
    reply_to_text=None,
    reply_to_caption=None,
    quote_text=None,
    chat_id=12345,
    text="follow-up",
):
    """Build a SimpleNamespace message that IS a reply.

    ``reply_to_message`` is always present (it has an id), but its ``text`` and
    ``caption`` default to ``None`` to model a reply to a rich message.
    """
    chat = SimpleNamespace(id=chat_id, type="private", title=None, full_name="Alice")
    user = SimpleNamespace(id=42, full_name="Alice")
    reply_to_message = SimpleNamespace(
        message_id=reply_to_id,
        text=reply_to_text,
        caption=reply_to_caption,
    )
    quote = SimpleNamespace(text=quote_text) if quote_text is not None else None
    return SimpleNamespace(
        chat=chat,
        from_user=user,
        text=text,
        message_thread_id=None,
        message_id=1001,
        reply_to_message=reply_to_message,
        quote=quote,
        date=None,
        forum_topic_created=None,
    )


# ── U1: cache helper behavior ──────────────────────────────────────────────


def test_remember_then_lookup_roundtrip():
    adapter = _make_adapter()
    adapter._remember_outbound_context("chat", "10", "hello world")
    assert adapter._lookup_outbound_context("chat", "10") == "hello world"


def test_snippet_capped_to_max_chars():
    adapter = _make_adapter()
    long = "x" * (adapter._OUTBOUND_CTX_MAX_CHARS + 500)
    adapter._remember_outbound_context("chat", "10", long)
    stored = adapter._lookup_outbound_context("chat", "10")
    assert stored is not None
    assert len(stored) == adapter._OUTBOUND_CTX_MAX_CHARS


def test_ttl_expiry_drops_entry():
    adapter = _make_adapter()
    adapter._remember_outbound_context("chat", "10", "stale")
    # Backdate the stored timestamp beyond the TTL so lookup treats it expired.
    key = ("chat", "10")
    snippet, ts = adapter._outbound_reply_context[key]
    expired_ts = ts - adapter._OUTBOUND_CTX_TTL_SECONDS - 1
    adapter._outbound_reply_context[key] = (snippet, expired_ts)
    assert adapter._lookup_outbound_context("chat", "10") is None
    # Expired entry is dropped on access.
    assert key not in adapter._outbound_reply_context


def test_entry_cap_evicts_oldest():
    adapter = _make_adapter()
    cap = adapter._OUTBOUND_CTX_MAX_ENTRIES
    for i in range(cap + 5):
        adapter._remember_outbound_context("chat", str(i), f"msg-{i}")
    assert len(adapter._outbound_reply_context) == cap
    # The five oldest are evicted; the newest survive.
    assert adapter._lookup_outbound_context("chat", "0") is None
    assert adapter._lookup_outbound_context("chat", "4") is None
    assert adapter._lookup_outbound_context("chat", str(cap + 4)) == f"msg-{cap + 4}"


def test_remember_guards_missing_id_or_content():
    adapter = _make_adapter()
    adapter._remember_outbound_context("chat", None, "content")
    adapter._remember_outbound_context("chat", "10", "")
    adapter._remember_outbound_context("chat", "10", None)
    assert len(adapter._outbound_reply_context) == 0


def test_lookup_unknown_key_returns_none():
    adapter = _make_adapter()
    assert adapter._lookup_outbound_context("chat", "nope") is None
    assert adapter._lookup_outbound_context("chat", None) is None


def test_key_normalization_int_vs_str():
    adapter = _make_adapter()
    adapter._remember_outbound_context(12345, 123, "normalized")
    # Stored with ints, retrieved with strings (the inbound code path uses str).
    assert adapter._lookup_outbound_context("12345", "123") == "normalized"
    # And the reverse direction resolves too.
    assert adapter._lookup_outbound_context(12345, 123) == "normalized"


# ── U2: send-path registration ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rich_send_registers_outbound_context():
    adapter = _make_adapter()
    content = "## Report\n\n| a | b |\n|---|---|\n| 1 | 2 |"

    result = await adapter.send("12345", content)

    assert result.success is True
    assert result.message_id == "123"
    # The rich path used sendRichMessage, and the content was remembered.
    adapter._bot.do_api_request.assert_awaited_once()
    assert adapter._lookup_outbound_context("12345", "123") == content


@pytest.mark.asyncio
async def test_legacy_single_chunk_registers_outbound_context():
    adapter = _make_adapter(extra={"rich_messages": False})
    content = "a short legacy reply"

    result = await adapter.send("12345", content)

    assert result.success is True
    adapter._bot.send_message.assert_awaited()
    for mid in result.raw_response["message_ids"]:
        assert adapter._lookup_outbound_context("12345", mid) == content


@pytest.mark.asyncio
async def test_legacy_multichunk_registers_each_chunk():
    adapter = _make_adapter(extra={"rich_messages": False})

    counter = {"n": 0}

    def _next_message(*args, **kwargs):
        counter["n"] += 1
        return MagicMock(message_id=counter["n"])

    adapter._bot.send_message = AsyncMock(side_effect=_next_message)
    # Force a multi-chunk split well past the 4096 single-message limit.
    content = "B" * (adapter.MAX_MESSAGE_LENGTH * 2 + 100)

    result = await adapter.send("12345", content)

    assert result.success is True
    message_ids = result.raw_response["message_ids"]
    assert len(message_ids) >= 2
    expected = content[: adapter._OUTBOUND_CTX_MAX_CHARS]
    # A reply to ANY delivered chunk recovers the original content snippet.
    for mid in message_ids:
        assert adapter._lookup_outbound_context("12345", mid) == expected


@pytest.mark.asyncio
async def test_failed_or_idless_send_registers_nothing():
    adapter = _make_adapter()
    # Rich result shape with no message_id (success but unparseable id).
    adapter._bot.do_api_request = AsyncMock(return_value={"result": None})

    result = await adapter.send("12345", "content with no id")

    assert result.message_id is None
    assert len(adapter._outbound_reply_context) == 0


# ── U3: inbound fallback in _build_message_event ───────────────────────────


def test_reply_to_rich_message_uses_cached_context():
    """The bug: rich reply has empty text/caption but a seeded cache hit."""
    adapter = _make_adapter()
    adapter._remember_outbound_context("12345", "123", "the original rich body")

    msg = _make_reply_message(reply_to_id=123, chat_id=12345)
    event = adapter._build_message_event(msg, MessageType.TEXT)

    assert event.reply_to_message_id == "123"
    assert event.reply_to_text == "the original rich body"


def test_native_quote_wins_over_cache():
    adapter = _make_adapter()
    adapter._remember_outbound_context("12345", "123", "cached body")

    msg = _make_reply_message(
        reply_to_id=123,
        chat_id=12345,
        reply_to_text="full prior body",
        quote_text="selected substring",
    )
    event = adapter._build_message_event(msg, MessageType.TEXT)

    assert event.reply_to_text == "selected substring"


def test_real_reply_text_wins_over_cache():
    adapter = _make_adapter()
    adapter._remember_outbound_context("12345", "123", "cached body")

    msg = _make_reply_message(
        reply_to_id=123, chat_id=12345, reply_to_text="real telegram text"
    )
    event = adapter._build_message_event(msg, MessageType.TEXT)

    assert event.reply_to_text == "real telegram text"


def test_cache_miss_yields_none():
    adapter = _make_adapter()
    msg = _make_reply_message(reply_to_id=999, chat_id=12345)
    event = adapter._build_message_event(msg, MessageType.TEXT)

    assert event.reply_to_message_id == "999"
    assert event.reply_to_text is None


def test_non_reply_message_does_not_consult_cache():
    adapter = _make_adapter()
    adapter._remember_outbound_context("12345", "123", "cached body")

    chat = SimpleNamespace(id=12345, type="private", title=None, full_name="Alice")
    user = SimpleNamespace(id=42, full_name="Alice")
    msg = SimpleNamespace(
        chat=chat,
        from_user=user,
        text="just a message",
        message_thread_id=None,
        message_id=1001,
        reply_to_message=None,
        quote=None,
        date=None,
        forum_topic_created=None,
    )
    event = adapter._build_message_event(msg, MessageType.TEXT)

    assert event.reply_to_message_id is None
    assert event.reply_to_text is None


def test_injection_condition_satisfied_for_rich_reply():
    """gateway/run.py injects `[Replying to: ...]` when both fields are set."""
    adapter = _make_adapter()
    adapter._remember_outbound_context("12345", "123", "context body")

    msg = _make_reply_message(reply_to_id=123, chat_id=12345)
    event = adapter._build_message_event(msg, MessageType.TEXT)

    assert bool(event.reply_to_text) and bool(event.reply_to_message_id)


# ── U4: end-to-end cron-announcement parity ────────────────────────────────


@pytest.mark.asyncio
async def test_cron_rich_reply_recovers_context_end_to_end():
    """Reproduce the reported bug: reply to a rich cron announcement.

    Sending a `Cronjob Response: ...` body via the rich path, then replying to
    it (with empty reply_to_message.text), must restore the cron snippet so the
    agent knows what the user is referring to.
    """
    adapter = _make_adapter()
    cron_body = "Cronjob Response: Daily Digest (job_id: abc123)\n\n- 3 PRs merged\n- 1 alert"

    send_result = await adapter.send("12345", cron_body)
    assert send_result.message_id == "123"

    reply = _make_reply_message(reply_to_id=123, chat_id=12345, text="do that again")
    event = adapter._build_message_event(reply, MessageType.TEXT)

    assert event.reply_to_text == cron_body
    assert "Cronjob Response: Daily Digest" in event.reply_to_text


# ── Review hardening: precedence, failure path, shape-independent TTL ───────


def test_caption_wins_over_cache():
    """A replied-to media message exposes .caption; it must beat the cache."""
    adapter = _make_adapter()
    adapter._remember_outbound_context("12345", "123", "cached body")

    msg = _make_reply_message(
        reply_to_id=123,
        chat_id=12345,
        reply_to_text=None,
        reply_to_caption="a media caption",
    )
    event = adapter._build_message_event(msg, MessageType.TEXT)

    assert event.reply_to_text == "a media caption"


@pytest.mark.asyncio
async def test_rich_send_failure_registers_nothing():
    """A rich send that fails (success=False) must not populate the cache."""
    adapter = _make_adapter()
    adapter._try_send_rich = AsyncMock(
        return_value=SendResult(success=False, error="transient", retryable=True)
    )

    result = await adapter.send("12345", "rich body that failed to send")

    assert result.success is False
    assert len(adapter._outbound_context_cache()) == 0


def test_ttl_expiry_via_clock_advance(monkeypatch):
    """Shape-independent TTL test: advance the monotonic clock past the TTL."""
    clock = {"t": 1000.0}
    monkeypatch.setattr(
        "gateway.platforms.telegram.time.monotonic", lambda: clock["t"]
    )
    adapter = _make_adapter()
    adapter._remember_outbound_context("c", "m", "fresh")
    assert adapter._lookup_outbound_context("c", "m") == "fresh"

    clock["t"] += adapter._OUTBOUND_CTX_TTL_SECONDS + 1
    assert adapter._lookup_outbound_context("c", "m") is None
