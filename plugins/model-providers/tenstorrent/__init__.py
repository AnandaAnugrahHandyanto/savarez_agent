"""Tenstorrent AI provider profile."""

from providers import register_provider
from providers.base import ProviderProfile


tenstorrent = ProviderProfile(
    name="tenstorrent",
    aliases=("tt", "tt-ai", "tenstorrent-ai"),
    env_vars=("TENSTORRENT_API_KEY", "TENSTORRENT_BASE_URL"),
    display_name="Tenstorrent AI",
    description="Tenstorrent AI — OpenAI-compatible chat and text API",
    signup_url="https://console.tenstorrent.com/",
    base_url="https://console.tenstorrent.com/v1",
    default_aux_model="Qwen/Qwen3-32B",
    fallback_models=(
        "deepseek-ai/DeepSeek-R1-0528",
        "Qwen/Qwen3-32B",
        "Qwen/Qwen3-VL-32B-Instruct",
    ),
)

register_provider(tenstorrent)
