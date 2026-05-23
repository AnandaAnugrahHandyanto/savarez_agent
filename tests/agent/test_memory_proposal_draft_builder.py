from copy import deepcopy

from agent.memory_block_review_queue import create_review_queue_item
from agent.memory_blocks import create_memory_block_candidate
from agent.memory_proposal_draft_builder import (
    MEMORY_PROPOSAL_DRAFT_KIND,
    MEMORY_PROPOSAL_DRAFT_POLICY,
    MEMORY_PROPOSAL_DRAFT_ROUTING,
    MEMORY_PROPOSAL_DRAFT_STATUS,
    create_memory_proposal_draft,
    explain_memory_proposal_draft,
    recommend_memory_proposal_draft_action,
    summarize_memory_proposal_drafts,
    validate_memory_proposal_draft,
)
from agent.memory_review_decision_gate import create_review_decision_candidate, evaluate_review_queue_item


def _decision(block_type="procedural_rules", decision=None, source_pattern_ids=None, source_fact_ids=None):
    block = create_memory_block_candidate(
        block_type,
        {"rules": ["Create draft candidates only."], "nested": {"value": "preserved"}},
        project_scope="memory-fabric",
        source_pattern_ids=source_pattern_ids or ["pattern-1"],
        source_fact_ids=source_fact_ids or ["fact-1"],
        metadata={"source": "test"},
    )
    queue_item = create_review_queue_item(block, reviewer="memory-reviewer")
    if decision is None:
        return evaluate_review_queue_item(queue_item, reviewer="memory-reviewer")
    return create_review_decision_candidate(queue_item, reviewer="memory-reviewer", decision=decision)


def test_approve_to_proposal_decision_creates_valid_draft_review_required_draft():
    candidate = _decision()

    draft = create_memory_proposal_draft(candidate, author="proposal-drafter")

    assert draft["proposal_kind"] == MEMORY_PROPOSAL_DRAFT_KIND
    assert draft["proposal_status"] == MEMORY_PROPOSAL_DRAFT_STATUS
    assert draft["routing"] == MEMORY_PROPOSAL_DRAFT_ROUTING
    assert draft["source_decision_id"] == candidate["decision_id"]
    assert draft["source_queue_item_id"] == candidate["queue_item_id"]
    assert draft["author"] == "proposal-drafter"
    assert draft["draft_validation"] == {"valid": True, "errors": []}
    assert validate_memory_proposal_draft(draft) == {"valid": True, "errors": []}
    assert draft["next_step_recommendation"]["action"] == "submit_to_separate_governed_proposal_flow"
    assert draft["next_step_recommendation"]["creates_real_proposals"] is False


def test_request_more_evidence_creates_invalid_draft_with_more_evidence_required():
    draft = create_memory_proposal_draft(_decision(decision="request_more_evidence"))

    assert draft["draft_validation"]["valid"] is False
    assert "more_evidence_required" in draft["draft_validation"]["errors"]
    assert draft["next_step_recommendation"]["action"] == "do_not_submit_draft"


def test_reject_creates_invalid_draft_with_rejected_decision():
    draft = create_memory_proposal_draft(_decision(decision="reject"))

    assert draft["draft_validation"]["valid"] is False
    assert "rejected_decision" in draft["draft_validation"]["errors"]


def test_defer_creates_invalid_draft_with_deferred_decision():
    draft = create_memory_proposal_draft(_decision(decision="defer"))

    assert draft["draft_validation"]["valid"] is False
    assert "deferred_decision" in draft["draft_validation"]["errors"]


def test_invalid_decision_candidate_creates_invalid_draft():
    draft = create_memory_proposal_draft(_decision(decision="apply_now"))

    assert draft["decision_validation"]["valid"] is False
    assert draft["draft_validation"]["valid"] is False
    assert "invalid_decision_candidate" in draft["draft_validation"]["errors"]


def test_payload_preview_preserves_block_snapshot_fields_needed_for_later_proposal_flow():
    candidate = _decision()

    draft = create_memory_proposal_draft(candidate)
    preview = draft["payload_preview"]
    block_snapshot = candidate["queue_item_snapshot"]["block_snapshot"]

    assert preview["block_id"] == block_snapshot["block_id"]
    assert preview["block_type"] == "procedural_rules"
    assert preview["status"] == "review_required"
    assert preview["project_scope"] == "memory-fabric"
    assert preview["content"] == block_snapshot["content"]
    assert preview["metadata"] == {"source": "test"}
    assert preview["version"] == "0.1"
    assert preview["mutation_policy"] == "proposal_only"
    assert preview["direct_write_allowed"] is False
    assert preview["validity"]["valid"] is True
    assert preview["applied"] is False
    assert preview["persisted"] is False
    assert preview["created_real_proposal"] is False


def test_source_pattern_ids_and_source_fact_ids_are_preserved():
    candidate = _decision(source_pattern_ids=["pattern-b", "pattern-a"], source_fact_ids=["fact-b", "fact-a"])

    draft = create_memory_proposal_draft(candidate)

    assert draft["source_pattern_ids"] == ["pattern-a", "pattern-b"]
    assert draft["source_fact_ids"] == ["fact-a", "fact-b"]
    assert draft["payload_preview"]["source_pattern_ids"] == ["pattern-a", "pattern-b"]
    assert draft["payload_preview"]["source_fact_ids"] == ["fact-a", "fact-b"]


def test_input_decision_candidate_is_not_mutated():
    candidate = _decision()
    before = deepcopy(candidate)

    draft = create_memory_proposal_draft(candidate)
    draft["source_decision_snapshot"]["queue_item_snapshot"]["block_snapshot"]["content"]["nested"]["value"] = "changed"

    assert candidate == before


def test_policy_proves_no_memory_config_graph_proposal_or_ledger_writes(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    draft = create_memory_proposal_draft(_decision())
    explanation = explain_memory_proposal_draft(draft)
    recommendation = recommend_memory_proposal_draft_action(draft)

    assert draft["policy"] == MEMORY_PROPOSAL_DRAFT_POLICY
    assert draft["policy"]["read_only"] is True
    assert draft["policy"]["would_write_memory"] is False
    assert draft["policy"]["would_modify_config"] is False
    assert draft["policy"]["would_write_graph"] is False
    assert draft["policy"]["does_not_create_operation_events"] is True
    assert draft["policy"]["creates_draft_candidates_only"] is True
    assert draft["policy"]["creates_real_proposals"] is False
    assert draft["policy"]["applies_proposals"] is False
    assert draft["policy"]["persists_approvals"] is False
    assert explanation["applied"] is False
    assert explanation["persisted"] is False
    assert explanation["created_real_proposal"] is False
    assert explanation["created_operation_event"] is False
    assert recommendation["creates_real_proposals"] is False
    assert not (hermes_home / "memory" / "graph" / "memory_graph.sqlite").exists()
    assert not (hermes_home / "memory" / "audit" / "memory_operation_ledger.jsonl").exists()
    assert not (hermes_home / "memory" / "proposals" / "memory_write_proposals.jsonl").exists()


def test_summary_counts_valid_invalid_drafts_and_by_block_type():
    drafts = [
        create_memory_proposal_draft(_decision("procedural_rules")),
        create_memory_proposal_draft(_decision("project_context")),
        create_memory_proposal_draft(_decision("procedural_rules", decision="reject")),
    ]

    summary = summarize_memory_proposal_drafts(drafts)

    assert summary["total"] == 3
    assert summary["valid_count"] == 2
    assert summary["invalid_count"] == 1
    assert summary["by_block_type"] == {"procedural_rules": 2, "project_context": 1}
    assert summary["by_status"] == {"draft_review_required": 3}
    assert summary["policy"] == MEMORY_PROPOSAL_DRAFT_POLICY
