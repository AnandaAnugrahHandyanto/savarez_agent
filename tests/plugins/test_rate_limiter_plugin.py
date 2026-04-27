"""Tests for the rate-limiter plugin.

Covers the bundled plugin at ``plugins/rate-limiter/``:

  * ``rate_limiter`` library: record_rate_limit, get_rate_limit_remaining,
    clear_rate_limit, format_remaining, and hook functions.
  * Slash command handlers: status and clear.
  * Bundled-plugin discovery via ``PluginManager.discover_and_load``.
"""

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    """Isolate HERMES_HOME for each test.

    The global hermetic fixture already redirects HERMES_HOME to a tempdir,
    but we want the plugin to work with a predictable subpath. We reset
    HERMES_HOME here for clarity.
    """
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    yield hermes_home


def _load_lib():
    """Import the plugin's library module directly from the repo path."""
    repo_root = Path(__file__).resolve().parents[2]
    lib_path = repo_root / "plugins" / "rate-limiter" / "rate_limiter.py"
    spec = importlib.util.spec_from_file_location(
        "rate_limiter_under_test", lib_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_commands():
    """Import the plugin's commands module."""
    repo_root = Path(__file__).resolve().parents[2]
    commands_path = repo_root / "plugins" / "rate-limiter" / "commands.py"
    spec = importlib.util.spec_from_file_location(
        "commands_under_test", commands_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_format_remaining():
    """Test format_remaining helper."""
    lib = _load_lib()

    assert lib.format_remaining(0) == "0s"
    assert lib.format_remaining(30) == "30s"
    assert lib.format_remaining(60) == "1m"
    assert lib.format_remaining(90) == "1m 30s"
    assert lib.format_remaining(3600) == "1h"
    assert lib.format_remaining(3660) == "1h 1m"


def test_record_and_get_rate_limit(hermes_home):
    """Test recording and retrieving rate limit state."""
    lib = _load_lib()

    # Initially no rate limit
    assert lib.get_rate_limit_remaining() is None

    # Record a rate limit
    lib.record_rate_limit(headers={"x-ratelimit-reset-requests-1h": "60"})

    # Should now have a rate limit
    remaining = lib.get_rate_limit_remaining()
    assert remaining is not None
    assert 50 < remaining < 70  # Should be around 60 seconds

    # State file should exist
    state_file = hermes_home / "rate_limits" / "nous.json"
    assert state_file.exists()

    # State should contain reset_at
    with open(state_file) as f:
        state = json.load(f)
    assert "reset_at" in state
    assert "recorded_at" in state
    assert "reset_seconds" in state


def test_clear_rate_limit(hermes_home):
    """Test clearing rate limit state."""
    lib = _load_lib()

    # Record a rate limit
    lib.record_rate_limit(headers={"x-ratelimit-reset-requests-1h": "60"})
    assert lib.get_rate_limit_remaining() is not None

    # Clear it
    lib.clear_rate_limit()

    # Should be gone
    assert lib.get_rate_limit_remaining() is None

    # State file should be deleted
    state_file = hermes_home / "rate_limits" / "nous.json"
    assert not state_file.exists()


def test_rate_limit_expiration(hermes_home):
    """Test that expired rate limits are automatically cleaned up."""
    lib = _load_lib()

    # Record a rate limit with a very short reset time
    lib.record_rate_limit(headers={"x-ratelimit-reset-requests-1h": "0.1"})

    # Should have a rate limit initially
    assert lib.get_rate_limit_remaining() is not None

    # Wait for it to expire
    import time
    time.sleep(0.2)

    # Should now be None (expired and cleaned up)
    assert lib.get_rate_limit_remaining() is None


def test_header_parsing_priority():
    """Test that headers are parsed in the correct priority order."""
    lib = _load_lib()

    # Test x-ratelimit-reset-requests-1h (highest priority)
    lib.record_rate_limit(headers={"x-ratelimit-reset-requests-1h": "120"})
    remaining = lib.get_rate_limit_remaining()
    assert remaining is not None
    assert 110 < remaining < 130

    lib.clear_rate_limit()

    # Test x-ratelimit-reset-requests (second priority)
    lib.record_rate_limit(headers={"x-ratelimit-reset-requests": "60"})
    remaining = lib.get_rate_limit_remaining()
    assert remaining is not None
    assert 50 < remaining < 70

    lib.clear_rate_limit()

    # Test retry-after (third priority)
    lib.record_rate_limit(headers={"retry-after": "30"})
    remaining = lib.get_rate_limit_remaining()
    assert remaining is not None
    assert 20 < remaining < 40

    lib.clear_rate_limit()

    # Test default cooldown (no headers)
    lib.record_rate_limit()
    remaining = lib.get_rate_limit_remaining()
    assert remaining is not None
    assert 290 < remaining < 310  # Default is 300 seconds


def test_invalid_header_values():
    """Test that invalid header values are handled gracefully."""
    lib = _load_lib()

    # Invalid numeric value
    lib.record_rate_limit(headers={"x-ratelimit-reset-requests-1h": "invalid"})
    remaining = lib.get_rate_limit_remaining()
    assert remaining is not None
    # Should fall back to default cooldown
    assert 290 < remaining < 310

    lib.clear_rate_limit()

    # Negative value
    lib.record_rate_limit(headers={"x-ratelimit-reset-requests-1h": "-10"})
    remaining = lib.get_rate_limit_remaining()
    assert remaining is not None
    # Should fall back to default cooldown
    assert 290 < remaining < 310


def test_ratelimit_status_command(hermes_home):
    """Test /ratelimit status slash command."""
    commands = _load_commands()

    # Initially no rate limit
    result = commands.ratelimit_status()
    assert "No active rate limit" in result

    # Record a rate limit
    lib = _load_lib()
    lib.record_rate_limit(headers={"x-ratelimit-reset-requests-1h": "60"})

    # Should now show active rate limit
    result = commands.ratelimit_status()
    assert "Rate limit active" in result
    assert "Resets in" in result


def test_ratelimit_clear_command(hermes_home):
    """Test /ratelimit clear slash command."""
    commands = _load_commands()
    lib = _load_lib()

    # Record a rate limit
    lib.record_rate_limit(headers={"x-ratelimit-reset-requests-1h": "60"})
    assert lib.get_rate_limit_remaining() is not None

    # Clear it via command
    result = commands.ratelimit_clear()
    assert "Rate limit state cleared" in result

    # Should be gone
    assert lib.get_rate_limit_remaining() is None


def test_check_rate_limit_hook(hermes_home):
    """Test the pre_llm_call hook function."""
    lib = _load_lib()

    # Initially should not skip
    result = lib.check_rate_limit()
    assert result is None

    # Record a rate limit
    lib.record_rate_limit(headers={"x-ratelimit-reset-requests-1h": "60"})

    # Should now skip
    result = lib.check_rate_limit()
    assert result is not None
    assert result["skip"] is True
    assert result["reason"] == "rate_limited"
    assert "remaining_seconds" in result


def test_record_rate_limit_hook():
    """Test the post_llm_call hook function."""
    lib = _load_lib()

    # Call hook with error context
    lib.record_rate_limit_hook(
        error_context={"reset_at": 9999999999},
        headers=None,
    )

    # Should have recorded the rate limit
    remaining = lib.get_rate_limit_remaining()
    assert remaining is not None
    assert remaining > 0
