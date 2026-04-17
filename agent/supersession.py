from __future__ import annotations

from typing import Dict, List, Tuple

from agent.memory_lanes import get_lane


def _normalize(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def suppress_derived_records(records: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[str]]:
    winners: List[Dict[str, str]] = []
    suppressed: List[Dict[str, str]] = []
    reasons: List[str] = []
    canonical_by_content = {
        _normalize(record.get("content", ""))
        for record in records
        if record.get("content") and not get_lane(record["lane"]).derived
    }
    for record in records:
        content_key = _normalize(record.get("content", ""))
        lane = get_lane(record["lane"])
        if lane.derived and content_key and content_key in canonical_by_content:
            suppressed.append(record)
            reason = "source lane outranks derived lane"
            if reason not in reasons:
                reasons.append(reason)
            continue
        winners.append(record)
    return winners, suppressed, reasons
