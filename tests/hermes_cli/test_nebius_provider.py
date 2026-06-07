"""Focused tests for the Nebius Token Factory provider.

Covers registry wiring (auth, model listing, identity layer, hostname/prefix
normalization) and — the piece earlier attempts missed — per-model reasoning
emission on the profile transport path.
"""

from __future__ import annotations

import pytest


# ── Profile + registry wiring ────────────────────────────────────────────────


def test_nebius_profile_loads():
    from providers import get_provider_profile

    p = get_provider_profile("nebius")
    assert p is not None
    assert p.name == "nebius"
    assert p.display_name == "Nebius Token Factory"
    assert p.base_url == "https://api.tokenfactory.nebius.com/v1"
    assert p.get_hostname() == "api.tokenfactory.nebius.com"
    assert p.auth_type == "api_key"
    assert p.env_vars[0] == "NEBIUS_API_KEY"
    assert "NEBIUS_TOKEN_FACTORY_API_KEY" in p.env_vars
    assert p.default_aux_model == "Qwen/Qwen3-30B-A3B-Instruct-2507"
    assert len(p.fallback_models) >= 5


@pytest.mark.parametrize(
    "alias",
    ["nebius-token-factory", "nebius-tokenfactory", "nebius-tf", "nebius-ai",
     "tokenfactory", "token-factory"],
)
def test_nebius_aliases_resolve_in_registry(alias):
    from providers import get_provider_profile

    prof = get_provider_profile(alias)
    assert prof is not None and prof.name == "nebius"


def test_nebius_auth_registry_autowires(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "nebius-secret")
    monkeypatch.setenv("NEBIUS_BASE_URL", "https://custom.nebius.example/v1")
    from hermes_cli.auth import (
        PROVIDER_REGISTRY,
        resolve_api_key_provider_credentials,
        resolve_provider,
    )

    cfg = PROVIDER_REGISTRY["nebius"]
    assert cfg.auth_type == "api_key"
    assert cfg.inference_base_url == "https://api.tokenfactory.nebius.com/v1"
    # The *_BASE_URL env var must be split out of the api-key vars.
    assert "NEBIUS_API_KEY" in cfg.api_key_env_vars
    assert "NEBIUS_BASE_URL" not in cfg.api_key_env_vars
    assert cfg.base_url_env_var == "NEBIUS_BASE_URL"

    # Aliases are registered in the auth registry too.
    assert resolve_provider("tokenfactory") == "nebius"

    creds = resolve_api_key_provider_credentials("nebius")
    assert creds["api_key"] == "nebius-secret"
    assert creds["base_url"] == "https://custom.nebius.example/v1"


def test_nebius_canonical_provider_and_label():
    from hermes_cli.models import CANONICAL_PROVIDERS, _PROVIDER_LABELS, normalize_provider

    assert "nebius" in {p.slug for p in CANONICAL_PROVIDERS}
    assert _PROVIDER_LABELS["nebius"] == "Nebius Token Factory"
    assert normalize_provider("token-factory") == "nebius"


def test_nebius_identity_layer():
    from hermes_cli.providers import (
        HERMES_OVERLAYS,
        determine_api_mode,
        get_label,
        get_provider,
        is_aggregator,
        normalize_provider,
    )

    assert HERMES_OVERLAYS["nebius"].base_url_override == "https://api.tokenfactory.nebius.com/v1"
    assert normalize_provider("nebius-tf") == "nebius"
    assert get_label("nebius") == "Nebius Token Factory"
    assert is_aggregator("nebius") is True
    nebius_def = get_provider("nebius")
    assert nebius_def is not None
    assert nebius_def.base_url == "https://api.tokenfactory.nebius.com/v1"
    assert determine_api_mode("nebius", "https://api.tokenfactory.nebius.com/v1") == "chat_completions"


def test_nebius_hostname_inference():
    from agent.model_metadata import _infer_provider_from_url

    assert _infer_provider_from_url("https://api.tokenfactory.nebius.com/v1") == "nebius"


# ── Model listing: live fetch preferred, fallback otherwise ──────────────────


def test_nebius_model_ids_prefer_live_fetch(monkeypatch):
    from providers import get_provider_profile
    from hermes_cli import models as models_mod

    profile = get_provider_profile("nebius")
    assert profile is not None
    monkeypatch.setattr(
        "hermes_cli.auth.resolve_api_key_provider_credentials",
        lambda pid: {"provider": pid, "api_key": "k",
                     "base_url": "https://api.tokenfactory.nebius.com/v1"},
    )
    monkeypatch.setattr(
        profile, "fetch_models",
        lambda *, api_key=None, timeout=8.0: ["Qwen/Qwen3-235B-A22B-Instruct-2507"],
    )
    assert models_mod.provider_model_ids("nebius") == ["Qwen/Qwen3-235B-A22B-Instruct-2507"]


def test_nebius_model_ids_fall_back_to_profile(monkeypatch):
    from providers import get_provider_profile
    from hermes_cli import models as models_mod

    profile = get_provider_profile("nebius")
    assert profile is not None
    monkeypatch.setattr(
        "hermes_cli.auth.resolve_api_key_provider_credentials",
        lambda pid: {"provider": pid, "api_key": "k",
                     "base_url": "https://api.tokenfactory.nebius.com/v1"},
    )
    monkeypatch.setattr(profile, "fetch_models", lambda *, api_key=None, timeout=8.0: None)
    assert models_mod.provider_model_ids("nebius") == list(profile.fallback_models)


# ── Case-sensitive model-id normalization ────────────────────────────────────


def test_nebius_model_normalize_preserves_case_and_strips_prefix():
    from hermes_cli.model_normalize import normalize_model_for_provider

    # Accidental provider prefix is repaired...
    assert (
        normalize_model_for_provider("nebius/Qwen/Qwen3-235B-A22B-Instruct-2507", "nebius")
        == "Qwen/Qwen3-235B-A22B-Instruct-2507"
    )
    # ...but the native vendor/model id is preserved verbatim (NOT lowercased).
    assert (
        normalize_model_for_provider("deepseek-ai/DeepSeek-V3.2", "nebius")
        == "deepseek-ai/DeepSeek-V3.2"
    )


# ── Reasoning emission on the profile path (the key differentiator) ──────────


def _extra_body(model, reasoning_config=None):
    from providers import get_provider_profile

    profile = get_provider_profile("nebius")
    assert profile is not None
    extra_body, top_level = profile.build_api_kwargs_extras(
        reasoning_config=reasoning_config, supports_reasoning=True, model=model,
    )
    return extra_body, top_level


# Real reasoning models from the live catalog (verified 2026-06-03).
@pytest.mark.parametrize(
    "model",
    [
        "Qwen/Qwen3-235B-A22B-Thinking-2507-fast",
        "Qwen/Qwen3-Next-80B-A3B-Thinking",
        "deepseek-ai/DeepSeek-V4-Pro",
        "openai/gpt-oss-120b",
        "NousResearch/Hermes-4-405B",
        "MiniMaxAI/MiniMax-M2.5",
        "PrimeIntellect/INTELLECT-3",
        "nvidia/Cosmos3-Super-Reasoner",
        "gpt-oss-120b",  # bare id (no vendor prefix) — exercises the no-slash branch
    ],
)
def test_reasoning_models_emit_reasoning(model):
    extra_body, _ = _extra_body(model)
    assert "reasoning" in extra_body, f"{model} should emit reasoning extra_body"


# Real chat/vision models from the live catalog that must NOT get reasoning.
@pytest.mark.parametrize(
    "model",
    [
        "Qwen/Qwen3-235B-A22B-Instruct-2507",
        "deepseek-ai/DeepSeek-V3.2",
        "meta-llama/Llama-3.3-70B-Instruct",
        "zai-org/GLM-5",
        "moonshotai/Kimi-K2.6",
        "google/gemma-3-27b-it",
        "Qwen/Qwen2.5-VL-72B-Instruct",
        "Llama-3.3-70B-Instruct",  # bare id (no vendor prefix)
    ],
)
def test_non_reasoning_models_emit_nothing(model):
    extra_body, top_level = _extra_body(model)
    assert extra_body == {} and top_level == {}, f"{model} must not emit reasoning"


def test_reasoning_respects_explicit_disable():
    extra_body, _ = _extra_body(
        "Qwen/Qwen3-235B-A22B-Thinking-2507", reasoning_config={"enabled": False},
    )
    assert extra_body == {}


def test_reasoning_forwards_caller_config():
    extra_body, _ = _extra_body(
        "openai/gpt-oss-120b", reasoning_config={"enabled": True, "effort": "high"},
    )
    assert extra_body["reasoning"] == {"enabled": True, "effort": "high"}


# ── End-to-end through the real transport (profile -> api_kwargs) ─────────────
# Proves the reasoning emission isn't just returned by the hook but actually
# lands in the request kwargs via ChatCompletionsTransport's profile path.


def _build_kwargs(model, reasoning_config):
    from agent.transports.chat_completions import ChatCompletionsTransport
    from providers import get_provider_profile

    profile = get_provider_profile("nebius")
    assert profile is not None
    return ChatCompletionsTransport().build_kwargs(
        model=model,
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
        provider_profile=profile,
        reasoning_config=reasoning_config,
    )


def test_transport_emits_reasoning_for_reasoning_model():
    kw = _build_kwargs("openai/gpt-oss-120b", {"enabled": True, "effort": "high"})
    assert kw.get("extra_body", {}).get("reasoning") == {"enabled": True, "effort": "high"}


def test_transport_omits_reasoning_for_chat_model():
    kw = _build_kwargs("meta-llama/Llama-3.3-70B-Instruct", {"enabled": True, "effort": "high"})
    assert "reasoning" not in kw.get("extra_body", {})
