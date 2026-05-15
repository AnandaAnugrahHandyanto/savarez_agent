"""Tests for Auriko provider plugin wiring."""

from __future__ import annotations

import sys
import types
from unittest.mock import patch

import pytest

if "dotenv" not in sys.modules:
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = fake_dotenv

from agent.auxiliary_client import resolve_provider_client
from agent.model_metadata import (
    _PROVIDER_PREFIXES,
    _URL_TO_PROVIDER,
    _infer_provider_from_url,
)
from hermes_cli.auth import PROVIDER_REGISTRY, resolve_provider
from hermes_cli.config import OPTIONAL_ENV_VARS
from hermes_cli.main import _is_profile_api_key_provider
from hermes_cli.models import (
    CANONICAL_PROVIDERS,
    _KNOWN_PROVIDER_NAMES,
    _PROVIDER_ALIASES,
    _PROVIDER_MODELS,
    normalize_provider,
    provider_model_ids,
)
from hermes_cli.providers import (
    determine_api_mode,
    get_label,
    get_provider,
    normalize_provider as providers_normalize,
)
from providers import get_provider_profile
from providers.base import ProviderProfile


@pytest.fixture(autouse=True)
def _clear_provider_env(monkeypatch):
    for key in (
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GLM_API_KEY",
        "KIMI_API_KEY",
        "MINIMAX_API_KEY",
        "AURIKO_API_KEY",
        "AURIKO_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


class TestAurikoPluginRegistration:
    """Core plugin: registration, alias resolution, profile fields."""

    def test_profile_registered(self):
        p = get_provider_profile("auriko")
        assert p is not None
        assert p.name == "auriko"

    def test_alias_resolves(self):
        p = get_provider_profile("auriko-ai")
        assert p is not None
        assert p.name == "auriko"

    def test_base_url(self):
        p = get_provider_profile("auriko")
        assert p.base_url == "https://api.auriko.ai/v1"

    def test_auth_type(self):
        p = get_provider_profile("auriko")
        assert p.auth_type == "api_key"

    def test_env_vars(self):
        p = get_provider_profile("auriko")
        assert "AURIKO_API_KEY" in p.env_vars
        assert "AURIKO_BASE_URL" in p.env_vars

    def test_fallback_models_populated(self):
        p = get_provider_profile("auriko")
        assert len(p.fallback_models) >= 20
        assert "claude-opus-4-7" in p.fallback_models
        assert "deepseek-v3.2" in p.fallback_models

    def test_default_aux_model(self):
        p = get_provider_profile("auriko")
        assert p.default_aux_model == "claude-haiku-4-5-20251001"


class TestAurikoAutoWiring:
    """Verify auto-wired registrations — these should work with ONLY the plugin files."""

    def test_auth_provider_registry(self):
        assert "auriko" in PROVIDER_REGISTRY
        cfg = PROVIDER_REGISTRY["auriko"]
        assert cfg.auth_type == "api_key"
        assert cfg.inference_base_url == "https://api.auriko.ai/v1"

    def test_auth_alias_registered(self):
        assert "auriko-ai" in PROVIDER_REGISTRY

    def test_config_optional_env_vars(self):
        assert "AURIKO_API_KEY" in OPTIONAL_ENV_VARS
        assert OPTIONAL_ENV_VARS["AURIKO_API_KEY"]["category"] == "provider"
        assert OPTIONAL_ENV_VARS["AURIKO_API_KEY"]["password"] is True
        assert "AURIKO_BASE_URL" in OPTIONAL_ENV_VARS
        assert OPTIONAL_ENV_VARS["AURIKO_BASE_URL"]["password"] is False

    def test_canonical_providers_entry(self):
        slugs = [p.slug for p in CANONICAL_PROVIDERS]
        assert "auriko" in slugs

    def test_url_to_provider_mapping(self):
        assert _URL_TO_PROVIDER.get("api.auriko.ai") == "auriko"

    def test_resolve_provider_with_key(self, monkeypatch):
        monkeypatch.setenv("AURIKO_API_KEY", "ak_live_test")
        assert resolve_provider("auriko") == "auriko"

    def test_resolve_alias_with_key(self, monkeypatch):
        monkeypatch.setenv("AURIKO_API_KEY", "ak_live_test")
        assert resolve_provider("auriko-ai") == "auriko"


class TestAurikoModelCatalog:
    """_PROVIDER_MODELS and _PROVIDER_ALIASES entries (manually added, not auto-wired)."""

    def test_static_models_exist(self):
        assert "auriko" in _PROVIDER_MODELS
        models = _PROVIDER_MODELS["auriko"]
        assert "claude-opus-4-7" in models
        assert "deepseek-v3.2" in models
        assert "gemini-2.5-pro" in models
        assert "grok-4.3" in models
        assert len(models) >= 20

    def test_alias_in_provider_aliases(self):
        assert _PROVIDER_ALIASES.get("auriko-ai") == "auriko"

    def test_normalize_provider_resolves_alias(self):
        assert normalize_provider("auriko-ai") == "auriko"
        assert normalize_provider("auriko") == "auriko"

    def test_alias_in_known_provider_names(self):
        assert "auriko" in _KNOWN_PROVIDER_NAMES
        assert "auriko-ai" in _KNOWN_PROVIDER_NAMES


class TestAurikoProviderPrefixes:
    """_PROVIDER_PREFIXES entry (manually added, not auto-wired)."""

    def test_auriko_in_prefixes(self):
        assert "auriko" in _PROVIDER_PREFIXES

    def test_auriko_alias_in_prefixes(self):
        assert "auriko-ai" in _PROVIDER_PREFIXES

    def test_infer_provider_from_url(self):
        assert _infer_provider_from_url("https://api.auriko.ai/v1") == "auriko"


class TestAurikoModelFetch:
    """Live model fetch vs static fallback."""

    def test_provider_model_ids_prefers_live_fetch(self, monkeypatch):
        live_models = ["claude-sonnet-4-6", "deepseek-v4-pro"]
        monkeypatch.setattr(
            "hermes_cli.auth.resolve_api_key_provider_credentials",
            lambda provider_id: {
                "provider": provider_id,
                "api_key": "ak_live_key",
                "base_url": "https://api.auriko.ai/v1",
                "source": "AURIKO_API_KEY",
            },
        )
        monkeypatch.setattr(
            ProviderProfile, "fetch_models", lambda self, **kw: live_models,
        )
        assert provider_model_ids("auriko") == live_models

    def test_provider_model_ids_falls_back_to_profile_fallback_models(self, monkeypatch):
        monkeypatch.setattr(
            "hermes_cli.auth.resolve_api_key_provider_credentials",
            lambda provider_id: {
                "provider": provider_id,
                "api_key": "ak_live_key",
                "base_url": "https://api.auriko.ai/v1",
                "source": "AURIKO_API_KEY",
            },
        )
        monkeypatch.setattr(ProviderProfile, "fetch_models", lambda self, **kw: None)
        profile = get_provider_profile("auriko")
        assert provider_model_ids("auriko") == list(profile.fallback_models)


class TestAurikoAuxiliary:
    """Auxiliary client — default model and alias resolution."""

    def test_resolve_provider_client(self, monkeypatch):
        monkeypatch.setenv("AURIKO_API_KEY", "ak_live_test")
        with patch("agent.auxiliary_client.OpenAI") as mock_openai:
            mock_openai.return_value = object()
            client, model = resolve_provider_client("auriko")
        assert client is not None
        assert model == "claude-haiku-4-5-20251001"
        assert mock_openai.call_args.kwargs["api_key"] == "ak_live_test"
        assert mock_openai.call_args.kwargs["base_url"] == "https://api.auriko.ai/v1"

    def test_resolve_via_alias(self, monkeypatch):
        monkeypatch.setenv("AURIKO_API_KEY", "ak_live_test")
        with patch("agent.auxiliary_client.OpenAI") as mock_openai:
            mock_openai.return_value = object()
            client, model = resolve_provider_client("auriko-ai")
        assert client is not None
        assert model == "claude-haiku-4-5-20251001"


class TestAurikoMainFlow:
    """CLI dispatch — provider selection routes to api_key flow."""

    def test_is_profile_api_key_provider(self):
        assert _is_profile_api_key_provider("auriko") is True

    def test_determine_api_mode_defaults_to_chat_completions(self):
        assert determine_api_mode("auriko") == "chat_completions"


class TestAurikoProvidersModule:
    """hermes_cli/providers.py — HERMES_OVERLAYS, ALIASES, label."""

    def test_get_provider_returns_provider_def(self):
        pdef = get_provider("auriko")
        assert pdef is not None
        assert pdef.id == "auriko"
        assert pdef.transport == "openai_chat"
        assert pdef.base_url == "https://api.auriko.ai/v1"

    def test_get_provider_via_alias(self):
        pdef = get_provider("auriko-ai")
        assert pdef is not None
        assert pdef.id == "auriko"

    def test_providers_normalize_resolves_alias(self):
        assert providers_normalize("auriko-ai") == "auriko"

    def test_get_label(self):
        assert get_label("auriko") == "Auriko"
