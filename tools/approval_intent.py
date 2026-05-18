"""Natural-language approval-intent classifier for messaging-platform replies.

Maps free-form text replies ("yes", "I approve", "execute this") to one of the
canonical approval choices, so the gateway can route them through the same
``resolve_gateway_approval()`` path that the ``/approve`` slash command uses.

Pure and side-effect-free so it is trivially unit-testable in isolation
from the gateway, the approval queue, and the messaging platform adapters.
"""

from __future__ import annotations

import re
from typing import Optional

# Phrases that signal "approve the pending action".  Matched against the
# full lowercased+normalised text — substring matching is intentionally
# avoided so a casual "yes, but actually wait" doesn't fire approval.
#
# Intentionally limited to the spec's explicit verbs.  Casual aliases
# like "ok", "okay", "go", "k", "y", "yep", "yeah", "confirm", "go ahead"
# are EXCLUDED to keep the false-positive surface narrow — those words
# show up too often in normal conversation while an approval is pending,
# and a misfire can execute sensitive workflows.  These direct execution
# phrases are only honored by the gateway when a formal approval is pending;
# otherwise they fall through as normal user instructions.
_APPROVE_PHRASES: frozenset[str] = frozenset({
    "yes",
    "approve",
    "approved",
    "i approve",
    "execute",
    "execute this",
    "execute it",
    "do it",
    "do this",
    "run it",
    "run this",
    "run it now",
    "confirmed",
    "proceed",
})

# Phrases that signal "deny the pending action".  Kept separate from
# approval so that future vocabulary changes don't accidentally widen
# the approve set.  Same trimming policy: only explicit-deny verbs;
# "no", "n", "stop", and other potentially-conversational tokens are
# omitted because a chat message of "no" should NOT auto-deny a queued
# command that the user is still deliberating about.
_DENY_PHRASES: frozenset[str] = frozenset({
    "deny",
    "denied",
    "cancel",
    "reject",
    "rejected",
    "nevermind",
    "never mind",
})


_TRAILING_PUNCT_RE = re.compile(r"[.!?,…\s]+$")
_LEADING_FILLER_RE = re.compile(r"^(please\s+|just\s+|pls\s+|um\s+|uh\s+)+")
_COLLAPSE_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Lowercase, strip wrapping whitespace, collapse inner whitespace,
    drop trailing punctuation, and remove a small set of leading fillers.

    Kept deliberately narrow: we do NOT do stemming or fuzzy matching.
    The phrase list is the source of truth.
    """
    if not text:
        return ""
    n = text.strip().lower()
    n = _COLLAPSE_WS_RE.sub(" ", n)
    n = _TRAILING_PUNCT_RE.sub("", n)
    n = _LEADING_FILLER_RE.sub("", n)
    return n.strip()


def classify(text: str) -> Optional[str]:
    """Return ``"approve"``, ``"deny"``, or ``None`` for *text*.

    ``None`` means "this is not an approval/deny phrase" — the caller
    should fall through to normal dispatch.  Returning ``None`` here is
    the safe default: conversational text is never reinterpreted.

    Slash-prefixed input is rejected so explicit slash commands continue
    to flow through the normal command pipeline.
    """
    if not text:
        return None
    stripped = text.strip()
    if not stripped or stripped.startswith("/"):
        return None
    norm = _normalize(stripped)
    if not norm:
        return None
    if norm in _APPROVE_PHRASES:
        return "approve"
    if norm in _DENY_PHRASES:
        return "deny"
    return None


def is_approve_phrase(text: str) -> bool:
    """Convenience predicate: ``True`` iff *text* classifies as approve."""
    return classify(text) == "approve"


def is_deny_phrase(text: str) -> bool:
    """Convenience predicate: ``True`` iff *text* classifies as deny."""
    return classify(text) == "deny"
