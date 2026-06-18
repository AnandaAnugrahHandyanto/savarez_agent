"""Tests for Signal recent-history prompt rendering in gateway.run."""

from gateway.run import _format_recent_signal_chat_history
from gateway.session import _hash_sender_id


def test_format_recent_signal_chat_history_hashes_raw_sender_when_redacting():
    prompt = _format_recent_signal_chat_history(
        [
            {
                "ts": 1712345678000,
                "sender": "+15551234567",
                "name": "+15551234567",
                "text": "hello",
            }
        ],
        redact_pii=True,
    )

    assert "+15551234567" not in prompt
    assert _hash_sender_id("+15551234567") in prompt
    assert "hello" in prompt


def test_format_recent_signal_chat_history_preserves_display_name_when_redacting():
    prompt = _format_recent_signal_chat_history(
        [
            {
                "ts": 1712345678000,
                "sender": "+15551234567",
                "name": "Alice",
                "text": "hello",
            }
        ],
        redact_pii=True,
    )

    assert "Alice" in prompt
    assert _hash_sender_id("+15551234567") not in prompt


def test_format_recent_signal_chat_history_returns_empty_for_no_messages():
    assert _format_recent_signal_chat_history([], redact_pii=True) == ""
