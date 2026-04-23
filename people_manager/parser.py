from __future__ import annotations

import re

from .constants import (
    ACTION_ASSESSMENT,
    ACTION_CHALLENGE,
    ACTION_NEW_REPORT,
    ACTION_ONE_ON_ONE,
    ACTION_PREP,
    ACTION_RESCHEDULE_ONCE,
    ACTION_REVIEW,
    ACTION_TEAM_QUESTION,
    ACTION_TEAM_SCAN,
    ACTION_TODO_MANAGER,
    ACTION_TODO_REPORT,
    ACTION_UPDATE,
)
from .types import ParserResult


def _match(pattern: str, raw: str):
    return re.match(pattern, raw, flags=re.IGNORECASE | re.DOTALL)


def parse_message(text: str) -> ParserResult | None:
    raw = (text or "").strip()
    if not raw:
        return None

    lowered = raw.lower()
    if lowered == "team scan":
        return ParserResult(action=ACTION_TEAM_SCAN, raw_text=raw, is_mutating=False)
    if lowered == "am i under-managing anyone?":
        return ParserResult(action=ACTION_TEAM_QUESTION, raw_text=raw, prompt_variant="under_managing", is_mutating=False)
    if lowered == "who is over-scoped?":
        return ParserResult(action=ACTION_TEAM_QUESTION, raw_text=raw, prompt_variant="over_scoped", is_mutating=False)
    if lowered == "where am i being too generous?":
        return ParserResult(action=ACTION_TEAM_QUESTION, raw_text=raw, prompt_variant="too_generous", is_mutating=False)

    m = _match(r"^new\s+report:\s*(.+?)\s*-\s*(.+?)\s*-\s*(.+)$", raw)
    if m:
        return ParserResult(
            action=ACTION_NEW_REPORT,
            raw_text=raw,
            report_name=m.group(1).strip(),
            role_title=m.group(2).strip(),
            body=m.group(3).strip(),
            is_mutating=True,
        )

    reschedule_match = _match(r"^(.+?)\s+1:1\s+rescheduled\s+\(one-off\)\s+to\s+(.+)$", raw)
    if reschedule_match:
        return ParserResult(
            action=ACTION_RESCHEDULE_ONCE,
            raw_text=raw,
            report_name=reschedule_match.group(1).strip(),
            body=reschedule_match.group(2).strip(),
            is_mutating=True,
        )

    patterns = [
        (r"^update\s+(.+?):\s*(.+)$", ACTION_UPDATE, True),
        (r"^1:1\s+(.+?):\s*(.+)$", ACTION_ONE_ON_ONE, True),
        (r"^assessment\s+(.+?):\s*(.+)$", ACTION_ASSESSMENT, True),
        (r"^todo\s+for\s+me\s+on\s+(.+?):\s*(.+)$", ACTION_TODO_MANAGER, True),
        (r"^todo\s+(.+?):\s*(.+)$", ACTION_TODO_REPORT, True),
        (r"^review\s+(.+)$", ACTION_REVIEW, False),
        (r"^challenge\s+my\s+view\s+of\s+(.+)$", ACTION_CHALLENGE, False),
    ]
    for pattern, action, is_mutating in patterns:
        match = _match(pattern, raw)
        if not match:
            continue
        if action in {ACTION_REVIEW, ACTION_CHALLENGE}:
            return ParserResult(action=action, raw_text=raw, report_name=match.group(1).strip(), is_mutating=is_mutating)
        return ParserResult(action=action, raw_text=raw, report_name=match.group(1).strip(), body=match.group(2).strip(), is_mutating=is_mutating)

    prep_patterns = [
        r"^prep\s+(.+)$",
        r"^1o1\s+prep\s+(.+)$",
        r"^1:1\s+prep\s+(.+)$",
        r"^1o1\s+(.+)$",
        r"^1:1\s+(.+)$",
    ]
    for pattern in prep_patterns:
        match = _match(pattern, raw)
        if match:
            return ParserResult(action=ACTION_PREP, raw_text=raw, report_name=match.group(1).strip(), prompt_variant="short", is_mutating=False)
    return None
