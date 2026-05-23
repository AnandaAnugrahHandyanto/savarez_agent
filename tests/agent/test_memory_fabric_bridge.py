from agent.memory_fabric_bridge import (
    memory_boundary_allowlist_audit,
    MEMORY_EVOLUTION_TIERS,
    memory_bridge_status,
    memory_evolution_status,
    memory_federation_gate,
    memory_policy_outcome_monitor,
    memory_recall_quality_evaluate,
)


def test_memory_evolution_tiers_are_fixed():
    names = [tier["name"] for tier in MEMORY_EVOLUTION_TIERS]

    assert names == [
        "星火记忆",
        "星点记忆",
        "星链记忆",
        "星图记忆",
        "星河记忆",
        "星辰记忆",
        "星域记忆",
        "星穹记忆",
        "星海记忆",
        "星界记忆",
        "星枢记忆",
        "星律记忆",
        "星魂记忆",
        "星宙记忆",
        "星源记忆",
    ]


def test_memory_evolution_status_is_read_only():
    result = memory_evolution_status()

    assert result["success"] is True
    assert len(result["taxonomy"]) == 15
    assert result["current"]["level"] >= 1
    assert "recall_quality" in result
    assert result["policy"]["taxonomy_is_fixed"] is True
    assert result["policy"]["status_is_read_only"] is True
    assert result["read_only_memory"] is True
    assert result["would_mutate_memory"] is False
    assert result["would_modify_config"] is False


def test_memory_bridge_status_includes_graph_and_policy_surfaces():
    result = memory_bridge_status()

    assert result["success"] is True
    assert "graph" in result["surfaces"]
    assert "policy_proposals" in result["surfaces"]
    assert result["policy"]["writes_are_proposal_only"] is True


def test_memory_federation_gate_blocks_direct_writes():
    result = memory_federation_gate(
        client="codex",
        operation="direct_write",
        target_scope="memory",
    )

    assert result["success"] is True
    assert result["decision"] == "block"
    assert result["allowed"] is False


def test_memory_policy_outcome_monitor_is_read_only():
    result = memory_policy_outcome_monitor(limit=10, stale_after_hours=72)

    assert result["success"] is True
    assert result["policy"]["monitor_is_read_only"] is True
    assert result["read_only_memory"] is True
    assert result["would_modify_config"] is False


def test_memory_recall_quality_evaluate_is_read_only():
    result = memory_recall_quality_evaluate(queries="memory,policy", limit=3)

    assert result["success"] is True
    assert result["evaluation_type"] == "hermes_memory_recall_quality_evaluate"
    assert result["summary"]["benchmark_query_count"] == 2
    assert result["policy"]["evaluation_is_read_only"] is True
    assert result["policy"]["does_not_append_ledger_events"] is True
    assert result["read_only_memory"] is True
    assert result["would_mutate_memory"] is False


def test_memory_boundary_allowlist_audit_is_read_only_and_ready_for_star_realm():
    result = memory_boundary_allowlist_audit(log_limit=200)

    assert result["success"] is True
    assert result["audit_type"] == "hermes_memory_boundary_allowlist_audit"
    assert result["ready"] is True
    assert result["boundary_readiness_score"] >= 90
    assert result["reviewed"] is True
    assert result["unreviewed_allowlists"] == []
    assert result["policy"]["audit_is_read_only"] is True
    assert result["policy"]["does_not_modify_config"] is True
    assert result["policy"]["does_not_write_memory"] is True
    assert result["policy"]["does_not_write_graph"] is True
    assert result["policy"]["does_not_approve_allowlists"] is True
    assert result["policy"]["does_not_enable_external_recall"] is True
    assert result["would_mutate_memory"] is False
    assert result["would_modify_config"] is False
    assert result["would_write_graph"] is False


def test_memory_evolution_reaches_star_realm_after_boundary_review(monkeypatch):
    # This readiness test intentionally checks the real local Hermes home.
    # The global pytest fixture isolates HERMES_HOME into a tempdir by default,
    # which is correct for most tests but would hide the real Memory Fabric.
    monkeypatch.delenv("HERMES_HOME", raising=False)

    result = memory_evolution_status()

    assert result["success"] is True
    assert result["current"]["level"] >= 10
    assert result["current"]["name"] == "星界记忆"
    assert result["evidence"]["boundary_allowlists_reviewed"] is True
    assert result["next"]["level"] == 11
