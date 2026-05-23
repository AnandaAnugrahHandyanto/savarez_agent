from agent.memory_bitemporal_fact_graph import (
    BITEMPORAL_FACT_GRAPH_POLICY,
    detect_fact_contradictions,
    explain_fact_lineage,
    fact_is_valid_at,
    normalize_fact,
    select_current_facts,
    supersede_fact,
)


def _fact(**overrides):
    base = {
        "fact_id": "fact-1",
        "subject": "Hermes Memory Fabric",
        "predicate": "retrieval_method",
        "object": "Hybrid Retrieval Fusion v0.1",
        "project_id": "memory-fabric",
        "source_episode_id": "episode-1",
        "provenance": {"source": "bench"},
        "confidence": 0.9,
        "valid_from": "2026-05-01T00:00:00Z",
        "system_created_at": "2026-05-20T00:00:00Z",
        "governance": BITEMPORAL_FACT_GRAPH_POLICY,
    }
    base.update(overrides)
    return base


def test_current_fact_selection_by_valid_from_and_valid_until():
    current = _fact(fact_id="current", object="Bi-temporal Fact Graph v0.1", valid_from="2026-05-22T00:00:00Z")
    expired = _fact(fact_id="expired", valid_until="2026-05-10T00:00:00Z")
    future = _fact(fact_id="future", object="Future Graph", valid_from="2026-06-01T00:00:00Z")

    selected = select_current_facts([expired, current, future], "2026-05-23T00:00:00Z")

    assert [fact.fact_id for fact in selected] == ["current"]


def test_old_fact_becomes_invalid_after_valid_until():
    old = normalize_fact(_fact(valid_until="2026-05-10T00:00:00Z"))

    assert fact_is_valid_at(old, "2026-05-09T23:59:59Z") is True
    assert fact_is_valid_at(old, "2026-05-10T00:00:00Z") is False
    assert fact_is_valid_at(old, "2026-05-11T00:00:00Z") is False


def test_system_created_at_is_separate_from_valid_from():
    fact = normalize_fact(
        _fact(
            fact_id="retroactive",
            valid_from="2026-04-01T00:00:00Z",
            system_created_at="2026-05-20T00:00:00Z",
        )
    )

    assert fact.valid_from.isoformat() != fact.system_created_at.isoformat()
    assert fact_is_valid_at(fact, "2026-04-15T00:00:00Z") is True


def test_supersede_fact_returns_copies_without_mutation():
    old = normalize_fact(_fact(fact_id="old", object="Hybrid Retrieval Fusion v0.1"))
    new = normalize_fact(_fact(fact_id="new", object="Bi-temporal Fact Graph v0.1", valid_from=None))

    updated_old, updated_new = supersede_fact(old, new, "2026-05-23T00:00:00Z")

    assert old.valid_until is None
    assert old.system_invalidated_at is None
    assert new.supersedes == ()
    assert updated_old.valid_until.isoformat() == "2026-05-23T00:00:00+00:00"
    assert updated_old.system_invalidated_at.isoformat() == "2026-05-23T00:00:00+00:00"
    assert updated_new.valid_from.isoformat() == "2026-05-23T00:00:00+00:00"
    assert updated_new.supersedes == ("old",)


def test_contradiction_detection_groups_conflicting_subject_predicate_project_objects():
    facts = [
        _fact(fact_id="allowed", object="allowed", project_id="memory-fabric"),
        _fact(fact_id="blocked", object="blocked", project_id="memory-fabric"),
        _fact(fact_id="other-project", object="allowed", project_id="openclaw"),
    ]

    contradictions = detect_fact_contradictions(facts)

    assert len(contradictions) == 1
    assert contradictions[0]["project_id"] == "memory-fabric"
    assert contradictions[0]["fact_ids"] == ["allowed", "blocked"]
    assert contradictions[0]["objects"] == ["allowed", "blocked"]


def test_project_scope_isolation():
    facts = [
        _fact(fact_id="memory-fabric", object="use bitemporal graph", project_id="memory-fabric"),
        _fact(fact_id="openclaw", object="use routing metrics", project_id="openclaw"),
    ]

    selected = select_current_facts(facts, "2026-05-23T00:00:00Z", project_scope="openclaw")

    assert [fact.fact_id for fact in selected] == ["openclaw"]


def test_provenance_and_source_episode_id_are_preserved():
    fact = normalize_fact(
        _fact(
            source_episode_id="episode-memory-bench",
            provenance={"fixture": "smoke_cases", "lineage": ["design-doc"]},
        )
    )

    assert fact.source_episode_id == "episode-memory-bench"
    assert fact.provenance == {"fixture": "smoke_cases", "lineage": ["design-doc"]}


def test_lineage_keeps_historical_fact_explainable_after_new_fact_wins():
    old = normalize_fact(_fact(fact_id="old", object="Temporal preference only"))
    new = normalize_fact(_fact(fact_id="new", object="Bi-temporal Fact Graph v0.1", supersedes=["old"]))

    explanation = explain_fact_lineage("new", [old, new])

    assert explanation["found"] is True
    assert explanation["fact"]["fact_id"] == "new"
    assert [fact["fact_id"] for fact in explanation["lineage"]] == ["old"]
    assert explanation["policy"] == BITEMPORAL_FACT_GRAPH_POLICY


def test_policy_proves_no_memory_config_graph_or_ledger_writes(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    result = explain_fact_lineage("missing", [])

    assert result["policy"] == BITEMPORAL_FACT_GRAPH_POLICY
    assert result["policy"]["read_only"] is True
    assert result["policy"]["would_write_memory"] is False
    assert result["policy"]["would_modify_config"] is False
    assert result["policy"]["would_write_graph"] is False
    assert result["policy"]["does_not_create_operation_events"] is True
    assert not (hermes_home / "memory" / "graph" / "memory_graph.sqlite").exists()
    assert not (hermes_home / "memory" / "audit" / "memory_operation_ledger.jsonl").exists()
    assert not (hermes_home / "memory" / "proposals" / "memory_write_proposals.jsonl").exists()
