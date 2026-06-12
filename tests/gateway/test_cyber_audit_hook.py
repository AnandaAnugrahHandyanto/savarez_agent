"""Tests for the built-in AgentCyber audit hook."""

import pytest

from gateway.builtin_hooks import cyber_audit


@pytest.mark.asyncio
async def test_cyber_audit_records_route_metadata(monkeypatch):
    written = []
    monkeypatch.setenv("HERMES_CYBER_AUDIT", "true")
    monkeypatch.setattr(cyber_audit, "_write", lambda record: written.append(record))

    route = {
        "route": "ir_breakglass",
        "provider_preference": "local_open_weight",
        "reason": "lockout or incident recovery request",
        "requires_hosted_secret_confirmation": True,
        "explicit_override": None,
    }

    await cyber_audit.handle(
        "agent:end",
        {
            "session_id": "sess-1",
            "platform": "discord",
            "cyber_route": route,
            "response": "ok",
        },
    )

    assert len(written) == 1
    assert written[0]["cyber_route"] == route
