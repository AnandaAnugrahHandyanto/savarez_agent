"""Tests for Google OAuth module (agent/google_oauth.py).

Covers PKCE generation, credential I/O, token refresh logic, and the full
OAuth login flow (mocked — no real network/browser activity).
"""

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from agent.google_oauth import (
    _generate_pkce,
    _REDIRECT_URI,
    _REDIRECT_PORT,
    GOOGLE_AUTH_URL,
    GOOGLE_TOKEN_URL,
    GOOGLE_OAUTH_SCOPES,
    exchange_code,
    get_valid_access_token,
    load_credentials,
    refresh_access_token,
    run_gemini_oauth_login_pure,
    run_google_oauth_login,
    save_credentials,
    clear_credentials,
)


# ── PKCE ──

class TestPKCE:
    def test_generates_verifier_and_challenge(self):
        verifier, challenge = _generate_pkce()
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) > 20
        assert len(challenge) > 20

    def test_different_each_call(self):
        v1, c1 = _generate_pkce()
        v2, c2 = _generate_pkce()
        assert v1 != v2
        assert c1 != c2

    def test_s256_challenge(self):
        """Verify the challenge is SHA-256 of the verifier, base64url-encoded."""
        import base64
        import hashlib

        verifier, challenge = _generate_pkce()
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        assert challenge == expected


# ── Credential I/O ──

class TestCredentialIO:
    @pytest.fixture(autouse=True)
    def _patch_oauth_file(self, tmp_path, monkeypatch):
        self.cred_file = tmp_path / "gemini_oauth.json"
        monkeypatch.setattr("agent.google_oauth._OAUTH_FILE", self.cred_file)

    def test_save_and_load(self):
        creds = {
            "client_id": "test-id",
            "client_secret": "test-secret",
            "access_token": "ya29.test",
            "refresh_token": "1//refresh",
            "expires_at": time.time() + 3600,
            "email": "test@example.com",
        }
        save_credentials(creds)
        loaded = load_credentials()
        assert loaded is not None
        assert loaded["access_token"] == "ya29.test"
        assert loaded["email"] == "test@example.com"

    def test_load_nonexistent(self):
        assert load_credentials() is None

    def test_load_corrupt(self):
        self.cred_file.write_text("not json", encoding="utf-8")
        assert load_credentials() is None

    def test_load_empty_token(self):
        self.cred_file.write_text('{"access_token":""}', encoding="utf-8")
        assert load_credentials() is None

    def test_file_permissions(self):
        save_credentials({"access_token": "test"})
        stat = os.stat(str(self.cred_file))
        assert stat.st_mode & 0o777 == 0o600

    def test_clear_credentials(self):
        save_credentials({"access_token": "test"})
        assert self.cred_file.exists()
        assert clear_credentials() is True
        assert not self.cred_file.exists()
        assert clear_credentials() is False  # already gone


# ── Token Refresh Logic ──

class TestGetValidAccessToken:
    @pytest.fixture(autouse=True)
    def _patch_oauth_file(self, tmp_path, monkeypatch):
        self.cred_file = tmp_path / "gemini_oauth.json"
        monkeypatch.setattr("agent.google_oauth._OAUTH_FILE", self.cred_file)

    def test_returns_none_when_no_creds(self):
        assert get_valid_access_token() is None

    def test_returns_token_when_fresh(self):
        save_credentials({
            "access_token": "ya29.fresh",
            "refresh_token": "1//refresh",
            "expires_at": time.time() + 7200,  # 2 hours from now
        })
        assert get_valid_access_token() == "ya29.fresh"

    def test_returns_none_when_expired_no_refresh(self):
        save_credentials({
            "access_token": "ya29.expired",
            "refresh_token": "",
            "expires_at": time.time() - 100,  # already expired
        })
        assert get_valid_access_token() is None

    @patch("agent.google_oauth.refresh_access_token")
    def test_refreshes_when_near_expiry(self, mock_refresh):
        mock_refresh.return_value = {
            "access_token": "ya29.refreshed",
            "expires_in": 3600,
        }
        save_credentials({
            "access_token": "ya29.about-to-expire",
            "refresh_token": "1//refresh",
            "expires_at": time.time() + 60,  # within 5-min margin
        })
        token = get_valid_access_token()
        assert token == "ya29.refreshed"
        mock_refresh.assert_called_once()

        # Verify file was updated
        updated = load_credentials()
        assert updated["access_token"] == "ya29.refreshed"

    @patch("agent.google_oauth.refresh_access_token")
    def test_refresh_failure_returns_none(self, mock_refresh):
        mock_refresh.return_value = None
        save_credentials({
            "access_token": "ya29.expired",
            "refresh_token": "1//refresh",
            "expires_at": time.time() - 100,
        })
        assert get_valid_access_token() is None


# ── Token Exchange ──

class TestExchangeCode:
    @patch("urllib.request.urlopen")
    def test_successful_exchange(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "access_token": "ya29.new",
            "refresh_token": "1//new-refresh",
            "expires_in": 3600,
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = exchange_code(
            "test-code", "test-verifier",
            client_id="test-id", client_secret="test-secret",
        )
        assert result is not None
        assert result["access_token"] == "ya29.new"

    @patch("urllib.request.urlopen")
    def test_exchange_failure(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("network error")
        result = exchange_code("code", "verifier", client_id="id", client_secret="s")
        assert result is None


# ── Token Refresh ──

class TestRefreshAccessToken:
    @patch("urllib.request.urlopen")
    def test_successful_refresh(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "access_token": "ya29.refreshed",
            "expires_in": 3600,
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = refresh_access_token(
            "1//old-refresh",
            client_id="test-id", client_secret="test-secret",
        )
        assert result is not None
        assert result["access_token"] == "ya29.refreshed"

    @patch("urllib.request.urlopen")
    def test_refresh_failure(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("401 Unauthorized")
        result = refresh_access_token("1//bad", client_id="id", client_secret="s")
        assert result is None


# ── Full Login Flow ──

class TestRunGoogleOAuthLogin:
    @patch("agent.google_oauth._fetch_user_email", return_value="user@gmail.com")
    @patch("agent.google_oauth.exchange_code")
    @patch("agent.google_oauth._wait_for_callback")
    @patch("webbrowser.open")
    def test_full_flow(self, mock_wb, mock_callback, mock_exchange, mock_email):
        mock_callback.return_value = "test-auth-code"
        mock_exchange.return_value = {
            "access_token": "ya29.full-flow",
            "refresh_token": "1//full-refresh",
            "expires_in": 3600,
        }

        result = run_google_oauth_login(
            client_id="test-client-id",
            client_secret="test-client-secret",
            open_browser=False,
        )

        assert result is not None
        assert result["access_token"] == "ya29.full-flow"
        assert result["refresh_token"] == "1//full-refresh"
        assert result["email"] == "user@gmail.com"
        assert result["client_id"] == "test-client-id"
        assert "expires_at" in result

    @patch("agent.google_oauth._wait_for_callback")
    @patch("webbrowser.open")
    def test_no_client_id(self, mock_wb, mock_callback):
        with patch("agent.google_oauth._get_client_id", return_value=""):
            result = run_google_oauth_login(open_browser=False)
            assert result is None

    @patch("agent.google_oauth._wait_for_callback")
    @patch("webbrowser.open")
    def test_callback_timeout_manual_cancel(self, mock_wb, mock_callback):
        mock_callback.return_value = None  # timeout
        with patch("builtins.input", return_value=""):
            result = run_google_oauth_login(
                client_id="test-id",
                client_secret="test-secret",
                open_browser=False,
            )
            assert result is None


# ── Pure Login (for credential pool) ──

class TestRunGeminiOAuthLoginPure:
    @patch("agent.google_oauth.run_google_oauth_login")
    def test_returns_pool_compatible_dict(self, mock_login):
        mock_login.return_value = {
            "access_token": "ya29.pool",
            "refresh_token": "1//pool-refresh",
            "expires_at": time.time() + 3600,
            "client_id": "test",
            "client_secret": "test",
            "email": "pool@test.com",
        }
        result = run_gemini_oauth_login_pure()
        assert result is not None
        assert result["access_token"] == "ya29.pool"
        assert result["refresh_token"] == "1//pool-refresh"
        assert "expires_at_ms" in result
        assert isinstance(result["expires_at_ms"], int)

    @patch("agent.google_oauth.run_google_oauth_login")
    def test_returns_none_on_failure(self, mock_login):
        mock_login.return_value = None
        assert run_gemini_oauth_login_pure() is None


# ── Constants ──

class TestConstants:
    def test_redirect_uri(self):
        assert _REDIRECT_URI == f"http://localhost:{_REDIRECT_PORT}/oauth2callback"
        assert _REDIRECT_PORT == 8085

    def test_auth_url(self):
        assert "accounts.google.com" in GOOGLE_AUTH_URL

    def test_token_url(self):
        assert "googleapis.com" in GOOGLE_TOKEN_URL

    def test_scopes(self):
        assert "cloud-platform" in GOOGLE_OAUTH_SCOPES
        assert "userinfo.email" in GOOGLE_OAUTH_SCOPES
