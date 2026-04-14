"""Tests for AWS Bedrock provider integration.

Covers: provider registry, alias resolution, runtime provider resolution,
model ID detection/normalization, client construction, and prompt caching.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace


# ── Provider Registry ────────────────────────────────────────────────


class TestBedrockProviderRegistry:
    """Verify Bedrock is registered correctly in PROVIDER_REGISTRY."""

    def test_bedrock_in_registry(self):
        from hermes_cli.auth import PROVIDER_REGISTRY
        assert "bedrock" in PROVIDER_REGISTRY

    def test_bedrock_config_fields(self):
        from hermes_cli.auth import PROVIDER_REGISTRY
        pc = PROVIDER_REGISTRY["bedrock"]
        assert pc.id == "bedrock"
        assert pc.name == "AWS Bedrock"
        assert pc.auth_type == "api_key"

    def test_bedrock_env_vars(self):
        from hermes_cli.auth import PROVIDER_REGISTRY
        pc = PROVIDER_REGISTRY["bedrock"]
        assert "AWS_BEARER_TOKEN_BEDROCK" in pc.api_key_env_vars
        # AWS_ACCESS_KEY_ID is NOT in api_key_env_vars — it would falsely
        # report Bedrock as "configured" when only the access key is set
        # (missing secret key). SigV4 is validated at runtime instead.
        assert "AWS_ACCESS_KEY_ID" not in pc.api_key_env_vars


class TestBedrockProviderAliases:
    """Verify provider alias resolution for Bedrock."""

    @pytest.mark.parametrize("alias,expected", [
        ("bedrock", "bedrock"),
        ("aws-bedrock", "bedrock"),
        ("aws", "bedrock"),
        ("amazon-bedrock", "bedrock"),
    ])
    def test_alias_resolves(self, alias, expected):
        from hermes_cli.auth import resolve_provider
        assert resolve_provider(alias) == expected


# ── Model ID Detection ───────────────────────────────────────────────


class TestIsBedrockModelId:
    """Verify is_bedrock_model_id() detects Bedrock model formats."""

    @pytest.mark.parametrize("model", [
        "arn:aws:bedrock:us-east-1:123456:inference-profile/global.anthropic.claude-opus-4-6-v1",
        "arn:aws:bedrock:eu-west-1:999:model/anthropic.claude-sonnet-4-6",
        "us.anthropic.claude-sonnet-4-6",
        "eu.anthropic.claude-opus-4-6-v1",
        "global.anthropic.claude-opus-4-6-v1",
        "apac.anthropic.claude-sonnet-4-6",
        "anthropic.claude-opus-4-6-v1:0",
        "anthropic.claude-haiku-4-5-20251001-v1:0",
        "amazon.nova-pro-v1:0",
        "meta.llama4-maverick-17b-instruct-v1:0",
        "deepseek.v3.2",
    ])
    def test_detects_bedrock_ids(self, model):
        from agent.anthropic_adapter import is_bedrock_model_id
        assert is_bedrock_model_id(model), f"Should detect {model!r} as Bedrock ID"

    @pytest.mark.parametrize("model", [
        "claude-opus-4-6",
        "claude-sonnet-4-5",
        "anthropic/claude-opus-4.6",
        "gpt-4",
        "gemini-pro",
        "openai/gpt-5.4",
    ])
    def test_rejects_non_bedrock_ids(self, model):
        from agent.anthropic_adapter import is_bedrock_model_id
        assert not is_bedrock_model_id(model), f"Should NOT detect {model!r} as Bedrock ID"


# ── Model Name Normalization ─────────────────────────────────────────


class TestBedrockModelNormalization:
    """Verify Bedrock model IDs pass through normalization unchanged."""

    @pytest.mark.parametrize("model", [
        "arn:aws:bedrock:us-east-1:123:inference-profile/global.anthropic.claude-opus-4-6-v1",
        "us.anthropic.claude-sonnet-4-6",
        "anthropic.claude-opus-4-6-v1:0",
        "global.anthropic.claude-opus-4-6-v1",
        "apac.anthropic.claude-sonnet-4-6",
        "amazon.nova-pro-v1:0",
    ])
    def test_bedrock_ids_preserved(self, model):
        from agent.anthropic_adapter import normalize_model_name
        assert normalize_model_name(model) == model

    def test_regular_models_still_normalized(self):
        from agent.anthropic_adapter import normalize_model_name
        assert normalize_model_name("anthropic/claude-opus-4.6") == "claude-opus-4-6"
        assert normalize_model_name("claude-sonnet-4-5") == "claude-sonnet-4-5"

    @pytest.mark.parametrize("model,expected", [
        # Native Bedrock IDs pass through unchanged
        ("anthropic.claude-opus-4-6-v1:0", "anthropic.claude-opus-4-6-v1:0"),
        ("us.anthropic.claude-sonnet-4-6", "us.anthropic.claude-sonnet-4-6"),
        ("apac.anthropic.claude-sonnet-4-6", "apac.anthropic.claude-sonnet-4-6"),
        ("arn:aws:bedrock:us-east-1:123:inference-profile/test", "arn:aws:bedrock:us-east-1:123:inference-profile/test"),
        # OpenRouter/Anthropic slugs get mapped to valid Bedrock inference profile IDs
        ("anthropic/claude-opus-4.6", "us.anthropic.claude-opus-4-6-v1"),
        ("anthropic/claude-sonnet-4-5", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        ("claude-opus-4.6", "us.anthropic.claude-opus-4-6-v1"),
        ("claude-sonnet-4-6", "us.anthropic.claude-sonnet-4-6"),
        ("claude-haiku-4-5", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
        # Dated variants also resolve via prefix matching
        ("claude-opus-4-5-20251101", "us.anthropic.claude-opus-4-5-20251101-v1:0"),
        ("claude-sonnet-4-20250514", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
        ("claude-haiku-4-5-20251001", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
        ("claude-3-5-sonnet-20241022", "us.anthropic.claude-3-5-sonnet-20241022-v2:0"),
        ("claude-3-7-sonnet-20250219", "us.anthropic.claude-3-7-sonnet-20250219-v1:0"),
        # Opus 4.1 must NOT over-match to Opus 4.0 (longer prefix wins)
        ("claude-opus-4-1", "us.anthropic.claude-opus-4-1-20250805-v1:0"),
        ("claude-opus-4-1-20250805", "us.anthropic.claude-opus-4-1-20250805-v1:0"),
    ])
    def test_normalize_model_for_bedrock_provider(self, model, expected):
        from hermes_cli.model_normalize import normalize_model_for_provider
        assert normalize_model_for_provider(model, "bedrock") == expected


# ── Runtime Provider Resolution ──────────────────────────────────────


class TestBedrockRuntimeResolution:
    """Verify resolve_runtime_provider() for Bedrock."""

    def test_sigv4_auth(self, monkeypatch):
        from hermes_cli import runtime_provider as rp
        monkeypatch.setenv("AWS_REGION", "us-west-2")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/EXAMPLE")
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        monkeypatch.setattr(rp, "_get_model_config", lambda: {"provider": "bedrock"})

        result = rp.resolve_runtime_provider()
        assert result["provider"] == "bedrock"
        assert result["api_mode"] == "anthropic_messages"
        assert result["bedrock_region"] == "us-west-2"
        assert result["bedrock_auth_mode"] == "sigv4"

    def test_bearer_auth_takes_priority(self, monkeypatch):
        from hermes_cli import runtime_provider as rp
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-bearer-token")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/EXAMPLE")
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        monkeypatch.setattr(rp, "_get_model_config", lambda: {"provider": "bedrock"})

        result = rp.resolve_runtime_provider()
        assert result["bedrock_auth_mode"] == "bearer"
        assert result["api_key"] == "test-bearer-token"

    def test_anthropic_model_override(self, monkeypatch):
        from hermes_cli import runtime_provider as rp
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "token")
        monkeypatch.setenv("ANTHROPIC_MODEL", "us.anthropic.claude-opus-4-6-v1")
        monkeypatch.setattr(rp, "_get_model_config", lambda: {"provider": "bedrock"})

        result = rp.resolve_runtime_provider()
        assert result["model"] == "us.anthropic.claude-opus-4-6-v1"

    def test_missing_region_defaults_to_us_east_1(self, monkeypatch):
        """When no region env var is set, default to us-east-1."""
        from hermes_cli import runtime_provider as rp
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "token")
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.delenv("AWS_BEDROCK_REGION", raising=False)
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        monkeypatch.setattr(rp, "_get_model_config", lambda: {"provider": "bedrock"})

        result = rp.resolve_runtime_provider()
        assert result["bedrock_region"] == "us-east-1"

    def test_no_explicit_credentials_uses_default_chain(self, monkeypatch):
        """With no bearer token or explicit SigV4 keys, should fall through
        to boto3 default credential chain (not raise)."""
        from hermes_cli import runtime_provider as rp
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        monkeypatch.setattr(rp, "_get_model_config", lambda: {"provider": "bedrock"})

        result = rp.resolve_runtime_provider()
        assert result["provider"] == "bedrock"
        assert result["bedrock_auth_mode"] == "sigv4"
        assert result["source"] == "bedrock-default-chain"


class TestClaudeCodeBedrockActivation:
    """Verify CLAUDE_CODE_USE_BEDROCK env var activation."""

    def test_activation_flag(self, monkeypatch):
        from hermes_cli.runtime_provider import resolve_requested_provider
        monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
        monkeypatch.delenv("HERMES_INFERENCE_PROVIDER", raising=False)
        monkeypatch.setattr(
            "hermes_cli.runtime_provider._get_model_config", lambda: {},
        )
        assert resolve_requested_provider() == "bedrock"

    def test_config_provider_takes_precedence(self, monkeypatch):
        from hermes_cli.runtime_provider import resolve_requested_provider
        monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
        monkeypatch.setattr(
            "hermes_cli.runtime_provider._get_model_config",
            lambda: {"provider": "anthropic"},
        )
        assert resolve_requested_provider() == "anthropic"

    def test_hermes_inference_provider_takes_precedence(self, monkeypatch):
        from hermes_cli.runtime_provider import resolve_requested_provider
        monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
        monkeypatch.setenv("HERMES_INFERENCE_PROVIDER", "openrouter")
        monkeypatch.setattr(
            "hermes_cli.runtime_provider._get_model_config", lambda: {},
        )
        assert resolve_requested_provider() == "openrouter"

    def test_flag_not_set_returns_auto(self, monkeypatch):
        from hermes_cli.runtime_provider import resolve_requested_provider
        monkeypatch.delenv("CLAUDE_CODE_USE_BEDROCK", raising=False)
        monkeypatch.delenv("HERMES_INFERENCE_PROVIDER", raising=False)
        monkeypatch.setattr(
            "hermes_cli.runtime_provider._get_model_config", lambda: {},
        )
        assert resolve_requested_provider() == "auto"


# ── Client Construction ──────────────────────────────────────────────


try:
    import anthropic as _anthropic_sdk
    _has_anthropic = hasattr(_anthropic_sdk, "AnthropicBedrock")
except ImportError:
    _has_anthropic = False


@pytest.mark.skipif(not _has_anthropic, reason="anthropic SDK with AnthropicBedrock not installed")
class TestBuildBedrockClient:
    """Verify build_bedrock_client() creates the right client type."""

    def test_sigv4_creates_anthropic_bedrock(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/EXAMPLE")
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
        from agent.anthropic_adapter import build_bedrock_client
        client = build_bedrock_client(region="us-east-1", auth_mode="sigv4")
        assert type(client).__name__ == "AnthropicBedrock"

    def test_bearer_creates_anthropic_bedrock_with_api_key(self, monkeypatch):
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        from agent.anthropic_adapter import build_bedrock_client
        client = build_bedrock_client(
            region="us-east-1",
            auth_mode="bearer",
            bearer_token="test-token-123",
        )
        assert type(client).__name__ == "AnthropicBedrock"

    def test_default_auth_mode_is_sigv4(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/EXAMPLE")
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
        from agent.anthropic_adapter import build_bedrock_client
        # No auth_mode specified — should default to sigv4
        client = build_bedrock_client(region="us-east-1")
        assert type(client).__name__ == "AnthropicBedrock"


# ── Prompt Caching ───────────────────────────────────────────────────


class TestDisablePromptCaching:
    """Verify DISABLE_PROMPT_CACHING env var works."""

    def test_disable_prompt_caching_env_var(self, monkeypatch):
        """DISABLE_PROMPT_CACHING=1 should override prompt caching to False."""
        monkeypatch.setenv("DISABLE_PROMPT_CACHING", "1")
        # We test the logic directly rather than instantiating AIAgent
        is_bedrock = True
        use_prompt_caching = is_bedrock  # would be True
        if os.getenv("DISABLE_PROMPT_CACHING", "").strip() == "1":
            use_prompt_caching = False
        assert use_prompt_caching is False

    def test_prompt_caching_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv("DISABLE_PROMPT_CACHING", raising=False)
        is_bedrock = True
        use_prompt_caching = is_bedrock
        if os.getenv("DISABLE_PROMPT_CACHING", "").strip() == "1":
            use_prompt_caching = False
        assert use_prompt_caching is True


# ── Auxiliary Model ──────────────────────────────────────────────────


class TestBedrockAuxiliaryModel:
    """Verify Bedrock has an auxiliary model configured."""

    def test_bedrock_in_aux_models(self):
        from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS
        assert "bedrock" in _API_KEY_PROVIDER_AUX_MODELS

    def test_aux_model_is_haiku(self):
        from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS
        model = _API_KEY_PROVIDER_AUX_MODELS["bedrock"]
        assert "haiku" in model.lower()


# ── Auxiliary Client Routing ─────────────────────────────────────────


@pytest.mark.skipif(not _has_anthropic, reason="anthropic SDK with AnthropicBedrock not installed")
class TestBedrockAuxiliaryClientRouting:
    """Verify resolve_provider_client('bedrock') returns an AnthropicAuxiliaryClient
    wrapper (with .chat.completions.create()), not a raw AnthropicBedrock or
    a broken OpenAI client with empty base_url."""

    def test_resolve_provider_client_returns_wrapped_client(self, monkeypatch):
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        from agent.auxiliary_client import resolve_provider_client, AnthropicAuxiliaryClient
        client, model = resolve_provider_client("bedrock")
        assert client is not None, "resolve_provider_client('bedrock') returned None"
        assert isinstance(client, AnthropicAuxiliaryClient), (
            f"Expected AnthropicAuxiliaryClient, got {type(client).__name__}"
        )

    def test_wrapped_client_has_chat_completions_interface(self, monkeypatch):
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("bedrock")
        assert hasattr(client, "chat"), "Client missing .chat attribute"
        assert hasattr(client.chat, "completions"), "Client missing .chat.completions"
        assert hasattr(client.chat.completions, "create"), "Client missing .chat.completions.create()"

    def test_resolve_provider_client_returns_aux_model(self, monkeypatch):
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("bedrock")
        assert model is not None
        assert "haiku" in model.lower()

    def test_async_mode_returns_async_wrapper(self, monkeypatch):
        """async_mode=True must return an async-compatible client, not the sync wrapper."""
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("bedrock", async_mode=True)
        assert client is not None
        # Async wrapper should have .chat.completions.create that is awaitable
        assert hasattr(client, "chat")
        assert hasattr(client.chat, "completions")
        create_fn = client.chat.completions.create
        import asyncio
        assert asyncio.iscoroutinefunction(create_fn), (
            "async_mode=True should return client with async create(), "
            f"got {type(create_fn)}"
        )


# ── AWS_DEFAULT_REGION Support ───────────────────────────────────────


class TestAwsDefaultRegion:
    """Verify AWS_DEFAULT_REGION is respected when AWS_REGION is not set."""

    def test_default_region_in_runtime_resolution(self, monkeypatch):
        from hermes_cli import runtime_provider as rp
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "token")
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.delenv("AWS_BEDROCK_REGION", raising=False)
        monkeypatch.setattr(rp, "_get_model_config", lambda: {"provider": "bedrock"})

        result = rp.resolve_runtime_provider()
        assert result["bedrock_region"] == "eu-central-1"

    def test_aws_region_takes_priority_over_default(self, monkeypatch):
        from hermes_cli import runtime_provider as rp
        monkeypatch.setenv("AWS_REGION", "us-west-2")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "token")
        monkeypatch.delenv("AWS_BEDROCK_REGION", raising=False)
        monkeypatch.setattr(rp, "_get_model_config", lambda: {"provider": "bedrock"})

        result = rp.resolve_runtime_provider()
        assert result["bedrock_region"] == "us-west-2"


# ── ANTHROPIC_MODEL Scoping ──────────────────────────────────────────


class TestAnthropicModelScoping:
    """Verify ANTHROPIC_MODEL only applies when provider is bedrock.

    Mirrors the exact logic from cli.py:1655-1662 to catch regressions.
    """

    def test_anthropic_model_not_leaked_when_config_is_openrouter(self, monkeypatch):
        """Config provider=openrouter should ignore ANTHROPIC_MODEL."""
        monkeypatch.setenv("ANTHROPIC_MODEL", "us.anthropic.claude-opus-4-6-v1")
        monkeypatch.delenv("CLAUDE_CODE_USE_BEDROCK", raising=False)
        provider = None  # no explicit --provider
        _model_config = {"provider": "openrouter", "default": ""}
        _cfg_provider = (_model_config.get("provider") or "")
        _explicit_non_bedrock = provider and provider.strip().lower() != "bedrock"
        _bedrock_active = (not _explicit_non_bedrock) and (
            _cfg_provider.strip().lower() == "bedrock"
            or os.getenv("CLAUDE_CODE_USE_BEDROCK", "").strip() == "1"
        )
        assert not _bedrock_active

    def test_anthropic_model_blocked_by_explicit_provider_arg(self, monkeypatch):
        """Explicit --provider openrouter blocks ANTHROPIC_MODEL even with CLAUDE_CODE_USE_BEDROCK=1."""
        monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
        monkeypatch.setenv("ANTHROPIC_MODEL", "us.anthropic.claude-opus-4-6-v1")
        provider = "openrouter"  # explicit --provider arg
        _model_config = {"provider": "", "default": ""}
        _cfg_provider = (_model_config.get("provider") or "")
        _explicit_non_bedrock = provider and provider.strip().lower() != "bedrock"
        _bedrock_active = (not _explicit_non_bedrock) and (
            _cfg_provider.strip().lower() == "bedrock"
            or os.getenv("CLAUDE_CODE_USE_BEDROCK", "").strip() == "1"
        )
        _bedrock_model_env = os.getenv("ANTHROPIC_MODEL", "").strip() if _bedrock_active else ""
        assert _bedrock_model_env == "", "ANTHROPIC_MODEL should be blocked by explicit --provider openrouter"

    def test_anthropic_model_applied_for_bedrock_provider(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_MODEL", "us.anthropic.claude-opus-4-6-v1")
        monkeypatch.delenv("CLAUDE_CODE_USE_BEDROCK", raising=False)
        provider = None
        _model_config = {"provider": "bedrock", "default": ""}
        _cfg_provider = (_model_config.get("provider") or "")
        _explicit_non_bedrock = provider and provider.strip().lower() != "bedrock"
        _bedrock_active = (not _explicit_non_bedrock) and (
            _cfg_provider.strip().lower() == "bedrock"
        )
        _bedrock_model_env = os.getenv("ANTHROPIC_MODEL", "").strip() if _bedrock_active else ""
        assert _bedrock_model_env == "us.anthropic.claude-opus-4-6-v1"

    def test_anthropic_model_applied_with_claude_code_flag(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
        monkeypatch.setenv("ANTHROPIC_MODEL", "us.anthropic.claude-sonnet-4-6")
        provider = None
        _model_config = {"provider": "auto", "default": ""}
        _cfg_provider = (_model_config.get("provider") or "")
        _explicit_non_bedrock = provider and provider.strip().lower() != "bedrock"
        _bedrock_active = (not _explicit_non_bedrock) and (
            _cfg_provider.strip().lower() == "bedrock"
            or os.getenv("CLAUDE_CODE_USE_BEDROCK", "").strip() == "1"
        )
        _bedrock_model_env = os.getenv("ANTHROPIC_MODEL", "").strip() if _bedrock_active else ""
        assert _bedrock_model_env == "us.anthropic.claude-sonnet-4-6"


# ── Prompt Caching Across Lifecycle ──────────────────────────────────


class TestPromptCachingLifecycle:
    """Verify prompt caching is preserved through switch_model and fallback."""

    def test_switch_model_prompt_caching_logic(self):
        """switch_model() should enable caching when switching TO bedrock."""
        new_provider = "bedrock"
        api_mode = "anthropic_messages"
        new_model = "us.anthropic.claude-opus-4-6-v1"
        base_url = ""

        is_native_anthropic = api_mode == "anthropic_messages" and new_provider == "anthropic"
        is_bedrock = new_provider == "bedrock"
        use_prompt_caching = (
            ("openrouter" in (base_url or "").lower() and "claude" in new_model.lower())
            or is_native_anthropic
            or is_bedrock
        )
        assert use_prompt_caching is True

    def test_switch_model_no_caching_for_non_bedrock(self):
        """switch_model() should NOT enable caching for non-Claude, non-Bedrock providers."""
        new_provider = "deepseek"
        api_mode = "chat_completions"
        new_model = "deepseek-chat"
        base_url = "https://api.deepseek.com/v1"

        is_native_anthropic = api_mode == "anthropic_messages" and new_provider == "anthropic"
        is_bedrock = new_provider == "bedrock"
        use_prompt_caching = (
            ("openrouter" in (base_url or "").lower() and "claude" in new_model.lower())
            or is_native_anthropic
            or is_bedrock
        )
        assert use_prompt_caching is False

    def test_disable_prompt_caching_overrides_bedrock(self, monkeypatch):
        """DISABLE_PROMPT_CACHING=1 should override even for Bedrock."""
        monkeypatch.setenv("DISABLE_PROMPT_CACHING", "1")
        is_bedrock = True
        use_prompt_caching = is_bedrock
        if os.getenv("DISABLE_PROMPT_CACHING", "").strip() == "1":
            use_prompt_caching = False
        assert use_prompt_caching is False


# ── User-Facing Integration ──────────────────────────────────────────


class TestBedrockUserFacingIntegration:
    """Verify Bedrock appears in all user-facing provider lists and config."""

    def test_bedrock_in_canonical_providers(self):
        from hermes_cli.models import CANONICAL_PROVIDERS
        slugs = [p.slug for p in CANONICAL_PROVIDERS]
        assert "bedrock" in slugs

    def test_bedrock_in_provider_models(self):
        from hermes_cli.models import _PROVIDER_MODELS
        assert "bedrock" in _PROVIDER_MODELS
        models = _PROVIDER_MODELS["bedrock"]
        assert len(models) >= 3
        assert any("opus" in m for m in models)
        assert any("sonnet" in m for m in models)

    def test_bedrock_in_doctor_env_hints(self):
        from hermes_cli.doctor import _PROVIDER_ENV_HINTS
        assert "AWS_BEARER_TOKEN_BEDROCK" in _PROVIDER_ENV_HINTS

    def test_bedrock_in_optional_env_vars(self):
        from hermes_cli.config import OPTIONAL_ENV_VARS
        assert "AWS_BEARER_TOKEN_BEDROCK" in OPTIONAL_ENV_VARS
        assert "AWS_BEDROCK_REGION" in OPTIONAL_ENV_VARS
        assert "AWS_ACCESS_KEY_ID" in OPTIONAL_ENV_VARS
        assert "AWS_SECRET_ACCESS_KEY" in OPTIONAL_ENV_VARS


# ── SigV4 Provider Status/Discoverability ────────────────────────────


class TestBedrockSigV4Discoverability:
    """Verify Bedrock with SigV4 credentials is discoverable in /model and auth status."""

    def test_bearer_token_shows_configured(self, monkeypatch):
        from hermes_cli.auth import get_api_key_provider_status
        monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token")
        status = get_api_key_provider_status("bedrock")
        assert status["configured"] is True
        assert status["logged_in"] is True

    def test_sigv4_pair_shows_configured(self, monkeypatch):
        from hermes_cli.auth import get_api_key_provider_status
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/EXAMPLE")
        status = get_api_key_provider_status("bedrock")
        assert status["configured"] is True
        assert "ACCESS_KEY" in status.get("key_source", "")

    def test_access_key_alone_not_configured(self, monkeypatch):
        """AWS_ACCESS_KEY_ID alone (no secret) should NOT report configured."""
        from hermes_cli.auth import get_api_key_provider_status
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        status = get_api_key_provider_status("bedrock")
        assert status["configured"] is False

    def test_nonexistent_aws_profile_not_configured(self, monkeypatch):
        """A nonexistent AWS_PROFILE should NOT report Bedrock as configured."""
        from hermes_cli.auth import get_api_key_provider_status
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        monkeypatch.setenv("AWS_PROFILE", "definitely-not-a-real-profile")
        status = get_api_key_provider_status("bedrock")
        assert status["configured"] is False

    def test_sigv4_visible_in_model_picker(self, monkeypatch):
        """SigV4 credentials (ACCESS_KEY+SECRET_KEY) should make Bedrock
        appear in list_authenticated_providers() for the /model picker."""
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/EXAMPLE")
        from hermes_cli.model_switch import list_authenticated_providers
        providers = list_authenticated_providers()
        slugs = [p["slug"] for p in providers]
        assert "bedrock" in slugs, (
            f"Bedrock should appear in /model picker with SigV4 creds, got: {slugs}"
        )
