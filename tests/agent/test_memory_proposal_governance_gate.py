from copy import deepcopy

from agent.memory_block_review_queue import create_review_queue_item
from agent.memory_blocks import create_memory_block_candidate
from agent.memory_proposal_draft_builder import create_memory_proposal_draft
from agent.memory_proposal_governance_gate import (
    MEMORY_GOVERNANCE_SUBMISSION_KIND,
    MEMORY_GOVERNANCE_SUBMISSION_ROUTING,
    MEMORY_GOVERNANCE_SUBMISSION_STATUS,
    MEMORY_PROPOSAL_GOVERNANCE_GATE_POLICY,
    create_governance_submission_candidate,
    explain_governance_submission_candidate,
    recommend_governance_submission_action,
    summarize_governance_submission_candidates,
    validate_governance_submission_candidate,
)
from agent.memory_review_decision_gate import create_review_decision_candidate, evaluate_review_queue_item


def _decision(block_type="procedural_rules", decision=None, source_pattern_ids=None, source_fact_ids=None):
    block = create_memory_block_candidate(
        block_type,
        {"rules": ["Create governance submission candidates only."], "nested": {"value": "preserved"}},
        project_scope="memory-fabric",
        source_pattern_ids=source_pattern_ids if source_pattern_ids is not None else ["pattern-1"],
        source_fact_ids=source_fact_ids if source_fact_ids is not None else ["fact-1"],
        metadata={"source": "test"},
    )
    queue_item = create_review_queue_item(block, reviewer="memory-reviewer")
    if decision is None:
        return evaluate_review_queue_item(queue_item, reviewer="memory-reviewer")
    return create_review_decision_candidate(queue_item, reviewer="memory-reviewer", decision=decision)


def _draft(block_type="procedural_rules", decision=None, source_pattern_ids=None, source_fact_ids=None):
    return create_memory_proposal_draft(
        _decision(
            block_type=block_type,
            decision=decision,
            source_pattern_ids=source_pattern_ids,
            source_fact_ids=source_fact_ids,
        ),
        author="proposal-drafter",
    )


def test_valid_proposal_draft_creates_governance_review_required_submission_candidate():
    draft = _draft()

    candidate = create_governance_submission_candidate(draft, reviewer="governance-reviewer")

    assert candidate["submission_kind"] == MEMORY_GOVERNANCE_SUBMISSION_KIND
    assert candidate["submission_status"] == MEMORY_GOVERNANCE_SUBMISSION_STATUS
    assert candidate["routing"] == MEMORY_GOVERNANCE_SUBMISSION_ROUTING
    assert candidate["source_draft_id"] == draft["draft_id"]
    assert candidate["source_decision_id"] == draft["source_decision_id"]
    assert candidate["source_queue_item_id"] == draft["source_queue_item_id"]
    assert candidate["reviewer"] == "governance-reviewer"
    assert candidate["submission_validation"] == {"valid": True, "errors": []}
    assert validate_governance_submission_candidate(candidate) == {"valid": True, "errors": []}
    assert candidate["next_step_recommendation"]["action"] == "create_real_proposal_manually_in_governed_flow"
    assert candidate["next_step_recommendation"]["creates_real_proposals"] is False
    assert candidate["next_step_recommendation"]["submits_to_governance"] is False


def test_invalid_draft_creates_invalid_candidate_with_invalid_proposal_draft():
    draft = _draft(decision="reject")

    candidate = create_governance_submission_candidate(draft)

    assert candidate["submission_validation"]["valid"] is False
    assert "invalid_proposal_draft" in candidate["submission_validation"]["errors"]
    assert candidate["next_step_recommendation"]["action"] == "do_not_create_governance_submission"


def test_missing_payload_preview_creates_invalid_candidate():
    draft = _draft()
    draft.pop("payload_preview")

    candidate = create_governance_submission_candidate(draft)

    assert candidate["submission_validation"]["valid"] is False
    assert "missing_payload_preview" in candidate["submission_validation"]["errors"]
    assert candidate["next_step_recommendation"]["action"] == "do_not_create_governance_submission"


def test_missing_source_ids_creates_invalid_candidate():
    draft = _draft(source_pattern_ids=[], source_fact_ids=[])

    candidate = create_governance_submission_candidate(draft)

    assert candidate["submission_validation"]["valid"] is False
    assert "missing_source_evidence" in candidate["submission_validation"]["errors"]


def test_payload_preview_and_source_ids_are_preserved():
    draft = _draft(source_pattern_ids=["pattern-b", "pattern-a"], source_fact_ids=["fact-b", "fact-a"])

    candidate = create_governance_submission_candidate(draft)

    assert candidate["payload_preview"] == draft["payload_preview"]
    assert candidate["source_pattern_ids"] == ["pattern-a", "pattern-b"]
    assert candidate["source_fact_ids"] == ["fact-a", "fact-b"]
    assert candidate["payload_preview"]["source_pattern_ids"] == ["pattern-a", "pattern-b"]
    assert candidate["payload_preview"]["source_fact_ids"] == ["fact-a", "fact-b"]


def test_input_proposal_draft_is_not_mutated():
    draft = _draft()
    before = deepcopy(draft)

    candidate = create_governance_submission_candidate(draft)
    candidate["source_draft_snapshot"]["payload_preview"]["content"]["nested"]["value"] = "changed"

    assert draft == before


def test_policy_proves_no_memory_config_graph_proposal_or_ledger_writes(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    candidate = create_governance_submission_candidate(_draft())
    explanation = explain_governance_submission_candidate(candidate)
    recommendation = recommend_governance_submission_action(candidate)

    assert candidate["policy"] == MEMORY_PROPOSAL_GOVERNANCE_GATE_POLICY
    assert candidate["policy"]["read_only"] is True
    assert candidate["policy"]["would_write_memory"] is False
    assert candidate["policy"]["would_modify_config"] is False
    assert candidate["policy"]["would_write_graph"] is False
    assert candidate["policy"]["does_not_create_operation_events"] is True
    assert candidate["policy"]["creates_submission_candidates_only"] is True
    assert candidate["policy"]["creates_real_proposals"] is False
    assert candidate["policy"]["applies_proposals"] is False
    assert candidate["policy"]["persists_approvals"] is False
    assert candidate["policy"]["submits_to_governance"] is False
    assert explanation["submitted"] is False
    assert explanation["applied"] is False
    assert explanation["persisted"] is False
    assert explanation["approved"] is False
    assert explanation["created_real_proposal"] is False
    assert explanation["created_operation_event"] is False
    assert recommendation["creates_real_proposals"] is False
    assert recommendation["submits_to_governance"] is False
    assert not (hermes_home / "memory" / "graph" / "memory_graph.sqlite").exists()
    assert not (hermes_home / "memory" / "audit" / "memory_operation_ledger.jsonl").exists()
    assert not (hermes_home / "memory" / "proposals" / "memory_write_proposals.jsonl").exists()


def test_candidate_must_never_be_marked_submitted_applied_persisted_or_approved():
    candidate = create_governance_submission_candidate(_draft())

    for forbidden_key in (
        "submitted",
        "applied",
        "persisted",
        "approved",
        "created_real_proposal",
        "created_operation_event",
    ):
        mutated = deepcopy(candidate)
        mutated[forbidden_key] = True
        validation = validate_governance_submission_candidate(mutated)
        assert validation["valid"] is False
        assert f"{forbidden_key}_must_be_false_or_absent" in validation["errors"]


def test_summary_counts_valid_invalid_submissions_and_by_block_type_status():
    candidates = [
        create_governance_submission_candidate(_draft("procedural_rules")),
        create_governance_submission_candidate(_draft("project_context")),
        create_governance_submission_candidate(_draft("procedural_rules", decision="reject")),
    ]

    summary = summarize_governance_submission_candidates(candidates)

    assert summary["total"] == 3
    assert summary["valid_count"] == 2
    assert summary["invalid_count"] == 1
    assert summary["by_block_type"] == {"procedural_rules": 2, "project_context": 1}
    assert summary["by_status"] == {"governance_review_required": 3}
    assert summary["policy"] == MEMORY_PROPOSAL_GOVERNANCE_GATE_POLICY
