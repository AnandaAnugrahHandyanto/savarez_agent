"""Tests for Concentrate AI provider support — aggregator with 115+ models."""

import types

import pytest

from hermes_cli.auth import (
    PROVIDER_REGISTRY,
    resolve_provider,
    get_api_key_provider_status,
    resolve_api_key_provider_credentials,
)


_OTHER_PROVIDER_KEYS = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
    "GOOGLE_API_KEY", "GEMINI_API_KEY", "DASHSCOPE_API_KEY",
    "XAI_API_KEY", "KIMI_API_KEY", "KIMI_CN_API_KEY",
    "MINIMAX_API_KEY", "MINIMAX_CN_API_KEY", "AI_GATEWAY_API_KEY",
    "KILOCODE_API_KEY", "HF_TOKEN", "GLM_API_KEY", "ZAI_API_KEY",
    "XIAOMI_API_KEY", "ARCEEAI_API_KEY", "COPILOT_GITHUB_TOKEN",
    "GH_TOKEN", "GITHUB_TOKEN",
)


# =============================================================================
# Provider Registry
# =============================================================================


class TestConcentrateProviderRegistry:
    def test_registered(self):
        assert "concentrate" in PROVIDER_REGISTRY

    def test_name(self):
        assert PROVIDER_REGISTRY["concentrate"].name == "Concentrate AI"

    def test_auth_type(self):
        assert PROVIDER_REGISTRY["concentrate"].auth_type == "api_key"

    def test_inference_base_url(self):
        assert PROVIDER_REGISTRY["concentrate"].inference_base_url == "https://api.concentrate.ai/v1"

    def test_api_key_env_vars(self):
        assert PROVIDER_REGISTRY["concentrate"].api_key_env_vars == ("CONCENTRATE_API_KEY",)

    def test_base_url_env_var(self):
        assert PROVIDER_REGISTRY["concentrate"].base_url_env_var == "CONCENTRATE_BASE_URL"


# =============================================================================
# Aliases
# =============================================================================


class TestConcentrateAliases:
    @pytest.mark.parametrize("alias", ["concentrate", "concentrate-ai"])
    def test_alias_resolves(self, alias, monkeypatch):
        for key in _OTHER_PROVIDER_KEYS + ("OPENROUTER_API_KEY",):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("CONCENTRATE_API_KEY", "conc-test-12345")
        assert resolve_provider(alias) == "concentrate"

    def test_normalize_provider_models_py(self):
        from hermes_cli.models import normalize_provider
        assert normalize_provider("concentrate-ai") == "concentrate"

    def test_normalize_provider_providers_py(self):
        from hermes_cli.providers import normalize_provider
        assert normalize_provider("concentrate-ai") == "concentrate"


# =============================================================================
# Credentials
# =============================================================================


class TestConcentrateCredentials:
    def test_status_configured(self, monkeypatch):
        monkeypatch.setenv("CONCENTRATE_API_KEY", "conc-test")
        status = get_api_key_provider_status("concentrate")
        assert status["configured"]

    def test_status_not_configured(self, monkeypatch):
        monkeypatch.delenv("CONCENTRATE_API_KEY", raising=False)
        status = get_api_key_provider_status("concentrate")
        assert not status["configured"]

    def test_openrouter_key_does_not_make_concentrate_configured(self, monkeypatch):
        """OpenRouter users should NOT see concentrate as configured."""
        monkeypatch.delenv("CONCENTRATE_API_KEY", raising=False)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        status = get_api_key_provider_status("concentrate")
        assert not status["configured"]

    def test_resolve_credentials(self, monkeypatch):
        monkeypatch.setenv("CONCENTRATE_API_KEY", "conc-direct-key")
        monkeypatch.delenv("CONCENTRATE_BASE_URL", raising=False)
        creds = resolve_api_key_provider_credentials("concentrate")
        assert creds["api_key"] == "conc-direct-key"
        assert creds["base_url"] == "https://api.concentrate.ai/v1"

    def test_custom_base_url_override(self, monkeypatch):
        monkeypatch.setenv("CONCENTRATE_API_KEY", "conc-x")
        monkeypatch.setenv("CONCENTRATE_BASE_URL", "https://custom.concentrate.example/v1")
        creds = resolve_api_key_provider_credentials("concentrate")
        assert creds["base_url"] == "https://custom.concentrate.example/v1"


# =============================================================================
# Model catalog
# =============================================================================


class TestConcentrateModelCatalog:
    def test_static_model_list(self):
        from hermes_cli.models import _PROVIDER_MODELS
        assert "concentrate" in _PROVIDER_MODELS
        models = _PROVIDER_MODELS["concentrate"]
        # Verify representative models across vendors
        assert "gpt-5.4" in models
        assert "gemini-2.5-flash" in models
        assert "claude-sonnet-4" in models

    def test_canonical_provider_entry(self):
        from hermes_cli.models import CANONICAL_PROVIDERS
        slugs = [p.slug for p in CANONICAL_PROVIDERS]
        assert "concentrate" in slugs


# =============================================================================
# Model normalization
# =============================================================================


class TestConcentrateNormalization:
    def test_in_matching_prefix_strip_set(self):
        from hermes_cli.model_normalize import _MATCHING_PREFIX_STRIP_PROVIDERS
        assert "concentrate" in _MATCHING_PREFIX_STRIP_PROVIDERS

    def test_in_aggregator_providers(self):
        """Concentrate is an aggregator like OpenRouter."""
        from hermes_cli.model_normalize import _AGGREGATOR_PROVIDERS
        assert "concentrate" in _AGGREGATOR_PROVIDERS

    def test_vendor_prefix_prepended_for_bare_name(self):
        """Aggregators need vendor/model format — bare names get vendor prepended."""
        from hermes_cli.model_normalize import normalize_model_for_provider
        assert normalize_model_for_provider("gpt-5.4", "concentrate") == "openai/gpt-5.4"

    def test_vendor_prefixed_name_preserved(self):
        """Already vendor-prefixed names are kept as-is for aggregators."""
        from hermes_cli.model_normalize import normalize_model_for_provider
        assert normalize_model_for_provider("openai/gpt-5.4", "concentrate") == "openai/gpt-5.4"
        assert normalize_model_for_provider("anthropic/claude-sonnet-4", "concentrate") == "anthropic/claude-sonnet-4"


# =============================================================================
# URL mapping
# =============================================================================


class TestConcentrateURLMapping:
    def test_url_to_provider(self):
        from agent.model_metadata import _URL_TO_PROVIDER
        assert _URL_TO_PROVIDER.get("api.concentrate.ai") == "concentrate"

    def test_provider_prefixes(self):
        from agent.model_metadata import _PROVIDER_PREFIXES
        assert "concentrate" in _PROVIDER_PREFIXES
        assert "concentrate-ai" in _PROVIDER_PREFIXES

    def test_trajectory_compressor_detects_concentrate(self):
        import trajectory_compressor as tc
        comp = tc.TrajectoryCompressor.__new__(tc.TrajectoryCompressor)
        comp.config = types.SimpleNamespace(base_url="https://api.concentrate.ai/v1")
        assert comp._detect_provider() == "concentrate"


# =============================================================================
# providers.py overlay + aliases
# =============================================================================


class TestConcentrateProvidersModule:
    def test_overlay_exists(self):
        from hermes_cli.providers import HERMES_OVERLAYS
        assert "concentrate" in HERMES_OVERLAYS
        overlay = HERMES_OVERLAYS["concentrate"]
        assert overlay.transport == "openai_chat"
        assert overlay.base_url_env_var == "CONCENTRATE_BASE_URL"
        assert overlay.is_aggregator is True

    def test_label(self):
        from hermes_cli.models import _PROVIDER_LABELS
        assert _PROVIDER_LABELS["concentrate"] == "Concentrate AI"


# =============================================================================
# Auxiliary client
# =============================================================================


class TestConcentrateAuxiliary:
    def test_aux_model_mapping(self):
        """Concentrate has an auxiliary model mapping for cheaper tasks."""
        from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS
        assert "concentrate" in _API_KEY_PROVIDER_AUX_MODELS
        assert _API_KEY_PROVIDER_AUX_MODELS["concentrate"] == "gemini-3-flash-preview"


# =============================================================================
# Environment variable registration
# =============================================================================


class TestConcentrateEnvVars:
    def test_api_key_in_optional_env_vars(self):
        from hermes_cli.config import OPTIONAL_ENV_VARS
        assert "CONCENTRATE_API_KEY" in OPTIONAL_ENV_VARS
        assert OPTIONAL_ENV_VARS["CONCENTRATE_API_KEY"]["password"] is True

    def test_base_url_in_optional_env_vars(self):
        from hermes_cli.config import OPTIONAL_ENV_VARS
        assert "CONCENTRATE_BASE_URL" in OPTIONAL_ENV_VARS
        assert OPTIONAL_ENV_VARS["CONCENTRATE_BASE_URL"]["advanced"] is True
