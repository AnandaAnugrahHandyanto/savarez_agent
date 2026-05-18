"""Tests for the agent.sanitize_provider_errors config surface.

When Hermes is operated as a managed service, the raw upstream provider
error returned in the user-facing ``final_response`` after an exhausted
API-failure retry loop can embed billing-dashboard URLs, account
identifiers, and internal endpoint hosts.  ``agent.sanitize_provider_errors``
replaces that user-facing string with a generic, category-based message
while keeping full detail in logs and the telemetry ``error`` field.
"""
from unittest.mock import patch

from run_agent import AIAgent
from agent.error_classifier import FailoverReason


def _make_agent(sanitize=None):
    """Build an AIAgent with a mocked config that optionally sets
    agent.sanitize_provider_errors."""
    cfg = {"agent": {}}
    if sanitize is not None:
        cfg["agent"]["sanitize_provider_errors"] = sanitize

    with patch("run_agent.OpenAI"), \
         patch("hermes_cli.config.load_config", return_value=cfg):
        return AIAgent(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            model="test/model",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )


def test_default_sanitize_provider_errors_is_false():
    """No config override → legacy verbatim-error behavior preserved."""
    agent = _make_agent()
    assert agent._sanitize_provider_errors is False


def test_sanitize_provider_errors_honors_truthy_values():
    """Boolean true and the common truthy strings all enable sanitization."""
    for value in (True, "true", "True", "1", "yes"):
        agent = _make_agent(sanitize=value)
        assert agent._sanitize_provider_errors is True, value


def test_sanitize_provider_errors_honors_falsy_values():
    """Boolean false and other strings leave sanitization disabled."""
    for value in (False, "false", "no", "0", "off"):
        agent = _make_agent(sanitize=value)
        assert agent._sanitize_provider_errors is False, value


def test_sanitized_user_error_messages_leak_no_provider_detail():
    """Every classified reason maps to a generic message that contains no
    URLs, no scheme prefixes, and no raw provider plumbing."""
    for reason in FailoverReason:
        msg = AIAgent._sanitized_user_error(reason)
        assert msg, reason
        lowered = msg.lower()
        assert "http" not in lowered, reason
        assert "://" not in msg, reason
        assert "openrouter" not in lowered, reason
        assert ".ai" not in lowered, reason


def test_sanitized_user_error_distinguishes_billing_from_rate_limit():
    """The generic message still conveys *what kind* of failure occurred."""
    billing = AIAgent._sanitized_user_error(FailoverReason.billing)
    rate_limit = AIAgent._sanitized_user_error(FailoverReason.rate_limit)
    assert billing != rate_limit
    assert "billing" in billing.lower() or "quota" in billing.lower()
    assert "busy" in rate_limit.lower() or "try again" in rate_limit.lower()


def test_sanitized_user_error_unknown_reason_falls_back():
    """An unmapped reason still yields a safe generic message."""
    msg = AIAgent._sanitized_user_error(FailoverReason.unknown)
    assert "unavailable" in msg.lower()
