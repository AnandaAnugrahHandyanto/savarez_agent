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

    m = re.match(r"(?i)^new\s+report:\s*(.+?)\s*-\s*(.+?)\s*-\s*(.+)$", raw)
    if m:
        return ParserResult(
            action=ACTION_NEW_REPORT,
            raw_text=raw,
            report_name=m.group(1).strip(),
            role_title=m.group(2).strip(),
            body=m.group(3).strip(),
            is_mutating=True,
        )

    reschedule_match = re.match(r"(?i)^(.+?)\s+1:1\s+rescheduled\s+\(one-off\)\s+to\s+(.+)$", raw)
    if reschedule_match:
        return ParserResult(
            action=ACTION_RESCHEDULE_ONCE,
            raw_text=raw,
            report_name=reschedule_match.group(1).strip(),
            body=reschedule_match.group(2).strip(),
            is_mutating=True,
        )

    patterns = [
        (r"(?i)^update\s+(.+?):\s*(.+)$", ACTION_UPDATE, True),
        (r"(?i)^1:1\s+(.+?):\s*(.+)$", ACTION_ONE_ON_ONE, True),
        (r"(?i)^assessment\s+(.+?):\s*(.+)$", ACTION_ASSESSMENT, True),
        (r"(?i)^todo\s+for\s+me\s+on\s+(.+?):\s*(.+)$", ACTION_TODO_MANAGER, True),
        (r"(?i)^todo\s+(.+?):\s*(.+)$", ACTION_TODO_REPORT, True),
        (r"(?i)^review\s+(.+)$", ACTION_REVIEW, False),
        (r"(?i)^challenge\s+my\s+view\s+of\s+(.+)$", ACTION_CHALLENGE, False),
    ]
    for pattern, action, is_mutating in patterns:
        match = re.match(pattern, raw)
        if not match:
            continue
        if action in {ACTION_REVIEW, ACTION_CHALLENGE}:
            return ParserResult(action=action, raw_text=raw, report_name=match.group(1).strip(), is_mutating=is_mutating)
        return ParserResult(action=action, raw_text=raw, report_name=match.group(1).strip(), body=match.group(2).strip(), is_mutating=is_mutating)

    prep_patterns = [
        r"(?i)^prep\s+(.+)$",
        r"(?i)^1o1\s+prep\s+(.+)$",
        r"(?i)^1:1\s+prep\s+(.+)$",
        r"(?i)^1o1\s+(.+)$",
        r"(?i)^1:1\s+(.+)$",
    ]
    for pattern in prep_patterns:
        match = re.match(pattern, raw)
        if match:
            return ParserResult(action=ACTION_PREP, raw_text=raw, report_name=match.group(1).strip(), prompt_variant="short", is_mutating=False)
    return None
