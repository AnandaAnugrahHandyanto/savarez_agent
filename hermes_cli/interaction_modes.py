"""Interaction mode prompts for Hermes slash commands.

Modes are lightweight, per-session behavioral overlays. They are injected as
turn-local instructions rather than persisted as user text.
"""

from __future__ import annotations

VALID_INTERACTION_MODES = frozenset({"9010", "transparency"})

MODE_LABELS = {
    "9010": "90/10 autonomous mode",
    "transparency": "transparency mode",
}

MODE_PROMPTS = {
    "9010": (
        "[Active mode: 90/10 autonomous. Proceed end-to-end toward completing "
        "the user's task. Use tools proactively, inspect/modify/test/verify as "
        "needed, and do not stop at a plan when execution is possible. Ask the user "
        "only when their 10% effort would save roughly 90% of the work, when there "
        "is a meaningful product/safety fork, or when credentials/payment/destructive "
        "approval is required. Keep final updates concise: changed, verified, risks.]"
    ),
    "transparency": (
        "[Active mode: transparency. Optimize for shared diagnosis, root-cause "
        "clarity, and reversible investigation. Prefer planning, hypotheses, evidence, "
        "and read-only inspection. Do not jump ahead into build/fix/execute steps or "
        "make material changes until Shawn explicitly approves. Clearly separate what "
        "is known, suspected, and the next diagnostic options.]"
    ),
}


def normalize_mode(name: str | None) -> str | None:
    """Return the canonical mode name, or None for normal/empty."""
    if not name:
        return None
    value = str(name).strip().lower().lstrip("/")
    if value in ("normal", "default", "off", "clear", "none"):
        return None
    if value in VALID_INTERACTION_MODES:
        return value
    return None


def mode_prompt(name: str | None) -> str:
    """Return the turn-local prompt for a mode, or an empty string."""
    mode = normalize_mode(name)
    return MODE_PROMPTS.get(mode or "", "")


def mode_label(name: str | None) -> str:
    """Return a user-facing label for a mode."""
    mode = normalize_mode(name)
    if not mode:
        return "normal mode"
    return MODE_LABELS.get(mode, mode)
