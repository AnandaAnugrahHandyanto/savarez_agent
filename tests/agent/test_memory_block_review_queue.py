from copy import deepcopy

from agent.memory_block_review_queue import (
    MEMORY_BLOCK_REVIEW_QUEUE_POLICY,
    build_review_queue,
    create_review_queue_item,
    explain_review_queue_item,
    prioritize_review_queue,
    recommend_review_queue_action,
    summarize_review_queue,
    validate_review_queue_item,
)
from agent.memory_blocks import create_memory_block_candidate


def test_valid_block_becomes_pending_review_queue_item():
    block = create_memory_block_candidate("project_context", {"text": "Hermes Memory Fabric foundation."})

    item = create_review_queue_item(block, reviewer="human-reviewer")

    assert item["status"] == "pending_review"
    assert item["block_id"] == block["block_id"]
    assert item["reviewer"] == "human-reviewer"
    assert item["validation"] == {"valid": True, "errors": []}
    assert item["recommended_action"]["action"] == "review_candidate"
    assert validate_review_queue_item(item) == {"valid": True, "errors": []}


def test_invalid_block_becomes_high_priority():
    block = create_memory_block_candidate("unsupported", {"text": "invalid"})

    item = create_review_queue_item(block)

    assert item["priority"] == 100
    assert item["risk_level"] == "high"
    assert item["validation"]["valid"] is False
    assert recommend_review_queue_action(item)["action"] == "review_and_reject_invalid_block"


def test_safety_policy_gets_high_risk_and_high_priority():
    block = create_memory_block_candidate("safety_policy", "Never write memory directly.")

    item = create_review_queue_item(block)

    assert item["priority"] == 90
    assert item["risk_level"] == "high"


def test_procedural_rules_gets_medium_risk():
    block = create_memory_block_candidate("procedural_rules", {"rules": ["Review before applying."]})

    item = create_review_queue_item(block)

    assert item["priority"] == 70
    assert item["risk_level"] == "medium"


def test_priority_sorting_is_deterministic():
    low = create_review_queue_item(create_memory_block_candidate("project_context", "low"))
    high = create_review_queue_item(create_memory_block_candidate("safety_policy", "high"))
    medium_a = create_review_queue_item(create_memory_block_candidate("persona", "medium-a"))
    medium_b = create_review_queue_item(create_memory_block_candidate("persona", "medium-b"))
    items = [medium_b, low, high, medium_a]

    first = prioritize_review_queue(items)
    second = prioritize_review_queue(list(reversed(items)))

    assert [item["priority"] for item in first] == [90, 60, 60, 40]
    assert [item["queue_item_id"] for item in first] == [item["queue_item_id"] for item in second]


def test_summary_counts_total_risk_block_type_and_invalid_count():
    items = build_review_queue(
        [
            create_memory_block_candidate("safety_policy", "high"),
            create_memory_block_candidate("procedural_rules", {"rules": ["medium"]}),
            create_memory_block_candidate("project_context", "low"),
            create_memory_block_candidate("unsupported", "invalid"),
        ]
    )

    summary = summarize_review_queue(items)

    assert summary["total"] == 4
    assert summary["by_risk"] == {"high": 2, "medium": 1, "low": 1}
    assert summary["by_block_type"]["safety_policy"] == 1
    assert summary["by_block_type"]["procedural_rules"] == 1
    assert summary["by_block_type"]["project_context"] == 1
    assert summary["by_block_type"]["unsupported"] == 1
    assert summary["invalid_count"] == 1


def test_queue_item_preserves_source_pattern_ids_and_source_fact_ids():
    block = create_memory_block_candidate(
        "procedural_rules",
        {"rules": ["Preserve sources."]},
        source_pattern_ids=["pattern-b", "pattern-a"],
        source_fact_ids=["fact-2", "fact-1"],
    )

    item = create_review_queue_item(block)

    assert item["source_pattern_ids"] == ["pattern-a", "pattern-b"]
    assert item["source_fact_ids"] == ["fact-1", "fact-2"]
    assert item["block_snapshot"]["source_pattern_ids"] == ["pattern-a", "pattern-b"]
    assert item["block_snapshot"]["source_fact_ids"] == ["fact-1", "fact-2"]


def test_input_blocks_are_not_mutated():
    block = create_memory_block_candidate(
        "collaboration_style",
        {"nested": ["review later"]},
        source_pattern_ids=["pattern-1"],
    )
    before = deepcopy(block)

    item = create_review_queue_item(block)
    item["block_snapshot"]["content"]["nested"].append("mutated-copy")

    assert block == before


def test_policy_proves_no_memory_config_graph_or_ledger_writes(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    block = create_memory_block_candidate("procedural_rules", {"rules": ["Only create review candidates."]})

    item = create_review_queue_item(block)
    explanation = explain_review_queue_item(item)
    recommendation = recommend_review_queue_action(item)

    assert item["policy"] == MEMORY_BLOCK_REVIEW_QUEUE_POLICY
    assert item["policy"]["read_only"] is True
    assert item["policy"]["would_write_memory"] is False
    assert item["policy"]["would_modify_config"] is False
    assert item["policy"]["would_write_graph"] is False
    assert item["policy"]["does_not_create_operation_events"] is True
    assert item["policy"]["creates_review_candidates_only"] is True
    assert item["policy"]["applies_blocks"] is False
    assert explanation["applied"] is False
    assert recommendation["applies_blocks"] is False
    assert not (hermes_home / "memory" / "graph" / "memory_graph.sqlite").exists()
    assert not (hermes_home / "memory" / "audit" / "memory_operation_ledger.jsonl").exists()
    assert not (hermes_home / "memory" / "proposals" / "memory_write_proposals.jsonl").exists()
