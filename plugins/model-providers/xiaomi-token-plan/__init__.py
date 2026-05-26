"""Xiaomi Token Plan (Europe) provider profile.

Separate from the standard `xiaomi` profile because it hits a different
endpoint (token-plan-ams.xiaomimimo.com/v1) with a dedicated token plan.
"""

from providers import register_provider
from providers.base import ProviderProfile

xiaomi_token = ProviderProfile(
    name="xiaomi-token-plan",
    aliases=("xiaomi-token", "mimo-token", "xiaomi-token-plan-europe"),
    display_name="Xiaomi Token Plan (Europe)",
    description="Xiaomi MiMo Token Plan — Europe endpoint",
    signup_url="https://platform.xiaomimimo.com/#/docs",
    env_vars=("XIAOMI_API_KEY",),
    base_url="https://token-plan-ams.xiaomimimo.com/v1",
    auth_type="api_key",
)

register_provider(xiaomi_token)