"""Lightweight routing for external memory recall.

This module is deliberately pure and dependency-free: it decides whether a
turn should use current-turn recall, reuse an active capsule, or skip memory.
The actual retrieval remains owned by memory providers and ``AIAgent``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


RouteAction = Literal[
    "skip",
    "reuse_active_capsule",
    "domain_capsule",
    "hindsight_now",
]


_NUTRITION_PATTERNS = (
    r"(?<![0-9a-zа-яё_])завтрак[а-яё]*",
    r"(?<![0-9a-zа-яё_])обед[а-яё]*",
    r"(?<![0-9a-zа-яё_])ужин[а-яё]*",
    r"(?<![0-9a-zа-яё_])перекус[а-яё]*",
    r"(?<![0-9a-zа-яё_])съе(л|ла|ли|ден|дено|денный|денная|денные)[а-яё]*",
    r"(?<![0-9a-zа-яё_])калор[а-яё]*",
    r"(?<![0-9a-zа-яё_])ккал(?![0-9a-zа-яё_])",
    r"(?<![0-9a-zа-яё_])бел(ок|ка|ки|ков|ком|ку|ке)(?![0-9a-zа-яё_])",
    r"(?<![0-9a-zа-яё_])протеин[а-яё]*",
    r"(?<![0-9a-zа-яё_])омлет[а-яё]*",
    r"(?<![0-9a-zа-яё_])яйц[а-яё]*",
    r"(?<![0-9a-zа-яё_])йогурт[а-яё]*",
    r"(?<![0-9a-zа-яё_])творог[а-яё]*",
)

_NUTRITION_WORD_TRIGGERS = (
    "ел",
    "ела",
)

_WORD_BOUNDARY = r"(?<![0-9a-zа-яё_]){word}(?![0-9a-zа-яё_])"

_PAST_REFERENCE_PATTERNS = (
    r"(?<![0-9a-zа-яё_])помнишь(?![0-9a-zа-яё_])",
    r"(?<![0-9a-zа-яё_])в прошлый раз(?![0-9a-zа-яё_])",
    r"(?<![0-9a-zа-яё_])мы (?:это )?обсуждали с тобой(?![0-9a-zа-яё_])",
    r"(?<![0-9a-zа-яё_])с тобой (?:это )?обсуждали(?![0-9a-zа-яё_])",
    r"(?<![0-9a-zа-яё_])что (?:мы )?(?:это )?решили(?![0-9a-zа-яё_])",
    r"(?<![0-9a-zа-яё_])как (?:мы )?(?:это )?решили(?![0-9a-zа-яё_])",
    r"(?<![0-9a-zа-яё_])о ч[её]м говорили(?![0-9a-zа-яё_])",
    r"(?<![0-9a-z_])last time(?![0-9a-z_])",
    r"(?<![0-9a-z_])remember when(?![0-9a-z_])",
    r"(?<![0-9a-z_])as we discussed(?![0-9a-z_])",
    r"(?<![0-9a-z_])we discussed (?:this )?(?:before|last time|previously)(?![0-9a-z_])",
)


@dataclass(frozen=True)
class MemoryRoute:
    """Decision from the memory router for a single user turn."""

    action: RouteAction
    topic: str = ""
    query: str = ""
    reason: str = ""
    max_tokens: int = 800
    sources: list[str] = field(default_factory=list)


@dataclass
class ActiveContextCapsule:
    """Small, reusable memory context for the current topic."""

    topic: str
    text: str
    sources: list[str] = field(default_factory=list)
    created_turn: int = 0
    last_used_turn: int = 0
    ttl_turns: int = 5

    def is_valid(self, *, current_turn: int) -> bool:
        if not self.topic or not self.text.strip():
            return False
        # Keep capsules bounded from creation time rather than extending them on
        # every reuse; otherwise a stale topic can live forever in a chatty thread.
        return (current_turn - self.created_turn) <= self.ttl_turns


class ActiveContextCapsuleCache:
    """One active context capsule per agent/session.

    A single active capsule is enough for the MVP: it captures the current topic
    and avoids repeated recall across short follow-up turns. When the topic
    changes, the new capsule replaces the old one.
    """

    def __init__(self, *, default_ttl_turns: int = 5) -> None:
        self.default_ttl_turns = max(1, int(default_ttl_turns))
        self._capsule: ActiveContextCapsule | None = None

    def set(self, capsule: ActiveContextCapsule) -> None:
        if capsule.ttl_turns <= 0:
            capsule.ttl_turns = self.default_ttl_turns
        if capsule.last_used_turn <= 0:
            capsule.last_used_turn = capsule.created_turn
        self._capsule = capsule

    def get(self, topic: str, *, current_turn: int) -> str:
        capsule = self._capsule
        if capsule is None or capsule.topic != topic:
            return ""
        if not capsule.is_valid(current_turn=current_turn):
            return ""
        capsule.last_used_turn = current_turn
        return capsule.text

    def clear(self) -> None:
        self._capsule = None

    def active_topic(self, *, current_turn: int) -> str:
        capsule = self._capsule
        if capsule is None or not capsule.is_valid(current_turn=current_turn):
            return ""
        return capsule.topic


class MemoryRouter:
    """Cheap deterministic router for deciding whether to recall memory."""

    def classify(self, message: str, *, active_topic: str = "") -> MemoryRoute:
        raw = message or ""
        text = raw.lower().strip()
        if not text:
            return MemoryRoute(action="skip", reason="empty")
        nutrition_turn = self._is_nutrition_turn(text)

        if self._matches_any_pattern(text, _PAST_REFERENCE_PATTERNS):
            return MemoryRoute(
                action="hindsight_now",
                topic="nutrition" if nutrition_turn else "",
                query=raw,
                reason="explicit past-reference",
                max_tokens=800,
                sources=["external-memory"],
            )

        if nutrition_turn:
            if active_topic == "nutrition":
                return MemoryRoute(
                    action="reuse_active_capsule",
                    topic="nutrition",
                    query=raw,
                    reason="same nutrition topic",
                )
            return MemoryRoute(
                action="domain_capsule",
                topic="nutrition",
                query=raw,
                reason="nutrition trigger",
                max_tokens=800,
                sources=["external-memory"],
            )

        return MemoryRoute(action="skip", query=raw, reason="no memory trigger")

    @staticmethod
    def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
        return any(needle in text for needle in needles)

    @classmethod
    def _contains_whole_word(cls, text: str, words: tuple[str, ...]) -> bool:
        return any(re.search(_WORD_BOUNDARY.format(word=re.escape(word)), text) for word in words)

    @staticmethod
    def _matches_any_pattern(text: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, text) for pattern in patterns)

    @classmethod
    def _is_nutrition_turn(cls, text: str) -> bool:
        return cls._matches_any_pattern(text, _NUTRITION_PATTERNS) or cls._contains_whole_word(
            text,
            _NUTRITION_WORD_TRIGGERS,
        )
