"""Skills Hub: tool-level guardrails for skill execution.

Two core functions:
1. **Runtime escalation / downgrade** — dynamically adjust model routing based on
   runtime conditions (tool chain depth, planning needs, decision complexity).
2. **Tool guard** — block high-cost tools (delegate_task, browser, etc.) on simple
   routes to prevent flash models from triggering expensive operations.

Integrated into AIAgent's tool-call dispatch. Depends on Brain's route
classification for simple/complex determination. Fails silent: if Brain is
disabled or classification is unavailable, all tools pass through.
"""

from .config import SkillsHubConfig
from .guard import (
    SkillsHubGuard,
    EscalationDecision,
)

__all__ = [
    "SkillsHubConfig",
    "SkillsHubGuard",
    "EscalationDecision",
]
