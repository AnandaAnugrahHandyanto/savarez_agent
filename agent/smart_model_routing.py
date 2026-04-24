"""Heuristics for routing obviously simple turns to a cheap model.

This module intentionally stays tiny: it only decides when a message is simple
enough that a low-cost route should be used instead of the main model.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

_DEEP_THOUGHT_KEYWORDS = {
    "should",
    "why",
    "whether",
    "advice",
    "recommend",
    "opinion",
    "think",
    "feel",
    "feeling",
    "worried",
    "concerned",
    "lately",
    "seems",
    "maybe",
    "perhaps",
    "decide",
    "decision",
}

_DEEP_THOUGHT_PHRASES = (
    "do you think",
    "what do you think",
    "should i",
    "should we",
    "why is",
    "why has",
    "help me decide",
)


def choose_cheap_model_route(
    user_message: str,
    routing_config: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return a cheap-model route for clearly simple turns.

    Returns ``None`` for anything that looks like a judgment call, advice,
    or deeper reflective question.
    """
    if not routing_config or not routing_config.get("enabled", False):
        return None

    cheap_model = routing_config.get("cheap_model") or {}
    provider = (cheap_model.get("provider") or "").strip()
    model = (cheap_model.get("model") or "").strip()
    if not provider or not model:
        return None

    text = (user_message or "").strip()
    if not text:
        return None

    max_simple_chars = int(routing_config.get("max_simple_chars", 160) or 160)
    max_simple_words = int(routing_config.get("max_simple_words", 28) or 28)
    lowered = text.lower()

    if any(phrase in lowered for phrase in _DEEP_THOUGHT_PHRASES):
        return None

    words = {
        token.strip(".,:;!?()[]{}\"'`")
        for token in lowered.split()
        if token.strip(".,:;!?()[]{}\"'`")
    }
    if words & _DEEP_THOUGHT_KEYWORDS:
        return None

    if len(text) > max_simple_chars or len(words) > max_simple_words:
        return None

    route = dict(cheap_model)
    route["routing_reason"] = "simple_turn"
    route["provider"] = provider
    route["model"] = model
    return route
