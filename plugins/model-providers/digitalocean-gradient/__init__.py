"""DigitalOcean Gradient serverless inference (OpenAI-compatible) profile."""

from providers import register_provider
from providers.base import ProviderProfile


digitalocean_gradient = ProviderProfile(
    name="digitalocean-gradient",
    aliases=("do-gradient", "digitalocean"),
    display_name="DigitalOcean Gradient",
    description=(
        "DigitalOcean Inference — serverless chat via OpenAI-compatible "
        "https://inference.do-ai.run (model access key or PAT as Bearer)"
    ),
    signup_url=(
        "https://docs.digitalocean.com/products/inference/how-to/manage-model-access-keys/"
    ),
    env_vars=("DIGITALOCEAN_GRADIENT_API_KEY", "DIGITALOCEAN_GRADIENT_BASE_URL"),
    base_url="https://inference.do-ai.run/v1",
    auth_type="api_key",
    default_aux_model="anthropic-claude-4.6-sonnet",
    fallback_models=(
        "anthropic-claude-4.6-sonnet",
        "kimi-k2.6",
        "deepseek-v4-pro",
        "qwen3-coder-flash",
        "alibaba-qwen3-32b",
    ),
)

register_provider(digitalocean_gradient)
