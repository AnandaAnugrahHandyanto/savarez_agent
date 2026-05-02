"""Tests for Fireworks AI provider support."""

import os

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
    "XIAOMI_API_KEY", "OPENROUTER_API_KEY", "COPILOT_GITHUB_TOKEN",
    "GH_TOKEN", "GITHUB_TOKEN", "ARCEEAI_API_KEY",
    "TOKENHUB_API_KEY", "OLLAMA_API_KEY",
)


class TestFireworksProviderRegistry:
    """Verify fireworks is registered correctly in the PROVIDER_REGISTRY."""

    def test_registered(self):
        assert "fireworks" in PROVIDER_REGISTRY

    def test_name(self):
        assert PROVIDER_REGISTRY["fireworks"].name == "Fireworks AI"

    def test_auth_type(self):
        assert PROVIDER_REGISTRY["fireworks"].auth_type == "api_key"

    def test_inference_base_url(self):
        assert (
            PROVIDER_REGISTRY["fireworks"].inference_base_url
            == "https://api.fireworks.ai/inference/v1"
        )

    def test_api_key_env_vars(self):
        assert PROVIDER_REGISTRY["fireworks"].api_key_env_vars == ("FIREWORKS_API_KEY",)

    def test_base_url_env_var(self):
        assert PROVIDER_REGISTRY["fireworks"].base_url_env_var == "FIREWORKS_BASE_URL"


class TestFireworksAliases:
    """All aliases should resolve to 'fireworks'."""

    @pytest.mark.parametrize("alias", ["fireworks", "fireworks-ai", "fw"])
    def test_alias_resolves(self, alias, monkeypatch):
        for key in _OTHER_PROVIDER_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("FIREWORKS_API_KEY", "fw-test-key-12345678")
        assert resolve_provider(alias) == "fireworks"

    def test_normalize_provider_models_py(self):
        from hermes_cli.models import normalize_provider
        assert normalize_provider("fireworks") == "fireworks"
        assert normalize_provider("fireworks-ai") == "fireworks"
        assert normalize_provider("fw") == "fireworks"


class TestFireworksAutoDetection:
    """Setting FIREWORKS_API_KEY should auto-detect the provider."""

    def test_auto_detect(self, monkeypatch):
        for var in _OTHER_PROVIDER_KEYS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("FIREWORKS_API_KEY", "fw-test-key-12345678")
        provider = resolve_provider("auto")
        assert provider == "fireworks"


class TestFireworksCredentials:
    """Test credential resolution for the fireworks provider."""

    def test_status_configured(self, monkeypatch):
        monkeypatch.setenv("FIREWORKS_API_KEY", "fw-test-12345678")
        status = get_api_key_provider_status("fireworks")
        assert status["configured"]

    def test_status_not_configured(self, monkeypatch):
        monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
        status = get_api_key_provider_status("fireworks")
        assert not status["configured"]

    def test_resolve_credentials(self, monkeypatch):
        monkeypatch.setenv("FIREWORKS_API_KEY", "fw-test-12345678")
        monkeypatch.delenv("FIREWORKS_BASE_URL", raising=False)
        creds = resolve_api_key_provider_credentials("fireworks")
        assert creds["api_key"] == "fw-test-12345678"
        assert creds["base_url"] == "https://api.fireworks.ai/inference/v1"

    def test_custom_base_url_override(self, monkeypatch):
        monkeypatch.setenv("FIREWORKS_API_KEY", "fw-test-12345678")
        monkeypatch.setenv(
            "FIREWORKS_BASE_URL", "https://custom.fireworks.example/v1"
        )
        creds = resolve_api_key_provider_credentials("fireworks")
        assert creds["base_url"] == "https://custom.fireworks.example/v1"


class TestFireworksModelCatalog:
    """Fireworks appears in the models.dev preferred list."""

    def test_in_models_dev_preferred(self):
        from hermes_cli.models import _MODELS_DEV_PREFERRED
        assert "fireworks" in _MODELS_DEV_PREFERRED


class TestFireworksCanonicalProvider:
    """Fireworks appears in the interactive model picker."""

    def test_in_canonical_providers(self):
        from hermes_cli.models import CANONICAL_PROVIDERS
        slugs = [p.slug for p in CANONICAL_PROVIDERS]
        assert "fireworks" in slugs

    def test_label(self):
        from hermes_cli.models import CANONICAL_PROVIDERS
        entry = next(p for p in CANONICAL_PROVIDERS if p.slug == "fireworks")
        assert entry.label == "Fireworks AI"


class TestFireworksApiMode:
    """Verify determine_api_mode routes fireworks correctly."""

    def test_determine_api_mode_direct(self):
        from hermes_cli.providers import determine_api_mode
        mode = determine_api_mode("fireworks")
        assert mode == "chat_completions"

    def test_determine_api_mode_with_base_url(self):
        from hermes_cli.providers import determine_api_mode
        mode = determine_api_mode("fireworks", "https://api.fireworks.ai/inference/v1")
        assert mode == "chat_completions"
