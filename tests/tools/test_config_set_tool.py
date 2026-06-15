"""Tests for tools/config_set_tool.py — whitelist, blacklist, credential guard.

Each test file runs in its own subprocess (see scripts/run_tests.sh) with:
  - HERMES_HOME pointing to a per-test tempdir
  - TZ=UTC, LANG=C.UTF-8, PYTHONHASHSEED=0
  - All credential env vars unset

We test the pure guard functions directly (fast, no side-effects) and the
full handler with a real temporary config.yaml where possible.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Ensure tools/ is importable (repo root is added by conftest, but be explicit)
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.config_set_tool import (
    BLACKLIST_SUFFIXES,
    WHITELIST_PREFIXES,
    _audit_log,
    _is_blacklisted,
    _is_credential_shaped,
    _is_whitelisted,
    _key_matches_any,
    config_set_value,
)


# =========================================================================
# _is_whitelisted
# =========================================================================


class TestIsWhitelisted:
    """Whitelist prefix matching."""

    def test_exact_prefix_match(self):
        assert _is_whitelisted("mcp_servers") is True

    def test_child_of_whitelisted_prefix(self):
        assert _is_whitelisted("mcp_servers.context7.command") is True
        assert _is_whitelisted("mcp_servers.context7.args") is True
        assert _is_whitelisted("stt.enabled") is True
        assert _is_whitelisted("tts.provider") is True
        assert _is_whitelisted("display.skin") is True
        assert _is_whitelisted("compression.enabled") is True
        assert _is_whitelisted("auxiliary.vision.model") is True

    def test_deeply_nested_child(self):
        assert _is_whitelisted("mcp_servers.context7.env.SOME_VAR") is True

    def test_not_whitelisted(self):
        assert _is_whitelisted("model") is False
        assert _is_whitelisted("model.default") is False
        assert _is_whitelisted("approvals.mode") is False
        assert _is_whitelisted("terminal.backend") is False
        assert _is_whitelisted("OPENROUTER_API_KEY") is False

    def test_case_insensitive(self):
        assert _is_whitelisted("MCP_SERVERS") is True
        assert _is_whitelisted("Stt.Enabled") is True


# =========================================================================
# _is_blacklisted
# =========================================================================


class TestIsBlacklisted:
    """Blacklist suffix matching."""

    def test_exact_blacklisted_key(self):
        assert _is_blacklisted("approvals.mode") is True
        assert _is_blacklisted("security.redact") is True
        assert _is_blacklisted("terminal.backend") is True
        assert _is_blacklisted("model.default") is True

    def test_child_of_blacklisted(self):
        assert _is_blacklisted("approvals.mode.something") is True

    def test_not_blacklisted(self):
        assert _is_blacklisted("stt.enabled") is False
        assert _is_blacklisted("display.skin") is False
        assert _is_blacklisted("mcp_servers.context7.command") is False

    def test_case_insensitive_blacklist(self):
        assert _is_blacklisted("Approvals.Mode") is True
        assert _is_blacklisted("TERMINAL.BACKEND") is True


# =========================================================================
# _is_credential_shaped
# =========================================================================


class TestIsCredentialShaped:
    """Credential-shape guard — blocks values that look like secrets."""

    def test_openai_style_key(self):
        assert _is_credential_shaped("sk-abc123def456ghi789jkl012mno") is True

    def test_github_pat(self):
        assert _is_credential_shaped("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef") is True

    def test_redacted_marker(self):
        assert _is_credential_shaped("***") is True
        assert _is_credential_shaped("[REDACTED]") is True

    def test_long_opaque_token(self):
        assert _is_credential_shaped("a" * 40) is True
        assert _is_credential_shaped("x" * 50) is True

    def test_slack_token(self):
        assert _is_credential_shaped("xoxb-123-456-abcdef") is True

    def test_telegram_bot_token(self):
        assert _is_credential_shaped("bot123456789:ABCdefGHIjklMNOpqrSTUvwxYZ") is True

    def test_normal_values_not_blocked(self):
        assert _is_credential_shaped("true") is False
        assert _is_credential_shaped("false") is False
        assert _is_credential_shaped("npx") is False
        assert _is_credential_shaped("@upstash/context7-mcp") is False
        assert _is_credential_shaped("anthropic/claude-sonnet-4") is False
        assert _is_credential_shaped("http://localhost:3000") is False
        assert _is_credential_shaped("edge") is False
        assert _is_credential_shaped("en") is False
        assert _is_credential_shaped("5000") is False
        assert _is_credential_shaped("") is False

    def test_short_strings_not_blocked(self):
        assert _is_credential_shaped("hi") is False
        assert _is_credential_shaped("abc") is False
        assert _is_credential_shaped("test") is False


# =========================================================================
# _key_matches_any
# =========================================================================


class TestKeyMatchesAny:
    """Prefix/equality matching helper."""

    def test_exact_match(self):
        assert _key_matches_any("model.default", ["model.default"]) is True

    def test_prefix_match(self):
        assert _key_matches_any("mcp_servers.context7.command", ["mcp_servers"]) is True

    def test_no_match(self):
        assert _key_matches_any("model.default", ["mcp_servers", "stt"]) is False


# =========================================================================
# Blacklist/whitelist cross-check
# =========================================================================


class TestWhitelistBlacklistInteraction:
    """Ensure blacklist always takes precedence over whitelist."""

    @pytest.mark.parametrize("key", [
        "approvals.mode",
        "security.redact",
        "terminal.backend",
        "model.default",
        "model.provider",
        "model.api_key",
        "delegation.max_spawn_depth",
    ])
    def test_blacklisted_keys_always_rejected(self, key: str):
        # Even if a key somehow matches whitelist prefix, blacklist wins
        # Our current whitelist doesn't overlap with blacklist, but guard anyway
        assert _is_blacklisted(key) is True

    @pytest.mark.parametrize("key", [
        "mcp_servers.context7.command",
        "stt.enabled",
        "tts.provider",
        "display.skin",
        "compression.enabled",
        "auxiliary.vision.model",
    ])
    def test_whitelisted_non_blacklisted_keys_allowed(self, key: str):
        assert _is_blacklisted(key) is False
        assert _is_whitelisted(key) is True


# =========================================================================
# config_set_value (integration, with mocked hermes_cli.config)
# =========================================================================


class TestConfigSetValueIntegration:
    """Test config_set_value with mocked set_config_value."""

    def _call(self, key: str, value: str, *, set_config_mock=None) -> dict:
        """Helper: call config_set_value and return parsed JSON."""
        with mock.patch("hermes_cli.config.set_config_value") as m:
            if set_config_mock:
                m.side_effect = set_config_mock
            result = config_set_value(key, value, session_id="test-session")
            return json.loads(result)

    # --- Blacklist ---

    def test_blacklisted_key_blocked(self):
        result = self._call("approvals.mode", "auto")
        assert "error" in result
        assert result.get("blocked") is True
        assert "suggestion" in result

    def test_blacklisted_model_key_blocked(self):
        result = self._call("model.default", "anthropic/claude-sonnet-4")
        assert "error" in result
        assert result.get("blocked") is True

    # --- Not whitelisted ---

    def test_non_whitelisted_key_rejected(self):
        result = self._call("unknown_key", "value")
        assert "error" in result
        assert result.get("not_whitelisted") is True

    # --- Credential guard ---

    def test_credential_shaped_value_blocked(self):
        result = self._call("mcp_servers.context7.env.API_KEY", "sk-abc123def456ghi789jkl012")
        assert "error" in result
        assert result.get("credential_blocked") is True
        assert result.get("issue_ref") == "#42727"

    # --- Successful set ---

    def test_normal_set_succeeds(self):
        result = self._call("stt.enabled", "true")
        assert result.get("success") is True
        assert result.get("requires_restart") is True
        assert result.get("audit_logged") is True

    def test_mcp_server_command_set_succeeds(self):
        result = self._call("mcp_servers.context7.command", "npx")
        assert result.get("success") is True

    def test_display_skin_set_succeeds(self):
        result = self._call("display.skin", "dark")
        assert result.get("success") is True

    # --- Error propagation ---

    def test_set_config_value_error_propagated(self):
        def boom(key, value):
            raise RuntimeError("disk full")

        result = self._call("stt.enabled", "true", set_config_mock=boom)
        assert "error" in result
        assert "disk full" in result["error"]


# =========================================================================
# Audit log
# =========================================================================


class TestAuditLog:
    """Audit log writes to HERMES_HOME/logs/config_changes.log."""

    def test_audit_log_creates_file(self, tmp_path: Path):
        log_dir = tmp_path / "logs"
        log_path = log_dir / "config_changes.log"

        with mock.patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            _audit_log("stt.enabled", "false", "true", session_id="test-123")

        assert log_path.exists()
        content = log_path.read_text()
        assert "stt.enabled" in content
        assert "test-123" in content
        assert "true" in content  # new value logged

    def test_audit_log_redacts_credential_values(self, tmp_path: Path):
        log_path = tmp_path / "logs" / "config_changes.log"

        with mock.patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            _audit_log(
                "mcp_servers.context7.env.KEY",
                "old",
                "sk-abc123def456ghi789jkl012",
                session_id="test-456",
            )

        content = log_path.read_text()
        assert "REDACTED" in content
        assert "sk-abc123" not in content

    def test_audit_log_no_crash_on_missing_dir(self):
        """Audit log should silently skip if HERMES_HOME is weird."""
        with mock.patch.dict(os.environ, {"HERMES_HOME": "/nonexistent/path/xyz"}):
            # Should not raise
            _audit_log("key", "old", "new", session_id="test")
