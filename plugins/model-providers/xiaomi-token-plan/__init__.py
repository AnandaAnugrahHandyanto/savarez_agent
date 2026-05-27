"""Xiaomi Token Plan provider profile.

Region-neutral: defaults to the Singapore endpoint. Users on other regions
can override via the XIAOMI_TOKEN_BASE_URL env var:

  Europe (Amsterdam): https://token-plan-ams.xiaomimimo.com/v1
  Singapore:          https://token-plan-sgp.xiaomimimo.com/v1
  China:              https://token-plan-cn.xiaomimimo.com/v1
"""

from providers import register_provider
from providers.base import ProviderProfile

xiaomi_token = ProviderProfile(
    name="xiaomi-token-plan",
    aliases=("xiaomi-token", "mimo-token"),
    display_name="Xiaomi Mimo Token Plan",
    description="Xiaomi Mimo Token Plan — region-selectable via XIAOMI_TOKEN_BASE_URL",
    signup_url="https://platform.xiaomimimo.com/#/docs",
    env_vars=("XIAOMI_API_KEY",),
    base_url="https://token-plan-sgp.xiaomimimo.com/v1",
    auth_type="api_key",
    supports_health_check=False,  # /v1/models returns 401 even with valid key
)

register_provider(xiaomi_token)