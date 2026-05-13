"""Tests for gateway_restart_notification config bridge in gateway/config.py.

Tests that the `gateway_restart_notification` key from platform config
is properly bridged to PlatformConfig.extra dict via load_gateway_config().
"""

import os

import pytest

from gateway.config import GatewayConfig, Platform, load_gateway_config


def test_gateway_restart_notification_bridged_to_platform_extra(tmp_path, monkeypatch):
    """gateway_restart_notification from platform config should be available in PlatformConfig.extra."""
    # Create a test config.yaml with telegram gateway and gateway_restart_notification
    config_dir = tmp_path / "test-false"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("""
gateway:
  platforms:
    telegram:
      enabled: true
      bot_token: "fake-token-for-test"
      gateway_restart_notification: false
""")

    # Mock HOME and HERMES_HOME environment to use test config directory
    monkeypatch.setenv("HOME", str(config_dir))
    monkeypatch.setenv("HERMES_HOME", str(config_dir))
    monkeypatch.setenv("HERMES_CONFIG", "")

    # Load config via load_gateway_config
    config = load_gateway_config()

    # The telegram platform should have gateway_restart_notification in its extra dict
    telegram_extra = config.platforms[Platform.TELEGRAM].extra

    # Assert that gateway_restart_notification is correctly bridged and set to False
    assert "gateway_restart_notification" in telegram_extra
    assert telegram_extra["gateway_restart_notification"] is False


def test_gateway_restart_notification_default_true_when_not_set(tmp_path, monkeypatch):
    """gateway_restart_notification should default to True when not set in config."""
    config_dir = tmp_path / "test-default"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("""
gateway:
  platforms:
    telegram:
      enabled: true
      bot_token: "fake-token-for-test"
""")

    monkeypatch.setenv("HOME", str(config_dir))
    monkeypatch.setenv("HERMES_HOME", str(config_dir))
    monkeypatch.setenv("HERMES_CONFIG", "")

    config = load_gateway_config()
    telegram_extra = config.platforms[Platform.TELEGRAM].extra

    # Should default to True (PlatformConfig default)
    assert "gateway_restart_notification" in telegram_extra
    assert telegram_extra["gateway_restart_notification"] is True
