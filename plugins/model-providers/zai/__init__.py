"""ZAI / GLM provider profile."""

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


_BLOCKED_SYSTEM_PROMPT_PHRASE = "Hermes Agent"
_SAFE_SYSTEM_PROMPT_PHRASE = "Hermes framework"


def _sanitize_system_prompt_content(content: Any) -> tuple[Any, bool]:
    if isinstance(content, str):
        if _BLOCKED_SYSTEM_PROMPT_PHRASE not in content:
            return content, False
        return (
            content.replace(_BLOCKED_SYSTEM_PROMPT_PHRASE, _SAFE_SYSTEM_PROMPT_PHRASE),
            True,
        )

    if not isinstance(content, list):
        return content, False

    changed = False
    sanitized_parts = []
    for part in content:
        if (
            isinstance(part, dict)
            and isinstance(part.get("text"), str)
            and _BLOCKED_SYSTEM_PROMPT_PHRASE in part["text"]
        ):
            sanitized_parts.append(
                {
                    **part,
                    "text": part["text"].replace(
                        _BLOCKED_SYSTEM_PROMPT_PHRASE,
                        _SAFE_SYSTEM_PROMPT_PHRASE,
                    ),
                }
            )
            changed = True
        else:
            sanitized_parts.append(part)
    return (sanitized_parts, True) if changed else (content, False)


class ZaiProviderProfile(ProviderProfile):
    def prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Avoid Z.AI Coding Plan's prompt-sensitive 1305 false overload.

        Z.AI GLM Coding Plan rejects requests whose effective system prompt
        contains the exact phrase "Hermes Agent" with HTTP 429 / code 1305.
        Rewrite only outbound system/developer prompt copies so cached Hermes
        prompts, history, and user text remain unchanged.
        """
        sanitized_messages = None
        for index, message in enumerate(messages):
            if (
                not isinstance(message, dict)
                or message.get("role") not in {"system", "developer"}
            ):
                continue
            content, changed = _sanitize_system_prompt_content(message.get("content"))
            if not changed:
                continue
            if sanitized_messages is None:
                sanitized_messages = list(messages)
            sanitized_messages[index] = {**message, "content": content}

        return sanitized_messages if sanitized_messages is not None else messages


zai = ZaiProviderProfile(
    name="zai",
    aliases=("glm", "z-ai", "z.ai", "zhipu"),
    env_vars=("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"),
    display_name="Z.AI (GLM)",
    description="Z.AI / GLM — Zhipu AI models",
    signup_url="https://z.ai/",
    fallback_models=(
        "glm-5.2",
        "glm-5",
        "glm-4-9b",
    ),
    base_url="https://api.z.ai/api/paas/v4",
    default_aux_model="glm-4.5-flash",
)

register_provider(zai)
