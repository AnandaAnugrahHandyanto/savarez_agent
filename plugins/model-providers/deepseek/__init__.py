"""DeepSeek provider profile."""

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


class DeepSeekProfile(ProviderProfile):
    """DeepSeek native API — V4 thinking + reasoning_effort plumbing.

    Reference: https://api-docs.deepseek.com/guides/thinking_mode

    The V4 API exposes thinking mode as an explicit request contract:
      - ``extra_body.thinking = {"type": "enabled" | "disabled"}``
        (default: ``enabled``)
      - top-level ``reasoning_effort = "high" | "max"``
        (DeepSeek accepts only those two values; ``low`` / ``medium``
        compatibility-map to ``"high"``, ``xhigh`` maps to ``"max"``)

    Without this override the registered profile inherits the no-op
    default and ``reasoning_effort`` is silently dropped before the
    request leaves Hermes.
    """

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        **context: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        extra_body: dict[str, Any] = {}
        top_level: dict[str, Any] = {}

        # No reasoning_config supplied → server defaults (thinking enabled,
        # effort=high). Be explicit so the payload is self-describing in logs.
        if not reasoning_config or not isinstance(reasoning_config, dict):
            extra_body["thinking"] = {"type": "enabled"}
            top_level["reasoning_effort"] = "high"
            return extra_body, top_level

        if reasoning_config.get("enabled") is False:
            extra_body["thinking"] = {"type": "disabled"}
            # Per DeepSeek docs reasoning_effort is meaningless when
            # thinking is off — omit entirely (mirrors KimiProfile).
            return extra_body, top_level

        extra_body["thinking"] = {"type": "enabled"}
        effort = (reasoning_config.get("effort") or "").strip().lower()
        if effort in ("max", "xhigh"):
            top_level["reasoning_effort"] = "max"
        else:
            # low / medium / high / unknown → "high" (DeepSeek's documented
            # compatibility mapping for clients that still emit the wider
            # OpenAI-style vocabulary).
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
        "deepseek-v4-pro",
        "deepseek-v4-flash",
        # Legacy aliases — server-side mapped to deepseek-v4-flash
        # non-thinking / thinking modes, retained until DeepSeek removes them.
        "deepseek-chat",
        "deepseek-reasoner",
    ),
    base_url="https://api.deepseek.com/v1",
)

register_provider(deepseek)
