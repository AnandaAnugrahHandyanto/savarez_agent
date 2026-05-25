"""ByteDance / BytePlus / Volcengine Coding Plan provider profile.

Targets the international coding endpoint:
  - Anthropic API: https://ark.ap-southeast.bytepluses.com/api/coding
  - OpenAI API:    https://ark.ap-southeast.bytepluses.com/api/coding/v3

This profile uses the OpenAI-compatible path by default.
"""

from providers import register_provider
from providers.base import ProviderProfile

bytedance = ProviderProfile(
    name="bytedance",
    aliases=("byte-dance", "byteplus", "volcengine", "doubao"),
    display_name="ByteDance Coding Plan",
    description="ByteDance / BytePlus Coding Plan — Doubao & Seed models",
    signup_url="https://www.byteplus.com/",
    env_vars=("BYTEDANCE_API_KEY", "BYTEPLUS_API_KEY", "VOLCENGINE_API_KEY"),
    base_url="https://ark.ap-southeast.bytepluses.com/api/coding/v3",
    auth_type="api_key",
    fallback_models=(
        "bytedance-seed-code",
        "dola-seed-2.0-pro",
        "dola-seed-2.0-lite",
        "dola-seed-2.0-code",
        "glm-5.1",
        "glm-4.7",
        "gpt-oss-120b",
        "kimi-k2.5",
    ),
)

register_provider(bytedance)
