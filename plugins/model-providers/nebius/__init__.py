"""Nebius Token Factory provider profile.

Nebius Token Factory exposes an OpenAI-compatible inference API, so it routes
through the standard ``openai_chat`` transport — no bespoke client needed.
Docs: https://docs.tokenfactory.nebius.com/quickstart
"""

from providers import register_provider
from providers.base import ProviderProfile


nebius = ProviderProfile(
    name="nebius",
    aliases=("nebius-token-factory", "token-factory", "tokenfactory", "nebius-ai-studio"),
    display_name="Nebius Token Factory",
    description="Nebius Token Factory — OpenAI-compatible API for open-weight LLMs",
    signup_url="https://tokenfactory.nebius.com/",
    env_vars=("NEBIUS_API_KEY", "NEBIUS_BASE_URL"),
    base_url="https://api.tokenfactory.nebius.com/v1",
    auth_type="api_key",
    default_aux_model="Qwen/Qwen3-30B-A3B-Instruct-2507",
    fallback_models=(
        "moonshotai/Kimi-K2.5",
        "zai-org/GLM-5",
        "deepseek-ai/DeepSeek-V3.2",
        "Qwen/Qwen3-235B-A22B-Instruct-2507",
        "openai/gpt-oss-120b",
        "MiniMaxAI/MiniMax-M2.5",
        "meta-llama/Llama-3.3-70B-Instruct",
    ),
)

register_provider(nebius)
