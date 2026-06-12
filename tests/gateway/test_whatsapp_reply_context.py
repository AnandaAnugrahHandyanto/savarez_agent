"""Regression tests for WhatsApp quoted/replied-message context."""

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.whatsapp import WhatsAppAdapter
from gateway.session import SessionSource


def _make_adapter(**extra):
    base = {"session_name": "test"}
    base.update(extra)
    return WhatsAppAdapter(PlatformConfig(enabled=True, extra=base))


def _bridge_reply_payload(**overrides):
    data = {
        "messageId": "reply-msg-1",
        "chatId": "15551234567@s.whatsapp.net",
        "senderId": "15551234567@s.whatsapp.net",
        "senderName": "Alice",
        "chatName": "Alice",
        "isGroup": False,
        "body": "yes, do that",
        "hasMedia": False,
        "mediaUrls": [],
        "mediaType": "",
        "quotedMessageId": "orig-msg-1",
        "quotedText": "Should I book the 4pm flight?",
        "hasQuotedMessage": True,
    }
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_bridge_quoted_text_becomes_message_event_reply_context():
    adapter = _make_adapter()

    event = await adapter._build_message_event(_bridge_reply_payload())

    assert event is not None
    assert event.text == "yes, do that"
    assert event.reply_to_message_id == "orig-msg-1"
    assert event.reply_to_text == "Should I book the 4pm flight?"
    assert event.raw_message["quotedText"] == "Should I book the 4pm flight?"


@pytest.mark.asyncio
async def test_quoted_text_without_stanza_id_still_gets_synthetic_reply_id():
    adapter = _make_adapter()

    event = await adapter._build_message_event(
        _bridge_reply_payload(quotedMessageId=None, quotedText="Use the blue design")
    )

    assert event is not None
    assert event.reply_to_message_id == "quoted:reply-msg-1"
    assert event.reply_to_text == "Use the blue design"


def test_reply_context_sanitizer_bounds_and_strips_control_chars():
    quoted = "line one\x00\x07\r\n" + ("x" * 1100)

    sanitized = WhatsAppAdapter._sanitize_reply_context_text(quoted)

    assert "\x00" not in sanitized
    assert "\x07" not in sanitized
    assert "\r" not in sanitized
    assert sanitized.startswith("line one")
    assert sanitized.endswith("…")
    assert len(sanitized) <= 1000


@pytest.mark.asyncio
async def test_gateway_prepares_agent_visible_reply_context_prefix():
    from gateway.platforms.base import MessageEvent
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = GatewayConfig(group_sessions_per_user=True)
    runner.adapters = {}
    setattr(runner, "_model", "test-model")
    setattr(runner, "_base_url", "")
    runner._has_setup_skill = lambda: False

    source = SessionSource(
        platform=Platform.WHATSAPP,
        chat_id="15551234567@s.whatsapp.net",
        chat_type="dm",
        user_id="15551234567@s.whatsapp.net",
        user_name="Alice",
    )
    event = MessageEvent(
        text="yes, do that",
        source=source,
        message_id="reply-msg-1",
        reply_to_message_id="orig-msg-1",
        reply_to_text="Should I book the 4pm flight?",
    )

    prepared = await runner._prepare_inbound_message_text(
        event=event,
        source=source,
        history=[],
    )

    assert prepared == (
        '[Replying to: "Should I book the 4pm flight?"]\n\n'
        "yes, do that"
    )
