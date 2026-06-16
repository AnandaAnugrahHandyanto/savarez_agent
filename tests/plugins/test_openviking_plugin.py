"""Tests for the OpenViking memory plugin.

Covers: _VikingClient._headers() tenant header behavior with api_key auth.
Regression test for #47344: X-OpenViking-Account/User headers must be
omitted when an API key is set (OV v0.4.1+ derives tenancy from the key).
"""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Imports — guarded since plugins/memory lives outside the standard test path
# ---------------------------------------------------------------------------

def _import_viking_client():
    """Import _VikingClient, skipping if httpx is unavailable."""
    try:
        from plugins.memory.openviking import _VikingClient
        return _VikingClient
    except ImportError:
        pytest.skip("openviking plugin or httpx not available")


@pytest.fixture()
def viking_client_cls():
    return _import_viking_client()


# ---------------------------------------------------------------------------
# _headers() — tenant header behavior
# ---------------------------------------------------------------------------

class TestHeadersTenantBehavior:
    """Verify X-OpenViking-Account/User are only sent in dev mode."""

    def test_api_key_omits_tenant_headers(self, viking_client_cls):
        """When api_key is set, tenant headers must NOT be sent.

        OV v0.4.1+ with auth_mode: api_key returns 400 if tenant
        headers are present alongside a valid API key.
        """
        client = viking_client_cls(
            endpoint="http://localhost:8080",
            api_key="sk-test-key",
            account="myaccount",
            user="myuser",
        )
        headers = client._headers()
        assert "X-OpenViking-Account" not in headers
        assert "X-OpenViking-User" not in headers

    def test_api_key_includes_auth_headers(self, viking_client_cls):
        """When api_key is set, X-API-Key and Authorization must be present."""
        client = viking_client_cls(
            endpoint="http://localhost:8080",
            api_key="sk-test-key",
        )
        headers = client._headers()
        assert headers["X-API-Key"] == "sk-test-key"
        assert headers["Authorization"] == "Bearer sk-test-key"

    def test_no_api_key_sends_tenant_headers(self, viking_client_cls):
        """In dev mode (no API key), tenant headers are required.

        OV 0.3.x requires X-OpenViking-Account/User for tenant-scoped APIs.
        """
        client = viking_client_cls(
            endpoint="http://localhost:8080",
            api_key="",
            account="myaccount",
            user="myuser",
        )
        headers = client._headers()
        assert headers["X-OpenViking-Account"] == "myaccount"
        assert headers["X-OpenViking-User"] == "myuser"

    def test_no_api_key_no_auth_headers(self, viking_client_cls):
        """In dev mode, X-API-Key and Authorization must NOT be present."""
        client = viking_client_cls(
            endpoint="http://localhost:8080",
            api_key="",
        )
        headers = client._headers()
        assert "X-API-Key" not in headers
        assert "Authorization" not in headers

    def test_always_sends_agent_and_content_type(self, viking_client_cls):
        """X-OpenViking-Agent and Content-Type must always be present."""
        # With API key
        client = viking_client_cls(
            endpoint="http://localhost:8080",
            api_key="sk-key",
            agent="test-agent",
        )
        headers = client._headers()
        assert headers["X-OpenViking-Agent"] == "test-agent"
        assert headers["Content-Type"] == "application/json"

        # Without API key
        client2 = viking_client_cls(
            endpoint="http://localhost:8080",
            api_key="",
            agent="test-agent",
        )
        headers2 = client2._headers()
        assert headers2["X-OpenViking-Agent"] == "test-agent"
        assert headers2["Content-Type"] == "application/json"

    def test_default_account_user_in_dev_mode(self, viking_client_cls):
        """Default account/user values should be sent in dev mode."""
        client = viking_client_cls(
            endpoint="http://localhost:8080",
            api_key="",
            # account and user default to env vars or "default"
        )
        headers = client._headers()
        # Default values from env or fallback
        assert "X-OpenViking-Account" in headers
        assert "X-OpenViking-User" in headers

    def test_multipart_headers_omit_content_type(self, viking_client_cls):
        """_multipart_headers must drop Content-Type but preserve auth."""
        client = viking_client_cls(
            endpoint="http://localhost:8080",
            api_key="sk-key",
        )
        headers = client._multipart_headers()
        assert "Content-Type" not in headers
        assert headers["X-API-Key"] == "sk-key"
        assert "X-OpenViking-Account" not in headers
