"""Tests that SSRF checks in browser_navigate are conditional on cloud mode.

In local mode (_get_cloud_provider returns None) the SSRF check is skipped
because the user already has terminal/network access on their own machine.
In cloud mode the SSRF check is enforced to prevent the agent from reaching
internal resources via a remote browser.
"""

import json

import pytest

from tools import browser_tool


def _make_browser_result(url="https://example.com"):
    """Return a mock successful browser command result."""
    return {"success": True, "data": {"title": "OK", "url": url}}


def _mock_cloud_provider():
    """Return a mock cloud provider with a create_session method."""
    class MockProvider:
        def create_session(self, task_id):
            return {
                "session_name": f"cloud_{task_id}",
                "bb_session_id": "test-session-id",
                "cdp_url": "ws://browserbase.example.com",
                "features": {"cloud": True},
            }
    return MockProvider()


# ---------------------------------------------------------------------------
# Pre-navigation SSRF check
# ---------------------------------------------------------------------------


class TestPreNavigationSsrf:
    PRIVATE_URL = "http://127.0.0.1:8080/dashboard"

    @pytest.fixture()
    def _common_patches(self, monkeypatch):
        """Shared patches for pre-navigation tests that pass the SSRF check."""
        monkeypatch.setattr(browser_tool, "_is_camofox_mode", lambda: False)
        monkeypatch.setattr(browser_tool, "check_website_access", lambda url: None)
        monkeypatch.setattr(
            browser_tool,
            "_get_session_info",
            lambda task_id: {
                "session_name": f"s_{task_id}",
                "bb_session_id": None,
                "cdp_url": None,
                "features": {"local": True},
                "_first_nav": False,
            },
        )
        monkeypatch.setattr(
            browser_tool,
            "_run_browser_command",
            lambda *a, **kw: _make_browser_result(),
        )

    def test_local_mode_allows_private_url(self, monkeypatch, _common_patches):
        monkeypatch.setattr(browser_tool, "_get_cloud_provider", lambda: None)
        # _is_safe_url would block this, but local mode skips the check
        monkeypatch.setattr(browser_tool, "_is_safe_url", lambda url: False)

        result = json.loads(browser_tool.browser_navigate(self.PRIVATE_URL))

        assert result["success"] is True

    def test_cloud_mode_blocks_private_url(self, monkeypatch, _common_patches):
        monkeypatch.setattr(browser_tool, "_get_cloud_provider", _mock_cloud_provider)
        monkeypatch.setattr(browser_tool, "_is_safe_url", lambda url: False)

        result = json.loads(browser_tool.browser_navigate(self.PRIVATE_URL))

        assert result["success"] is False
        assert "private or internal address" in result["error"]

    def test_cloud_mode_allows_public_url(self, monkeypatch, _common_patches):
        monkeypatch.setattr(browser_tool, "_get_cloud_provider", _mock_cloud_provider)
        monkeypatch.setattr(browser_tool, "_is_safe_url", lambda url: True)

        result = json.loads(browser_tool.browser_navigate("https://example.com"))

        assert result["success"] is True


# ---------------------------------------------------------------------------
# Post-redirect SSRF check
# ---------------------------------------------------------------------------


class TestPostRedirectSsrf:
    PUBLIC_URL = "https://example.com/redirect"
    PRIVATE_FINAL_URL = "http://192.168.1.1/internal"

    @pytest.fixture()
    def _common_patches(self, monkeypatch):
        """Shared patches for redirect tests."""
        monkeypatch.setattr(browser_tool, "_is_camofox_mode", lambda: False)
        monkeypatch.setattr(browser_tool, "check_website_access", lambda url: None)
        monkeypatch.setattr(
            browser_tool,
            "_get_session_info",
            lambda task_id: {
                "session_name": f"s_{task_id}",
                "bb_session_id": None,
                "cdp_url": None,
                "features": {"local": True},
                "_first_nav": False,
            },
        )

    def test_local_mode_allows_redirect_to_private(self, monkeypatch, _common_patches):
        monkeypatch.setattr(browser_tool, "_get_cloud_provider", lambda: None)
        # Initial URL passes SSRF, redirect target would fail SSRF but local mode skips it
        monkeypatch.setattr(
            browser_tool, "_is_safe_url",
            lambda url: "192.168" not in url,
        )
        monkeypatch.setattr(
            browser_tool,
            "_run_browser_command",
            lambda *a, **kw: _make_browser_result(url=self.PRIVATE_FINAL_URL),
        )

        result = json.loads(browser_tool.browser_navigate(self.PUBLIC_URL))

        assert result["success"] is True
        assert result["url"] == self.PRIVATE_FINAL_URL

    def test_cloud_mode_blocks_redirect_to_private(self, monkeypatch, _common_patches):
        monkeypatch.setattr(browser_tool, "_get_cloud_provider", _mock_cloud_provider)
        # Initial URL passes SSRF, redirect target fails SSRF
        monkeypatch.setattr(
            browser_tool, "_is_safe_url",
            lambda url: "192.168" not in url,
        )
        monkeypatch.setattr(
            browser_tool,
            "_run_browser_command",
            lambda *a, **kw: _make_browser_result(url=self.PRIVATE_FINAL_URL),
        )

        result = json.loads(browser_tool.browser_navigate(self.PUBLIC_URL))

        assert result["success"] is False
        assert "redirect landed on a private/internal address" in result["error"]

    def test_cloud_mode_allows_redirect_to_public(self, monkeypatch, _common_patches):
        final = "https://example.com/final"
        monkeypatch.setattr(browser_tool, "_get_cloud_provider", _mock_cloud_provider)
        monkeypatch.setattr(browser_tool, "_is_safe_url", lambda url: True)
        monkeypatch.setattr(
            browser_tool,
            "_run_browser_command",
            lambda *a, **kw: _make_browser_result(url=final),
        )

        result = json.loads(browser_tool.browser_navigate(self.PUBLIC_URL))

        assert result["success"] is True
        assert result["url"] == final
