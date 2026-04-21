from __future__ import annotations

from copy import deepcopy
from typing import Any

from .storage import utc_now_iso


def _append_log(report: dict[str, Any], *, entry_type: str, facts: list[str], michael_judgment: list[str], lane_id: str, raw_text: str, resulting_actions: list[str] | None = None) -> dict[str, Any]:
    report = deepcopy(report)
    report.setdefault("interaction_log", [])
    entry_id = f"evt_{len(report['interaction_log']) + 1:04d}"
    report["interaction_log"].append(
        {
            "id": entry_id,
            "date": utc_now_iso(),
            "type": entry_type,
            "source": {
                "platform": lane_id.split(":", 1)[0] if ":" in lane_id else "local",
                "lane": lane_id,
                "message_text": raw_text,
            },
            "facts": facts,
            "michael_judgment": michael_judgment,
            "miya_synthesis": [],
            "resulting_actions": resulting_actions or [],
        }
    )
    report["updated_at"] = utc_now_iso()
    return report


def append_structured_log(
    report: dict[str, Any],
    *,
    entry_type: str,
    lane_id: str,
    raw_text: str,
    facts: list[str] | None = None,
    michael_judgment: list[str] | None = None,
    resulting_actions: list[str] | None = None,
) -> dict[str, Any]:
    return _append_log(
        report,
        entry_type=entry_type,
        facts=facts or [],
        michael_judgment=michael_judgment or [],
        lane_id=lane_id,
        raw_text=raw_text,
        resulting_actions=resulting_actions,
    )


def _split_facts_and_judgment(text: str) -> tuple[list[str], list[str]]:
    text = (text or "").strip()
    if not text:
        return [], []
    if ", but " in text:
        fact, judgment = text.split(", but ", 1)
        return [fact.strip()], [judgment.strip()]
    if " but " in text:
        fact, judgment = text.split(" but ", 1)
        return [fact.strip()], [judgment.strip()]
    return [text], []


def apply_update(report: dict[str, Any], body: str, *, lane_id: str) -> dict[str, Any]:
    facts, judgments = _split_facts_and_judgment(body)
    return _append_log(
        report,
        entry_type="update",
        facts=facts,
        michael_judgment=judgments,
        lane_id=lane_id,
        raw_text=f"Update {report['name']}: {body}",
    )


def apply_one_on_one(report: dict[str, Any], body: str, *, lane_id: str) -> dict[str, Any]:
    facts, judgments = _split_facts_and_judgment(body)
    return _append_log(
        report,
        entry_type="one_on_one",
        facts=facts,
        michael_judgment=judgments,
        lane_id=lane_id,
        raw_text=f"1:1 {report['name']}: {body}",
    )


def apply_todo(report: dict[str, Any], body: str, *, for_manager: bool, lane_id: str) -> dict[str, Any]:
    report = deepcopy(report)
    bucket = "open_todos_for_michael" if for_manager else "open_todos_for_them"
    report.setdefault("open_loops", {}).setdefault(bucket, [])
    if body not in report["open_loops"][bucket]:
        report["open_loops"][bucket].append(body)
    prefix = "Todo for me on" if for_manager else "Todo"
    report = _append_log(
        report,
        entry_type="todo_manager" if for_manager else "todo_report",
        facts=[body],
        michael_judgment=[],
        lane_id=lane_id,
        raw_text=f"{prefix} {report['name']}: {body}",
        resulting_actions=[body],
    )
    return report


def apply_assessment(report: dict[str, Any], body: str, *, lane_id: str) -> dict[str, Any]:
    report = deepcopy(report)
    text = body.strip()
    lowered = text.lower()
    performance = report.setdefault("performance", {})

    chunks = [chunk.strip() for chunk in text.split(",") if chunk.strip()]
    if chunks:
        performance["current_performance_read"] = chunks[0]
    if "rising" in lowered:
        performance["trajectory"] = "rising"
    elif "declining" in lowered:
        performance["trajectory"] = "declining"
    elif "flat" in lowered:
        performance["trajectory"] = "flat"
    if "well matched" in lowered or "well-matched" in lowered:
        performance["scope_fit"] = "well-matched"
    elif "under scoped" in lowered or "under-scoped" in lowered:
        performance["scope_fit"] = "under-scoped"
    elif "over scoped" in lowered or "over-scoped" in lowered:
        performance["scope_fit"] = "over-scoped"
    if "confidence high" in lowered:
        performance["confidence_level_in_read"] = "high"
    elif "confidence medium" in lowered:
        performance["confidence_level_in_read"] = "medium"
    elif "confidence low" in lowered:
        performance["confidence_level_in_read"] = "low"
    performance.setdefault("evidence_basis", []).append(text)

    report = _append_log(
        report,
        entry_type="assessment",
        facts=[],
        michael_judgment=[text],
        lane_id=lane_id,
        raw_text=f"Assessment {report['name']}: {body}",
    )
    report["performance"] = performance
    return report
