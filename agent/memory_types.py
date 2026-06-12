"""Memory entry types + per-type recall governance.

Inspired by holaOS's memory-governance.ts: six entry categories
with a recall boost (relevance weight) and a staleness window
(how long an entry stays "fresh" before the system starts
nudging the user to re-verify it).

Why this lives in the framework
-------------------------------
Different memory entries have different lifecycles:

- A **preference** ("user is vegetarian") is durable and should
  be boosted heavily on recall — the LLM should always remember
  it when planning meals, even if the user is asking about
  something unrelated.
- A **fact** ("user's email is alice@example.com") is durable
  but only relevant to specific contexts.
- A **reference** ("see doc at https://...") goes stale fast;
  the link might be dead in a week, so the system should
  re-verify it.
- A **blocker** ("backend API is down, use fallback X") is
  time-sensitive and should be surfaced aggressively, then
  cleared when it stops being true.

Without type metadata, every entry has the same weight, the same
staleness window, and the same governance story — which is
fine for a small MEMORY.md but falls apart the moment a user
accumulates hundreds of entries across years of use.

The framework layer here is the *contract*: a 6-value enum, a
recall boost (per-type, with a global default), a staleness
window, and a `classify_entry` helper that external providers
can call to opt in.  No provider is *required* to participate
— providers that don't override ``classify_entry`` get the
default behavior (everything is a ``fact``), preserving full
backward compatibility with all 7 existing memory plugins
(honcho, mem0, supermemory, retaindb, hindsight, byterover,
openviking, holographic).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# EntryType enum
# ---------------------------------------------------------------------------


class EntryType(str, Enum):
    """The six memory entry categories.

    Inherits from ``str`` so values serialize cleanly to JSON
    (``"preference"``, not ``"EntryType.PREFERENCE"``) and can
    be compared against provider-side string literals.  Use the
    bare string in code (``EntryType.PREFERENCE``) — they round-
    trip through ``str(EntryType.PREFERENCE) == "preference"``.

    The order in this enum is part of the contract: providers
    that fall back to ``for type_ in EntryType`` should see
    preference first (highest recall boost).
    """

    PREFERENCE = "preference"   # durable user choices / how the user wants things done
    IDENTITY = "identity"       # who the user is, role, relationships
    FACT = "fact"               # stable factual statements
    PROCEDURE = "procedure"     # how-to / runbooks / step sequences
    BLOCKER = "blocker"         # active problems, workarounds
    REFERENCE = "reference"     # pointers (URLs, file paths, ticket IDs)


# ---------------------------------------------------------------------------
# Per-type governance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntryTypePolicy:
    """The recall + staleness policy for a single :class:`EntryType`.

    Fields
    ------
    recall_boost:
        Multiplicative weight applied during recall ranking.  A
        ``preference`` (boost=4) outranks a generic ``fact``
        (boost=1) on every recall.  Use the boost to encode
        "this kind of information is the user's *operating
        context* — they want the LLM to remember it
        disproportionately."

    stale_after_seconds:
        Number of seconds after which the system starts nudging
        the user to re-verify the entry.  ``None`` means
        "durable, no auto-staleness check" (preference,
        identity).  A 7-day reference might be dead by next
        month; a 30-day fact can usually wait a month.

    description:
        Human-readable description for UI / logs.  Optional —
        the enum member name is the default.
    """

    recall_boost: float
    stale_after_seconds: Optional[float]
    description: str = ""


# Mirrors holaOS memory-governance.ts:25-68.  Numbers are tuned to
# the same regime: preferences dominate, blockers are aggressive,
# references decay fast.  ``stale_after_seconds`` is None for
# the durable categories (preference, identity) — those don't
# auto-stale.
_DEFAULT_POLICIES: dict = {
    EntryType.PREFERENCE: EntryTypePolicy(
        recall_boost=4.0,
        stale_after_seconds=None,
        description="User choices and preferences — how the user wants things done.",
    ),
    EntryType.IDENTITY: EntryTypePolicy(
        recall_boost=3.0,
        stale_after_seconds=None,
        description="Who the user is: role, relationships, self-description.",
    ),
    EntryType.FACT: EntryTypePolicy(
        recall_boost=1.0,
        stale_after_seconds=30 * 24 * 3600,  # 30 days
        description="Stable factual statements that may drift over time.",
    ),
    EntryType.PROCEDURE: EntryTypePolicy(
        recall_boost=1.5,
        stale_after_seconds=60 * 24 * 3600,  # 60 days
        description="How-to knowledge, runbooks, step sequences.",
    ),
    EntryType.BLOCKER: EntryTypePolicy(
        recall_boost=2.5,
        stale_after_seconds=7 * 24 * 3600,  # 7 days
        description="Active problems and current workarounds; clear when resolved.",
    ),
    EntryType.REFERENCE: EntryTypePolicy(
        recall_boost=1.2,
        stale_after_seconds=7 * 24 * 3600,  # 7 days
        description="Pointers to external resources (URLs, file paths, ticket IDs).",
    ),
}


# Module-level mutable table so tests, plugins, or future
# "agent config" surfaces can tweak the policy at runtime
# without monkeypatching call sites.  Use the accessors below,
# not the bare dict.
_type_policies: dict = {
    t: p for t, p in _DEFAULT_POLICIES.items()
}


def get_policy(entry_type: EntryType) -> EntryTypePolicy:
    """Return the recall/staleness policy for an entry type.

    Always returns a policy — unknown entry types fall back to
    the ``FACT`` policy (the safe default — same as a generic
    memory entry before the type system was introduced).
    """
    return _type_policies.get(entry_type) or _DEFAULT_POLICIES[EntryType.FACT]


def set_policy(entry_type: EntryType, policy: EntryTypePolicy) -> None:
    """Override the policy for one entry type.

    Useful for plugins that want a different recall profile
    (e.g. a code-assistant provider boosting ``PROCEDURE`` to
    3.0 for code-generation tasks).  Validates the boost is
    non-negative so a typo can't disable a category entirely.
    """
    if policy.recall_boost < 0:
        raise ValueError(
            f"recall_boost for {entry_type!r} must be non-negative, "
            f"got {policy.recall_boost!r}"
        )
    _type_policies[entry_type] = policy


def reset_policies() -> None:
    """Restore the built-in default policy table.

    Tests use this to leave global state clean.
    """
    _type_policies.clear()
    _type_policies.update(
        {t: p for t, p in _DEFAULT_POLICIES.items()}
    )


# ---------------------------------------------------------------------------
# Staleness check
# ---------------------------------------------------------------------------


def is_stale(entry_type: EntryType, age_seconds: float) -> bool:
    """Return True if an entry of this type, ``age_seconds`` old,
    should be re-verified by the user.

    Returns False for entry types with ``stale_after_seconds=None``
    (durable categories: preference, identity).
    """
    policy = get_policy(entry_type)
    if policy.stale_after_seconds is None:
        return False
    return age_seconds > policy.stale_after_seconds


# ---------------------------------------------------------------------------
# Heuristic classifier
# ---------------------------------------------------------------------------


# Keyword sets used by the default ``classify_entry`` heuristic.
# A single keyword match is enough to label an entry; the order
# of the ``EntryType`` enum acts as the priority order
# (preference first, reference last).  Phrases are substring
# matched (case-insensitive, no regex).
_CLASSIFY_PHRASES: list = [
    (EntryType.PREFERENCE, ("i prefer", "i like", "i don't like", "i love", "i hate",
                            "don't bother me with", "always use", "never use",
                            "my preference", "use instead of", "rather than",
                            "i want", "i'd rather", "let's go with",
                            "prefers", "preference:", "favors", "favoured")),
    (EntryType.IDENTITY, ("my name is", "name is", "i am a", "i'm a", "i work as", "my role",
                          "i work at", "my job", "i live in", "based in",
                          "my team", "i report to")),
    (EntryType.PROCEDURE, ("how to", "runbook", "procedure", "step by step",
                          "first, then, finally", "to deploy", "to release",
                          "to test", "to build", "to run")),
    (EntryType.BLOCKER, ("blocked by", "is down", "is broken", "is failing",
                        "workaround:", "currently broken", "known issue",
                        "in progress", "ticket:", "bug #", "fix in",
                        "use fallback")),
    (EntryType.REFERENCE, ("see ", "see also", "doc:", "link:", "url:",
                          "http://", "https://", "ticket ", "issue #",
                          "at github.com", "wiki:", "readme:")),
    # FACT is the fallback — no keywords needed.
]


def classify_entry(content: str) -> EntryType:
    """Best-effort heuristic classifier for a memory entry.

    Used by providers that store text-only entries (e.g. the
    built-in ``MEMORY.md`` / ``USER.md`` files) and want a
    type without parsing structured metadata.  Substring match,
    case-insensitive, no regex — the cheapest possible rule.

    Returns ``EntryType.FACT`` when no phrase matches.  Providers
    that have a better signal (the user explicitly tagged the
    entry, or the storage backend already classifies it) should
    override ``MemoryProvider.classify_entry`` to return that
    signal instead.
    """
    if not content or not content.strip():
        return EntryType.FACT
    lower = content.lower()
    for entry_type, phrases in _CLASSIFY_PHRASES:
        for phrase in phrases:
            if phrase in lower:
                return entry_type
    return EntryType.FACT


__all__ = [
    "EntryType",
    "EntryTypePolicy",
    "get_policy",
    "set_policy",
    "reset_policies",
    "is_stale",
    "classify_entry",
]
