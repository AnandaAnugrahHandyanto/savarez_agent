"""Tests for Cloudflare Workers AI provider support."""

import os
import sys
import types

import pytest

# Ensure dotenv doesn't interfere
if "dotenv" not in sys.modules:
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = fake_dotenv

from hermes_cli.auth import (
    AuthError,
    CLOUDFLARE_WORKERS_AI_BASE_URL_TEMPLATE,
    PROVIDER_REGISTRY,
    _resolve_cloudflare_workers_ai_base_url,
    get_api_key_provider_status,
    resolve_api_key_provider_credentials,
    resolve_provider,
)


# Canonical un-substituted template
_CF_DEFAULT = CLOUDFLARE_WORKERS_AI_BASE_URL_TEMPLATE


def _clear_all_provider_keys(monkeypatch):
    """Unset every provider env var so auto-detection sees a clean slate."""
    for var in (
        "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN",
        "DEEPSEEK_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY",
        "DASHSCOPE_API_KEY", "XAI_API_KEY", "KIMI_API_KEY",
        "MINIMAX_API_KEY", "AI_GATEWAY_API_KEY", "KILOCODE_API_KEY",
        "HF_TOKEN", "GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY",
        "COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN",
        "MINIMAX_CN_API_KEY", "XIAOMI_API_KEY",
        "OPENCODE_ZEN_API_KEY", "OPENCODE_GO_API_KEY",
        "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_API_KEY",
        "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_WORKERS_AI_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)


# =============================================================================
# Provider Registry
# =============================================================================


class TestCloudflareProviderRegistry:
    """Verify Cloudflare Workers AI is registered correctly."""

    def test_registered(self):
        assert "cloudflare-workers-ai" in PROVIDER_REGISTRY

    def test_name(self):
        assert PROVIDER_REGISTRY["cloudflare-workers-ai"].name == "Cloudflare Workers AI"

    def test_auth_type(self):
        assert PROVIDER_REGISTRY["cloudflare-workers-ai"].auth_type == "api_key"

    def test_inference_base_url_is_template(self):
        assert PROVIDER_REGISTRY["cloudflare-workers-ai"].inference_base_url == _CF_DEFAULT
        assert "{account_id}" in _CF_DEFAULT

    def test_api_key_env_vars(self):
        assert PROVIDER_REGISTRY["cloudflare-workers-ai"].api_key_env_vars == (
            "CLOUDFLARE_API_TOKEN",
        )

    def test_base_url_env_var(self):
        assert (
            PROVIDER_REGISTRY["cloudflare-workers-ai"].base_url_env_var
            == "CLOUDFLARE_WORKERS_AI_BASE_URL"
        )


# =============================================================================
# Account ID templating (unique to Cloudflare)
# =============================================================================


class TestCloudflareAccountIdTemplating:
    """Verify the base URL helper substitutes CLOUDFLARE_ACCOUNT_ID correctly."""

    def test_helper_substitutes_account_id(self, monkeypatch):
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        url = _resolve_cloudflare_workers_ai_base_url("tok", _CF_DEFAULT, "")
        assert url == "https://api.cloudflare.com/client/v4/accounts/abc123/ai/v1"

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        override = "https://custom.example/v1"
        url = _resolve_cloudflare_workers_ai_base_url("tok", _CF_DEFAULT, override)
        assert url == override

    def test_missing_account_id_returns_template(self, monkeypatch):
        monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
        url = _resolve_cloudflare_workers_ai_base_url("tok", _CF_DEFAULT, "")
        assert url == _CF_DEFAULT
        assert "{account_id}" in url


# =============================================================================
# Aliases
# =============================================================================


class TestCloudflareAliases:
    """Accepted aliases should resolve to 'cloudflare-workers-ai'."""

    @pytest.mark.parametrize("alias", [
        "cloudflare-workers-ai",
        "cf-workers-ai",
        "workers-ai",
    ])
    def test_alias_resolves(self, alias, monkeypatch):
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        assert resolve_provider(alias) == "cloudflare-workers-ai"

    def test_reserved_bare_cloudflare_is_not_aliased(self, monkeypatch):
        """Bare 'cloudflare' must NOT be an alias — reserved for future Gateway."""
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        with pytest.raises(AuthError):
            resolve_provider("cloudflare")

    def test_normalize_provider_models_py(self):
        from hermes_cli.models import normalize_provider
        assert normalize_provider("cf-workers-ai") == "cloudflare-workers-ai"
        assert normalize_provider("workers-ai") == "cloudflare-workers-ai"

    def test_normalize_provider_providers_py(self):
        from hermes_cli.providers import normalize_provider
        assert normalize_provider("cf-workers-ai") == "cloudflare-workers-ai"
        assert normalize_provider("workers-ai") == "cloudflare-workers-ai"


# =============================================================================
# Auto-detection
# =============================================================================


class TestCloudflareAutoDetection:
    """Both CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID must be set for auto-detect."""

    def test_auto_detect_with_both_vars(self, monkeypatch):
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        assert resolve_provider("auto") == "cloudflare-workers-ai"

    def test_auto_detect_skips_without_account_id(self, monkeypatch):
        """Token set but no account_id → CF must NOT be selected."""
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")
        # No CLOUDFLARE_ACCOUNT_ID
        with pytest.raises(AuthError):
            resolve_provider("auto")

    def test_auto_detect_accepts_base_url_override_without_account_id(self, monkeypatch):
        """Explicit base URL override should be enough for auto-detect."""
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")
        monkeypatch.setenv(
            "CLOUDFLARE_WORKERS_AI_BASE_URL",
            "https://api.cloudflare.com/client/v4/accounts/override/ai/v1",
        )
        assert resolve_provider("auto") == "cloudflare-workers-ai"


# =============================================================================
# Credentials
# =============================================================================


class TestCloudflareCredentials:
    """Test credential resolution for cloudflare-workers-ai."""

    def test_status_configured(self, monkeypatch):
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        status = get_api_key_provider_status("cloudflare-workers-ai")
        assert status["configured"]
        assert status["base_url"] == "https://api.cloudflare.com/client/v4/accounts/abc123/ai/v1"

    def test_status_not_configured_without_account_id(self, monkeypatch):
        """Token set but no account_id → configured=False (URL unresolved)."""
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")
        status = get_api_key_provider_status("cloudflare-workers-ai")
        assert not status["configured"]

    def test_status_not_configured_without_token(self, monkeypatch):
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        status = get_api_key_provider_status("cloudflare-workers-ai")
        assert not status["configured"]

    def test_resolve_credentials(self, monkeypatch):
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        creds = resolve_api_key_provider_credentials("cloudflare-workers-ai")
        assert creds["api_key"] == "tok-12345678"
        assert creds["base_url"] == "https://api.cloudflare.com/client/v4/accounts/abc123/ai/v1"

    def test_resolve_credentials_raises_without_account_id(self, monkeypatch):
        """Resolving at request time without account_id must raise AuthError."""
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")
        with pytest.raises(AuthError) as exc_info:
            resolve_api_key_provider_credentials("cloudflare-workers-ai")
        assert "CLOUDFLARE_ACCOUNT_ID" in str(exc_info.value)

    def test_custom_base_url_override(self, monkeypatch):
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")
        monkeypatch.setenv(
            "CLOUDFLARE_WORKERS_AI_BASE_URL",
            "https://custom.cloudflare.example/v1",
        )
        creds = resolve_api_key_provider_credentials("cloudflare-workers-ai")
        assert creds["base_url"] == "https://custom.cloudflare.example/v1"


# =============================================================================
# Model catalog
# =============================================================================


class TestCloudflareModelCatalog:
    """Cloudflare uses dynamic discovery via models.dev + a static fallback."""

    def test_models_dev_mapping(self):
        from agent.models_dev import PROVIDER_TO_MODELS_DEV
        assert PROVIDER_TO_MODELS_DEV["cloudflare-workers-ai"] == "cloudflare-workers-ai"

    def test_static_model_list_fallback(self):
        """Static _PROVIDER_MODELS fallback must exist for the model picker."""
        from hermes_cli.models import _PROVIDER_MODELS
        assert "cloudflare-workers-ai" in _PROVIDER_MODELS
        models = _PROVIDER_MODELS["cloudflare-workers-ai"]
        assert "@cf/google/gemma-4-26b-a4b-it" in models
        assert "@cf/moonshotai/kimi-k2.5" in models


# =============================================================================
# URL mapping
# =============================================================================


class TestCloudflareURLMapping:
    """Test URL → provider inference for Cloudflare endpoints."""

    def test_url_to_provider(self):
        from agent.model_metadata import _URL_TO_PROVIDER
        assert _URL_TO_PROVIDER.get("api.cloudflare.com") == "cloudflare-workers-ai"

    def test_provider_prefixes(self):
        from agent.model_metadata import _PROVIDER_PREFIXES
        assert "cloudflare-workers-ai" in _PROVIDER_PREFIXES
        assert "cf-workers-ai" in _PROVIDER_PREFIXES
        assert "workers-ai" in _PROVIDER_PREFIXES

    def test_infer_from_url(self):
        from agent.model_metadata import _infer_provider_from_url
        account_url = "https://api.cloudflare.com/client/v4/accounts/abc123/ai/v1"
        assert _infer_provider_from_url(account_url) == "cloudflare-workers-ai"


# =============================================================================
# providers.py
# =============================================================================


class TestCloudflareProvidersModule:
    """Test Cloudflare in the unified providers module."""

    def test_overlay_exists(self):
        from hermes_cli.providers import HERMES_OVERLAYS
        assert "cloudflare-workers-ai" in HERMES_OVERLAYS
        overlay = HERMES_OVERLAYS["cloudflare-workers-ai"]
        assert overlay.transport == "openai_chat"
        assert overlay.base_url_env_var == "CLOUDFLARE_WORKERS_AI_BASE_URL"
        assert "CLOUDFLARE_ACCOUNT_ID" in overlay.extra_env_vars
        assert not overlay.is_aggregator

    def test_alias_resolves(self):
        from hermes_cli.providers import normalize_provider
        assert normalize_provider("cf-workers-ai") == "cloudflare-workers-ai"
        assert normalize_provider("workers-ai") == "cloudflare-workers-ai"

    def test_label(self):
        from hermes_cli.providers import get_label
        assert get_label("cloudflare-workers-ai") == "Cloudflare Workers AI"

    def test_get_provider_uses_auth_registry_fallback_when_models_dev_missing(self, monkeypatch):
        monkeypatch.setattr("agent.models_dev.get_provider_info", lambda provider: None)
        from hermes_cli.providers import get_provider

        pdef = get_provider("cloudflare-workers-ai")

        assert pdef is not None
        assert pdef.id == "cloudflare-workers-ai"
        assert pdef.base_url == _CF_DEFAULT
        assert "CLOUDFLARE_API_TOKEN" in pdef.api_key_env_vars
        assert "CLOUDFLARE_ACCOUNT_ID" in pdef.api_key_env_vars


# =============================================================================
# Credential pool + /model picker
# =============================================================================


class TestCloudflareCredentialPool:
    def test_pool_seeds_resolved_base_url(self, monkeypatch, tmp_path):
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc123")

        from agent.credential_pool import load_pool

        pool = load_pool("cloudflare-workers-ai")
        entry = pool.select()

        assert entry is not None
        assert entry.base_url == "https://api.cloudflare.com/client/v4/accounts/abc123/ai/v1"

    def test_pool_skips_unresolved_placeholder_entry(self, monkeypatch, tmp_path):
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")

        from agent.credential_pool import load_pool

        pool = load_pool("cloudflare-workers-ai")
        assert not pool.has_credentials()


class TestCloudflareModelPicker:
    def test_list_authenticated_providers_skips_missing_account_id(self, monkeypatch):
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")
        monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})

        from hermes_cli.model_switch import list_authenticated_providers

        providers = list_authenticated_providers()
        assert not any(p["slug"] == "cloudflare-workers-ai" for p in providers)

    def test_list_authenticated_providers_accepts_base_url_override(self, monkeypatch):
        _clear_all_provider_keys(monkeypatch)
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-12345678")
        monkeypatch.setenv(
            "CLOUDFLARE_WORKERS_AI_BASE_URL",
            "https://api.cloudflare.com/client/v4/accounts/override/ai/v1",
        )
        monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})

        from hermes_cli.model_switch import list_authenticated_providers

        providers = list_authenticated_providers()
        cf_provider = next((p for p in providers if p["slug"] == "cloudflare-workers-ai"), None)
        assert cf_provider is not None
        assert cf_provider["models"] == [
            "@cf/google/gemma-4-26b-a4b-it",
            "@cf/moonshotai/kimi-k2.5",
        ]


# =============================================================================
# Auxiliary client
# =============================================================================


class TestCloudflareAuxiliary:
    """Cloudflare Workers AI should have a default auxiliary model."""

    def test_aux_model_defined(self):
        from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS
        assert "cloudflare-workers-ai" in _API_KEY_PROVIDER_AUX_MODELS
        assert (
            _API_KEY_PROVIDER_AUX_MODELS["cloudflare-workers-ai"]
            == "@cf/google/gemma-4-26b-a4b-it"
        )


# =============================================================================
# Doctor + agent init
# =============================================================================


class TestCloudflareDoctor:
    """Verify hermes doctor recognizes Cloudflare env vars."""

    def test_provider_env_hints(self):
        from hermes_cli.doctor import _PROVIDER_ENV_HINTS
        assert "CLOUDFLARE_API_TOKEN" in _PROVIDER_ENV_HINTS
        assert "CLOUDFLARE_ACCOUNT_ID" in _PROVIDER_ENV_HINTS


class TestCloudflareAgentInit:
    """Verify the agent can be constructed with cloudflare-workers-ai without errors."""

    def test_no_syntax_errors(self):
        """Importing run_agent with cloudflare-workers-ai should not raise."""
        import importlib
        importlib.import_module("run_agent")

    def test_api_mode_is_chat_completions(self):
        from hermes_cli.providers import HERMES_OVERLAYS, TRANSPORT_TO_API_MODE
        overlay = HERMES_OVERLAYS["cloudflare-workers-ai"]
        api_mode = TRANSPORT_TO_API_MODE[overlay.transport]
        assert api_mode == "chat_completions"
