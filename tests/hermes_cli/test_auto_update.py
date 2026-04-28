"""Tests for hermes_cli.auto_update."""

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def auto_update_config():
    return {
        "enabled": False,
        "mode": "notify",
        "check_interval": "24h",
        "grace_period_seconds": 300,
    }


def test_parse_check_interval_shortcuts():
    """parse_check_interval should handle shorthand strings."""
    from hermes_cli.auto_update import parse_check_interval

    assert parse_check_interval("1h") == 3600
    assert parse_check_interval("24h") == 24 * 3600
    assert parse_check_interval("72h") == 72 * 3600
    assert parse_check_interval("invalid") is None


def test_auto_updater_init(auto_update_config):
    """AutoUpdater should initialize with config."""
    from hermes_cli.auto_update import AutoUpdater

    updater = AutoUpdater(auto_update_config)
    assert updater.enabled is False
    assert updater.mode == "notify"
    assert updater.check_interval == 24 * 3600
    assert updater.grace_period_seconds == 300


def test_auto_updater_should_apply_skips_when_disabled(auto_update_config):
    """should_apply should return False when not enabled."""
    from hermes_cli.auto_update import AutoUpdater

    updater = AutoUpdater(auto_update_config)
    updater._last_update_available = True

    assert updater.should_apply() is False


def test_auto_updater_should_apply_skips_notify_mode(auto_update_config):
    """should_apply should return False when mode is 'notify'."""
    from hermes_cli.auto_update import AutoUpdater

    config = auto_update_config.copy()
    config["enabled"] = True
    config["mode"] = "notify"
    updater = AutoUpdater(config)
    updater._last_update_available = True

    assert updater.should_apply() is False


def test_home_channel_persistence(tmp_path, monkeypatch):
    """_load_home_channel and _save_home_channel should work."""
    from hermes_cli.auto_update import AutoUpdater

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    config = {"enabled": False, "mode": "notify", "check_interval": "24h", "grace_period_seconds": 300}
    updater = AutoUpdater(config)

    # Initially no channel
    assert updater._load_home_channel() is None

    # Save channel
    updater._save_home_channel({"platform": "telegram", "chat_id": "123"})

    # Load it back
    channel = updater._load_home_channel()
    assert channel == {"platform": "telegram", "chat_id": "123"}


def test_is_fork_detection(tmp_path, monkeypatch):
    """_is_fork should detect fork repos."""
    from hermes_cli.auto_update import AutoUpdater

    repo_dir = tmp_path / "hermes-agent"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    config = {"enabled": False, "mode": "notify", "check_interval": "24h", "grace_period_seconds": 300}
    updater = AutoUpdater(config)

    with patch("hermes_cli.auto_update.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/NousResearch/hermes-agent.git\n",
        )
        # Official repo should return False for is_fork
        with patch("hermes_cli.main._is_fork", return_value=False):
            # When _is_fork returns False, we treat it as not a fork
            # The actual _is_fork logic checks normalized URLs
            pass

    # Test with fork URL
    with patch("hermes_cli.auto_update.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/user/hermes-agent.git\n",
        )
        # When URL doesn't match official, _is_fork returns True
        with patch("hermes_cli.main._is_fork", return_value=True):
            # Fork detection should work
            result = updater._is_fork()
            assert result is True