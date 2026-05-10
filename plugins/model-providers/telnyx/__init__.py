"""Telnyx AI provider profile."""

from hermes_cli import __version__ as _HERMES_VERSION
from providers import register_provider
from providers.base import ProviderProfile

TELNYX_BASE_URL = "https://api.telnyx.com/v2/ai"
TELNYX_DEFAULT_AUX_MODEL = "openai/gpt-4o-mini"

# Snapshot of the Telnyx-hosted text model catalog used as a picker fallback
# when the live /models endpoint is unavailable.  Keep slash-form model IDs:
# Telnyx's OpenAI-compatible API expects these IDs directly.
TELNYX_FALLBACK_MODELS = (
    "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "openai/gpt-5.2",
    "openai/gpt-5.1",
    "openai/gpt-5",
    "openai/gpt-4.1",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "anthropic/claude-opus-4-6",
    "anthropic/claude-haiku-4-5",
    "google/gemini-2.5-flash",
    "moonshotai/Kimi-K2.6",
    "moonshotai/Kimi-K2.5",
    "MiniMaxAI/MiniMax-M2.7",
    "zai-org/GLM-5.1-FP8",
    "Qwen/Qwen3-235B-A22B",
    "Groq/gpt-oss-120b",
    "meta-llama/Llama-3.3-70B-Instruct",
    "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "google/gemma-2b-it",
)


telnyx = ProviderProfile(
    name="telnyx",
    aliases=("telnyx-ai", "telnyx-intelligence"),
    display_name="Telnyx AI",
    description="Telnyx AI — direct OpenAI-compatible chat completions",
    signup_url="https://portal.telnyx.com/#/app/api-keys",
    env_vars=("TELNYX_API_KEY", "TELNYX_BASE_URL"),
    base_url=TELNYX_BASE_URL,
    auth_type="api_key",
    # Attribution so Telnyx can identify Hermes Agent traffic while the generic
    # OpenAI-compatible runtime path stays provider-agnostic.
    default_headers={"User-Agent": f"HermesAgent/{_HERMES_VERSION}"},
    default_aux_model=TELNYX_DEFAULT_AUX_MODEL,
    fallback_models=TELNYX_FALLBACK_MODELS,
)

register_provider(telnyx)
