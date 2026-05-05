"""Focused tests for the holographic understanding layer."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

from plugins.memory.holographic import HolographicMemoryProvider
from plugins.memory.holographic.cli import cmd_inspect, cmd_query_debug, cmd_reindex, cmd_status
from plugins.memory.holographic.ingestion import drain_understanding_ingest, queue_turn_ingest
from plugins.memory.holographic.retrieval import FactRetriever
from plugins.memory.holographic.store import MemoryStore


class UnavailableEmbeddingProvider:
    name = "openai"
    model = "text-embedding-3-small"

    def is_available(self) -> bool:
        return False

    def embed_one(self, _text: str):
        return None


def _make_store(tmp_path: Path, *, embedding_provider=None) -> MemoryStore:
    return MemoryStore(
        db_path=tmp_path / "memory_store.db",
        embedding_provider=embedding_provider,
    )


def test_search_falls_back_when_embeddings_unavailable(tmp_path):
    store = _make_store(tmp_path, embedding_provider=UnavailableEmbeddingProvider())
    try:
        store.add_fact(
            "Deployment rollback procedure uses feature flags and canary checks.",
            category="project",
            source_channel="tool:fact_store",
        )
        retriever = FactRetriever(store=store, semantic_weight=0.6, keyword_weight=0.2)

        results = retriever.search("deployment rollback", debug=True, limit=3)

        assert results
        assert results[0]["content"].startswith("Deployment rollback procedure")
        assert "debug" in results[0]
        assert results[0]["debug"]["score_breakdown"]["keyword"] > 0
    finally:
        store.close()


def test_add_fact_enriches_metadata_and_links(tmp_path):
    store = _make_store(tmp_path)
    try:
        first_id = store.add_fact(
            "Alice Johnson scheduled the Hermes project review in Shanghai on 2026-04-23 at 3pm.",
            category="project",
            tags="release,review",
            source_channel="telegram:ops",
        )
        second_id = store.add_fact(
            "Hermes project status with Alice Johnson is blocked by the release checklist in Shanghai.",
            category="project",
            source_channel="tool:fact_store",
        )

        fact = store.get_fact(first_id)
        assert fact is not None
        metadata = fact["metadata"]
        assert "Alice Johnson" in metadata["entities"]
        assert "Alice Johnson" in metadata["people"]
        assert any("hermes" in project.lower() for project in metadata["projects"])
        assert "Shanghai" in metadata["locations"]
        assert "2026-04-23" in metadata["dates"]
        assert any("3pm" in value.lower() for value in metadata["times"])

        linked_ids = {link["linked_fact_id"] for link in fact["links"]}
        assert second_id in linked_ids
    finally:
        store.close()


def test_ranking_uses_recency_salience_and_confidence(tmp_path):
    store = _make_store(tmp_path)
    try:
        older_id = store.add_fact(
            "Hermes migration checklist for memory understanding rollout.",
            category="project",
            source_channel="tool:fact_store",
            source_confidence=0.4,
            salience_score=0.3,
        )
        newer_id = store.add_fact(
            "Hermes migration checklist for memory understanding rollout with production blockers.",
            category="project",
            source_channel="builtin:user",
            source_confidence=0.95,
            salience_score=0.95,
        )

        store._conn.execute(
            "UPDATE facts SET updated_at = '2024-01-01 00:00:00' WHERE fact_id = ?",
            (older_id,),
        )
        store._conn.commit()

        retriever = FactRetriever(store=store, temporal_decay_half_life=30)
        results = retriever.search("Hermes migration checklist", debug=True, limit=5)

        assert results[0]["fact_id"] == newer_id
        assert results[0]["debug"]["score_breakdown"]["salience"] > results[1]["debug"]["score_breakdown"]["salience"]
        assert results[0]["debug"]["score_breakdown"]["confidence"] > results[1]["debug"]["score_breakdown"]["confidence"]
    finally:
        store.close()


def test_search_debug_output_contains_explanations(tmp_path):
    store = _make_store(tmp_path)
    try:
        store.add_fact(
            "Alice Johnson prefers the Hermes release checklist before every production deploy.",
            category="user_pref",
            source_channel="builtin:user",
        )
        retriever = FactRetriever(store=store)

        results = retriever.search("What does Alice Johnson prefer for Hermes deploys?", debug=True, limit=3)

        assert results
        debug = results[0]["debug"]
        assert debug["why"]
        assert set(debug["score_breakdown"]) == {"semantic", "keyword", "recency", "salience", "confidence", "weighted"}
        assert "Alice Johnson" in debug["matched_entities"]
        assert any("alice johnson" in cluster for cluster in debug["matched_clusters"])
        assert isinstance(debug["related_memory_ids"], list)
        assert "recency_contribution" in debug
    finally:
        store.close()


def test_rebuild_understanding_index_restores_metadata_and_links(tmp_path):
    store = _make_store(tmp_path)
    try:
        first_id = store.add_fact(
            "Hermes project launch review with Alice Johnson in Shanghai.",
            category="project",
            source_channel="telegram:ops",
        )
        second_id = store.add_fact(
            "Alice Johnson asked for the Hermes launch review checklist.",
            category="project",
            source_channel="tool:fact_store",
        )

        store._conn.execute("UPDATE facts SET metadata_json = '{}', hrr_vector = NULL")
        store._conn.execute("DELETE FROM fact_links")
        store._conn.commit()

        result = store.rebuild_understanding_index(include_embeddings=False, refresh_links=True)

        assert result["facts_reindexed"] == 2
        fact = store.get_fact(first_id)
        assert fact is not None
        assert fact["metadata"]["entities"]
        linked_ids = {link["linked_fact_id"] for link in fact["links"]}
        assert second_id in linked_ids
    finally:
        store.close()


def test_operator_cli_commands_work(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "memory": {"provider": "holographic"},
                "plugins": {
                    "hermes-memory-store": {
                        "db_path": str(tmp_path / "memory_store.db"),
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    store = _make_store(tmp_path)
    try:
        fact_id = store.add_fact(
            "Alice Johnson prefers the Hermes deploy checklist in Shanghai.",
            category="user_pref",
            source_channel="builtin:user",
        )
    finally:
        store.close()

    cmd_status(SimpleNamespace())
    status_out = capsys.readouterr().out
    assert "Holographic memory index status" in status_out
    assert "Pending ingest" in status_out

    cmd_inspect(SimpleNamespace(fact_id=str(fact_id)))
    inspect_out = capsys.readouterr().out
    assert "Alice Johnson prefers the Hermes deploy checklist" in inspect_out
    assert "Cluster keys" in inspect_out

    cmd_query_debug(
        SimpleNamespace(
            query="Alice Johnson deploy checklist",
            category=None,
            min_trust=0.0,
            limit=2,
        )
    )
    debug_out = capsys.readouterr().out
    assert '"matched_entities"' in debug_out
    assert '"matched_clusters"' in debug_out


def test_deferred_turn_ingest_updates_status_and_facts(tmp_path):
    provider = HolographicMemoryProvider(
        config={
            "db_path": str(tmp_path / "memory_store.db"),
            "deferred_ingest": True,
            "turn_understanding": True,
            "ingest_batch_size": 2,
        }
    )
    provider.initialize(session_id="sess-turn", platform="cli")
    try:
        provider.sync_turn(
            "I prefer the Hermes deploy checklist in Shanghai before every release.",
            "Noted.",
            session_id="sess-turn",
        )
        status = provider._store.index_status()
        assert status["pending_ingest_items"] == 1
        assert status["last_ingest_success"] is None

        provider.queue_prefetch("Hermes deploy checklist", session_id="sess-turn")
        status = provider._store.index_status()
        assert status["pending_ingest_items"] == 0
        assert status["failed_ingest_items"] == 0
        assert status["last_ingest_success"] is not None

        facts = provider._store.list_facts(limit=10)
        assert any(fact["source_channel"].startswith("turn_understanding:user_pref") for fact in facts)
    finally:
        provider.shutdown()


def test_deferred_ingest_failure_is_visible_and_retryable(tmp_path, monkeypatch):
    store = _make_store(tmp_path)
    try:
        cfg = {
            "deferred_ingest": True,
            "turn_understanding": True,
            "ingest_retry_delay_seconds": 1,
        }
        queue_turn_ingest(
            store,
            cfg,
            session_id="sess-fail",
            user_content="We decided the Hermes project needs a rollout checklist.",
            assistant_content="",
        )

        original_add_fact = store.add_fact
        state = {"calls": 0}

        def flaky_add_fact(*args, **kwargs):
            state["calls"] += 1
            if state["calls"] == 1:
                raise RuntimeError("synthetic ingest failure")
            return original_add_fact(*args, **kwargs)

        monkeypatch.setattr(store, "add_fact", flaky_add_fact)

        first = drain_understanding_ingest(store, cfg, reason="test_failure")
        assert first["failed"] == 1

        status = store.index_status()
        assert status["failed_ingest_items"] == 1
        assert "synthetic ingest failure" in status["last_ingest_error"]

        store._conn.execute("UPDATE understanding_ingest_queue SET available_at = CURRENT_TIMESTAMP")
        store._conn.commit()

        second = drain_understanding_ingest(store, cfg, reason="test_retry")
        assert second["processed"] == 1

        status = store.index_status()
        assert status["failed_ingest_items"] == 0
        assert status["pending_ingest_items"] == 0
        assert status["last_ingest_success"] is not None
    finally:
        store.close()


def test_stale_processing_ingest_is_recovered_on_startup(tmp_path):
    store = _make_store(tmp_path)
    try:
        queue_turn_ingest(
            store,
            {"deferred_ingest": True, "turn_understanding": True},
            session_id="sess-stale",
            user_content="We decided the Hermes project needs a rollout checklist.",
            assistant_content="",
        )
        claimed = store.claim_ingest_batch(limit=1)
        assert claimed
        ingest_id = int(claimed[0]["ingest_id"])
        store._conn.execute(
            """
            UPDATE understanding_ingest_queue
            SET started_at = '2000-01-01 00:00:00'
            WHERE ingest_id = ?
            """,
            (ingest_id,),
        )
        store._conn.commit()
    finally:
        store.close()

    recovered = _make_store(tmp_path)
    try:
        status = recovered.index_status()
        assert status["failed_ingest_items"] == 1
        assert status["last_ingest_error"] == "Recovered interrupted ingest attempt"
    finally:
        recovered.close()


def test_session_auto_extract_uses_deferred_ingest(tmp_path):
    provider = HolographicMemoryProvider(
        config={
            "db_path": str(tmp_path / "memory_store.db"),
            "auto_extract": True,
            "deferred_ingest": True,
            "ingest_batch_size": 4,
        }
    )
    provider.initialize(session_id="sess-end", platform="cli")
    try:
        provider.on_session_end(
            [
                {
                    "role": "user",
                    "content": "We decided the Hermes project uses canary checks in Shanghai.",
                }
            ]
        )

        status = provider._store.index_status()
        assert status["pending_ingest_items"] == 0
        assert status["last_ingest_success"] is not None

        facts = provider._store.list_facts(limit=10)
        assert any(fact["source_channel"].startswith("session_auto_extract:project") for fact in facts)
    finally:
        provider.shutdown()


def test_canonicalization_clusters_project_aliases(tmp_path):
    store = _make_store(tmp_path)
    try:
        first_id = store.add_fact(
            "Hermes project rollout is blocked by the release checklist.",
            category="project",
            source_channel="tool:fact_store",
        )
        second_id = store.add_fact(
            "The hermes-project repo needs Alice Johnson for the rollout.",
            category="project",
            source_channel="tool:fact_store",
        )

        first = store.get_fact(first_id)
        second = store.get_fact(second_id)
        assert first is not None
        assert second is not None
        assert "hermes" in first["metadata"]["project_keys"]
        assert "hermes" in second["metadata"]["project_keys"]

        linked_ids = {link["linked_fact_id"] for link in first["links"]}
        assert second_id in linked_ids
    finally:
        store.close()


def test_reindex_drains_pending_ingest(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "memory": {"provider": "holographic"},
                "plugins": {
                    "hermes-memory-store": {
                        "db_path": str(tmp_path / "memory_store.db"),
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    store = _make_store(tmp_path)
    try:
        queue_turn_ingest(
            store,
            {"deferred_ingest": True, "turn_understanding": True},
            session_id="sess-reindex",
            user_content="I prefer the Hermes deploy checklist before each release.",
            assistant_content="",
        )
    finally:
        store.close()

    cmd_reindex(
        SimpleNamespace(
            include_embeddings=False,
            refresh_links=True,
            drain_pending=True,
        )
    )
    reindex_out = capsys.readouterr().out
    assert "Pending ingest:" in reindex_out

    store = _make_store(tmp_path)
    try:
        status = store.index_status()
        facts = store.list_facts(limit=10)
        assert status["pending_ingest_items"] == 0
        assert any(fact["source_channel"].startswith("turn_understanding:user_pref") for fact in facts)
    finally:
        store.close()
