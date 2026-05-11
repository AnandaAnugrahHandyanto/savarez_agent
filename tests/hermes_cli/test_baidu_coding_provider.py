"""Tests for Baidu Qianfan provider support."""

import os

import pytest

from hermes_cli.auth import (
    PROVIDER_REGISTRY,
    resolve_provider,
    get_api_key_provider_status,
    resolve_api_key_provider_credentials,
    AuthError,
)
from providers import get_provider_profile


# =============================================================================
# Plugin Profile
# =============================================================================

class TestBaiduQianfanProfile:
    """Verify the provider plugin profile."""

    def test_registered(self):
        p = get_provider_profile("baidu-coding")
        assert p is not None
        assert p.name == "baidu-coding"

    def test_aliases(self):
        assert get_provider_profile("baidu").name == "baidu-coding"
        assert get_provider_profile("qianfan").name == "baidu-coding"
        assert get_provider_profile("baidu-coding").name == "baidu-coding"
        assert get_provider_profile("baidu-coding-plan").name == "baidu-coding"

    def test_base_url(self):
        p = get_provider_profile("baidu-coding")
        assert p.base_url == "https://qianfan.baidubce.com/v2/coding"

    def test_env_vars_primary(self):
        p = get_provider_profile("baidu-coding")
        assert "BAIDU_CODING_API_KEY" in p.env_vars

    def test_env_vars_fallback(self):
        p = get_provider_profile("baidu-coding")
        assert "BAIDU_API_KEY" in p.env_vars

    def test_env_vars_base_url(self):
        p = get_provider_profile("baidu-coding")
        assert "BAIDU_CODING_BASE_URL" in p.env_vars

    def test_auth_type(self):
        p = get_provider_profile("baidu-coding")
        assert p.auth_type == "api_key"

    def test_fallback_models(self):
        p = get_provider_profile("baidu-coding")
        assert "glm-5" in p.fallback_models
        assert "deepseek-v3.2" in p.fallback_models
        # glm-4.7 is NOT on Coding Plan — must not be a fallback
        assert "glm-4.7" not in p.fallback_models

    def test_default_aux_model(self):
        p = get_provider_profile("baidu-coding")
        assert p.default_aux_model == "deepseek-v3.2"


# =============================================================================
# Provider Registry (auth.py)
# =============================================================================

class TestBaiduQianfanRegistry:
    """Verify Baidu Qianfan is registered correctly in the PROVIDER_REGISTRY."""

    def test_registered(self):
        assert "baidu-coding" in PROVIDER_REGISTRY

    def test_name(self):
        assert PROVIDER_REGISTRY["baidu-coding"].name == "Baidu Coding Plan"

    def test_auth_type(self):
        assert PROVIDER_REGISTRY["baidu-coding"].auth_type == "api_key"

    def test_inference_base_url(self):
        assert PROVIDER_REGISTRY["baidu-coding"].inference_base_url == "https://qianfan.baidubce.com/v2/coding"

    def test_api_key_env_vars(self):
        env_vars = PROVIDER_REGISTRY["baidu-coding"].api_key_env_vars
        assert "BAIDU_CODING_API_KEY" in env_vars
        assert "BAIDU_API_KEY" in env_vars
        # Primary key should come first
        assert env_vars[0] == "BAIDU_CODING_API_KEY"

    def test_base_url_env_var(self):
        assert PROVIDER_REGISTRY["baidu-coding"].base_url_env_var == "BAIDU_CODING_BASE_URL"


# =============================================================================
# Aliases (auth.py + providers.py + models.py)
# =============================================================================

class TestBaiduQianfanAliases:
    """All aliases should resolve to 'baidu-coding'."""

    @pytest.mark.parametrize("alias", [
        "baidu", "qianfan", "baidu-coding", "baidu-coding-plan",
    ])
    def test_alias_resolves(self, alias, monkeypatch):
        for key in ("BAIDU_CODING_API_KEY", "BAIDU_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("BAIDU_CODING_API_KEY", "***")
        assert resolve_provider(alias) == "baidu-coding"

    def test_normalize_provider_models_py(self):
        from hermes_cli.models import normalize_provider
        # models.py _PROVIDER_ALIASES does not include "baidu" or "qianfan"
        # aliases; those are in providers.py only.
        assert normalize_provider("baidu") == "baidu"
        assert normalize_provider("qianfan") == "qianfan"
        assert normalize_provider("baidu-coding") == "baidu-coding"

    def test_normalize_provider_providers_py(self):
        from hermes_cli.providers import normalize_provider
        assert normalize_provider("baidu") == "baidu-coding"
        assert normalize_provider("qianfan") == "baidu-coding"


# =============================================================================
# Auto-detection
# =============================================================================

class TestBaiduQianfanAutoDetection:
    """Setting env vars should allow provider resolution."""

    def test_primary_key_resolution(self, monkeypatch):
        monkeypatch.setenv("BAIDU_CODING_API_KEY", "sk-sp-test")
        assert resolve_provider("baidu-coding") == "baidu-coding"

    def test_fallback_key_resolution(self, monkeypatch):
        monkeypatch.delenv("BAIDU_CODING_API_KEY", raising=False)
        monkeypatch.setenv("BAIDU_API_KEY", "sk-sp-test")
        assert resolve_provider("baidu-coding") == "baidu-coding"


# =============================================================================
# HermesOverlay (providers.py)
# =============================================================================

class TestBaiduQianfanOverlay:
    """Verify the HermesOverlay entry."""

    def test_overlay_exists(self):
        from hermes_cli.providers import HERMES_OVERLAYS
        assert "baidu-coding" in HERMES_OVERLAYS

    def test_transport(self):
        from hermes_cli.providers import HERMES_OVERLAYS
        assert HERMES_OVERLAYS["baidu-coding"].transport == "openai_chat"

    def test_extra_env_vars(self):
        from hermes_cli.providers import HERMES_OVERLAYS
        overlay = HERMES_OVERLAYS["baidu-coding"]
        assert "BAIDU_CODING_API_KEY" in overlay.extra_env_vars
        assert "BAIDU_API_KEY" in overlay.extra_env_vars

    def test_base_url_env_var(self):
        from hermes_cli.providers import HERMES_OVERLAYS
        assert HERMES_OVERLAYS["baidu-coding"].base_url_env_var == "BAIDU_CODING_BASE_URL"


# =============================================================================
# Model List (models.py) — only official Coding Plan models
# =============================================================================

class TestBaiduQianfanModels:
    """Verify model list matches official Coding Plan page exactly."""

    def test_model_list_exists(self):
        from hermes_cli.models import _PROVIDER_MODELS
        assert "baidu-coding" in _PROVIDER_MODELS

    def test_official_coding_plan_models(self):
        """Exactly the 7 models from cloud.baidu.com/doc/qianfan/s/imlg0beiu."""
        from hermes_cli.models import _PROVIDER_MODELS
        models = _PROVIDER_MODELS["baidu-coding"]
        assert set(models) == {
            "glm-5.1",
            "glm-5",
            "deepseek-v3.2",
            "deepseek-v4-flash",
            "kimi-k2.5",
            "minimax-m2.5",
            "ernie-4.5-turbo",
        }

    def test_no_non_coding_plan_models(self):
        """Models on standard Qianfan but NOT Coding Plan must be excluded."""
        from hermes_cli.models import _PROVIDER_MODELS
        models = _PROVIDER_MODELS["baidu-coding"]
        assert "glm-4.7" not in models
        assert "deepseek-v3.2-think" not in models


# =============================================================================
# CANONICAL_PROVIDERS (models.py)
# =============================================================================

class TestBaiduQianfanCanonical:
    """Verify entry in CANONICAL_PROVIDERS for TUI picker."""

    def test_in_canonical_providers(self):
        from hermes_cli.models import CANONICAL_PROVIDERS
        slugs = [p.slug for p in CANONICAL_PROVIDERS]
        assert "baidu-coding" in slugs


# =============================================================================
# Context Length Table — verified from official Baidu docs
# =============================================================================

class TestBaiduQianfanContextLengths:
    """Verify the static context length table for Baidu Qianfan.

    Source: https://cloud.baidu.com/doc/qianfan/s/rmh4stp0j
    """

    def test_glm_51_context(self):
        from agent.baidu_coding_context import get_baidu_coding_context_length
        assert get_baidu_coding_context_length("glm-5.1") == 198_000

    def test_glm_5_context(self):
        from agent.baidu_coding_context import get_baidu_coding_context_length
        assert get_baidu_coding_context_length("glm-5") == 198_000

    def test_deepseek_v32_context(self):
        from agent.baidu_coding_context import get_baidu_coding_context_length
        assert get_baidu_coding_context_length("deepseek-v3.2") == 128_000

    def test_deepseek_v4_flash_context(self):
        from agent.baidu_coding_context import get_baidu_coding_context_length
        assert get_baidu_coding_context_length("deepseek-v4-flash") == 1_000_000

    def test_kimi_k25_context(self):
        from agent.baidu_coding_context import get_baidu_coding_context_length
        assert get_baidu_coding_context_length("kimi-k2.5") == 256_000

    def test_minimax_m25_context(self):
        from agent.baidu_coding_context import get_baidu_coding_context_length
        assert get_baidu_coding_context_length("minimax-m2.5") == 192_000

    def test_ernie_45_turbo_context(self):
        from agent.baidu_coding_context import get_baidu_coding_context_length
        assert get_baidu_coding_context_length("ernie-4.5-turbo") == 128_000

    def test_unknown_model_default(self):
        from agent.baidu_coding_context import get_baidu_coding_context_length
        assert get_baidu_coding_context_length("unknown-model") == 128_000

    def test_baidu_differs_from_zai(self):
        """glm-5.1 should be 198k on Baidu, not 204,800 (Z.AI) or 202,752 (hardcoded catch-all)."""
        from agent.baidu_coding_context import get_baidu_coding_context_length
        ctx = get_baidu_coding_context_length("glm-5.1")
        assert ctx == 198_000
        assert ctx != 204_800  # Z.AI
        assert ctx != 202_752  # DEFAULT_CONTEXT_LENGTHS catch-all

    def test_kimi_differs_from_native(self):
        """kimi-k2.5 should be 256k on Baidu, not 262,144 (Moonshot native)."""
        from agent.baidu_coding_context import get_baidu_coding_context_length
        ctx = get_baidu_coding_context_length("kimi-k2.5")
        assert ctx == 256_000
        assert ctx != 262_144  # Moonshot native

    def test_minimax_differs_from_native(self):
        """minimax-m2.5 should be 192k on Baidu, not 204,800 (MiniMax native)."""
        from agent.baidu_coding_context import get_baidu_coding_context_length
        ctx = get_baidu_coding_context_length("minimax-m2.5")
        assert ctx == 192_000
        assert ctx != 204_800  # MiniMax native


# =============================================================================
# Credentials
# =============================================================================


class TestBaiduCredentials:
    """Test credential resolution for the baidu-coding provider."""

    def test_primary_key_preferred(self, monkeypatch):
        """BAIDU_CODING_API_KEY takes priority over BAIDU_API_KEY."""
        monkeypatch.setenv("BAIDU_CODING_API_KEY", "primary-key")
        monkeypatch.setenv("BAIDU_API_KEY", "fallback-key")
        creds = resolve_api_key_provider_credentials("baidu-coding")
        assert creds["api_key"] == "primary-key"

    def test_fallback_key_used(self, monkeypatch):
        """BAIDU_API_KEY is used when BAIDU_CODING_API_KEY is not set."""
        monkeypatch.delenv("BAIDU_CODING_API_KEY", raising=False)
        monkeypatch.setenv("BAIDU_API_KEY", "fallback-key")
        creds = resolve_api_key_provider_credentials("baidu-coding")
        assert creds["api_key"] == "fallback-key"

    def test_missing_both_keys_raises(self, monkeypatch):
        """Missing both keys returns empty api_key (no AuthError)."""
        monkeypatch.delenv("BAIDU_CODING_API_KEY", raising=False)
        monkeypatch.delenv("BAIDU_API_KEY", raising=False)
        monkeypatch.setattr("hermes_cli.config.get_env_value", lambda k: None)
        creds = resolve_api_key_provider_credentials("baidu-coding")
        assert not creds["api_key"]

    def test_status_configured(self, monkeypatch):
        monkeypatch.setenv("BAIDU_CODING_API_KEY", "sk-sp-testkey")
        monkeypatch.delenv("BAIDU_API_KEY", raising=False)
        monkeypatch.setattr("hermes_cli.config.get_env_value", lambda k: os.environ.get(k))
        status = get_api_key_provider_status("baidu-coding")
        assert status["configured"]

    def test_status_not_configured(self, monkeypatch):
        monkeypatch.delenv("BAIDU_CODING_API_KEY", raising=False)
        monkeypatch.delenv("BAIDU_API_KEY", raising=False)
        monkeypatch.setattr("hermes_cli.config.get_env_value", lambda k: None)
        status = get_api_key_provider_status("baidu-coding")
        assert not status["configured"]


# =============================================================================
# URL mapping
# =============================================================================


class TestBaiduURLMapping:
    """Test URL → provider inference for Baidu Qianfan endpoints."""

    def test_url_to_provider(self):
        from agent.model_metadata import _URL_TO_PROVIDER
        assert _URL_TO_PROVIDER.get("qianfan.baidubce.com") == "baidu-coding"

    def test_provider_prefixes(self):
        from agent.model_metadata import _PROVIDER_PREFIXES
        assert "baidu" in _PROVIDER_PREFIXES
        assert "qianfan" in _PROVIDER_PREFIXES
        assert "baidu-coding" in _PROVIDER_PREFIXES
        assert "baidu-qianfan" in _PROVIDER_PREFIXES

    def test_infer_from_url(self):
        from agent.model_metadata import _infer_provider_from_url
        assert _infer_provider_from_url("https://qianfan.baidubce.com/v2/coding") == "baidu-coding"


# =============================================================================
# Doctor
# =============================================================================


class TestBaiduDoctor:
    """Verify hermes doctor recognizes Baidu env vars."""

    def test_primary_env_hint(self):
        from hermes_cli.doctor import _PROVIDER_ENV_HINTS
        assert "BAIDU_CODING_API_KEY" in _PROVIDER_ENV_HINTS

    def test_fallback_env_hint(self):
        from hermes_cli.doctor import _PROVIDER_ENV_HINTS
        assert "BAIDU_API_KEY" in _PROVIDER_ENV_HINTS


# =============================================================================
# Auxiliary client
# =============================================================================


class TestBaiduAuxiliary:
    """Baidu Qianfan auxiliary model routing."""

    def test_aux_model_registered(self):
        from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS
        assert "baidu-coding" in _API_KEY_PROVIDER_AUX_MODELS
        assert _API_KEY_PROVIDER_AUX_MODELS["baidu-coding"] == "deepseek-v3.2"

    def test_aux_aliases(self):
        from agent.auxiliary_client import _PROVIDER_ALIASES
        assert _PROVIDER_ALIASES.get("baidu") == "baidu-coding"
        assert _PROVIDER_ALIASES.get("qianfan") == "baidu-coding"
        assert _PROVIDER_ALIASES.get("baidu-qianfan") == "baidu-coding"

    def test_aux_fallback_model(self):
        from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS_FALLBACK
        assert _API_KEY_PROVIDER_AUX_MODELS_FALLBACK.get("baidu-coding") == "deepseek-v3.2"
