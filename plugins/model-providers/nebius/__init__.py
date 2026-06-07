"""Nebius Token Factory provider profile.

Nebius Token Factory (https://tokenfactory.nebius.com) is an OpenAI-compatible
inference endpoint serving open-weight models (Qwen, DeepSeek, GLM, Kimi, Llama,
Gemma, Hermes, gpt-oss, Nemotron, MiniMax, and more) behind a single API key.
The live ``/v1/models`` catalog is authoritative and changes regularly, so
``provider_model_ids()`` fetches it live (``fetch_models``); the
``fallback_models`` tuple below is the curated offline subset shown in the
picker when no key/network is available — tool-calling-capable models only.
The fallback + reasoning markers were verified against the live catalog
(``GET https://api.tokenfactory.nebius.com/v1/models``) on 2026-06-03.

Reasoning support
-----------------
Several Nebius models are reasoning/thinking models (Qwen3 ``*-Thinking``,
DeepSeek-V4/R*, Hermes-4, gpt-oss, MiniMax-M2, INTELLECT-3, Cosmos-Reasoner).
Hermes routes a *registered profile* through the profile transport path
(``ChatCompletionsTransport._build_kwargs_from_profile``), which emits reasoning
**only** via ``build_api_kwargs_extras`` / ``build_extra_body``. The automatic
``extra_body["reasoning"]`` fallback in the legacy ``build_kwargs`` path does
**not** run for profiles. So a bare ``ProviderProfile`` sends no reasoning
params — reasoning models then spend their output budget on hidden thinking
tokens and truncate tool calls (``finish_reason="length"``).

We therefore emit ``extra_body.reasoning`` here, scoped to reasoning-capable
model families, so reasoning works on the plugin path. Non-reasoning models get
nothing and are unaffected. (Registering Nebius as a bare ``ProviderProfile``
without this hook is why reasoning models truncated in earlier attempts.)
"""

from __future__ import annotations

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

# Reasoning-capable model-family markers, matched case-insensitively against the
# bare model id (vendor prefix stripped). Only models matching one of these
# receive ``extra_body.reasoning``. Verified against the live /v1/models catalog
# (2026-06-03): catches Qwen3-*-Thinking, DeepSeek-V4-Pro, Hermes-4-*, gpt-oss-*,
# MiniMax-M2.5, INTELLECT-3 and Cosmos3-Super-Reasoner while leaving Instruct /
# chat / vision / embedding models (DeepSeek-V3.2, Qwen3-*-Instruct, GLM-5,
# Kimi-K2.5/2.6, Llama-3.3, gemma-3, *-VL, *-Embedding) untouched.
# A false negative just reverts to plain chat (no worse than today); a false
# positive sends a field Nebius's OpenAI-compatible endpoint ignores.
_REASONING_MARKERS: tuple[str, ...] = (
    "thinking",      # Qwen/Qwen3-*-Thinking-*
    "reasoner",      # nvidia/Cosmos3-Super-Reasoner
    "gpt-oss",       # openai/gpt-oss-*
    "hermes-4",      # NousResearch/Hermes-4-* (hybrid reasoning)
    "minimax-m2",    # MiniMaxAI/MiniMax-M2.*
    "intellect-3",   # PrimeIntellect/INTELLECT-3
    "deepseek-v4",   # deepseek-ai/DeepSeek-V4-* (V4 thinks; V3.x excluded)
    "deepseek-r",    # deepseek-ai/DeepSeek-R* (R1-style reasoners)
)


def _is_reasoning_model(model: str | None) -> bool:
    """True when *model* is a Nebius reasoning/thinking family member."""
    m = (model or "").strip().lower()
    if not m:
        return False
    bare = m.split("/", 1)[1] if "/" in m else m
    return any(marker in bare for marker in _REASONING_MARKERS)


class NebiusProfile(ProviderProfile):
    """Nebius Token Factory — OpenAI-compatible, per-model reasoning.

    The reasoning emission lives in ``build_api_kwargs_extras`` because the
    profile transport path does not auto-emit reasoning (see module docstring).
    """

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        model: str | None = None,
        **context: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        # Only reasoning-capable families get reasoning extra_body.
        if not _is_reasoning_model(model):
            return {}, {}
        # Honour an explicit disable; otherwise forward the caller's reasoning
        # config (or a sane default) as OpenAI-style unified reasoning, which
        # Nebius's endpoint accepts.
        if isinstance(reasoning_config, dict):
            if reasoning_config.get("enabled") is False:
                return {}, {}
            return {"reasoning": dict(reasoning_config)}, {}
        return {"reasoning": {"enabled": True, "effort": "medium"}}, {}


nebius = NebiusProfile(
    name="nebius",
    aliases=(
        "nebius-token-factory",
        "nebius-tokenfactory",
        "nebius-tf",
        "nebius-ai",
        "tokenfactory",
        "token-factory",
    ),
    display_name="Nebius Token Factory",
    description="Nebius Token Factory — open-weight models via one OpenAI-compatible endpoint",
    signup_url="https://studio.nebius.com/",
    # NEBIUS_API_KEY is canonical; NEBIUS_TOKEN_FACTORY_API_KEY is accepted as an
    # alternative; NEBIUS_BASE_URL overrides the endpoint (e.g. region pinning).
    env_vars=("NEBIUS_API_KEY", "NEBIUS_TOKEN_FACTORY_API_KEY", "NEBIUS_BASE_URL"),
    base_url="https://api.tokenfactory.nebius.com/v1",
    auth_type="api_key",
    # Cheap, reliable, in-catalog model for auxiliary tasks (compression, etc.).
    default_aux_model="Qwen/Qwen3-30B-A3B-Instruct-2507",
    # Curated tool-calling subset for offline/no-key display, verified present in
    # the live catalog on 2026-06-03. The live fetch is authoritative and
    # overrides this whenever a key is set; embedding/vision/`-fast` variants are
    # omitted here but still surface via the live catalog.
    fallback_models=(
        "Qwen/Qwen3.5-397B-A17B",
        "Qwen/Qwen3-235B-A22B-Instruct-2507",
        "Qwen/Qwen3-235B-A22B-Thinking-2507-fast",
        "Qwen/Qwen3-Next-80B-A3B-Thinking",
        "Qwen/Qwen3-30B-A3B-Instruct-2507",
        "Qwen/Qwen3-32B",
        "deepseek-ai/DeepSeek-V3.2",
        "deepseek-ai/DeepSeek-V4-Pro",
        "moonshotai/Kimi-K2.6",
        "moonshotai/Kimi-K2.5",
        "zai-org/GLM-5.1",
        "zai-org/GLM-5",
        "MiniMaxAI/MiniMax-M2.5",
        "NousResearch/Hermes-4-405B",
        "NousResearch/Hermes-4-70B",
        "openai/gpt-oss-120b",
        "PrimeIntellect/INTELLECT-3",
        "nvidia/nemotron-3-super-120b-a12b",
        "nvidia/Llama-3_1-Nemotron-Ultra-253B-v1",
        "meta-llama/Llama-3.3-70B-Instruct",
        "google/gemma-3-27b-it",
    ),
)

register_provider(nebius)
