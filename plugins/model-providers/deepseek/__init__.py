"""DeepSeek provider profile.

DeepSeek V4 models support thinking mode with two independent controls:
- Thinking toggle: ``{"thinking": {"type": "enabled/disabled"}}`` in extra_body
- Effort control: ``{"reasoning_effort": "high/max"}`` as a top-level parameter

See: https://api-docs.deepseek.com/guides/thinking_mode
"""

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


class DeepSeekProfile(ProviderProfile):
    """DeepSeek — thinking toggle via extra_body + reasoning_effort as top-level."""

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, **context: Any
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Emit extra_body.thinking + top-level reasoning_effort.

        Per DeepSeek API docs:
        - Default: thinking enabled, reasoning_effort = "high"
        - Valid effort values: "high", "max"
        - low/medium → high, xhigh → max (server-side mapping, but we
          normalize here for predictability)
        - When thinking is disabled, reasoning_effort is omitted.
        """
        extra_body: dict[str, Any] = {}
        top_level: dict[str, Any] = {}

        if not reasoning_config or not isinstance(reasoning_config, dict):
            # No config → thinking enabled, default effort
            extra_body["thinking"] = {"type": "enabled"}
            top_level["reasoning_effort"] = "high"
            return extra_body, top_level

        enabled = reasoning_config.get("enabled", True)
        if enabled is False:
            extra_body["thinking"] = {"type": "disabled"}
            # No reasoning_effort when thinking is off
            return extra_body, top_level

        # Thinking enabled
        extra_body["thinking"] = {"type": "enabled"}

        effort = (reasoning_config.get("effort") or "").strip().lower()
        # DeepSeek only natively supports "high" and "max".
        # Map the OpenRouter-style effort levels for compatibility:
        #   low/medium → high
        #   high       → high
        #   xhigh      → max
        #   max        → max
        if effort in ("high", "max"):
            top_level["reasoning_effort"] = effort
        elif effort == "xhigh":
            top_level["reasoning_effort"] = "max"
        else:
            top_level["reasoning_effort"] = "high"

        return extra_body, top_level


deepseek = DeepSeekProfile(
    name="deepseek",
    aliases=("deepseek-chat",),
    env_vars=("DEEPSEEK_API_KEY",),
    display_name="DeepSeek",
    description="DeepSeek — native DeepSeek API",
    signup_url="https://platform.deepseek.com/",
    fallback_models=(
        "deepseek-chat",
        "deepseek-reasoner",
    ),
    base_url="https://api.deepseek.com/v1",
)

register_provider(deepseek)
