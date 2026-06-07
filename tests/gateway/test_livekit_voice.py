import json

import pytest

from gateway.livekit_voice import (
    build_dispatch_rule_payload,
    build_inbound_trunk_payload,
    build_livekit_preflight,
    build_room_name,
)


def test_preflight_reports_missing_number_without_blocking_web_mvp():
    env = {
        "LIVEKIT_URL": "wss://pafi-livekit.example.com",
        "LIVEKIT_API_KEY": "livekit-key",
        "LIVEKIT_API_SECRET": "livekit-secret",
    }

    report = build_livekit_preflight(env)

    assert report["ok"] is True
    assert report["ready"]["web_mvp"] is True
    assert report["ready"]["sip_phone"] is False
    assert any(issue["code"] == "missing_phone_number" for issue in report["issues"])


def test_preflight_can_require_phone_number_for_sip_gate():
    env = {
        "LIVEKIT_URL": "wss://pafi-livekit.example.com",
        "LIVEKIT_API_KEY": "livekit-key",
        "LIVEKIT_API_SECRET": "livekit-secret",
    }

    report = build_livekit_preflight(env, require_phone_number=True)

    assert report["ok"] is False
    assert any(
        issue["code"] == "missing_phone_number" and issue["severity"] == "error"
        for issue in report["issues"]
    )


def test_preflight_redacts_secret_values():
    env = {
        "LIVEKIT_URL": "wss://pafi-livekit.example.com",
        "LIVEKIT_API_KEY": "lk_API_KEY_SECRET_VALUE",
        "LIVEKIT_API_SECRET": "lk_API_SECRET_VALUE",
        "HERMES_LIVEKIT_AGENT_NAME": "hermes-live-voice",
    }

    report = build_livekit_preflight(env)
    rendered = json.dumps(report, sort_keys=True)

    assert "lk_API_KEY_SECRET_VALUE" not in rendered
    assert "lk_API_SECRET_VALUE" not in rendered
    assert report["config"]["livekit_api_key"] == "set"
    assert report["config"]["livekit_api_secret"] == "set"


def test_dispatch_rule_payload_uses_explicit_agent_dispatch():
    payload = build_dispatch_rule_payload(
        agent_name="hermes-live-voice",
        room_prefix="hermes-call-",
        metadata={"route": "hermes-main", "mode": "sip"},
        trunk_ids=["ST_123"],
    )

    assert payload == {
        "name": "Hermes live voice dispatch",
        "trunkIds": ["ST_123"],
        "rule": {"dispatchRuleIndividual": {"roomPrefix": "hermes-call-"}},
        "roomConfig": {
            "agents": [
                {
                    "agentName": "hermes-live-voice",
                    "metadata": '{"mode":"sip","route":"hermes-main"}',
                }
            ]
        },
    }


def test_inbound_trunk_payload_requires_e164_number():
    with pytest.raises(ValueError, match="E.164"):
        build_inbound_trunk_payload("0740000000")

    payload = build_inbound_trunk_payload("+40740000000", allowed_numbers=["+40741111111"])

    assert payload == {
        "trunk": {
            "name": "Hermes live voice inbound trunk",
            "numbers": ["+40740000000"],
            "krispEnabled": True,
            "allowedNumbers": ["+40741111111"],
        }
    }


def test_room_name_is_stable_safe_and_prefixed():
    assert build_room_name("Hermes Call ", "Pafi Main Chat", suffix="abc123") == (
        "hermes-call-pafi-main-chat-abc123"
    )
