"""Test that Nous explicit runtime refreshes expired agent_keys.

This is a regression test for GitHub issue #32068:
https://github.com/NousResearch/hermes-agent/issues/32068

When delegation.provider=nous is configured, sub-agents should fail
over to resolve_nous_runtime_credentials() when the cached agent_key
is expired, rather than using the expired key and causing HTTP 401 errors.
"""

import os
from unittest.mock import patch, MagicMock

from hermes_cli.runtime_provider import _resolve_explicit_runtime


def test_nous_explicit_runtime_refreshes_expired_agent_key():
    """Expired agent_key in explicit runtime should trigger refresh."""
    # Mock the provider auth state with an expired key
    expired_state = {
        "agent_key": "expired.jwt.token",
        "agent_key_expires_at": "2025-01-01T00:00:00Z",  # Far in the past
        "inference_base_url": "https://api.nousresearch.com",
    }

    # Mock get_provider_auth_state to return expired state
    with patch("hermes_cli.runtime_provider.auth_mod.get_provider_auth_state", return_value=expired_state):
        # Mock _agent_key_is_usable to detect expiration
        with patch("hermes_cli.runtime_provider._agent_key_is_usable", return_value=False):
            # Mock resolve_nous_runtime_credentials to return fresh credentials
            fresh_creds = {
                "api_key": "fresh.jwt.token",
                "expires_at": "2099-01-01T00:00:00Z",
                "base_url": "https://api.nousresearch.com",
            }
            with patch("hermes_cli.runtime_provider.resolve_nous_runtime_credentials", return_value=fresh_creds):
                result = _resolve_explicit_runtime(
                    provider="nous",
                    requested_provider="nous",
                    model_cfg={"provider": "nous", "default": "deepseek/deepseek-v4-flash:free"},
                    explicit_api_key=None,
                    explicit_base_url=None,
                )

                # Should return fresh credentials, not expired ones
                assert result is not None
                assert result["api_key"] == "fresh.jwt.token", "Should use refreshed key, not expired cached key"
                assert result["provider"] == "nous"


def test_nous_explicit_runtime_keeps_valid_agent_key():
    """Valid agent_key in explicit runtime should not trigger refresh."""
    # Mock the provider auth state with a valid key
    valid_state = {
        "agent_key": "valid.jwt.token",
        "agent_key_expires_at": "2099-01-01T00:00:00Z",  # Far in the future
        "inference_base_url": "https://api.nousresearch.com",
    }

    # Mock get_provider_auth_state to return valid state
    with patch("hermes_cli.runtime_provider.auth_mod.get_provider_auth_state", return_value=valid_state):
        # Mock _agent_key_is_usable to return True
        with patch("hermes_cli.runtime_provider._agent_key_is_usable", return_value=True):
            # resolve_nous_runtime_credentials should NOT be called
            with patch("hermes_cli.runtime_provider.resolve_nous_runtime_credentials") as mock_resolve:
                result = _resolve_explicit_runtime(
                    provider="nous",
                    requested_provider="nous",
                    model_cfg={"provider": "nous", "default": "deepseek/deepseek-v4-flash:free"},
                    explicit_api_key=None,
                    explicit_base_url=None,
                )

                # Should return cached valid credentials
                assert result is not None
                assert result["api_key"] == "valid.jwt.token", "Should use cached valid key"
                assert result["provider"] == "nous"
                # Refresh function should not have been called
                mock_resolve.assert_not_called()


def test_nous_explicit_runtime_explicit_api_key_bypasses_expiry_check():
    """Explicit api_key bypasses expiry check."""
    # Mock the provider auth state with an expired key
    expired_state = {
        "agent_key": "expired.jwt.token",
        "agent_key_expires_at": "2025-01-01T00:00:00Z",
        "inference_base_url": "https://api.nousresearch.com",
    }

    # Mock get_provider_auth_state to return expired state
    with patch("hermes_cli.runtime_provider.auth_mod.get_provider_auth_state", return_value=expired_state):
        # Mock _agent_key_is_usable (should not be called)
        with patch("hermes_cli.runtime_provider._agent_key_is_usable") as mock_usable:
            # resolve_nous_runtime_credentials should NOT be called
            with patch("hermes_cli.runtime_provider.resolve_nous_runtime_credentials") as mock_resolve:
                result = _resolve_explicit_runtime(
                    provider="nous",
                    requested_provider="nous",
                    model_cfg={"provider": "nous", "default": "deepseek/deepseek-v4-flash:free"},
                    explicit_api_key="user-provided-api-key",  # Explicit key
                    explicit_base_url=None,
                )

                # Should return the explicit key without expiry check
                assert result is not None
                assert result["api_key"] == "user-provided-api-key", "Should use explicit API key"
                assert result["provider"] == "nous"
                # Neither expiry check nor refresh should have been called
                mock_usable.assert_not_called()
                mock_resolve.assert_not_called()