"""Tests for structural output redaction in gateway and cron delivery paths.

Verifies that credentials/secrets in the LLM's final response are redacted
before reaching external platforms (Discord, Telegram, etc.).

This is a defense-in-depth measure: tool outputs are already redacted
individually, but the LLM can compose responses that re-state secrets.
"""

import pytest

from agent.redact import redact_sensitive_text


class TestResponseRedaction:
    """Verify redact_sensitive_text catches common credential patterns."""

    def test_openai_api_key_redacted(self):
        response = "Your API key is sk-proj-abc123def456ghi789jkl012mno345pqr678stu901vwx234"
        result = redact_sensitive_text(response)
        assert "abc123def456ghi789jkl012" not in result

    def test_github_pat_redacted(self):
        response = "I found the token: ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        result = redact_sensitive_text(response)
        assert "1234567890abcdefghij" not in result

    def test_anthropic_key_redacted(self):
        response = "The Anthropic key is sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890"
        result = redact_sensitive_text(response)
        assert "abcdefghijklmno" not in result

    def test_env_assignment_redacted(self):
        response = 'In your .env file:\nDISCORD_BOT_TOKEN=MTQ4NDk1NzM4OTQ3NTE1.GPP3r-.abc123\nTELEGRAM_BOT_TOKEN=7654321:AAHabcdefghijklmnop'
        result = redact_sensitive_text(response)
        assert "MTQ4NDk1NzM4OTQ3NTE1" not in result

    def test_bearer_token_redacted(self):
        response = "curl -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def'"
        result = redact_sensitive_text(response)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result

    def test_json_api_key_redacted(self):
        response = '{"api_key": "super-secret-key-1234567890abcdef"}'
        result = redact_sensitive_text(response)
        assert "super-secret-key-1234567890" not in result

    def test_private_key_redacted(self):
        response = "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBg\n-----END PRIVATE KEY-----"
        result = redact_sensitive_text(response)
        assert "MIIEvgIBADANBg" not in result

    def test_normal_text_unchanged(self):
        response = "I've updated the configuration file and restarted the service. Everything looks good."
        result = redact_sensitive_text(response)
        assert result == response

    def test_none_input_returns_none(self):
        assert redact_sensitive_text(None) is None

    def test_empty_string_returns_empty(self):
        assert redact_sensitive_text("") == ""

    def test_mixed_content_only_secrets_redacted(self):
        response = (
            "Here's the status:\n"
            "- Server: running\n"
            "- API key: sk-proj-abcdefghijklmnopqrstuvwxyz1234567890abcdef\n"
            "- Port: 8080\n"
        )
        result = redact_sensitive_text(response)
        assert "Server: running" in result
        assert "Port: 8080" in result
        assert "abcdefghijklmnopqrstuvwxyz1234567890" not in result
