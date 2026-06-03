"""Xiaomi MiMo provider profile."""

import copy
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


class XiaomiProfile(ProviderProfile):
    """Xiaomi MiMo — handles API-specific quirks.

    MiMo API requires non-empty ``content`` on every assistant message,
    even those carrying only ``tool_calls`` with no natural-language body.
    Without this, replay of tool-call-only assistant turns causes
    HTTP 400 "text is not set".
    """

    def prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ensure assistant messages have non-empty content.

        MiMo API rejects messages where ``content`` is empty or missing,
        even when ``tool_calls`` are present.  Pad with a single space
        so the API accepts the request while keeping visible output
        identical.
        """
        prepared = copy.deepcopy(messages)
        for msg in prepared:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") != "assistant":
                continue
            # Skip if content is already non-empty
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                continue
            if isinstance(content, list) and content:
                continue
            # Has tool_calls but empty content — pad with space
            if msg.get("tool_calls"):
                msg["content"] = " "
        return prepared


xiaomi = XiaomiProfile(
    name="xiaomi",
    aliases=("mimo", "xiaomi-mimo"),
    env_vars=("XIAOMI_API_KEY",),
    base_url="https://api.xiaomimimo.com/v1",
    supports_health_check=False,  # /v1/models returns 401 even with valid key
)

register_provider(xiaomi)
