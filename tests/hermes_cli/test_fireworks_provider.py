"""Tests for Fireworks AI provider integration."""

import os
import pytest
from unittest.mock import patch, MagicMock

from hermes_cli.auth import PROVIDER_REGISTRY, resolve_provider, resolve_api_key_provider_credentials
from hermes_cli.models import _PROVIDER_MODELS, _PROVIDER_LABELS, _PROVIDER_ALIASES, normalize_provider
from hermes_cli.model_normalize import normalize_model_for_provider
from agent.model_metadata import _URL_TO_PROVIDER, _PROVIDER_PREFIXES
from agent.models_dev import PROVIDER_TO_MODELS_DEV, list_agentic_models


# ── Provider Registry ──

class TestFireworksProviderRegistry:
    def test_in_registry(self):
        assert "fireworks" in PROVIDER_REGISTRY

    def test_config(self):
        pconfig = PROVIDER_REGISTRY["fireworks"]
        assert pconfig.id == "fireworks"
        assert pconfig.name == "Fireworks AI"
        assert pconfig.auth_type == "api_key"
        assert pconfig.inference_base_url == "https://api.fireworks.ai/inference/v1"

    def test_env_vars(self):
        pconfig = PROVIDER_REGISTRY["fireworks"]
        assert pconfig.api_key_env_vars == ("FIREWORKS_API_KEY",)
        assert pconfig.base_url_env_var == "FIREWORKS_BASE_URL"

    def test_base_url(self):
        assert "api.fireworks.ai" in PROVIDER_REGISTRY["fireworks"].inference_base_url


# ── Provider Aliases ──

PROVIDER_ENV_VARS = (
    "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY", "GEMINI_API_KEY", "FIREWORKS_API_KEY",
    "GLM_API_KEY", "ZAI_API_KEY", "KIMI_API_KEY",
    "MINIMAX_API_KEY", "DEEPSEEK_API_KEY",
)

@pytest.fixture(autouse=True)
def _clean_provider_env(monkeypatch):
    for var in PROVIDER_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class TestFireworksAliases:
    def test_explicit(self):
        assert resolve_provider("fireworks") == "fireworks"

    def test_alias_fireworks_ai(self):
        assert resolve_provider("fireworks-ai") == "fireworks"

    def test_alias_fw(self):
        assert resolve_provider("fw") == "fireworks"

    def test_models_py_aliases(self):
        assert _PROVIDER_ALIASES.get("fireworks-ai") == "fireworks"
        assert _PROVIDER_ALIASES.get("fw") == "fireworks"

    def test_normalize_provider(self):
        assert normalize_provider("fireworks") == "fireworks"
        assert normalize_provider("fw") == "fireworks"
        assert normalize_provider("fireworks-ai") == "fireworks"


# ── Auto-detection ──

class TestFireworksAutoDetection:
    def test_auto_detects_api_key(self, monkeypatch):
        monkeypatch.setenv("FIREWORKS_API_KEY", "test-key")
        assert resolve_provider("auto") == "fireworks"


# ── Credential Resolution ──

class TestFireworksCredentials:
    def test_resolve_with_api_key(self, monkeypatch):
        monkeypatch.setenv("FIREWORKS_API_KEY", "fw-secret")
        creds = resolve_api_key_provider_credentials("fireworks")
        assert creds["provider"] == "fireworks"
        assert creds["api_key"] == "fw-secret"
        assert creds["base_url"] == "https://api.fireworks.ai/inference/v1"

    def test_resolve_with_custom_base_url(self, monkeypatch):
        monkeypatch.setenv("FIREWORKS_API_KEY", "key")
        monkeypatch.setenv("FIREWORKS_BASE_URL", "https://custom.fw/v1")
        creds = resolve_api_key_provider_credentials("fireworks")
        assert creds["base_url"] == "https://custom.fw/v1"

    def test_runtime(self, monkeypatch):
        monkeypatch.setenv("FIREWORKS_API_KEY", "fw-key")
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="fireworks")
        assert result["provider"] == "fireworks"
        assert result["api_mode"] == "chat_completions"
        assert result["api_key"] == "fw-key"
        assert result["base_url"] == "https://api.fireworks.ai/inference/v1"


# ── Model Catalog (dynamic) ──

class TestFireworksModelCatalog:
    def test_no_static_model_list(self):
        """Fireworks models are discovered dynamically via models.dev + live API."""
        assert "fireworks" not in _PROVIDER_MODELS

    def test_provider_label(self):
        assert "fireworks" in _PROVIDER_LABELS
        assert _PROVIDER_LABELS["fireworks"] == "Fireworks AI"


# ── Model Normalization ──

class TestFireworksModelNormalization:
    def test_passthrough(self):
        """Fireworks uses vendor-prefixed model names as-is."""
        model = "accounts/fireworks/models/gpt-oss-120b"
        assert normalize_model_for_provider(model, "fireworks") == model

    def test_passthrough_short(self):
        assert normalize_model_for_provider("llama3.1-8b", "fireworks") == "llama3.1-8b"


# ── URL-to-Provider Mapping ──

class TestFireworksUrlMapping:
    def test_url_to_provider(self):
        assert _URL_TO_PROVIDER.get("api.fireworks.ai") == "fireworks"

    def test_provider_prefix_canonical(self):
        assert "fireworks" in _PROVIDER_PREFIXES

    def test_provider_prefix_alias_fw(self):
        assert "fw" in _PROVIDER_PREFIXES

    def test_provider_prefix_alias_fireworks_ai(self):
        assert "fireworks-ai" in _PROVIDER_PREFIXES


# ── models.dev Integration ──

class TestFireworksModelsDev:
    def test_mapped(self):
        assert PROVIDER_TO_MODELS_DEV.get("fireworks") == "fireworks-ai"

    def test_list_agentic_models_with_mock_data(self):
        mock_data = {
            "fireworks-ai": {
                "models": {
                    "accounts/fireworks/models/gpt-oss-120b": {"tool_call": True},
                    "accounts/fireworks/models/llama3.1-8b": {"tool_call": True},
                    "accounts/fireworks/models/some-embedding": {"tool_call": False},
                }
            }
        }
        with patch("agent.models_dev.fetch_models_dev", return_value=mock_data):
            result = list_agentic_models("fireworks")
        assert "accounts/fireworks/models/gpt-oss-120b" in result
        assert "accounts/fireworks/models/llama3.1-8b" in result
        assert "accounts/fireworks/models/some-embedding" not in result


# ── Agent Init ──

class TestFireworksAgentInit:
    def test_agent_imports_without_error(self):
        import importlib
        import run_agent
        importlib.reload(run_agent)

    def test_uses_chat_completions(self, monkeypatch):
        monkeypatch.setenv("FIREWORKS_API_KEY", "test-key")
        with patch("run_agent.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            from run_agent import AIAgent
            agent = AIAgent(
                model="accounts/fireworks/models/gpt-oss-120b",
                provider="fireworks",
                api_key="test-key",
                base_url="https://api.fireworks.ai/inference/v1",
            )
            assert agent.api_mode == "chat_completions"
            assert agent.provider == "fireworks"


# ── providers.py New System ──

class TestFireworksProvidersNew:
    def test_overlay_exists(self):
        from hermes_cli.providers import HERMES_OVERLAYS
        assert "fireworks" in HERMES_OVERLAYS
        overlay = HERMES_OVERLAYS["fireworks"]
        assert overlay.transport == "openai_chat"
        assert overlay.base_url_env_var == "FIREWORKS_BASE_URL"

    def test_alias_resolves(self):
        from hermes_cli.providers import normalize_provider as np
        assert np("fireworks") == "fireworks"
        assert np("fw") == "fireworks"
        assert np("fireworks-ai") == "fireworks"

    def test_label(self):
        from hermes_cli.providers import get_label
        assert get_label("fireworks") == "Fireworks AI"

    def test_get_provider(self):
        from hermes_cli.providers import get_provider
        pdef = get_provider("fireworks")
        assert pdef is not None
        assert pdef.id == "fireworks"
        assert pdef.transport == "openai_chat"


# ── Auxiliary Model ──

class TestFireworksAuxiliary:
    def test_aux_model_defined(self):
        from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS
        assert "fireworks" in _API_KEY_PROVIDER_AUX_MODELS
