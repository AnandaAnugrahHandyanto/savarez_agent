"""Append-only handoff observability ledger for Discord protocol v2.

The ledger is intentionally small and local: JSONL records are safe, redacted,
and correlate runtime handoff events with Discord projection message IDs without
using Discord as agent-to-agent transport.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from gateway.secret_refs import redact_sensitive_data

LEDGER_FILENAME = "handoff_ledger.jsonl"
KNOWN_THREAD_ID = "1516956247536963615"
KNOWN_DISCORD_MESSAGE_IDS = {
    "infra_timeout": "1517005917260877970",
    "ops_evidence": "1517006548113821766",
    "reviewer_verdict": "1517006922035888222",
}


def handoff_correlation_id(agent_event_id: str | None = None, *, handoff_id: str | None = None) -> str:
    """Return a stable opaque correlation id for handoff progress/result/close events."""

    base = str(agent_event_id or handoff_id or "unknown").strip() or "unknown"
    return f"corr_{base}"


def append_handoff_ledger_record(
    root_dir: str | Path,
    *,
    event: str,
    correlation_id: str,
    status: str | None = None,
    agent_event_id: str | None = None,
    handoff_id: str | None = None,
    source_agent_id: str | None = None,
    target_agent_id: str | None = None,
    topic_id: str | None = None,
    discord_thread_id: str | None = None,
    discord_message_ids: Mapping[str, str] | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one redacted JSON object and return the written record."""

    path = Path(root_dir) / LEDGER_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "event": str(event),
        "correlation_id": str(correlation_id),
        "status": str(status) if status is not None else None,
        "agent_event_id": str(agent_event_id) if agent_event_id else None,
        "handoff_id": str(handoff_id) if handoff_id else None,
        "source_agent_id": str(source_agent_id) if source_agent_id else None,
        "target_agent_id": str(target_agent_id) if target_agent_id else None,
        "topic_id": str(topic_id) if topic_id else None,
        "discord_thread_id": str(discord_thread_id) if discord_thread_id else None,
        "discord_message_ids": dict(discord_message_ids or {}),
        "payload": redact_sensitive_data(dict(payload or {})),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
        fh.write("\n")
    return record


def build_timeout_post_mortem(
    *,
    last_tool: str | None,
    elapsed_seconds: float | int | None,
    status: str,
    timeout_classification: str | None = None,
    partial_verdict: str | None = None,
) -> dict[str, Any]:
    """Create the minimal timeout hook payload used by result/close ledger events."""

    classification = timeout_classification or classify_timeout(status)
    return redact_sensitive_data(
        {
            "last_tool": last_tool,
            "elapsed_seconds": float(elapsed_seconds) if elapsed_seconds is not None else None,
            "status": str(status),
            "timeout_classification": classification,
            "partial_verdict": partial_verdict,
        }
    )


def classify_timeout(status: str | None) -> str:
    value = str(status or "").lower()
    if "infra" in value and "timeout" in value:
        return "infra_timeout"
    if "timeout" in value or "timed_out" in value:
        return "runtime_timeout"
    return "not_timeout"


def backfill_known_thread_handoff_ids(root_dir: str | Path) -> dict[str, Any]:
    """Append a safe local backfill marker for the known MB-PROP Discord thread IDs."""

    return append_handoff_ledger_record(
        root_dir,
        event="handoff.backfill.discord_ids",
        correlation_id=handoff_correlation_id(f"discord_thread_{KNOWN_THREAD_ID}"),
        status="observed",
        discord_thread_id=KNOWN_THREAD_ID,
        discord_message_ids=KNOWN_DISCORD_MESSAGE_IDS,
        payload={
            "source": "MB-PROP thread backfill",
            "notes": "Known Discord IDs only; no sensitive content stored.",
        },
    )
