"""Cerebras Inference provider profile."""

from providers import register_provider
from providers.base import ProviderProfile

cerebras = ProviderProfile(
    name="cerebras",
    env_vars=("CEREBRAS_API_KEY", "CEREBRAS_BASE_URL"),
    display_name="Cerebras",
    description="Cerebras — ultra-fast wafer-scale inference (OpenAI-compatible)",
    signup_url="https://cloud.cerebras.ai/",
    base_url="https://api.cerebras.ai/v1",
    auth_type="api_key",
    default_aux_model="llama-3.3-70b",
    fallback_models=(
        "gpt-oss-120b",
        "llama-3.3-70b",
        "llama-4-maverick-17b-128e-instruct",
        "llama-4-scout-17b-16e-instruct",
    ),
)

register_provider(cerebras)
