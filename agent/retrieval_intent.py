"""Intent inference and 6-dim scoring for retrieval reranking.

Borrowed from holaOS's memory-retrieval-intent.ts and memory-reranker.ts
(deterministic 6-dim scoring, intent-weighted rerank, no LLM call).

Why this lives in the framework
-------------------------------
Different user queries want different *kinds* of recall:

- ``"what's the user's email preference"`` → wants a stable ``fact``,
  the high-recall-boost ``preference`` category.
- ``"what changed since last week"`` → wants *new* items, not durable
  ones.  Novelty dominates.
- ``"how do I deploy this service"`` → wants a ``procedure``,
  actionable steps, not opinions.
- ``"what should I know before this meeting"`` → wants a *briefing*,
  signal-dense recent items, both durable and transient.
- ``"what's blocking the Q3 release"`` → wants ``blockers`` first,
  then dependencies / impact.

holaOS's insight is that intent-shaping should be **deterministic
and zero-cost** — keyword/phrase heuristics, not a classification
LLM call.  It then applies intent-specific 6-dim weights
(novelty / signal / urgency / impact / actionability / contradiction)
to rank candidates.  Both pieces are pure-Python and ~300 LOC, so
they belong in the framework rather than as a plugin.

This module is a standalone helper used by ``MemoryManager`` and
``ContextCompressor``-style flows; it does not depend on any LLM,
embedding model, or sqlite — only stdlib + dataclasses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Intent vocabulary (inspired by holaOS memory-retrieval-intent.ts:5)
# ---------------------------------------------------------------------------


class IntentKind:
    """The five retrieval intents, as plain string constants.

    Using strings (not an Enum) so providers can pass them through
    JSON boundaries and config files without special encoding.
    """

    FACT_LOOKUP = "fact_lookup"
    PROCEDURE_LOOKUP = "procedure_lookup"
    BRIEFING = "briefing"
    PLANNING = "planning"
    DELTA = "delta"


# Canonical list, in stable order — used for fall-through default
# ``FACT_LOOKUP`` when no heuristic matches.
INTENT_KINDS: tuple = (
    IntentKind.FACT_LOOKUP,
    IntentKind.PROCEDURE_LOOKUP,
    IntentKind.BRIEFING,
    IntentKind.PLANNING,
    IntentKind.DELTA,
)


# Keyword → intent.  Multi-word phrases come first so they win over
# single-word matches ("what changed since" beats "changed").
# Each phrase is a lowercase substring match (no regex), so common
# plural/tense variations are covered without lemmatization.
# (Patterned on holaOS memory-retrieval-intent.ts:34-92.)
_INTENT_PHRASES: List[Tuple[str, str]] = [
    # DELTA — "what changed / what's new / since last ..."
    ("what changed", IntentKind.DELTA),
    ("what's new", IntentKind.DELTA),
    ("whats new", IntentKind.DELTA),
    ("since last", IntentKind.DELTA),
    ("anything new", IntentKind.DELTA),
    ("recent changes", IntentKind.DELTA),
    ("latest updates", IntentKind.DELTA),
    # BRIEFING — "what should I know / catch me up / important ..."
    ("what should i know", IntentKind.BRIEFING),
    ("catch me up", IntentKind.BRIEFING),
    ("give me a briefing", IntentKind.BRIEFING),
    ("important emails", IntentKind.BRIEFING),
    ("key updates", IntentKind.BRIEFING),
    # PLANNING — "next steps / plan / unblock / roadmap"
    ("next steps", IntentKind.PLANNING),
    ("what's the plan", IntentKind.PLANNING),
    ("how do we unblock", IntentKind.PLANNING),
    ("roadmap", IntentKind.PLANNING),
    ("plan to", IntentKind.PLANNING),
    # PROCEDURE — "how do I / runbook / procedure / steps to"
    ("how do i", IntentKind.PROCEDURE_LOOKUP),
    ("how to", IntentKind.PROCEDURE_LOOKUP),
    ("runbook", IntentKind.PROCEDURE_LOOKUP),
    ("procedure for", IntentKind.PROCEDURE_LOOKUP),
    ("steps to", IntentKind.PROCEDURE_LOOKUP),
    # FACT_LOOKUP — explicit "what is / what's the X" doesn't have a
    # phrase; it is the default.  We add a couple of "what is"-style
    # fallbacks to make the intent explicit rather than implicit.
    ("what is the", IntentKind.FACT_LOOKUP),
    ("what's the user's", IntentKind.FACT_LOOKUP),
    ("what's my", IntentKind.FACT_LOOKUP),
]


def infer_intent(query: str) -> str:
    """Classify a user query into one of the five intents.

    Pure-string heuristic; no LLM call.  Returns the first matching
    intent from :data:`INTENT_KINDS` (priority order) and falls
    through to ``FACT_LOOKUP`` if nothing matches.  Empty/whitespace
    queries also return ``FACT_LOOKUP``.

    Examples
    --------
    >>> infer_intent("What changed since last week?")
    'delta'
    >>> infer_intent("How do I deploy this?")
    'procedure_lookup'
    >>> infer_intent("What is the user's timezone?")
    'fact_lookup'
    """
    if not query or not query.strip():
        return IntentKind.FACT_LOOKUP
    q = query.lower()
    for phrase, intent in _INTENT_PHRASES:
        if phrase in q:
            return intent
    return IntentKind.FACT_LOOKUP


# ---------------------------------------------------------------------------
# 6-dim scoring
# ---------------------------------------------------------------------------


# The six dimensions.  Each is a float in [0.0, 1.0]; values outside
# the range are clipped at rerank time.  Field names are stable —
# downstream code reads them by name, not by index.
DIMENSION_NAMES: tuple = (
    "novelty",        # how new / not-seen-before
    "signal",         # information density / quality
    "urgency",        # time-pressure / "this is needed now"
    "impact",         # blast radius / how much it changes things
    "actionability",  # can the user/agent do something with this
    "contradiction",  # disagrees with other known info
)


@dataclass
class Score6D:
    """A 6-dimensional relevance score plus a per-section category.

    Each dimension is a float in [0.0, 1.0].  ``category`` is one of
    the :data:`agent.retrieval_pack.PACK_SECTIONS` keys, used by
    intent-weighted reranking to apply cross-section bonuses.
    """

    novelty: float = 0.0
    signal: float = 0.0
    urgency: float = 0.0
    impact: float = 0.0
    actionability: float = 0.0
    contradiction: float = 0.0
    category: str = "high_signal"  # default; provider should set
    label: str = ""                # optional human-readable label

    def as_dict(self) -> Dict[str, float]:
        return {name: float(getattr(self, name)) for name in DIMENSION_NAMES}

    def clip(self) -> "Score6D":
        """Return a copy with each dimension clipped to [0.0, 1.0]."""
        for name in DIMENSION_NAMES:
            v = float(getattr(self, name))
            setattr(self, name, max(0.0, min(1.0, v)))
        return self


# Intent → per-dim multipliers.  Mirrors holaOS memory-reranker.ts:137-307
# "intent weight tables".  Numbers are in roughly the same ballpark as
# holaOS's tuned values; the framework's policy is "tunable, not
# hard-coded" — see ``set_intent_weights()`` for runtime override.
_DEFAULT_INTENT_WEIGHTS: Dict[str, Dict[str, float]] = {
    IntentKind.FACT_LOOKUP: {
        "novelty": 0.4, "signal": 1.0, "urgency": 0.4,
        "impact": 0.6, "actionability": 0.4, "contradiction": 0.8,
    },
    IntentKind.PROCEDURE_LOOKUP: {
        "novelty": 0.3, "signal": 0.9, "urgency": 0.6,
        "impact": 0.6, "actionability": 1.0, "contradiction": 0.7,
    },
    IntentKind.BRIEFING: {
        "novelty": 0.6, "signal": 0.7, "urgency": 0.55,
        "impact": 0.65, "actionability": 0.6, "contradiction": 0.75,
    },
    IntentKind.PLANNING: {
        "novelty": 0.4, "signal": 0.7, "urgency": 0.6,
        "impact": 0.85, "actionability": 0.95, "contradiction": 0.5,
    },
    IntentKind.DELTA: {
        # delta is novelty-dominant; contradiction matters because
        # "what changed" often surfaces conflicts with prior state
        "novelty": 1.2, "signal": 0.5, "urgency": 0.4,
        "impact": 0.6, "actionability": 0.4, "contradiction": 0.7,
    },
}


# Module-level mutable weights table so the framework can be tuned at
# runtime by tests, plugins, or future "agent config" surfaces without
# monkeypatching call sites.  Always pass via ``get_intent_weights()``
# in production code, not the bare dict.
_intent_weights: Dict[str, Dict[str, float]] = {
    k: dict(v) for k, v in _DEFAULT_INTENT_WEIGHTS.items()
}


def get_intent_weights(intent: str) -> Dict[str, float]:
    """Return a copy of the dim-weight table for an intent.

    Returns a fresh dict so callers can mutate freely without
    affecting the global table.  Unknown intents fall through to
    ``FACT_LOOKUP`` weights (the safest, most stable default).
    """
    base = _intent_weights.get(intent) or _DEFAULT_INTENT_WEIGHTS[IntentKind.FACT_LOOKUP]
    return dict(base)


def set_intent_weights(intent: str, weights: Dict[str, float]) -> None:
    """Override the weight table for one intent.

    Useful for A/B testing or user-specific tuning.  Validates that
    the dict has the right six keys, else raises ``ValueError`` so a
    typo doesn't silently disable a dimension.
    """
    missing = [d for d in DIMENSION_NAMES if d not in weights]
    if missing:
        raise ValueError(
            f"weights for intent {intent!r} missing dimensions: {missing}; "
            f"required: {DIMENSION_NAMES}"
        )
    _intent_weights[intent] = dict(weights)


def reset_intent_weights() -> None:
    """Restore all intent weight tables to the built-in defaults."""
    _intent_weights.clear()
    _intent_weights.update(
        {k: dict(v) for k, v in _DEFAULT_INTENT_WEIGHTS.items()}
    )


# ---------------------------------------------------------------------------
# Rerank
# ---------------------------------------------------------------------------


def rerank_by_intent(
    candidates: Iterable[Tuple[Any, Score6D]],
    intent: str,
) -> List[Tuple[Any, float]]:
    """Score and order candidates using intent-weighted 6-dim weights.

    Parameters
    ----------
    candidates:
        Iterable of ``(item, score)`` pairs.  ``item`` is opaque to
        this function (the caller decides what to do with the
        ordering — usually slice the top-N).  ``score`` is the
        :class:`Score6D` previously computed for the item (likely
        by a provider's embed-and-similarity step).
    intent:
        One of the :data:`INTENT_KINDS` values, usually the result
        of :func:`infer_intent` on the user's query.

    Returns
    -------
    list of ``(item, final_score)`` sorted by ``final_score``
    descending.  The final score is the dot product of the
    intent-weighted 6-dim vector with the candidate's 6-dim
    vector, plus a small cross-section bonus when the candidate's
    ``category`` is one the intent boosts (e.g. BRIEFING boosts
    ``high_signal`` and ``known_facts``).
    """
    weights = get_intent_weights(intent)
    scored: List[Tuple[Any, float]] = []
    for item, score in candidates:
        score.clip()
        s = sum(float(getattr(score, d)) * float(weights[d]) for d in DIMENSION_NAMES)
        # Tiny cross-section bonus (mirrors holaOS's per-intent
        # category boosts in memory-reranker.ts:246-307).  Bounded
        # so a single candidate can't dominate via category alone.
        s += _CATEGORY_BONUSES.get(intent, {}).get(score.category, 0.0)
        scored.append((item, s))
    scored.sort(key=lambda kv: kv[1], reverse=True)
    return scored


# Per-intent category bonus.  Smaller than dim weights because
# category alone shouldn't drown out a high-dim-score candidate.
_CATEGORY_BONUSES: Dict[str, Dict[str, float]] = {
    IntentKind.BRIEFING: {"high_signal": 0.45, "known_facts": 0.2},
    IntentKind.DELTA: {"high_signal": 0.55},
    IntentKind.PLANNING: {"blockers": 0.5, "constraints": 0.3},
    IntentKind.PROCEDURE_LOOKUP: {"constraints": 0.2, "high_signal": 0.2},
    IntentKind.FACT_LOOKUP: {"known_facts": 0.4, "constraints": 0.2},
}


__all__ = [
    "DIMENSION_NAMES",
    "INTENT_KINDS",
    "IntentKind",
    "Score6D",
    "infer_intent",
    "get_intent_weights",
    "set_intent_weights",
    "reset_intent_weights",
    "rerank_by_intent",
]
