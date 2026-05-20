"""v0 dogfood contract DTOs carry schema_version and safe refs only."""

from contextops_ese import (
    SCHEMA_VERSION,
    ContextPack,
    EvidenceBundle,
    Finding,
    MessageSummary,
    Observation,
    PreviewConfig,
    Recommendation,
    RuntimeEvent,
    SafetyDecision,
    TaskHandoffAckObservation,
    safe_ref,
)


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def test_dogfood_v0_contracts_include_schema_version():
    ref = safe_ref("fixture")
    finding = Finding(
        finding_ref=safe_ref("finding"),
        kind="missing_origin_ack",
        title="Missing origin ACK after delegated work",
        confidence=0.9,
        evidence=EvidenceBundle((ref,), "opaque refs support this suggestion"),
        recommendation=Recommendation("contextops_backlog", "Route a final report to the origin manually"),
        safety_decision=SafetyDecision(),
    )
    rows = [
        Observation("raw-1", "safe signal").to_dict(),
        ContextPack("pack", ("restore this",), ("avoid that",), (ref,)).to_dict(),
        PreviewConfig().to_dict(),
        RuntimeEvent(ref, "kanban_completed").to_dict(),
        MessageSummary(ref, ref, role="assistant", summary="safe summary").to_dict(),
        TaskHandoffAckObservation(task_ref=ref, delegated=True, completed=True).to_dict(),
        finding.to_dict(),
    ]
    for row in rows:
        for nested in _walk_dicts(row):
            assert nested["schema_version"] == SCHEMA_VERSION


def test_safety_decision_is_suggestion_only_and_read_only():
    row = SafetyDecision().to_dict()
    assert row["policy_mode"] == "suggestion_only"
    assert row["read_only"] is True
    assert row["mutation_allowed"] is False
    assert row["dispatch_allowed"] is False
