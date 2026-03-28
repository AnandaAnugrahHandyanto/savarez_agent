"""Shared constants for Hermes Agent.

Import-safe module with no dependencies — can be imported from anywhere
without risk of circular imports.
"""

import contextvars
import os
from pathlib import Path

# Per-task override for named agents. When set, get_hermes_home() returns
# this value instead of the process-global HERMES_HOME env var.
# The gateway sets this via _hermes_home_override.set(agent_dir) before
# processing a message, so every downstream call automatically resolves
# to the agent's own directory — no parameter threading needed.
_hermes_home_override: contextvars.ContextVar["Path | None"] = contextvars.ContextVar(
    "_hermes_home_override", default=None
)


def get_hermes_home() -> Path:
    """Return the Hermes home directory (default: ~/.hermes).

    Checks the per-task contextvar override first (set by the gateway for
    named agents), then HERMES_HOME env var, then falls back to ~/.hermes.
    This is the single source of truth — all other copies should import this.
    """
    override = _hermes_home_override.get()
    if override is not None:
        return override
    return Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))


VALID_REASONING_EFFORTS = ("xhigh", "high", "medium", "low", "minimal")


def parse_reasoning_effort(effort: str) -> dict | None:
    """Parse a reasoning effort level into a config dict.

    Valid levels: "xhigh", "high", "medium", "low", "minimal", "none".
    Returns None when the input is empty or unrecognized (caller uses default).
    Returns {"enabled": False} for "none".
    Returns {"enabled": True, "effort": <level>} for valid effort levels.
    """
    if not effort or not effort.strip():
        return None
    effort = effort.strip().lower()
    if effort == "none":
        return {"enabled": False}
    if effort in VALID_REASONING_EFFORTS:
        return {"enabled": True, "effort": effort}
    return None


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS_URL = f"{OPENROUTER_BASE_URL}/models"
OPENROUTER_CHAT_URL = f"{OPENROUTER_BASE_URL}/chat/completions"

AI_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"
AI_GATEWAY_MODELS_URL = f"{AI_GATEWAY_BASE_URL}/models"
AI_GATEWAY_CHAT_URL = f"{AI_GATEWAY_BASE_URL}/chat/completions"

NOUS_API_BASE_URL = "https://inference-api.nousresearch.com/v1"
NOUS_API_CHAT_URL = f"{NOUS_API_BASE_URL}/chat/completions"
