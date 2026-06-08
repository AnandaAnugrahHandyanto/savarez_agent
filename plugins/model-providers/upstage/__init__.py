"""Upstage Solar provider profile.

Upstage exposes its Solar family (Solar Pro 3, Solar Pro 2, Solar Mini) behind
an OpenAI-compatible chat-completions endpoint at ``https://api.upstage.ai/v1``,
so no custom transport is needed — this is a plain api-key profile and the
generic ``chat_completions`` path handles it. The Solar Pro models are
tool-calling/agentic and are the only ones surfaced in ``fallback_models``
(used when the live ``/v1/models`` catalog fetch is unavailable).

Reasoning: Solar Pro 2/3 accept an optional top-level ``reasoning_effort`` and
default to non-reasoning when it is omitted — unlike DeepSeek/Kimi, the endpoint
does not require echoing ``reasoning_content`` back on subsequent turns, so the
generic wire format is safe and no ``build_api_kwargs_extras`` override is
needed here.
"""

from providers import register_provider
from providers.base import ProviderProfile

upstage = ProviderProfile(
    name="upstage",
    aliases=("solar",),
    display_name="Upstage Solar",
    description="Upstage Solar — Korean-built Solar models (OpenAI-compatible API)",
    signup_url="https://console.upstage.ai/api-keys",
    # UPSTAGE_BASE_URL lets self-hosted / regional deployments override the host.
    env_vars=("UPSTAGE_API_KEY", "UPSTAGE_BASE_URL"),
    base_url="https://api.upstage.ai/v1",
    auth_type="api_key",
    # Solar Mini is the cheap/fast model — used for compression, vision
    # summaries, and other auxiliary side tasks.
    default_aux_model="solar-mini",
    fallback_models=(
        "solar-pro3",
        "solar-pro2",
        "solar-mini",
    ),
)

register_provider(upstage)
