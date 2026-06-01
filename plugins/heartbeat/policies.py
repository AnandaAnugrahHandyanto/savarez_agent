"""Deterministic Heartbeat policies."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

from .models import FindingProposal, ReviewDecision

_FINGERPRINT_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{2,127}$")
_CONTEXT_FENCE_RE = re.compile(
    r"</?\s*(?:heartbeat-active-findings|memory-context)\s*>",
    re.IGNORECASE,
)
_PRIORITIES = {"low", "medium", "high"}


def active_hours_allow(config: Dict[str, Any], now: datetime | None = None) -> bool:
    hours = config["active_hours"]
    if not hours.get("enabled", False):
        return True
    if now is None:
        timezone_name = str(config.get("timezone") or "").strip()
        if timezone_name:
            try:
                from zoneinfo import ZoneInfo

                now = datetime.now(ZoneInfo(timezone_name))
            except Exception:
                now = datetime.now()
        else:
            now = datetime.now()
    current = now.strftime("%H:%M")
    start = hours["start"]
    end = hours["end"]
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def sanitize_text(value: Any, max_chars: int) -> str:
    text = str(value or "").replace("\x00", "").strip()
    text = _CONTEXT_FENCE_RE.sub("", text)
    return text[:max_chars]


def normalize_fingerprint(value: Any) -> str:
    text = sanitize_text(value, 128).lower().replace(" ", "-")
    if not _FINGERPRINT_RE.fullmatch(text):
        raise ValueError("invalid heartbeat fingerprint")
    return text


def parse_review(payload: Any, *, default_ttl_hours: int) -> ReviewDecision:
    if not isinstance(payload, dict):
        raise ValueError("heartbeat review must be a JSON object")
    action = str(payload.get("action") or "").strip().lower()
    if action not in {"suppress", "defer", "notify"}:
        raise ValueError("invalid heartbeat review action")
    reason = sanitize_text(payload.get("reason"), 500)
    proposals: List[FindingProposal] = []
    raw_findings = payload.get("findings") or []
    if not isinstance(raw_findings, list):
        raise ValueError("heartbeat review findings must be a list")
    for raw in raw_findings[:5]:
        if not isinstance(raw, dict):
            continue
        priority = str(raw.get("priority") or "medium").lower()
        if priority not in _PRIORITIES:
            priority = "medium"
        try:
            ttl = int(raw.get("ttl_hours", default_ttl_hours))
        except (TypeError, ValueError):
            ttl = default_ttl_hours
        ttl = min(max(ttl, 1), 168)
        summary = sanitize_text(raw.get("summary"), 800)
        if not summary:
            continue
        proposals.append(
            FindingProposal(
                fingerprint=normalize_fingerprint(raw.get("fingerprint")),
                priority=priority,
                summary=summary,
                recommended_action=sanitize_text(raw.get("recommended_action"), 800),
                ttl_hours=ttl,
            )
        )
    if action == "notify" and not proposals:
        action = "suppress"
    return ReviewDecision(action=action, reason=reason, findings=proposals)


def eligible_findings(
    decision: ReviewDecision,
    *,
    inbox: Any,
    cooldown_minutes: int,
    daily_cap: int,
) -> Tuple[List[FindingProposal], str]:
    if decision.action != "notify":
        return [], decision.action
    if daily_cap <= inbox.notifications_today():
        return [], "daily_notification_cap"
    remaining = max(0, daily_cap - inbox.notifications_today())
    accepted = [
        proposal
        for proposal in decision.findings
        if not inbox.has_recent_fingerprint(proposal.fingerprint, cooldown_minutes)
    ][:remaining]
    return accepted, "accepted" if accepted else "cooldown"
