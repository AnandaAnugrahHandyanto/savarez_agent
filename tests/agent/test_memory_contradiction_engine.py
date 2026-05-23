from copy import deepcopy

from agent.memory_bitemporal_fact_graph import BITEMPORAL_FACT_GRAPH_POLICY
from agent.memory_contradiction_engine import (
    CONTRADICTION_ENGINE_POLICY,
    RELATION_LABELS,
    classify_fact_relation,
    detect_contradiction_candidates,
    explain_contradiction_group,
    group_contradictions,
    recommend_contradiction_action,
)


def _fact(**overrides):
    base = {
        "fact_id": "fact-1",
        "subject": "Hermes Memory Fabric",
        "predicate": "foundation",
        "object": "Bi-temporal Fact Graph v0.1",
        "project_id": "memory-fabric",
        "source_episode_id": "episode-1",
        "provenance": {"source": "bench"},
        "confidence": 0.9,
        "valid_from": "2026-05-23T00:00:00Z",
        "system_created_at": "2026-05-23T08:00:00Z",
        "governance": BITEMPORAL_FACT_GRAPH_POLICY,
    }
    base.update(overrides)
    return base


def test_relation_labels_include_required_values():
    assert set(RELATION_LABELS) == {"supports", "updates", "contradicts", "unrelated", "needs_review"}


def test_same_fact_supports():
    existing = _fact(fact_id="existing")
    candidate = _fact(fact_id="candidate")

    relation = classify_fact_relation(existing, candidate)

    assert relation["relation"] == "supports"
    assert relation["same_subject"] is True
    assert relation["same_predicate"] is True
    assert relation["same_project_id"] is True
    assert relation["policy"] == CONTRADICTION_ENGINE_POLICY


def test_same_subject_predicate_project_different_object_contradicts():
    existing = _fact(fact_id="existing", object="Hybrid Retrieval Fusion v0.1")
    candidate = _fact(fact_id="candidate", object="Contradiction Engine v0.1")

    relation = classify_fact_relation(existing, candidate)

    assert relation["relation"] == "contradicts"
    assert relation["same_object"] is False
    assert "same_subject_predicate_project_with_different_object" in relation["reasons"]


def test_newer_valid_candidate_updates_older_expired_fact():
    existing = _fact(
        fact_id="old",
        object="Bi-temporal Fact Graph v0.1",
        valid_from="2026-05-20T00:00:00Z",
        valid_until="2026-05-23T00:00:00Z",
        system_invalidated_at="2026-05-23T00:00:00Z",
    )
    candidate = _fact(
        fact_id="new",
        object="Contradiction Engine v0.1",
        valid_from="2026-05-23T00:00:00Z",
        system_created_at="2026-05-23T10:00:00Z",
        supersedes=["old"],
    )

    relation = classify_fact_relation(existing, candidate)

    assert relation["relation"] == "updates"
    assert relation["validity_windows_overlap"] is False


def test_different_project_is_unrelated():
    existing = _fact(fact_id="existing", project_id="memory-fabric")
    candidate = _fact(fact_id="candidate", project_id="openclaw")

    relation = classify_fact_relation(existing, candidate)

    assert relation["relation"] == "unrelated"
    assert relation["same_project_id"] is False


def test_missing_provenance_creates_needs_review_rather_than_hard_allow():
    existing = _fact(fact_id="existing")
    candidate = _fact(fact_id="candidate", provenance=None, source_episode_id=None)

    relation = classify_fact_relation(existing, candidate)

    assert relation["relation"] == "needs_review"
    assert "missing_provenance" in relation["risks"]


def test_unsafe_governance_creates_reviewable_contradiction_risk():
    existing = _fact(fact_id="existing", object="external exposure allowed")
    candidate = _fact(
        fact_id="candidate",
        object="external exposure blocked",
        governance={"read_only": False, "would_write_memory": True},
    )

    relation = classify_fact_relation(existing, candidate)

    assert relation["relation"] == "needs_review"
    assert "same_subject_predicate_project_with_different_object" in relation["reasons"]
    assert "unsafe_governance:would_write_memory" in relation["risks"]
    assert "unsafe_governance:read_only" in relation["risks"]


def test_input_facts_are_not_mutated():
    existing = _fact(fact_id="existing", object="allowed")
    candidate = _fact(fact_id="candidate", object="blocked")
    existing_before = deepcopy(existing)
    candidate_before = deepcopy(candidate)

    classify_fact_relation(existing, candidate)
    group_contradictions([existing, candidate])

    assert existing == existing_before
    assert candidate == candidate_before


def test_detect_and_group_contradictions_return_review_recommendation():
    existing = _fact(fact_id="allowed", object="external-channel memory exposure allowed")
    candidate = _fact(fact_id="blocked", object="external-channel memory exposure blocked")

    detected = detect_contradiction_candidates([existing], [candidate])
    groups = group_contradictions([existing, candidate])
    explanation = explain_contradiction_group(groups[0])
    action = recommend_contradiction_action(groups[0])

    assert [item["relation"] for item in detected] == ["contradicts"]
    assert len(groups) == 1
    assert groups[0]["objects"] == [
        "external-channel memory exposure allowed",
        "external-channel memory exposure blocked",
    ]
    assert explanation["recommended_action"]["action"] == "review_contradiction"
    assert action["creates_review_recommendations_only"] is True


def test_policy_proves_no_memory_config_graph_or_ledger_writes(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    relation = classify_fact_relation(_fact(fact_id="existing"), _fact(fact_id="candidate"))

    assert relation["policy"] == CONTRADICTION_ENGINE_POLICY
    assert relation["policy"]["read_only"] is True
    assert relation["policy"]["would_write_memory"] is False
    assert relation["policy"]["would_modify_config"] is False
    assert relation["policy"]["would_write_graph"] is False
    assert relation["policy"]["does_not_create_operation_events"] is True
    assert relation["policy"]["creates_review_recommendations_only"] is True
    assert not (hermes_home / "memory" / "graph" / "memory_graph.sqlite").exists()
    assert not (hermes_home / "memory" / "audit" / "memory_operation_ledger.jsonl").exists()
    assert not (hermes_home / "memory" / "proposals" / "memory_write_proposals.jsonl").exists()
