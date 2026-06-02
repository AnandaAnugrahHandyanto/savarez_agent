"""Tests for WhatsApp bridge read-receipt behavior."""

from pathlib import Path


BRIDGE_JS = Path(__file__).resolve().parents[2] / "scripts" / "whatsapp-bridge" / "bridge.js"


def test_bridge_marks_incoming_messages_read_before_queueing_for_agent():
    """Accepted incoming WhatsApp messages should be marked read immediately.

    This gives senders WhatsApp read receipts (blue ticks / seen) as soon as
    the bridge has accepted the message for Hermes, rather than only after the
    agent sends a reply.
    """
    source = BRIDGE_JS.read_text(encoding="utf-8")

    read_call = "await sock.readMessages([msg.key]);"
    queue_call = "messageQueue.push(event);"

    assert read_call in source
    assert source.index(read_call) < source.index(queue_call)
