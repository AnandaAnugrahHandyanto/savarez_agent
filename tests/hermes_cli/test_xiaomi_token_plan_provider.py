"""Tests for Xiaomi MiMo Token Plan provider support."""

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
)
from hermes_cli.model_switch import list_authenticated_providers
from hermes_cli.runtime_provider import resolve_runtime_provider


class TestXiaomiTokenPlanProviderRegistry:
    def test_registered(self):
        assert "xiaomi-token-plan" in PROVIDER_REGISTRY

    def test_name(self):
        assert PROVIDER_REGISTRY["xiaomi-token-plan"].name == "Xiaomi MiMo (Token Plan)"

    def test_auth_type(self):
        assert PROVIDER_REGISTRY["xiaomi-token-plan"].auth_type == "api_key"

    def test_inference_base_url(self):
        assert (
            PROVIDER_REGISTRY["xiaomi-token-plan"].inference_base_url
            == "https://token-plan-sgp.xiaomimimo.com/v1"
        )

    def test_api_key_env_vars(self):
        assert PROVIDER_REGISTRY["xiaomi-token-plan"].api_key_env_vars == (
            "XIAOMI_TOKEN_PLAN_API_KEY",
        )

    def test_base_url_env_var(self):
        assert PROVIDER_REGISTRY["xiaomi-token-plan"].base_url_env_var == (
            "XIAOMI_TOKEN_PLAN_BASE_URL"
        )


class TestXiaomiTokenPlanAliases:
    @pytest.mark.parametrize(
        "alias",
        ["xiaomi-token-plan", "xiaomi-token", "mimo-token-plan", "xiaomi-sgp"],
    )
    def test_alias_resolves(self, alias, monkeypatch):
        monkeypatch.setenv("XIAOMI_TOKEN_PLAN_API_KEY", "tp-test-key")
        monkeypatch.delenv("XIAOMI_API_KEY", raising=False)
        assert resolve_provider(alias) == "xiaomi-token-plan"

    def test_normalize_provider_models_py(self):
        from hermes_cli.models import normalize_provider

        assert normalize_provider("xiaomi-token") == "xiaomi-token-plan"
        assert normalize_provider("mimo-token-plan") == "xiaomi-token-plan"
        assert normalize_provider("xiaomi-sgp") == "xiaomi-token-plan"

    def test_normalize_provider_providers_py(self):
        from hermes_cli.providers import normalize_provider

        assert normalize_provider("xiaomi-token") == "xiaomi-token-plan"
        assert normalize_provider("mimo-token-plan") == "xiaomi-token-plan"
        assert normalize_provider("xiaomi-sgp") == "xiaomi-token-plan"


class TestXiaomiTokenPlanAutoDetection:
    def test_auto_detect_prefers_token_plan_when_only_token_plan_key_is_set(self, monkeypatch):
        for var in (
            "OPENROUTER_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_TOKEN",
            "CLAUDE_CODE_OAUTH_TOKEN",
            "DEEPSEEK_API_KEY",
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "DASHSCOPE_API_KEY",
            "XAI_API_KEY",
            "KIMI_API_KEY",
            "MINIMAX_API_KEY",
            "AI_GATEWAY_API_KEY",
            "KILOCODE_API_KEY",
            "HF_TOKEN",
            "GLM_API_KEY",
            "COPILOT_GITHUB_TOKEN",
            "GH_TOKEN",
            "GITHUB_TOKEN",
            "MINIMAX_CN_API_KEY",
            "XIAOMI_API_KEY",
        ):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("XIAOMI_TOKEN_PLAN_API_KEY", "tp-test-key")
        assert resolve_provider("auto") == "xiaomi-token-plan"


class TestXiaomiTokenPlanCredentials:
    def test_status_configured(self, monkeypatch):
        monkeypatch.setenv("XIAOMI_TOKEN_PLAN_API_KEY", "tp-test-key")
        status = get_api_key_provider_status("xiaomi-token-plan")
        assert status["configured"]

    def test_resolve_credentials(self, monkeypatch):
        monkeypatch.setenv("XIAOMI_TOKEN_PLAN_API_KEY", "tp-test-key")
        monkeypatch.delenv("XIAOMI_TOKEN_PLAN_BASE_URL", raising=False)
        creds = resolve_api_key_provider_credentials("xiaomi-token-plan")
        assert creds["api_key"] == "tp-test-key"
        assert creds["base_url"] == "https://token-plan-sgp.xiaomimimo.com/v1"

    def test_custom_base_url_override(self, monkeypatch):
        monkeypatch.setenv("XIAOMI_TOKEN_PLAN_API_KEY", "tp-test-key")
        monkeypatch.setenv(
            "XIAOMI_TOKEN_PLAN_BASE_URL", "https://token-plan-ams.xiaomimimo.com/v1"
        )
        creds = resolve_api_key_provider_credentials("xiaomi-token-plan")
        assert creds["base_url"] == "https://token-plan-ams.xiaomimimo.com/v1"


class TestXiaomiTokenPlanModelsAndListing:
    def test_static_model_list_exists(self):
        from hermes_cli.models import _PROVIDER_MODELS

        assert "xiaomi-token-plan" in _PROVIDER_MODELS
        models = _PROVIDER_MODELS["xiaomi-token-plan"]
        assert "mimo-v2-pro" in models
        assert "mimo-v2-omni" in models
        assert "mimo-v2-flash" in models

    def test_normalize_strips_provider_prefix(self):
        from hermes_cli.model_normalize import normalize_model_for_provider

        assert (
            normalize_model_for_provider("xiaomi/mimo-v2-pro", "xiaomi-token-plan")
            == "mimo-v2-pro"
        )

    def test_authenticated_provider_listing_includes_token_plan(self, monkeypatch):
        monkeypatch.setenv("XIAOMI_TOKEN_PLAN_API_KEY", "***")
        monkeypatch.delenv("XIAOMI_API_KEY", raising=False)
        providers = list_authenticated_providers(current_provider="xiaomi-token-plan")
        slugs = [p["slug"] for p in providers]
        assert "xiaomi-token-plan" in slugs
        entry = next(p for p in providers if p["slug"] == "xiaomi-token-plan")
        assert entry["is_current"] is True
        assert entry["models"][:3] == ["mimo-v2-pro", "mimo-v2-omni", "mimo-v2-flash"]


class TestXiaomiTokenPlanRuntimeResolution:
    def test_runtime_provider_uses_token_plan_base_url(self, monkeypatch):
        monkeypatch.setenv("XIAOMI_TOKEN_PLAN_API_KEY", "tp-test-key")
        monkeypatch.delenv("XIAOMI_TOKEN_PLAN_BASE_URL", raising=False)
        runtime = resolve_runtime_provider(requested="xiaomi-token-plan")
        assert runtime["provider"] == "xiaomi-token-plan"
        assert runtime["base_url"] == "https://token-plan-sgp.xiaomimimo.com/v1"
        assert runtime["api_mode"] == "chat_completions"


class TestXiaomiTokenPlanConfigAndDoctor:
    def test_optional_env_vars_registered(self):
        from hermes_cli.config import OPTIONAL_ENV_VARS

        assert "XIAOMI_TOKEN_PLAN_API_KEY" in OPTIONAL_ENV_VARS
        assert OPTIONAL_ENV_VARS["XIAOMI_TOKEN_PLAN_API_KEY"]["category"] == "provider"
        assert OPTIONAL_ENV_VARS["XIAOMI_TOKEN_PLAN_API_KEY"]["password"] is True
        assert "XIAOMI_TOKEN_PLAN_BASE_URL" in OPTIONAL_ENV_VARS
        assert OPTIONAL_ENV_VARS["XIAOMI_TOKEN_PLAN_BASE_URL"]["category"] == "provider"
        assert OPTIONAL_ENV_VARS["XIAOMI_TOKEN_PLAN_BASE_URL"]["advanced"] is True

    def test_provider_env_hints(self):
        from hermes_cli.doctor import _PROVIDER_ENV_HINTS

        assert "XIAOMI_TOKEN_PLAN_API_KEY" in _PROVIDER_ENV_HINTS
