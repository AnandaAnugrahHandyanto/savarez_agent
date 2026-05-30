from __future__ import annotations

import threading

from tools.approval import (
    register_gateway_notify,
    request_gateway_approval,
    resolve_gateway_approval,
    unregister_gateway_notify,
)


def test_request_gateway_approval_enqueues_structured_metadata_without_shell_command():
    session_key = "semantic-session"
    observed = {}

    def notify(data):
        observed.update(data)
        threading.Timer(0.01, lambda: resolve_gateway_approval(session_key, "once")).start()

    register_gateway_notify(session_key, notify)
    try:
        result = request_gateway_approval(
            session_key,
            description="Workit/M365 write approval",
            metadata={
                "system": "khaw-workit",
                "provider": "m365",
                "operation": "m365.outlook.send",
                "payload_hash": "abc123",
            },
        )
    finally:
        unregister_gateway_notify(session_key)

    assert result["approved"] is True
    assert observed["approval_type"] == "semantic"
    assert observed["command"] == ""
    assert observed["metadata"]["operation"] == "m365.outlook.send"
    assert observed["metadata"]["payload_hash"] == "abc123"


def test_request_gateway_approval_fails_closed_without_gateway_notify():
    result = request_gateway_approval(
        "missing-session",
        description="Workit/M365 write approval",
        metadata={"system": "khaw-workit"},
    )

    assert result["approved"] is False
    assert result["reason"] == "gateway_notify_unavailable"
