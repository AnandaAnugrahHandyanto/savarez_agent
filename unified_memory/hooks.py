"""
Lifecycle Hooks for the Unified Memory System.

Inspired by Icarus-Daedalus hook architecture:
  - on_topic_change: detect topic shifts, proactively retrieve context
  - on_session_end: generate summary of session decisions and outcomes

These hooks are called by the agent loop (tick_unified_memory and
get_unified_memory_injection) to provide automatic memory management.
"""

from __future__ import annotations

import re
import logging
from typing import Optional, List, Set

logger = logging.getLogger(__name__)

# Stop words for topic extraction
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "they",
    "it", "its", "this", "that", "these", "those",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "and", "or", "but", "not", "no", "so", "if", "then", "than",
    "what", "which", "who", "where", "when", "how", "why",
    "about", "into", "through", "during", "before", "after",
    "just", "also", "very", "too", "quite", "really",
    "yes", "no", "ok", "okay", "sure", "thanks", "please",
})


class TopicTracker:
    """Track conversation topic and detect shifts.

    Maintains a sliding window of topic tokens from recent turns.
    When the topic shifts significantly (low overlap with previous),
    triggers proactive retrieval of context for the new topic.
    """

    def __init__(self, shift_threshold: float = 0.15):
        self.shift_threshold = shift_threshold
        self._previous_tokens: Set[str] = set()
        self._turn_count: int = 0

    def _extract_topic_tokens(self, text: str) -> Set[str]:
        """Extract meaningful topic tokens from text."""
        words = set(re.findall(r"[a-z0-9]{3,}", text.lower()))
        return words - _STOP_WORDS

    def check_topic_shift(self, message: str) -> Optional[str]:
        """Check if the message represents a topic shift.

        Returns the new topic query if a shift is detected, None otherwise.
        """
        self._turn_count += 1
        current_tokens = self._extract_topic_tokens(message)

        if not current_tokens:
            return None

        # First message is never a "shift"
        if not self._previous_tokens:
            self._previous_tokens = current_tokens
            return None

        # Compute overlap
        previous = self._previous_tokens
        overlap = len(current_tokens & previous)
        union = len(current_tokens | previous)
        similarity = overlap / union if union > 0 else 0.0

        # Detect shift: low similarity = new topic
        is_shift = similarity < self.shift_threshold and len(current_tokens) >= 3

        # Compute new topic words BEFORE updating state
        new_topic_words = sorted(current_tokens - previous)[:5] if is_shift else []

        # Update state
        self._previous_tokens = current_tokens

        if is_shift and new_topic_words:
            return " ".join(new_topic_words)

        return None

    def reset(self):
        """Reset topic tracking state."""
        self._previous_tokens = set()
        self._turn_count = 0


def generate_session_summary(
    facts_stored: List[str],
    facts_recalled: List[str],
    decisions_made: List[str],
) -> Optional[str]:
    """Generate a summary of the current session.

    Called at session end to create a summary entry that captures
    the key outcomes. Inspired by Icarus on_session_end hook.

    Args:
        facts_stored: Content strings of facts stored during session
        facts_recalled: Content strings of facts recalled during session
        decisions_made: Content strings identified as decisions

    Returns:
        Summary string if there's meaningful content, None otherwise.
    """
    if not facts_stored and not decisions_made:
        return None

    parts = []

    if decisions_made:
        parts.append("Decisions: " + "; ".join(decisions_made[:5]))

    if facts_stored:
        # Extract themes from stored facts
        all_words = []
        for fact in facts_stored[:10]:
            words = re.findall(r"[a-z]{4,}", fact.lower())
            all_words.extend(w for w in words if w not in _STOP_WORDS)

        # Most common theme words
        from collections import Counter
        themes = [w for w, _ in Counter(all_words).most_common(5)]
        if themes:
            parts.append(f"Topics: {', '.join(themes)}")

        parts.append(f"Facts stored: {len(facts_stored)}")

    if facts_recalled:
        parts.append(f"Facts recalled: {len(facts_recalled)}")

    return " | ".join(parts) if parts else None


def detect_decisions(text: str) -> List[str]:
    """Extract decision-like statements from text.

    Looks for language indicating a choice was made:
    "we decided", "let's go with", "chose", "selected", etc.
    """
    decisions = []
    sentences = re.split(r"[.!?\n]+", text)

    decision_patterns = [
        r"\b(?:decided|chose|selected|picked|went with|opted for|settled on)\b",
        r"\blet'?s\s+(?:go with|use|do|try|switch to|move to)\b",
        r"\bwe(?:'ll| will| should| must)\s+(?:use|go|switch|move|implement)\b",
        r"\b(?:decision|conclusion|verdict):\s",
    ]

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 10:
            continue
        for pattern in decision_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                decisions.append(sentence[:200])
                break

    return decisions
