"""Tests for Eden AI provider support."""

import types

import pytest

from hermes_cli.auth import (
    PROVIDER_REGISTRY,
    resolve_provider,
    get_api_key_provider_status,
    resolve_api_key_provider_credentials,
)


@pytest.fixture(autouse=True)
def _clear_provider_env(monkeypatch):
    """Clear every provider's env vars + auth store before each test.

    Reads ``PROVIDER_REGISTRY`` dynamically so the list stays current as new
    providers land — no hardcoded constant to maintain. Extras list covers
    env vars that intentionally live outside ``PROVIDER_REGISTRY``: OpenRouter
    (Hermes' default-fallback, special-cased in ``auth.py``), the GitHub /
    Copilot tokens (resolved through external auth flows), and HF_TOKEN.
    """
    for pcfg in PROVIDER_REGISTRY.values():
        for env in pcfg.api_key_env_vars:
            monkeypatch.delenv(env, raising=False)
        if pcfg.base_url_env_var:
            monkeypatch.delenv(pcfg.base_url_env_var, raising=False)
    for env in (
        "OPENROUTER_API_KEY",
        "COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN",
        "HF_TOKEN",
    ):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr("hermes_cli.auth._load_auth_store", lambda: {})


# =============================================================================
# Provider Registry
# =============================================================================


class TestEdenAIProviderRegistry:
    def test_registered(self):
        assert "edenai" in PROVIDER_REGISTRY

    def test_name(self):
        assert PROVIDER_REGISTRY["edenai"].name == "Eden AI"

    def test_auth_type(self):
        assert PROVIDER_REGISTRY["edenai"].auth_type == "api_key"

    def test_inference_base_url(self):
        assert PROVIDER_REGISTRY["edenai"].inference_base_url == "https://api.edenai.run/v3"

    def test_api_key_env_vars(self):
        assert PROVIDER_REGISTRY["edenai"].api_key_env_vars == ("EDENAI_API_KEY",)

    def test_base_url_env_var(self):
        assert PROVIDER_REGISTRY["edenai"].base_url_env_var == "EDENAI_BASE_URL"


# =============================================================================
# Aliases (auth.py + models.py + providers.py)
# =============================================================================


class TestEdenAIAliases:
    @pytest.mark.parametrize("alias", ["edenai", "eden", "eden-ai", "eden_ai"])
    def test_alias_resolves_in_auth(self, alias, monkeypatch):
        monkeypatch.setenv("EDENAI_API_KEY", "eden-test-12345")
        assert resolve_provider(alias) == "edenai"

    def test_normalize_provider_models_py(self):
        from hermes_cli.models import normalize_provider
        assert normalize_provider("eden") == "edenai"
        assert normalize_provider("eden-ai") == "edenai"

    def test_normalize_provider_providers_py(self):
        from hermes_cli.providers import normalize_provider
        assert normalize_provider("eden") == "edenai"
        assert normalize_provider("eden-ai") == "edenai"


# =============================================================================
# Credentials
# =============================================================================


class TestEdenAICredentials:
    # Env-clear is handled by the module-level ``_clear_provider_env`` autouse
    # fixture at the top of this file — no per-class duplication needed.

    def test_status_configured(self, monkeypatch):
        monkeypatch.setenv("EDENAI_API_KEY", "eden-test")
        status = get_api_key_provider_status("edenai")
        assert status["configured"]

    def test_status_not_configured(self):
        status = get_api_key_provider_status("edenai")
        assert not status["configured"]

    def test_status_isolated_from_other_provider_keys(self, monkeypatch):
        """An unrelated provider's API key must not flip Eden AI to ``configured``.

        Verified with ``ANTHROPIC_API_KEY`` rather than ``OPENROUTER_API_KEY``
        because OpenRouter is Hermes' default-fallback provider — its priority
        behaviour is host-internal logic, not an Eden AI concern.
        """
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        status = get_api_key_provider_status("edenai")
        assert not status["configured"]

    def test_auto_detects_when_only_edenai_env_set(self, monkeypatch):
        monkeypatch.setenv("EDENAI_API_KEY", "eden-key")
        assert resolve_provider("auto") == "edenai"

    def test_resolve_credentials(self, monkeypatch):
        monkeypatch.setenv("EDENAI_API_KEY", "eden-direct-key")
        creds = resolve_api_key_provider_credentials("edenai")
        assert creds["api_key"] == "eden-direct-key"
        assert creds["base_url"] == "https://api.edenai.run/v3"
        assert creds["source"] == "EDENAI_API_KEY"

    def test_custom_base_url_override(self, monkeypatch):
        monkeypatch.setenv("EDENAI_API_KEY", "eden-x")
        monkeypatch.setenv("EDENAI_BASE_URL", "https://custom.edenai.example/v3")
        creds = resolve_api_key_provider_credentials("edenai")
        assert creds["base_url"] == "https://custom.edenai.example/v3"

    def test_runtime_uses_chat_completions(self, monkeypatch):
        monkeypatch.setenv("EDENAI_API_KEY", "rt-key")
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="edenai")
        assert result["provider"] == "edenai"
        assert result["api_mode"] == "chat_completions"
        assert result["api_key"] == "rt-key"
        assert result["base_url"] == "https://api.edenai.run/v3"


# =============================================================================
# Model catalog — static fallback + live /v3/models probe
# =============================================================================


class TestEdenAIModelCatalog:
    def test_static_model_list(self):
        """A static fallback exists so the picker shows something when offline."""
        from hermes_cli.models import _PROVIDER_MODELS
        assert "edenai" in _PROVIDER_MODELS
        assert len(_PROVIDER_MODELS["edenai"]) >= 1

    def test_canonical_provider_entry(self):
        from hermes_cli.models import CANONICAL_PROVIDERS
        slugs = [p.slug for p in CANONICAL_PROVIDERS]
        assert "edenai" in slugs

    def test_label(self):
        from hermes_cli.models import _PROVIDER_LABELS
        assert _PROVIDER_LABELS["edenai"] == "Eden AI"

    def test_static_anthropic_ids_use_hyphen_form(self):
        """Eden AI's catalog stores anthropic/claude-opus-4-6 (hyphen), not the
        dot form Anthropic / OpenRouter use. The static fallback must match
        so users hit a working default if the live probe fails."""
        from hermes_cli.models import _PROVIDER_MODELS
        anthropic_picks = [m for m in _PROVIDER_MODELS["edenai"] if m.startswith("anthropic/")]
        assert anthropic_picks
        for m in anthropic_picks:
            tail = m.split("/", 1)[1]
            assert "." not in tail, f"Eden AI anthropic id must be hyphen-form: {m!r}"

    def test_fetch_edenai_models_callable(self):
        """The live-probe helper exists and returns a list of (id, desc) tuples."""
        from hermes_cli.models import fetch_edenai_models
        # Network call is OK to skip in unit tests; we only assert the
        # function is wired and returns the expected shape on cache or fallback.
        result = fetch_edenai_models()
        assert isinstance(result, list)
        if result:
            mid, desc = result[0]
            assert isinstance(mid, str) and mid
            assert isinstance(desc, str)


# =============================================================================
# Model normalisation — Eden AI uses vendor/model format, no prefix-strip
# =============================================================================


class TestEdenAINormalization:
    def test_NOT_in_matching_prefix_strip_set(self):
        """Eden AI sends ids in vendor/model form (e.g. anthropic/claude-opus-4-6).
        Stripping the 'edenai/' prefix from a user input would mangle that, so
        we deliberately keep edenai out of the prefix-strip set."""
        from hermes_cli.model_normalize import _MATCHING_PREFIX_STRIP_PROVIDERS
        assert "edenai" not in _MATCHING_PREFIX_STRIP_PROVIDERS

    def test_vendor_prefix_preserved(self):
        from hermes_cli.model_normalize import normalize_model_for_provider
        # User says "anthropic/claude-opus-4-6" + provider "edenai".
        # We must keep the vendor prefix intact — Eden AI requires it.
        assert (
            normalize_model_for_provider("anthropic/claude-opus-4-6", "edenai")
            == "anthropic/claude-opus-4-6"
        )


# =============================================================================
# URL mapping (model_metadata + trajectory_compressor)
# =============================================================================


class TestEdenAIURLMapping:
    def test_url_to_provider(self):
        from agent.model_metadata import _URL_TO_PROVIDER
        assert _URL_TO_PROVIDER.get("api.edenai.run") == "edenai"

    def test_provider_prefixes(self):
        from agent.model_metadata import _PROVIDER_PREFIXES
        assert "edenai" in _PROVIDER_PREFIXES
        assert "eden" in _PROVIDER_PREFIXES
        assert "eden-ai" in _PROVIDER_PREFIXES

    def test_trajectory_compressor_detects_edenai(self):
        import trajectory_compressor as tc
        comp = tc.TrajectoryCompressor.__new__(tc.TrajectoryCompressor)
        comp.config = types.SimpleNamespace(base_url="https://api.edenai.run/v3")
        assert comp._detect_provider() == "edenai"


# =============================================================================
# providers.py overlay — is_aggregator drives picker /models probing
# =============================================================================


class TestEdenAIProvidersModule:
    def test_overlay_exists(self):
        from hermes_cli.providers import HERMES_OVERLAYS
        assert "edenai" in HERMES_OVERLAYS
        overlay = HERMES_OVERLAYS["edenai"]
        assert overlay.transport == "openai_chat"
        assert overlay.base_url_env_var == "EDENAI_BASE_URL"

    def test_overlay_marks_aggregator(self):
        """Eden AI fronts 349 models — the picker probes /v3/models for the live catalog."""
        from hermes_cli.providers import HERMES_OVERLAYS
        assert HERMES_OVERLAYS["edenai"].is_aggregator is True


# =============================================================================
# Auxiliary client — Eden AI exposes cheap GPT-4o-mini for side tasks
# =============================================================================


class TestEdenAIAuxiliary:
    def test_aux_model_registered(self):
        """Eden AI registers an OpenAI-side cheap model for summary / vision /
        memory side tasks. Without this entry, side tasks fall back to the
        user's main model — expensive when the main is Claude Opus."""
        from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS
        assert "edenai" in _API_KEY_PROVIDER_AUX_MODELS
        assert _API_KEY_PROVIDER_AUX_MODELS["edenai"]  # non-empty
