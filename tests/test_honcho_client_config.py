"""Tests for Honcho client configuration."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from plugins.memory.honcho.client import HonchoClientConfig, _sanitize_honcho_id


class TestHonchoClientConfigAutoEnable:
    """Test auto-enable behavior when API key is present."""

    def test_auto_enables_when_api_key_present_no_explicit_enabled(self, tmp_path):
        """When API key exists and enabled is not set, should auto-enable."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "apiKey": "test-api-key-12345",
            # Note: no "enabled" field
        }))

        cfg = HonchoClientConfig.from_global_config(config_path=config_path)

        assert cfg.api_key == "test-api-key-12345"
        assert cfg.enabled is True  # Auto-enabled because API key exists

    def test_respects_explicit_enabled_false(self, tmp_path):
        """When enabled is explicitly False, should stay disabled even with API key."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "apiKey": "test-api-key-12345",
            "enabled": False,  # Explicitly disabled
        }))

        cfg = HonchoClientConfig.from_global_config(config_path=config_path)

        assert cfg.api_key == "test-api-key-12345"
        assert cfg.enabled is False  # Respects explicit setting

    def test_respects_explicit_enabled_true(self, tmp_path):
        """When enabled is explicitly True, should be enabled."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "apiKey": "test-api-key-12345",
            "enabled": True,
        }))

        cfg = HonchoClientConfig.from_global_config(config_path=config_path)

        assert cfg.api_key == "test-api-key-12345"
        assert cfg.enabled is True

    def test_disabled_when_no_api_key_and_no_explicit_enabled(self, tmp_path):
        """When no API key and enabled not set, should be disabled."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "workspace": "test",
            # No apiKey, no enabled
        }))

        # Clear env var if set
        env_key = os.environ.pop("HONCHO_API_KEY", None)
        try:
            cfg = HonchoClientConfig.from_global_config(config_path=config_path)
            assert cfg.api_key is None
            assert cfg.enabled is False  # No API key = not enabled
        finally:
            if env_key:
                os.environ["HONCHO_API_KEY"] = env_key

    def test_auto_enables_with_env_var_api_key(self, tmp_path, monkeypatch):
        """When API key is in env var (not config), should auto-enable."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "workspace": "test",
            # No apiKey in config
        }))

        monkeypatch.setenv("HONCHO_API_KEY", "env-api-key-67890")

        cfg = HonchoClientConfig.from_global_config(config_path=config_path)

        assert cfg.api_key == "env-api-key-67890"
        assert cfg.enabled is True  # Auto-enabled from env var API key

    def test_from_env_always_enabled(self, monkeypatch):
        """from_env() should always set enabled=True."""
        monkeypatch.setenv("HONCHO_API_KEY", "env-test-key")

        cfg = HonchoClientConfig.from_env()

        assert cfg.api_key == "env-test-key"
        assert cfg.enabled is True

    def test_falls_back_to_env_when_no_config_file(self, tmp_path, monkeypatch):
        """When config file doesn't exist, should fall back to from_env()."""
        nonexistent = tmp_path / "nonexistent.json"
        monkeypatch.setenv("HONCHO_API_KEY", "fallback-key")

        cfg = HonchoClientConfig.from_global_config(config_path=nonexistent)

        assert cfg.api_key == "fallback-key"
        assert cfg.enabled is True  # from_env() sets enabled=True


class TestSanitizeHonchoId:
    """Test _sanitize_honcho_id replaces non-alphanumeric chars with hyphens."""

    def test_dots_replaced(self):
        assert _sanitize_honcho_id("hermes.asher") == "hermes-asher"

    def test_multiple_dots(self):
        assert _sanitize_honcho_id("a.b.c.d") == "a-b-c-d"

    def test_colons_replaced(self):
        assert _sanitize_honcho_id("hermes:profile") == "hermes-profile"

    def test_valid_id_unchanged(self):
        assert _sanitize_honcho_id("hermes-asher_01") == "hermes-asher_01"

    def test_plain_host_unchanged(self):
        assert _sanitize_honcho_id("hermes") == "hermes"

    def test_leading_trailing_special_stripped(self):
        assert _sanitize_honcho_id(".hermes.") == "hermes"

    def test_consecutive_special_collapsed(self):
        assert _sanitize_honcho_id("a..b") == "a-b"


class TestDotProfileSanitization:
    """Regression tests for #30246: dot-containing profiles produce valid IDs."""

    def test_from_global_config_sanitizes_workspace_and_ai_peer(self, tmp_path, monkeypatch):
        """workspace_id and ai_peer derived from a dotted host must be sanitized."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "apiKey": "test-key",
        }))
        # Simulate resolve_active_host() returning "hermes.asher"
        monkeypatch.setattr(
            "plugins.memory.honcho.client.resolve_active_host",
            lambda: "hermes.asher",
        )
        cfg = HonchoClientConfig.from_global_config(config_path=config_path)
        assert cfg.workspace_id == "hermes-asher"
        assert cfg.ai_peer == "hermes-asher"

    def test_from_env_sanitizes_ai_peer(self, monkeypatch):
        """from_env() must sanitize ai_peer derived from a dotted host."""
        monkeypatch.setattr(
            "plugins.memory.honcho.client.resolve_active_host",
            lambda: "hermes.asher",
        )
        monkeypatch.setenv("HONCHO_API_KEY", "test-key")
        cfg = HonchoClientConfig.from_env()
        assert cfg.ai_peer == "hermes-asher"

    def test_from_env_sanitizes_explicit_workspace(self, monkeypatch):
        """from_env() must sanitize a caller-supplied dotted workspace_id."""
        monkeypatch.setenv("HONCHO_API_KEY", "test-key")
        cfg = HonchoClientConfig.from_env(workspace_id="org.team")
        assert cfg.workspace_id == "org-team"
