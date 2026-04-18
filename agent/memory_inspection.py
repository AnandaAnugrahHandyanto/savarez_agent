from __future__ import annotations

from agent.memory_policy import ConflictDecision
from agent.memory_records import MemoryRecord


def explain_write(record: MemoryRecord, reason: str) -> dict:
    return {
        "record_id": record.record_id,
        "topic_key": record.topic_key,
        "scope": record.scope.value,
        "status": record.status.value,
        "trust_tier": record.trust_tier.value,
        "salience_tier": record.salience_tier.value,
        "reason": reason,
    }


def explain_conflict(decision: ConflictDecision) -> dict:
    return {
        "winner_record_id": decision.winner.record_id,
        "loser_record_id": decision.loser.record_id,
        "loser_status": decision.loser_status.value,
        "reason": decision.reason,
        "topic_key": decision.winner.topic_key,
    }