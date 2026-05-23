from copy import deepcopy

from agent.memory_block_review_queue import create_review_queue_item
from agent.memory_blocks import create_memory_block_candidate
from agent.memory_governance_submission_packet import (
    MEMORY_GOVERNANCE_SUBMISSION_PACKET_KIND,
    MEMORY_GOVERNANCE_SUBMISSION_PACKET_POLICY,
    MEMORY_GOVERNANCE_SUBMISSION_PACKET_ROUTING,
    MEMORY_GOVERNANCE_SUBMISSION_PACKET_STATUS,
    create_governance_submission_packet,
    explain_governance_submission_packet,
    recommend_governance_submission_packet_action,
    summarize_governance_submission_packets,
    validate_governance_submission_packet,
)
from agent.memory_proposal_draft_builder import create_memory_proposal_draft
from agent.memory_proposal_governance_gate import create_governance_submission_candidate
from agent.memory_review_decision_gate import create_review_decision_candidate, evaluate_review_queue_item


def _decision(block_type="procedural_rules", decision=None, source_pattern_ids=None, source_fact_ids=None):
    block = create_memory_block_candidate(
        block_type,
        {"rules": ["Create governance review packets only."], "nested": {"value": "preserved"}},
        project_scope="memory-fabric",
        source_pattern_ids=source_pattern_ids if source_pattern_ids is not None else ["pattern-1"],
        source_fact_ids=source_fact_ids if source_fact_ids is not None else ["fact-1"],
        metadata={"source": "test"},
    )
    queue_item = create_review_queue_item(block, reviewer="memory-reviewer")
    if decision is None:
        return evaluate_review_queue_item(queue_item, reviewer="memory-reviewer")
    return create_review_decision_candidate(queue_item, reviewer="memory-reviewer", decision=decision)


def _submission(block_type="procedural_rules", decision=None, source_pattern_ids=None, source_fact_ids=None):
    draft = create_memory_proposal_draft(
        _decision(
            block_type=block_type,
            decision=decision,
            source_pattern_ids=source_pattern_ids,
            source_fact_ids=source_fact_ids,
        ),
        author="proposal-drafter",
    )
    return create_governance_submission_candidate(draft, reviewer="governance-reviewer")


def test_valid_governance_submission_creates_human_review_packet_required_packet():
    submission = _submission()

    packet = create_governance_submission_packet(submission, reviewer="packet-reviewer")

    assert packet["packet_kind"] == MEMORY_GOVERNANCE_SUBMISSION_PACKET_KIND
    assert packet["packet_status"] == MEMORY_GOVERNANCE_SUBMISSION_PACKET_STATUS
    assert packet["routing"] == MEMORY_GOVERNANCE_SUBMISSION_PACKET_ROUTING
    assert packet["source_submission_id"] == submission["submission_id"]
    assert packet["source_draft_id"] == submission["source_draft_id"]
    assert packet["source_decision_id"] == submission["source_decision_id"]
    assert packet["source_queue_item_id"] == submission["source_queue_item_id"]
    assert packet["reviewer"] == "packet-reviewer"
    assert packet["packet_validation"] == {"valid": True, "errors": []}
    assert validate_governance_submission_packet(packet) == {"valid": True, "errors": []}
    assert packet["next_step_recommendation"]["action"] == "route_packet_to_manual_human_review"
    assert packet["next_step_recommendation"]["creates_real_proposals"] is False
    assert packet["next_step_recommendation"]["submits_to_governance"] is False
    assert packet["next_step_recommendation"]["converts_to_real_proposal"] is False


def test_invalid_submission_creates_invalid_packet_with_invalid_governance_submission_candidate():
    submission = _submission(decision="reject")

    packet = create_governance_submission_packet(submission)

    assert packet["packet_validation"]["valid"] is False
    assert "invalid_governance_submission_candidate" in packet["packet_validation"]["errors"]
    assert packet["next_step_recommendation"]["action"] == "do_not_route_packet"


def test_missing_payload_preview_creates_invalid_packet():
    submission = _submission()
    submission.pop("payload_preview")

    packet = create_governance_submission_packet(submission)

    assert packet["packet_validation"]["valid"] is False
    assert "missing_payload_preview" in packet["packet_validation"]["errors"]
    assert packet["next_step_recommendation"]["action"] == "do_not_route_packet"


def test_missing_source_evidence_creates_invalid_packet():
    submission = _submission(source_pattern_ids=[], source_fact_ids=[])

    packet = create_governance_submission_packet(submission)

    assert packet["packet_validation"]["valid"] is False
    assert "missing_source_evidence" in packet["packet_validation"]["errors"]


def test_evidence_summary_includes_source_pattern_and_fact_counts():
    submission = _submission(source_pattern_ids=["pattern-a", "pattern-b"], source_fact_ids=["fact-a"])

    packet = create_governance_submission_packet(submission)

    assert packet["evidence_summary"]["source_pattern_count"] == 2
    assert packet["evidence_summary"]["source_fact_count"] == 1
    assert packet["evidence_summary"]["source_pattern_ids"] == ["pattern-a", "pattern-b"]
    assert packet["evidence_summary"]["source_fact_ids"] == ["fact-a"]
    assert packet["evidence_summary"]["has_source_evidence"] is True


def test_human_review_checklist_exists_and_is_deterministic():
    packet_a = create_governance_submission_packet(_submission())
    packet_b = create_governance_submission_packet(_submission())

    assert packet_a["human_review_checklist"]
    assert packet_a["human_review_checklist"] == packet_b["human_review_checklist"]
    assert [item["id"] for item in packet_a["human_review_checklist"]] == [
        "verify_payload_preview",
        "verify_source_evidence",
        "verify_scope_and_routing",
        "verify_no_side_effects",
    ]


def test_input_submission_candidate_is_not_mutated():
    submission = _submission()
    before = deepcopy(submission)

    packet = create_governance_submission_packet(submission)
    packet["source_submission_snapshot"]["payload_preview"]["content"]["nested"]["value"] = "changed"

    assert submission == before


def test_policy_proves_no_memory_config_graph_proposal_or_ledger_writes(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    packet = create_governance_submission_packet(_submission())
    explanation = explain_governance_submission_packet(packet)
    recommendation = recommend_governance_submission_packet_action(packet)

    assert packet["policy"] == MEMORY_GOVERNANCE_SUBMISSION_PACKET_POLICY
    assert packet["policy"]["read_only"] is True
    assert packet["policy"]["would_write_memory"] is False
    assert packet["policy"]["would_modify_config"] is False
    assert packet["policy"]["would_write_graph"] is False
    assert packet["policy"]["does_not_create_operation_events"] is True
    assert packet["policy"]["creates_review_packets_only"] is True
    assert packet["policy"]["creates_real_proposals"] is False
    assert packet["policy"]["applies_proposals"] is False
    assert packet["policy"]["persists_approvals"] is False
    assert packet["policy"]["submits_to_governance"] is False
    assert packet["policy"]["converts_to_real_proposal"] is False
    assert explanation["submitted"] is False
    assert explanation["applied"] is False
    assert explanation["persisted"] is False
    assert explanation["approved"] is False
    assert explanation["converted_to_real_proposal"] is False
    assert explanation["created_real_proposal"] is False
    assert explanation["created_operation_event"] is False
    assert recommendation["creates_real_proposals"] is False
    assert recommendation["submits_to_governance"] is False
    assert recommendation["converts_to_real_proposal"] is False
    assert not (hermes_home / "memory" / "graph" / "memory_graph.sqlite").exists()
    assert not (hermes_home / "memory" / "audit" / "memory_operation_ledger.jsonl").exists()
    assert not (hermes_home / "memory" / "proposals" / "memory_write_proposals.jsonl").exists()


def test_packet_must_never_be_marked_submitted_applied_persisted_approved_or_converted():
    packet = create_governance_submission_packet(_submission())

    for forbidden_key in (
        "submitted",
        "applied",
        "persisted",
        "approved",
        "converted_to_real_proposal",
        "created_real_proposal",
        "created_operation_event",
    ):
        mutated = deepcopy(packet)
        mutated[forbidden_key] = True
        validation = validate_governance_submission_packet(mutated)
        assert validation["valid"] is False
        assert f"{forbidden_key}_must_be_false_or_absent" in validation["errors"]


def test_summary_counts_valid_invalid_packets_and_by_block_type_status():
    packets = [
        create_governance_submission_packet(_submission("procedural_rules")),
        create_governance_submission_packet(_submission("project_context")),
        create_governance_submission_packet(_submission("procedural_rules", decision="reject")),
    ]

    summary = summarize_governance_submission_packets(packets)

    assert summary["total"] == 3
    assert summary["valid_count"] == 2
    assert summary["invalid_count"] == 1
    assert summary["by_block_type"] == {"procedural_rules": 2, "project_context": 1}
    assert summary["by_status"] == {"human_review_packet_required": 3}
    assert summary["policy"] == MEMORY_GOVERNANCE_SUBMISSION_PACKET_POLICY
