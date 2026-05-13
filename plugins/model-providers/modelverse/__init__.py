"""ModelVerse provider profile."""

from providers import register_provider
from providers.base import ProviderProfile

modelverse = ProviderProfile(
    name="modelverse",
    aliases=("modelverse-cn",),
    env_vars=("MODELVERSE_API_KEY",),
    display_name="ModelVerse",
    description="ModelVerse — UCloud model aggregation platform",
    signup_url="https://astraflow.ucloud.cn/docs/modelverse",
    base_url="https://api.modelverse.cn/v1",
    auth_type="api_key",
)

register_provider(modelverse)
