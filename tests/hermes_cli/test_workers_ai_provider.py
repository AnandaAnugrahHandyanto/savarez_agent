"""Tests for Cloudflare Workers AI provider support.

Covers the multi-var auth setup (TOKEN + ACCOUNT_ID + optional GATEWAY_ID),
URL construction for both the direct API and AI Gateway forms, the
auto-detect hijack guard, and the per-request session-affinity header.
"""

import pytest

from hermes_cli.auth import (
    AuthError,
    PROVIDER_REGISTRY,
    _resolve_workers_ai_base_url,
    get_api_key_provider_status,
    resolve_api_key_provider_credentials,
    resolve_provider,
)


_OTHER_PROVIDER_KEYS = (
    "OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY",
    "DASHSCOPE_API_KEY", "XAI_API_KEY", "KIMI_API_KEY", "KIMI_CN_API_KEY",
    "MINIMAX_API_KEY", "MINIMAX_CN_API_KEY", "AI_GATEWAY_API_KEY",
    "KILOCODE_API_KEY", "HF_TOKEN", "GLM_API_KEY", "ZAI_API_KEY",
    "XIAOMI_API_KEY", "ARCEEAI_API_KEY", "NVIDIA_API_KEY",
    "COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "STEPFUN_API_KEY",
)

_CF_KEYS = (
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_GATEWAY_ID", "WORKERS_AI_BASE_URL",
)


def _clear_cf_env(monkeypatch):
    for k in _CF_KEYS:
        monkeypatch.delenv(k, raising=False)


def _clear_other_provider_env(monkeypatch):
    for k in _OTHER_PROVIDER_KEYS:
        monkeypatch.delenv(k, raising=False)


# =============================================================================
# Provider Registry
# =============================================================================


class TestWorkersAIProviderRegistry:
    def test_api_key_env_var(self):
        """Only CLOUDFLARE_API_TOKEN is accepted — matches CF's own tooling."""
        env_vars = PROVIDER_REGISTRY["workers-ai"].api_key_env_vars
        assert env_vars == ("CLOUDFLARE_API_TOKEN",)


# =============================================================================
# Aliases
# =============================================================================


class TestWorkersAIAliases:
    @pytest.mark.parametrize("alias", ["workers-ai", "cloudflare", "cf", "cloudflare-ai"])
    def test_alias_resolves(self, alias, monkeypatch):
        _clear_other_provider_env(monkeypatch)
        _clear_cf_env(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-test-token")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test-account")
        assert resolve_provider(alias) == "workers-ai"

    def test_normalize_provider_models_py(self):
        from hermes_cli.models import normalize_provider
        assert normalize_provider("cloudflare") == "workers-ai"
        assert normalize_provider("cf") == "workers-ai"
        assert normalize_provider("cloudflare-ai") == "workers-ai"

    def test_normalize_provider_providers_py(self):
        from hermes_cli.providers import normalize_provider
        assert normalize_provider("cloudflare") == "workers-ai"
        assert normalize_provider("cf") == "workers-ai"


# =============================================================================
# Auto-detect hijack guard
# =============================================================================


class TestWorkersAIAutoDetectGuard:
    """A bare CLOUDFLARE_API_TOKEN is commonly set for Wrangler / Terraform.
    Auto-detect must not route to workers-ai unless CLOUDFLARE_ACCOUNT_ID is
    also set (which is workers-ai-specific)."""

    def test_token_alone_does_not_auto_route(self, monkeypatch):
        _clear_other_provider_env(monkeypatch)
        _clear_cf_env(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-token")
        # No account_id set — auto-detect should fall through to "no provider".
        with pytest.raises(AuthError) as exc_info:
            resolve_provider()
        assert exc_info.value.code == "no_provider_configured"

    def test_token_plus_account_id_auto_routes(self, monkeypatch):
        _clear_other_provider_env(monkeypatch)
        _clear_cf_env(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-token")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        assert resolve_provider() == "workers-ai"


# =============================================================================
# Base URL resolution
# =============================================================================


class TestResolveWorkersAIBaseURL:
    def test_no_env_returns_empty(self, monkeypatch):
        _clear_cf_env(monkeypatch)
        assert _resolve_workers_ai_base_url() == ""

    def test_account_id_only_direct_url(self, monkeypatch):
        _clear_cf_env(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        assert _resolve_workers_ai_base_url() == (
            "https://api.cloudflare.com/client/v4/accounts/abc123/ai/v1"
        )

    def test_account_id_plus_gateway_id(self, monkeypatch):
        _clear_cf_env(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        monkeypatch.setenv("CLOUDFLARE_GATEWAY_ID", "my-gateway")
        assert _resolve_workers_ai_base_url() == (
            "https://gateway.ai.cloudflare.com/v1/abc123/my-gateway/workers-ai/v1"
        )

    def test_env_override_wins(self, monkeypatch):
        _clear_cf_env(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        monkeypatch.setenv("CLOUDFLARE_GATEWAY_ID", "my-gateway")
        result = _resolve_workers_ai_base_url("https://override.example/v1")
        assert result == "https://override.example/v1"

    def test_env_override_strips_trailing_slash(self, monkeypatch):
        _clear_cf_env(monkeypatch)
        result = _resolve_workers_ai_base_url("https://override.example/v1/")
        assert result == "https://override.example/v1"


# =============================================================================
# Credentials resolution
# =============================================================================


class TestWorkersAICredentials:
    def test_status_configured(self, monkeypatch):
        _clear_other_provider_env(monkeypatch)
        _clear_cf_env(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-token")
        status = get_api_key_provider_status("workers-ai")
        assert status["configured"]

    def test_resolve_credentials_with_account_id(self, monkeypatch):
        _clear_other_provider_env(monkeypatch)
        _clear_cf_env(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-token-xyz")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        creds = resolve_api_key_provider_credentials("workers-ai")
        assert creds["api_key"] == "cf-token-xyz"
        assert creds["base_url"] == (
            "https://api.cloudflare.com/client/v4/accounts/abc123/ai/v1"
        )

    def test_resolve_credentials_via_ai_gateway(self, monkeypatch):
        _clear_other_provider_env(monkeypatch)
        _clear_cf_env(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-token-xyz")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        monkeypatch.setenv("CLOUDFLARE_GATEWAY_ID", "my-gw")
        creds = resolve_api_key_provider_credentials("workers-ai")
        assert creds["base_url"] == (
            "https://gateway.ai.cloudflare.com/v1/abc123/my-gw/workers-ai/v1"
        )

    def test_resolve_credentials_missing_account_id_raises(self, monkeypatch):
        _clear_other_provider_env(monkeypatch)
        _clear_cf_env(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-token")
        # No CLOUDFLARE_ACCOUNT_ID and no WORKERS_AI_BASE_URL → must raise
        # rather than return a broken URL.
        with pytest.raises(AuthError) as exc_info:
            resolve_api_key_provider_credentials("workers-ai")
        assert exc_info.value.code == "missing_account_id"

    def test_workers_ai_base_url_override(self, monkeypatch):
        _clear_other_provider_env(monkeypatch)
        _clear_cf_env(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-token")
        monkeypatch.setenv(
            "WORKERS_AI_BASE_URL", "https://my-proxy.example/workers-ai/v1"
        )
        creds = resolve_api_key_provider_credentials("workers-ai")
        assert creds["base_url"] == "https://my-proxy.example/workers-ai/v1"


# =============================================================================
# Model catalog & picker entry
# =============================================================================


class TestWorkersAIModelCatalog:
    def test_all_model_ids_use_cf_prefix(self):
        """Namespace isolation — every workers-ai model ID starts with @cf/
        so explicit context-length entries can't bleed into models served
        by upstream providers (Moonshot, NVIDIA, etc.)."""
        from hermes_cli.models import _PROVIDER_MODELS
        for model_id in _PROVIDER_MODELS["workers-ai"]:
            assert model_id.startswith("@cf/"), model_id

    def test_no_super_typo_in_nemotron_id(self):
        """Catalog ID per models.dev is @cf/nvidia/nemotron-3-120b-a12b
        (no 'super'). Regression guard against the original MR's typo."""
        from hermes_cli.models import _PROVIDER_MODELS
        assert "@cf/nvidia/nemotron-3-120b-a12b" in _PROVIDER_MODELS["workers-ai"]
        assert "@cf/nvidia/nemotron-3-super-120b-a12b" not in (
            _PROVIDER_MODELS["workers-ai"]
        )


# =============================================================================
# URL → provider mapping
# =============================================================================


class TestWorkersAIURLMapping:
    def test_direct_api_url_to_provider(self):
        from agent.model_metadata import _URL_TO_PROVIDER
        assert _URL_TO_PROVIDER.get("api.cloudflare.com") == "workers-ai"

    def test_ai_gateway_url_to_provider(self):
        from agent.model_metadata import _URL_TO_PROVIDER
        assert _URL_TO_PROVIDER.get("gateway.ai.cloudflare.com") == "workers-ai"


# =============================================================================
# providers.py overlay
# =============================================================================


class TestWorkersAIProvidersModule:
    def test_overlay_exists(self):
        from hermes_cli.providers import HERMES_OVERLAYS
        assert "workers-ai" in HERMES_OVERLAYS
        overlay = HERMES_OVERLAYS["workers-ai"]
        assert overlay.transport == "openai_chat"
        assert overlay.base_url_env_var == "WORKERS_AI_BASE_URL"


# =============================================================================
# Client-level User-Agent header
# =============================================================================


class TestWorkersAIClientHeaders:
    """Both the direct Workers AI URL and the AI Gateway URL get a
    `HermesAgent/{version}` User-Agent so traffic is identifiable in
    the AI Gateway dashboard's request log."""

    def _apply(self, base_url):
        from run_agent import AIAgent
        agent = AIAgent.__new__(AIAgent)
        agent._client_kwargs = {}
        agent._apply_client_headers_for_base_url(base_url)
        return agent._client_kwargs.get("default_headers") or {}

    def test_user_agent_set_for_direct_api(self):
        headers = self._apply("https://api.cloudflare.com/client/v4/accounts/abc/ai/v1")
        assert headers.get("User-Agent", "").startswith("HermesAgent/")

    def test_user_agent_set_for_ai_gateway(self):
        headers = self._apply(
            "https://gateway.ai.cloudflare.com/v1/abc/gw/workers-ai/v1"
        )
        assert headers.get("User-Agent", "").startswith("HermesAgent/")

    def test_does_not_leak_to_other_providers(self):
        headers = self._apply("https://api.openai.com/v1")
        assert "HermesAgent/" not in headers.get("User-Agent", "")
