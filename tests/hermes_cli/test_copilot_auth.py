"""Tests for hermes_cli.copilot_auth — Copilot token validation and resolution."""

import os
import pytest
from unittest.mock import patch, MagicMock


class TestTokenValidation:
    """Token type validation."""

    def test_classic_pat_rejected(self):
        from hermes_cli.copilot_auth import validate_copilot_token
        valid, msg = validate_copilot_token("ghp_abcdefghijklmnop1234")
        assert valid is False
        assert "Classic Personal Access Tokens" in msg
        assert "ghp_" in msg

    def test_oauth_token_accepted(self):
        from hermes_cli.copilot_auth import validate_copilot_token
        valid, msg = validate_copilot_token("gho_abcdefghijklmnop1234")
        assert valid is True

    def test_fine_grained_pat_accepted(self):
        from hermes_cli.copilot_auth import validate_copilot_token
        valid, msg = validate_copilot_token("github_pat_abcdefghijklmnop1234")
        assert valid is True

    def test_github_app_token_accepted(self):
        from hermes_cli.copilot_auth import validate_copilot_token
        valid, msg = validate_copilot_token("ghu_abcdefghijklmnop1234")
        assert valid is True

    def test_empty_token_rejected(self):
        from hermes_cli.copilot_auth import validate_copilot_token
        valid, msg = validate_copilot_token("")
        assert valid is False



class TestResolveToken:
    """Token resolution with env var priority.

    Tests use ``exchange=False`` to verify raw-token resolution order,
    since the exchange itself is tested separately in TestTokenExchange.
    """

    def test_copilot_github_token_first_priority(self, monkeypatch):
        from hermes_cli.copilot_auth import resolve_copilot_token
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "gho_copilot_first")
        monkeypatch.setenv("GH_TOKEN", "gho_gh_second")
        monkeypatch.setenv("GITHUB_TOKEN", "gho_github_third")
        token, source, base_url = resolve_copilot_token(exchange=False)
        assert token == "gho_copilot_first"
        assert source == "COPILOT_GITHUB_TOKEN"

    def test_gh_token_second_priority(self, monkeypatch):
        from hermes_cli.copilot_auth import resolve_copilot_token
        monkeypatch.delenv("COPILOT_GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GH_TOKEN", "gho_gh_second")
        monkeypatch.setenv("GITHUB_TOKEN", "gho_github_third")
        token, source, base_url = resolve_copilot_token(exchange=False)
        assert token == "gho_gh_second"
        assert source == "GH_TOKEN"

    def test_github_token_third_priority(self, monkeypatch):
        from hermes_cli.copilot_auth import resolve_copilot_token
        monkeypatch.delenv("COPILOT_GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.setenv("GITHUB_TOKEN", "gho_github_third")
        token, source, base_url = resolve_copilot_token(exchange=False)
        assert token == "gho_github_third"
        assert source == "GITHUB_TOKEN"

    def test_classic_pat_in_env_skipped(self, monkeypatch):
        """Classic PATs in env vars should be skipped, not returned."""
        from hermes_cli.copilot_auth import resolve_copilot_token
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "ghp_classic_pat_nope")
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.setenv("GITHUB_TOKEN", "gho_valid_oauth")
        token, source, base_url = resolve_copilot_token(exchange=False)
        # Should skip the ghp_ token and find the gho_ one
        assert token == "gho_valid_oauth"
        assert source == "GITHUB_TOKEN"

    def test_gh_cli_fallback(self, monkeypatch):
        from hermes_cli.copilot_auth import resolve_copilot_token
        monkeypatch.delenv("COPILOT_GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch("hermes_cli.copilot_auth._try_gh_cli_token", return_value="gho_from_cli"):
            token, source, base_url = resolve_copilot_token(exchange=False)
        assert token == "gho_from_cli"
        assert source == "gh auth token"

    def test_gh_cli_classic_pat_raises(self, monkeypatch):
        from hermes_cli.copilot_auth import resolve_copilot_token
        monkeypatch.delenv("COPILOT_GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch("hermes_cli.copilot_auth._try_gh_cli_token", return_value="ghp_classic"):
            with pytest.raises(ValueError, match="classic PAT"):
                resolve_copilot_token(exchange=False)

    def test_no_token_returns_empty(self, monkeypatch):
        from hermes_cli.copilot_auth import resolve_copilot_token
        monkeypatch.delenv("COPILOT_GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch("hermes_cli.copilot_auth._try_gh_cli_token", return_value=None):
            token, source, base_url = resolve_copilot_token(exchange=False)
        assert token == ""
        assert source == ""

    def test_exchange_enabled_by_default(self, monkeypatch):
        """Default resolve_copilot_token() performs token exchange."""
        from hermes_cli.copilot_auth import resolve_copilot_token
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "gho_raw_token")
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch(
            "hermes_cli.copilot_auth.resolve_copilot_api_token",
            return_value=("jwt_exchanged_token", None),
        ) as mock_exchange:
            token, source, base_url = resolve_copilot_token()
        mock_exchange.assert_called_once_with("gho_raw_token")
        assert token == "jwt_exchanged_token"
        assert source == "COPILOT_GITHUB_TOKEN"


class TestTokenExchange:
    """Copilot token exchange (raw GitHub token -> Copilot API JWT)."""

    def test_exchange_calls_correct_endpoint(self):
        import json as _json
        from hermes_cli.copilot_auth import (
            exchange_copilot_token,
            COPILOT_TOKEN_EXCHANGE_URL,
            _jwt_cache,
        )
        _jwt_cache.clear()

        response_body = _json.dumps({
            "token": "eyJhbGciOiJSUzI1N_test_jwt",
            "expires_at": 9999999999,
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            jwt, expires_at, base_url = exchange_copilot_token("gho_test_raw")

        assert jwt == "eyJhbGciOiJSUzI1N_test_jwt"
        assert expires_at == 9999999999.0

        # Verify the request was correct
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.full_url == COPILOT_TOKEN_EXCHANGE_URL
        assert req.get_header("Authorization") == "Bearer gho_test_raw"
        assert req.get_method() == "GET"

    def test_exchange_caches_jwt(self):
        import json as _json
        from hermes_cli.copilot_auth import exchange_copilot_token, _jwt_cache
        _jwt_cache.clear()

        response_body = _json.dumps({
            "token": "jwt_cached",
            "expires_at": 9999999999,
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            jwt1, _, _ = exchange_copilot_token("gho_cache_test")
            jwt2, _, _ = exchange_copilot_token("gho_cache_test")

        # Should only call the API once — second call uses cache
        assert mock_urlopen.call_count == 1
        assert jwt1 == jwt2 == "jwt_cached"

    def test_exchange_refreshes_expired_cache(self):
        import json as _json
        import time
        from hermes_cli.copilot_auth import (
            exchange_copilot_token, _jwt_cache, _token_fp,
            _JWT_REFRESH_MARGIN_SECONDS,
        )
        _jwt_cache.clear()

        # Pre-populate cache with an expired token
        fp = _token_fp("gho_expired_test")
        _jwt_cache[fp] = ("old_jwt", time.time() - 10, None)

        response_body = _json.dumps({
            "token": "fresh_jwt",
            "expires_at": 9999999999,
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            jwt, _, _ = exchange_copilot_token("gho_expired_test")

        assert jwt == "fresh_jwt"

    def test_exchange_raises_on_failure(self):
        from hermes_cli.copilot_auth import exchange_copilot_token, _jwt_cache
        _jwt_cache.clear()

        with patch("urllib.request.urlopen", side_effect=Exception("network error")):
            with pytest.raises(ValueError, match="Copilot token exchange failed"):
                exchange_copilot_token("gho_fail_test")

    def test_exchange_raises_on_empty_token(self):
        import json as _json
        from hermes_cli.copilot_auth import exchange_copilot_token, _jwt_cache
        _jwt_cache.clear()

        response_body = _json.dumps({"token": "", "expires_at": 0}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(ValueError, match="empty token"):
                exchange_copilot_token("gho_empty_test")

    def test_resolve_copilot_api_token_fallback(self):
        """resolve_copilot_api_token falls back to raw token on exchange failure."""
        from hermes_cli.copilot_auth import resolve_copilot_api_token, _jwt_cache
        _jwt_cache.clear()

        with patch("urllib.request.urlopen", side_effect=Exception("offline")):
            token, base_url = resolve_copilot_api_token("gho_fallback_raw")

        # Should return the raw token as fallback
        assert token == "gho_fallback_raw"
        assert base_url is None

    def test_resolve_copilot_api_token_success(self):
        """resolve_copilot_api_token returns JWT on success."""
        import json as _json
        from hermes_cli.copilot_auth import resolve_copilot_api_token, _jwt_cache
        _jwt_cache.clear()

        response_body = _json.dumps({
            "token": "jwt_success",
            "expires_at": 9999999999,
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            token, base_url = resolve_copilot_api_token("gho_success_raw")

        assert token == "jwt_success"

    def test_resolve_copilot_api_token_empty_input(self):
        """resolve_copilot_api_token returns empty string for empty input."""
        from hermes_cli.copilot_auth import resolve_copilot_api_token
        token, base_url = resolve_copilot_api_token("")
        assert token == ""
        assert base_url is None


class TestDeriveBaseUrl:
    """Copilot base URL derivation from token proxy-ep field."""

    def test_extracts_proxy_ep(self):
        from hermes_cli.copilot_auth import derive_copilot_base_url_from_token
        token = "tid=abc;exp=123;proxy-ep=proxy.enterprise.githubcopilot.com;sku=free"
        assert derive_copilot_base_url_from_token(token) == "https://api.enterprise.githubcopilot.com"

    def test_no_proxy_ep_returns_none(self):
        from hermes_cli.copilot_auth import derive_copilot_base_url_from_token
        token = "tid=abc;exp=123;sku=free"
        assert derive_copilot_base_url_from_token(token) is None

    def test_proxy_ep_with_https_prefix(self):
        from hermes_cli.copilot_auth import derive_copilot_base_url_from_token
        token = "tid=abc;proxy-ep=https://proxy.individual.githubcopilot.com/"
        assert derive_copilot_base_url_from_token(token) == "https://api.individual.githubcopilot.com"

    def test_proxy_ep_without_proxy_prefix(self):
        from hermes_cli.copilot_auth import derive_copilot_base_url_from_token
        token = "tid=abc;proxy-ep=custom.githubcopilot.com"
        assert derive_copilot_base_url_from_token(token) == "https://custom.githubcopilot.com"

    def test_empty_token(self):
        from hermes_cli.copilot_auth import derive_copilot_base_url_from_token
        assert derive_copilot_base_url_from_token("") is None


class TestCopilotContextWindow:
    """Copilot model catalog context window lookup."""

    def test_returns_context_window_from_catalog(self):
        from hermes_cli.models import get_copilot_model_context_window, _copilot_catalog_cache
        import hermes_cli.models as models_mod
        # Inject a mock catalog
        models_mod._copilot_catalog_cache = {
            "claude-opus-4.6-1m": {
                "id": "claude-opus-4.6-1m",
                "capabilities": {
                    "limits": {
                        "max_prompt_tokens": 1000000,
                        "max_context_window_tokens": 1048576,
                    }
                }
            }
        }
        models_mod._copilot_catalog_cache_time = __import__("time").time()
        try:
            result = get_copilot_model_context_window("claude-opus-4.6-1m")
            assert result == 1000000  # prefers max_prompt_tokens
        finally:
            models_mod._copilot_catalog_cache = None
            models_mod._copilot_catalog_cache_time = 0.0

    def test_returns_none_for_unknown_model(self):
        from hermes_cli.models import get_copilot_model_context_window
        import hermes_cli.models as models_mod
        models_mod._copilot_catalog_cache = {"gpt-4o": {"id": "gpt-4o", "capabilities": {}}}
        models_mod._copilot_catalog_cache_time = __import__("time").time()
        try:
            assert get_copilot_model_context_window("nonexistent-model") is None
        finally:
            models_mod._copilot_catalog_cache = None
            models_mod._copilot_catalog_cache_time = 0.0

    def test_falls_back_to_context_window_tokens(self):
        from hermes_cli.models import get_copilot_model_context_window
        import hermes_cli.models as models_mod
        models_mod._copilot_catalog_cache = {
            "gpt-4o": {
                "id": "gpt-4o",
                "capabilities": {
                    "limits": {
                        "max_context_window_tokens": 128000,
                    }
                }
            }
        }
        models_mod._copilot_catalog_cache_time = __import__("time").time()
        try:
            assert get_copilot_model_context_window("gpt-4o") == 128000
        finally:
            models_mod._copilot_catalog_cache = None
            models_mod._copilot_catalog_cache_time = 0.0


class TestRequestHeaders:
    """Copilot API header generation."""

    def test_default_headers_include_openai_intent(self):
        from hermes_cli.copilot_auth import copilot_request_headers
        headers = copilot_request_headers()
        assert headers["Openai-Intent"] == "conversation-edits"
        assert headers["User-Agent"] == "HermesAgent/1.0"
        assert "Editor-Version" in headers

    def test_agent_turn_sets_initiator(self):
        from hermes_cli.copilot_auth import copilot_request_headers
        headers = copilot_request_headers(is_agent_turn=True)
        assert headers["x-initiator"] == "agent"

    def test_user_turn_sets_initiator(self):
        from hermes_cli.copilot_auth import copilot_request_headers
        headers = copilot_request_headers(is_agent_turn=False)
        assert headers["x-initiator"] == "user"

    def test_vision_header(self):
        from hermes_cli.copilot_auth import copilot_request_headers
        headers = copilot_request_headers(is_vision=True)
        assert headers["Copilot-Vision-Request"] == "true"

    def test_no_vision_header_by_default(self):
        from hermes_cli.copilot_auth import copilot_request_headers
        headers = copilot_request_headers()
        assert "Copilot-Vision-Request" not in headers


class TestCopilotDefaultHeaders:
    """The models.py copilot_default_headers uses copilot_auth."""

    def test_includes_openai_intent(self):
        from hermes_cli.models import copilot_default_headers
        headers = copilot_default_headers()
        assert "Openai-Intent" in headers
        assert headers["Openai-Intent"] == "conversation-edits"

    def test_includes_x_initiator(self):
        from hermes_cli.models import copilot_default_headers
        headers = copilot_default_headers()
        assert "x-initiator" in headers


class TestApiModeSelection:
    """API mode selection matching opencode's shouldUseCopilotResponsesApi."""

    def test_gpt5_uses_responses(self):
        from hermes_cli.models import _should_use_copilot_responses_api
        assert _should_use_copilot_responses_api("gpt-5.4") is True
        assert _should_use_copilot_responses_api("gpt-5.4-mini") is True
        assert _should_use_copilot_responses_api("gpt-5.3-codex") is True
        assert _should_use_copilot_responses_api("gpt-5.2-codex") is True
        assert _should_use_copilot_responses_api("gpt-5.2") is True
        assert _should_use_copilot_responses_api("gpt-5.1-codex-max") is True

    def test_gpt5_mini_excluded(self):
        from hermes_cli.models import _should_use_copilot_responses_api
        assert _should_use_copilot_responses_api("gpt-5-mini") is False

    def test_gpt4_uses_chat(self):
        from hermes_cli.models import _should_use_copilot_responses_api
        assert _should_use_copilot_responses_api("gpt-4.1") is False
        assert _should_use_copilot_responses_api("gpt-4o") is False
        assert _should_use_copilot_responses_api("gpt-4o-mini") is False

    def test_non_gpt_uses_chat(self):
        from hermes_cli.models import _should_use_copilot_responses_api
        assert _should_use_copilot_responses_api("claude-sonnet-4.6") is False
        assert _should_use_copilot_responses_api("claude-opus-4.6") is False
        assert _should_use_copilot_responses_api("gemini-2.5-pro") is False
        assert _should_use_copilot_responses_api("grok-code-fast-1") is False


class TestEnvVarOrder:
    """PROVIDER_REGISTRY has correct env var order."""

    def test_copilot_env_vars_include_copilot_github_token(self):
        from hermes_cli.auth import PROVIDER_REGISTRY
        copilot = PROVIDER_REGISTRY["copilot"]
        assert "COPILOT_GITHUB_TOKEN" in copilot.api_key_env_vars
        # COPILOT_GITHUB_TOKEN should be first
        assert copilot.api_key_env_vars[0] == "COPILOT_GITHUB_TOKEN"

    def test_copilot_env_vars_order_matches_docs(self):
        from hermes_cli.auth import PROVIDER_REGISTRY
        copilot = PROVIDER_REGISTRY["copilot"]
        assert copilot.api_key_env_vars == (
            "COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"
        )
