from agent.memory_inspection import explain_conflict, explain_write
from agent.memory_policy import ConflictDecision
from agent.memory_records import (
    MemoryRecord,
    MemoryScope,
    MemoryType,
    RecordStatus,
    SalienceTier,
    TrustTier,
)


def _make_record(record_id: str, *, status: RecordStatus = RecordStatus.ACTIVE) -> MemoryRecord:
    return MemoryRecord(
        record_id=record_id,
        memory_type=MemoryType.PROFILE,
        scope=MemoryScope.OPERATOR,
        topic_key="preference:spelling",
        content="User prefers British spelling.",
        source="memory_tool:add",
        source_kind="explicit_user_statement",
        trust_tier=TrustTier.USER_ASSERTED,
        salience_tier=SalienceTier.HIGH,
        status=status,
    )


def test_explain_write_includes_reason_topic_and_scope():
    record = _make_record("rec-1")

    payload = explain_write(record, "explicit_operator_signal")

    assert payload["record_id"] == "rec-1"
    assert payload["topic_key"] == "preference:spelling"
    assert payload["scope"] == "operator"
    assert payload["reason"] == "explicit_operator_signal"


def test_explain_conflict_reports_winner_loser_and_reason():
    winner = _make_record("rec-2")
    loser = _make_record("rec-1", status=RecordStatus.SUPERSEDED)
    decision = ConflictDecision(
        winner=winner,
        loser=loser,
        loser_status=RecordStatus.SUPERSEDED,
        reason="higher_trust_new_record",
    )

    payload = explain_conflict(decision)

    assert payload == {
        "winner_record_id": "rec-2",
        "loser_record_id": "rec-1",
        "loser_status": "superseded",
        "reason": "higher_trust_new_record",
        "topic_key": "preference:spelling",
    }