"""Focused tests for Telnyx AI first-class provider wiring."""

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
from agent.model_metadata import get_model_context_length
from hermes_cli.auth import resolve_provider
from hermes_cli.model_normalize import normalize_model_for_provider
from hermes_cli.models import (
    CANONICAL_PROVIDERS,
    _PROVIDER_LABELS,
    normalize_provider,
    provider_model_ids,
)


@pytest.fixture(autouse=True)
def _clear_provider_env(monkeypatch):
    for key in (
        "TELNYX_API_KEY",
        "TELNYX_BASE_URL",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GLM_API_KEY",
        "KIMI_API_KEY",
        "MINIMAX_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


class TestTelnyxAliases:
    @pytest.mark.parametrize("alias", ["telnyx", "telnyx-ai", "telnyx-intelligence"])
    def test_auth_alias_resolves(self, alias, monkeypatch):
        monkeypatch.setenv("TELNYX_API_KEY", "telnyx-test-key")
        assert resolve_provider(alias) == "telnyx"

    @pytest.mark.parametrize("alias", ["telnyx-ai", "telnyx-intelligence"])
    def test_models_normalize_provider(self, alias):
        assert normalize_provider(alias) == "telnyx"

    @pytest.mark.parametrize("alias", ["telnyx-ai", "telnyx-intelligence"])
    def test_providers_normalize_provider(self, alias):
        from hermes_cli.providers import normalize_provider as normalize_provider_in_providers

        assert normalize_provider_in_providers(alias) == "telnyx"


class TestTelnyxConfigRegistry:
    def test_optional_env_vars_include_telnyx(self):
        from hermes_cli.config import OPTIONAL_ENV_VARS

        assert "TELNYX_API_KEY" in OPTIONAL_ENV_VARS
        assert OPTIONAL_ENV_VARS["TELNYX_API_KEY"]["category"] == "provider"
        assert OPTIONAL_ENV_VARS["TELNYX_API_KEY"]["password"] is True
        assert OPTIONAL_ENV_VARS["TELNYX_API_KEY"]["url"] == "https://portal.telnyx.com/#/app/api-keys"

        assert "TELNYX_BASE_URL" in OPTIONAL_ENV_VARS
        assert OPTIONAL_ENV_VARS["TELNYX_BASE_URL"]["category"] == "provider"
        assert OPTIONAL_ENV_VARS["TELNYX_BASE_URL"]["password"] is False


class TestTelnyxModelCatalog:
    def test_canonical_provider_entry_is_profile_injected(self):
        slugs = [p.slug for p in CANONICAL_PROVIDERS]
        assert "telnyx" in slugs
        assert _PROVIDER_LABELS["telnyx"] == "Telnyx AI"

    def test_provider_model_ids_prefers_live_api(self, monkeypatch):
        monkeypatch.setattr(
            "hermes_cli.auth.resolve_api_key_provider_credentials",
            lambda provider_id: {
                "provider": provider_id,
                "api_key": "telnyx-live-key",
                "base_url": "https://api.telnyx.com/v2/ai",
                "source": "TELNYX_API_KEY",
            },
        )

        from providers import get_provider_profile

        profile = get_provider_profile("telnyx")
        assert profile is not None
        monkeypatch.setattr(
            profile,
            "fetch_models",
            lambda api_key=None, timeout=8.0: [
                "openai/gpt-5.2",
                "zai-org/GLM-5.1-FP8",
            ],
        )

        assert provider_model_ids("telnyx") == [
            "openai/gpt-5.2",
            "zai-org/GLM-5.1-FP8",
        ]

    def test_provider_model_ids_falls_back_to_profile_models(self, monkeypatch):
        monkeypatch.setattr(
            "hermes_cli.auth.resolve_api_key_provider_credentials",
            lambda provider_id: {
                "provider": provider_id,
                "api_key": "telnyx-live-key",
                "base_url": "https://api.telnyx.com/v2/ai",
                "source": "TELNYX_API_KEY",
            },
        )

        from providers import get_provider_profile

        profile = get_provider_profile("telnyx")
        assert profile is not None
        monkeypatch.setattr(profile, "fetch_models", lambda api_key=None, timeout=8.0: None)

        models = provider_model_ids("telnyx")
        assert models[0] == "meta-llama/Meta-Llama-3.1-70B-Instruct"
        assert "openai/gpt-5.2" in models
        assert "anthropic/claude-opus-4-6" in models
        assert "zai-org/GLM-5.1-FP8" in models


class TestTelnyxProvidersModule:
    def test_overlay_exists(self):
        from hermes_cli.providers import HERMES_OVERLAYS, get_provider

        assert "telnyx" in HERMES_OVERLAYS
        overlay = HERMES_OVERLAYS["telnyx"]
        assert overlay.transport == "openai_chat"
        assert overlay.extra_env_vars == ("TELNYX_API_KEY",)
        assert overlay.base_url_override == "https://api.telnyx.com/v2/ai"
        assert overlay.base_url_env_var == "TELNYX_BASE_URL"
        assert not overlay.is_aggregator

        pdef = get_provider("telnyx-ai")
        assert pdef is not None
        assert pdef.id == "telnyx"
        assert pdef.base_url == "https://api.telnyx.com/v2/ai"
        assert pdef.api_key_env_vars == ("TELNYX_API_KEY",)

    def test_provider_profile(self):
        from providers import get_provider_profile

        profile = get_provider_profile("telnyx")
        assert profile is not None
        assert profile.base_url == "https://api.telnyx.com/v2/ai"
        assert profile.env_vars == ("TELNYX_API_KEY", "TELNYX_BASE_URL")
        assert profile.default_aux_model == "openai/gpt-4o-mini"
        assert profile.default_headers.get("User-Agent", "").startswith("HermesAgent/")


class TestTelnyxModelMetadata:
    def test_url_to_provider(self):
        from agent.model_metadata import _URL_TO_PROVIDER

        assert _URL_TO_PROVIDER.get("api.telnyx.com") == "telnyx"

    @pytest.mark.parametrize("prefix", ["telnyx", "telnyx-ai", "telnyx-intelligence"])
    def test_provider_prefixes(self, prefix):
        from agent.model_metadata import _PROVIDER_PREFIXES

        assert prefix in _PROVIDER_PREFIXES

    def test_infer_from_url(self):
        from agent.model_metadata import _infer_provider_from_url

        assert _infer_provider_from_url("https://api.telnyx.com/v2/ai") == "telnyx"

    def test_known_telnyx_endpoint_uses_endpoint_metadata(self):
        with patch(
            "agent.model_metadata.get_cached_context_length",
            return_value=None,
        ), patch(
            "agent.model_metadata.fetch_endpoint_model_metadata",
            return_value={"openai/gpt-5.2": {"context_length": 400000}},
        ), patch(
            "agent.models_dev.lookup_models_dev_context",
            return_value=None,
        ), patch(
            "agent.model_metadata.fetch_model_metadata",
            return_value={},
        ):
            result = get_model_context_length(
                "openai/gpt-5.2",
                base_url="https://api.telnyx.com/v2/ai",
                api_key="telnyx-test-key",
                provider="custom",
            )

        assert result == 400000


class TestTelnyxRuntimeHelpers:
    def test_model_normalization_strips_matching_telnyx_prefix_only(self):
        assert normalize_model_for_provider("telnyx/openai/gpt-5.2", "telnyx") == "openai/gpt-5.2"
        assert normalize_model_for_provider("openai/gpt-5.2", "telnyx") == "openai/gpt-5.2"
        assert normalize_model_for_provider("anthropic/claude-opus-4-6", "telnyx") == "anthropic/claude-opus-4-6"

    def test_aux_default_model(self):
        from agent.auxiliary_client import _get_aux_model_for_provider

        assert _get_aux_model_for_provider("telnyx") == "openai/gpt-4o-mini"

    def test_resolve_provider_client_uses_telnyx_profile(self, monkeypatch):
        monkeypatch.setenv("TELNYX_API_KEY", "telnyx-test-key")

        with patch("agent.auxiliary_client.OpenAI") as mock_openai:
            mock_openai.return_value = object()
            client, model = resolve_provider_client("telnyx-ai")

        assert client is not None
        assert model == "openai/gpt-4o-mini"
        assert mock_openai.call_args.kwargs["api_key"] == "telnyx-test-key"
        assert mock_openai.call_args.kwargs["base_url"] == "https://api.telnyx.com/v2/ai"
        headers = mock_openai.call_args.kwargs.get("default_headers", {})
        assert headers.get("User-Agent", "").startswith("HermesAgent/")
