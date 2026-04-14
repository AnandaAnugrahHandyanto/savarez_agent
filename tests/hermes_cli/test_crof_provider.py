"""Tests for CrofAI provider support."""

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
    PROVIDER_REGISTRY,
    resolve_provider,
    get_api_key_provider_status,
    resolve_api_key_provider_credentials,
    AuthError,
)


# =============================================================================
# Provider Registry
# =============================================================================


class TestCrofProviderRegistry:
    """Verify CrofAI is registered correctly in the PROVIDER_REGISTRY."""

    def test_registered(self):
        assert "crof" in PROVIDER_REGISTRY

    def test_name(self):
        assert PROVIDER_REGISTRY["crof"].name == "CrofAI"

    def test_auth_type(self):
        assert PROVIDER_REGISTRY["crof"].auth_type == "api_key"

    def test_inference_base_url(self):
        assert PROVIDER_REGISTRY["crof"].inference_base_url == "https://crof.ai/v1"

    def test_api_key_env_vars(self):
        assert PROVIDER_REGISTRY["crof"].api_key_env_vars == ("CROFAI_API_KEY",)

    def test_base_url_env_var(self):
        assert PROVIDER_REGISTRY["crof"].base_url_env_var == "CROFAI_BASE_URL"


# =============================================================================
# Aliases
# =============================================================================


class TestCrofAliases:
    """All aliases should resolve to 'crof'."""

    @pytest.mark.parametrize("alias", [
        "crof", "crofai", "crof-ai",
    ])
    def test_alias_resolves(self, alias, monkeypatch):
        for key in ("CROFAI_API_KEY",):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("CROFAI_API_KEY", "sk-test...5678")
        assert resolve_provider(alias) == "crof"

    def test_normalize_provider_models_py(self):
        from hermes_cli.models import normalize_provider
        assert normalize_provider("crofai") == "crof"
        assert normalize_provider("crof-ai") == "crof"


# =============================================================================
# Auto-detection
# =============================================================================


class TestCrofAutoDetection:
    """Setting CROFAI_API_KEY should auto-detect the provider."""

    def test_auto_detect(self, monkeypatch):
        for var in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                     "DEEPSEEK_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY",
                     "DASHSCOPE_API_KEY", "XAI_API_KEY", "KIMI_API_KEY",
                     "MINIMAX_API_KEY", "AI_GATEWAY_API_KEY", "KILOCODE_API_KEY",
                     "HF_TOKEN", "GLM_API_KEY", "COPILOT_GITHUB_TOKEN",
                     "GH_TOKEN", "GITHUB_TOKEN", "MINIMAX_CN_API_KEY",
                     "XIAOMI_API_KEY", "ARCEEAI_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CROFAI_API_KEY", "sk-crof...5678")
        provider = resolve_provider("auto")
        assert provider == "crof"


# =============================================================================
# Credentials
# =============================================================================


class TestCrofCredentials:
    """Test credential resolution for the crof provider."""

    def test_status_configured(self, monkeypatch):
        monkeypatch.setenv("CROFAI_API_KEY", "sk-crof-test-key-1234")
        status = get_api_key_provider_status("crof")
        assert status["configured"]

    def test_status_not_configured(self, monkeypatch):
        monkeypatch.delenv("CROFAI_API_KEY", raising=False)
        status = get_api_key_provider_status("crof")
        assert not status["configured"]

    def test_resolve_credentials(self, monkeypatch):
        monkeypatch.setenv("CROFAI_API_KEY", "sk-crof-test-key-1234")
        monkeypatch.delenv("CROFAI_BASE_URL", raising=False)
        creds = resolve_api_key_provider_credentials("crof")
        assert creds["api_key"] == "sk-crof-test-key-1234"
        assert creds["base_url"] == "https://crof.ai/v1"

    def test_custom_base_url_override(self, monkeypatch):
        monkeypatch.setenv("CROFAI_API_KEY", "sk-crof-test-key-1234")
        monkeypatch.setenv("CROFAI_BASE_URL", "https://custom.crof.example/v1")
        creds = resolve_api_key_provider_credentials("crof")
        assert creds["base_url"] == "https://custom.crof.example/v1"


# =============================================================================
# Model catalog
# =============================================================================


class TestCrofModelCatalog:
    """CrofAI has a static model list."""

    def test_static_model_list(self):
        from hermes_cli.models import _PROVIDER_MODELS
        assert "crof" in _PROVIDER_MODELS
        models = _PROVIDER_MODELS["crof"]
        assert "glm-5.1" in models
        assert "kimi-k2.5" in models
        assert "deepseek-v3.2" in models

    def test_default_model(self):
        from hermes_cli.models import get_default_model_for_provider
        assert get_default_model_for_provider("crof") == "glm-5.1"

    def test_canonical_provider_entry(self):
        from hermes_cli.models import _PROVIDER_LABELS
        assert _PROVIDER_LABELS.get("crof") == "CrofAI"


# =============================================================================
# Normalization
# =============================================================================


class TestCrofNormalization:
    """Model name normalization — CrofAI is a direct provider."""

    def test_matching_prefix_strip(self):
        from hermes_cli.model_normalize import _MATCHING_PREFIX_STRIP_PROVIDERS
        assert "crof" in _MATCHING_PREFIX_STRIP_PROVIDERS

    def test_normalize_strips_provider_prefix(self):
        from hermes_cli.model_normalize import normalize_model_for_provider
        result = normalize_model_for_provider("crof/glm-5.1", "crof")
        assert result == "glm-5.1"

    def test_normalize_bare_name_unchanged(self):
        from hermes_cli.model_normalize import normalize_model_for_provider
        result = normalize_model_for_provider("glm-5.1", "crof")
        assert result == "glm-5.1"

    def test_normalize_crofai_prefix(self):
        from hermes_cli.model_normalize import normalize_model_for_provider
        result = normalize_model_for_provider("crofai/glm-5.1", "crof")
        assert result == "glm-5.1"


# =============================================================================
# URL mapping
# =============================================================================


class TestCrofURLMapping:
    """Test URL -> provider inference for CrofAI endpoints."""

    def test_url_to_provider(self):
        from agent.model_metadata import _URL_TO_PROVIDER
        assert _URL_TO_PROVIDER.get("crof.ai") == "crof"

    def test_provider_prefixes(self):
        from agent.model_metadata import _PROVIDER_PREFIXES
        assert "crof" in _PROVIDER_PREFIXES
        assert "crofai" in _PROVIDER_PREFIXES

    def test_infer_from_url(self):
        from agent.model_metadata import _infer_provider_from_url
        assert _infer_provider_from_url("https://crof.ai/v1") == "crof"


# =============================================================================
# Context lengths
# =============================================================================


class TestCrofContextLengths:
    """Verify context lengths are registered for CrofAI models."""

    def test_glm51_context(self):
        from agent.model_metadata import DEFAULT_CONTEXT_LENGTHS
        assert DEFAULT_CONTEXT_LENGTHS.get("glm-5.1") == 202752

    def test_kimi_context(self):
        from agent.model_metadata import DEFAULT_CONTEXT_LENGTHS
        assert DEFAULT_CONTEXT_LENGTHS.get("kimi-k2.5") == 262144

    def test_deepseek_context(self):
        from agent.model_metadata import DEFAULT_CONTEXT_LENGTHS
        assert DEFAULT_CONTEXT_LENGTHS.get("deepseek-v3.2") == 163840


# =============================================================================
# providers.py
# =============================================================================


class TestCrofProvidersModule:
    """Test CrofAI in the unified providers module."""

    def test_overlay_exists(self):
        from hermes_cli.providers import HERMES_OVERLAYS
        assert "crof" in HERMES_OVERLAYS
        overlay = HERMES_OVERLAYS["crof"]
        assert overlay.transport == "openai_chat"
        assert overlay.base_url_env_var == "CROFAI_BASE_URL"
        assert not overlay.is_aggregator

    def test_label(self):
        from hermes_cli.providers import get_label
        assert get_label("crof") == "CrofAI"


# =============================================================================
# Auxiliary client
# =============================================================================


class TestCrofAuxiliary:
    """CrofAI auxiliary routing: vision -> kimi-k2.5."""

    def test_vision_model_override(self):
        from agent.auxiliary_client import _PROVIDER_VISION_MODELS
        assert "crof" in _PROVIDER_VISION_MODELS
        assert _PROVIDER_VISION_MODELS["crof"] == "kimi-k2.5"


# =============================================================================
# Doctor
# =============================================================================


class TestCrofDoctor:
    """Verify hermes doctor recognizes CrofAI env vars."""

    def test_provider_env_hints(self):
        from hermes_cli.doctor import _PROVIDER_ENV_HINTS
        assert "CROFAI_API_KEY" in _PROVIDER_ENV_HINTS


# =============================================================================
# Agent init
# =============================================================================


class TestCrofAgentInit:
    """Verify the agent can be constructed with crof provider without errors."""

    def test_no_syntax_errors(self):
        import importlib
        importlib.import_module("run_agent")

    def test_api_mode_is_chat_completions(self):
        from hermes_cli.providers import HERMES_OVERLAYS, TRANSPORT_TO_API_MODE
        overlay = HERMES_OVERLAYS["crof"]
        api_mode = TRANSPORT_TO_API_MODE[overlay.transport]
        assert api_mode == "chat_completions"
