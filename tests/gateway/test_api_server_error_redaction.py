"""Regression tests for api_server error-message redaction.

Verifies that provider credential material and internal paths are
redacted before crossing the HTTP boundary, covering the fix for
GitHub issue #37733.
"""

import pytest

# ---------------------------------------------------------------------------
# _openai_error redaction
# ---------------------------------------------------------------------------

class TestOpenaiErrorRedaction:
    """_openai_error must redact sensitive text in the message field."""

    def test_redacts_api_key_in_message(self):
        from gateway.platforms.api_server import _openai_error
        err = _openai_error("Auth failed: sk-proj-abc123XYZ_secret_key_here")
        msg = err["error"]["message"]
        assert "sk-proj-abc123XYZ_secret_key_here" not in msg
        assert "***" in msg or "sk-proj" not in msg

    def test_redacts_bearer_token(self):
        from gateway.platforms.api_server import _openai_error
        err = _openai_error("Error: Bearer ghp_abcdefghijklmnopqrstuvwxyz123456")
        msg = err["error"]["message"]
        assert "ghp_abcdefghijklmnopqrstuvwxyz123456" not in msg

    def test_preserves_error_structure(self):
        from gateway.platforms.api_server import _openai_error
        err = _openai_error("Something broke", err_type="server_error", code="test_code")
        assert err["error"]["type"] == "server_error"
        assert err["error"]["code"] == "test_code"
        assert "Something broke" in err["error"]["message"]

    def test_handles_non_string_message(self):
        from gateway.platforms.api_server import _openai_error
        # message could be an exception object passed via f-string
        err = _openai_error(str(ValueError("test error")))
        assert "test error" in err["error"]["message"]

    def test_redacts_openai_key_format(self):
        from gateway.platforms.api_server import _openai_error
        err = _openai_error("Provider error: key sk-1234567890abcdef1234567890abcdef")
        msg = err["error"]["message"]
        assert "sk-1234567890abcdef1234567890abcdef" not in msg

    def test_redacts_anthropic_key_format(self):
        from gateway.platforms.api_server import _openai_error
        err = _openai_error("Authentication failed: sk-ant-api03-abcdefghij1234567890")
        msg = err["error"]["message"]
        assert "sk-ant-api03-abcdefghij1234567890" not in msg


# ---------------------------------------------------------------------------
# redact_sensitive_text import
# ---------------------------------------------------------------------------

class TestRedactImport:
    """Verify the redaction function is importable in api_server."""

    def test_redact_function_available(self):
        from gateway.platforms.api_server import redact_sensitive_text
        result = redact_sensitive_text("test sk-proj-secret123 text", force=True)
        assert "sk-proj-secret123" not in result

    def test_redact_passthrough_on_clean_text(self):
        from gateway.platforms.api_server import redact_sensitive_text
        result = redact_sensitive_text("no secrets here", force=True)
        assert result == "no secrets here"
