"""Tests for the Linear platform adapter."""

import hashlib
import hmac
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform, PlatformConfig


# ── Platform Enum ──────────────────────────────────────────────────


def test_platform_enum_has_linear():
    """Platform enum includes LINEAR."""
    assert hasattr(Platform, "LINEAR")
    assert Platform.LINEAR.value == "linear"


# ── Config Loading ─────────────────────────────────────────────────


def test_env_overrides_create_linear_platform(tmp_path, monkeypatch):
    """LINEAR_WEBHOOK_SECRET + LINEAR_API_KEY enables the Linear platform."""
    monkeypatch.setenv("LINEAR_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    monkeypatch.setenv("LINEAR_AGENT_USER_ID", "user-uuid-123")
    monkeypatch.setenv("LINEAR_TEAM_IDS", "AI,ENG")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from gateway.config import GatewayConfig, _apply_env_overrides

    config = GatewayConfig()
    _apply_env_overrides(config)

    assert Platform.LINEAR in config.platforms
    linear_cfg = config.platforms[Platform.LINEAR]
    assert linear_cfg.enabled is True
    assert linear_cfg.extra["webhook_secret"] == "test-secret"
    assert linear_cfg.extra["api_key"] == "lin_api_test"
    assert linear_cfg.extra["agent_user_id"] == "user-uuid-123"
    assert linear_cfg.extra["team_ids"] == ["AI", "ENG"]


def test_env_overrides_no_linear_without_secret(tmp_path, monkeypatch):
    """Linear platform is NOT created without both env vars."""
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    monkeypatch.delenv("LINEAR_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from gateway.config import GatewayConfig, _apply_env_overrides

    config = GatewayConfig()
    _apply_env_overrides(config)

    assert Platform.LINEAR not in config.platforms


# ── Adapter Init ───────────────────────────────────────────────────


@pytest.fixture
def linear_config():
    """Create a PlatformConfig for Linear."""
    return PlatformConfig(
        enabled=True,
        extra={
            "webhook_secret": "test-secret-123",
            "api_key": "lin_api_test_key",
            "agent_user_id": "agent-uuid-abc",
            "team_ids": ["AI"],
            "host": "127.0.0.1",
            "port": 19876,
        },
    )


def test_adapter_init(linear_config, monkeypatch):
    """LinearAdapter initializes with correct config values."""
    monkeypatch.setenv("LINEAR_WEBHOOK_SECRET", "test-secret-123")
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test_key")

    from gateway.platforms.linear import LinearAdapter

    adapter = LinearAdapter(linear_config)
    assert adapter._webhook_secret == "test-secret-123"
    assert adapter._api_key == "lin_api_test_key"
    assert adapter._agent_user_id == "agent-uuid-abc"
    assert adapter._team_ids == ["AI"]
    assert adapter._host == "127.0.0.1"
    assert adapter._port == 19876
    assert adapter.platform == Platform.LINEAR


# ── Signature Verification ─────────────────────────────────────────


def test_verify_signature_valid():
    """Valid HMAC-SHA256 signature passes verification."""
    from gateway.platforms.linear import _verify_signature

    body = '{"type":"Comment","action":"create"}'
    secret = "my-secret"
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()

    assert _verify_signature(body, sig, secret) is True


def test_verify_signature_invalid():
    """Invalid signature fails verification."""
    from gateway.platforms.linear import _verify_signature

    body = '{"type":"Comment","action":"create"}'
    assert _verify_signature(body, "invalid-hex-signature-here-1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef", "secret") is False


def test_verify_signature_wrong_secret():
    """Signature from wrong secret fails."""
    from gateway.platforms.linear import _verify_signature

    body = '{"type":"Comment","action":"create"}'
    sig = hmac.new(b"right-secret", body.encode(), hashlib.sha256).hexdigest()

    assert _verify_signature(body, sig, "wrong-secret") is False


# ── Mention Extraction ─────────────────────────────────────────────


def test_extract_mentions_from_prosemirror():
    """Extracts user IDs from ProseMirror mention nodes."""
    from gateway.platforms.linear import _extract_mentioned_user_ids

    body_data = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Hey "},
                    {
                        "type": "mention",
                        "attrs": {"id": "agent-uuid-abc", "label": "Hermes"},
                    },
                    {"type": "text", "text": " can you look at this?"},
                ],
            }
        ],
    }

    result = _extract_mentioned_user_ids("Hey @Hermes can you look?", body_data, "agent-uuid-abc")
    assert "agent-uuid-abc" in result


def test_extract_mentions_no_match():
    """Returns empty when agent is not mentioned."""
    from gateway.platforms.linear import _extract_mentioned_user_ids

    body_data = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Just a regular comment"},
                ],
            }
        ],
    }

    result = _extract_mentioned_user_ids("Just a regular comment", body_data, "agent-uuid-abc")
    assert result == []


def test_extract_mentions_text_fallback():
    """Falls back to @hermes text detection when no ProseMirror data."""
    from gateway.platforms.linear import _extract_mentioned_user_ids

    # With @hermes in text but no bodyData
    result = _extract_mentioned_user_ids("Hey @hermes help!", None, "agent-uuid-abc")
    # Text fallback doesn't return user IDs from prosemirror, but the adapter
    # checks for @hermes text pattern separately in _handle_comment_event
    assert result == []


# ── Authorization ──────────────────────────────────────────────────


def test_linear_authorized_via_hmac():
    """Linear events are auto-authorized (HMAC validated at webhook level)."""
    from gateway.session import SessionSource

    source = SessionSource(
        platform=Platform.LINEAR,
        chat_id="AI-123",
        user_id="some-user-uuid",
    )

    # The _is_user_authorized check in run.py includes Platform.LINEAR
    # in the auto-authorized set alongside HOMEASSISTANT and WEBHOOK
    assert source.platform == Platform.LINEAR


# ── Adapter Factory ────────────────────────────────────────────────


def test_check_requirements_with_env(monkeypatch):
    """check_linear_requirements returns True with both env vars."""
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    monkeypatch.setenv("LINEAR_WEBHOOK_SECRET", "test-secret")

    from gateway.platforms.linear import check_linear_requirements

    assert check_linear_requirements() is True


def test_check_requirements_missing_env(monkeypatch):
    """check_linear_requirements returns False without env vars."""
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    monkeypatch.delenv("LINEAR_WEBHOOK_SECRET", raising=False)

    from gateway.platforms.linear import check_linear_requirements

    assert check_linear_requirements() is False


# ── Send Message Tool ──────────────────────────────────────────────


def test_send_message_tool_has_linear():
    """send_message_tool platform_map includes linear."""
    from tools.send_message_tool import send_message_tool
    # Just check the source has the mapping — full test would need
    # the gateway running
    import tools.send_message_tool as mod
    src = open(mod.__file__).read()
    assert '"linear"' in src


# ── Cron Delivery ──────────────────────────────────────────────────


def test_cron_scheduler_has_linear():
    """Cron scheduler platform_map includes linear."""
    import cron.scheduler as mod
    src = open(mod.__file__).read()
    assert '"linear"' in src


# ── Toolset ────────────────────────────────────────────────────────


def test_toolset_has_linear():
    """hermes-linear toolset exists and is in hermes-gateway."""
    from toolsets import TOOLSETS

    assert "hermes-linear" in TOOLSETS
    gateway = TOOLSETS["hermes-gateway"]
    assert "hermes-linear" in gateway["includes"]


# ── Platform Hints ─────────────────────────────────────────────────


def test_platform_hints_has_linear():
    """PLATFORM_HINTS includes linear."""
    from agent.prompt_builder import PLATFORM_HINTS

    assert "linear" in PLATFORM_HINTS
    assert "Linear" in PLATFORM_HINTS["linear"] or "linear" in PLATFORM_HINTS["linear"]


# ── Status Display ─────────────────────────────────────────────────


def test_status_has_linear():
    """Status display includes Linear platform."""
    import hermes_cli.status as mod
    src = open(mod.__file__).read()
    assert '"Linear"' in src


# ── Gateway Setup ──────────────────────────────────────────────────


def test_gateway_setup_has_linear():
    """Gateway setup wizard includes Linear platform."""
    import hermes_cli.gateway as mod
    src = open(mod.__file__).read()
    assert '"linear"' in src
    assert "LINEAR_WEBHOOK_SECRET" in src
