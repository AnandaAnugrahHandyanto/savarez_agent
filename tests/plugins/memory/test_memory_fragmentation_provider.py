import json
from pathlib import Path

import plugins.memory.memory_fragmentation as mf_module
from plugins.memory.memory_fragmentation import (
    MemoryFragmentationProvider,
    _load_memory_fragmentation_config,
    _save_memory_fragmentation_config,
)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class FakeEmbeddingBackend:
    name = "fake"
    model = "fake-semantic-v1"
    dimensions = 2

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def embed(self, text: str) -> list[float]:
        if self.fail:
            raise RuntimeError("embedding backend unavailable")
        lowered = text.lower()
        if any(term in lowered for term in ("allocation planner", "downside stability", "drawdown metrics", "quant strategy")):
            return [1.0, 0.0]
        if "shared semantic" in lowered:
            return [0.0, 1.0]
        return [0.0, 0.0]


class RecordingEmbeddingBackend:
    name = "fake"
    model = "fake-semantic-v1"
    dimensions = 2

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [1.0, 0.0]


def _enable_fake_embeddings(tmp_path: Path, monkeypatch, *, fail: bool = False) -> None:
    _save_memory_fragmentation_config(
        {
            "embeddings": {
                "enabled": True,
                "provider": "fake",
                "model": "fake-semantic-v1",
                "dimensions": 2,
                "similarity_threshold": 0.75,
                "max_neighbors_per_record": 5,
            }
        },
        str(tmp_path),
    )
    monkeypatch.setattr(mf_module, "_create_embedding_backend", lambda _config: FakeEmbeddingBackend(fail=fail))


def test_load_and_save_config_round_trip(tmp_path):
    _save_memory_fragmentation_config(
        {
            "enabled": True,
            "max_recall_items": 3,
            "summary_budget_chars": 240,
            "min_turn_chars": 42,
        },
        str(tmp_path),
    )

    cfg = _load_memory_fragmentation_config(str(tmp_path))

    assert cfg["schema_version"] == "v2"
    assert cfg["enabled"] is True
    assert cfg["function"] == "key-summary-full-memory-fragmentation"
    assert cfg["canonical_key"] == "raw human-readable title"
    assert cfg["identity_policy"] == "raw_key_is_canonical; tokenizer_views_are_auxiliary"
    assert cfg["retrieval_policy"]["lexical_method"] == "bm25"
    assert cfg["retrieval_policy"]["hybrid_fusion"] == "weighted_linear"
    assert cfg["embeddings"]["enabled"] is False
    assert cfg["embeddings"]["lazy_rebuild"] == "local_only"
    assert cfg["embeddings"]["retry_failed"] is False
    assert cfg["embeddings"]["embed_full_content"] is False
    assert cfg["embeddings"]["embed_sensitive_records"] is False
    assert cfg["relations"]["embedding_neighbors"] is True
    assert cfg["max_recall_items"] == 3
    assert cfg["summary_budget_chars"] == 240
    assert cfg["min_turn_chars"] == 42


def test_save_config_uses_fail_closed_boolean_and_numeric_parsing(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.save_config(
        {
            "enabled": "disabled",
            "max_recall_items": float("inf"),
            "summary_budget_chars": "bad",
            "min_turn_chars": 12,
        },
        str(tmp_path),
    )

    cfg = _load_memory_fragmentation_config(str(tmp_path))

    assert cfg["enabled"] is False
    assert cfg["max_recall_items"] == 5
    assert cfg["summary_budget_chars"] == 520
    assert cfg["min_turn_chars"] == 12

    provider.save_config({"enabled": "not-a-bool"}, str(tmp_path))
    cfg = _load_memory_fragmentation_config(str(tmp_path))
    assert cfg["enabled"] is False

    provider.save_config({"enabled": float("inf")}, str(tmp_path))
    cfg = _load_memory_fragmentation_config(str(tmp_path))
    assert cfg["enabled"] is False


def test_post_setup_creates_config_and_activates_provider(tmp_path, monkeypatch):
    saved_configs = []

    def fake_save_config(config):
        saved_configs.append(config)

    monkeypatch.setattr("hermes_cli.config.save_config", fake_save_config)
    provider = MemoryFragmentationProvider()
    config = {"memory": {"provider": ""}}

    provider.post_setup(str(tmp_path), config)

    assert config["memory"]["provider"] == "memory_fragmentation"
    assert saved_configs == [config]
    cfg = _load_memory_fragmentation_config(str(tmp_path))
    assert cfg["enabled"] is True
    assert (tmp_path / "memory_fragmentation" / "config.json").exists()


def test_sync_turn_writes_key_summary_full_fragment(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize(
        "session-1",
        hermes_home=str(tmp_path),
        platform="cli",
        user_id="user-1",
        agent_identity="coder",
    )

    provider.sync_turn(
        "Please build a quant strategy with momentum and volatility signals.",
        "Completed the quant strategy work. Touched src/strategies/momentum.py and reports/performance.md. CAGR 24%, Sortino 2.1, max drawdown -9%.",
        session_id="session-1",
    )

    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")
    assert len(records) == 1
    record = records[0]
    assert record["session_id"] == "session-1"
    assert record["user_id"] == "user-1"
    assert record["memory_type"] == "conversation_round"
    assert record["status"] == "active"
    assert record["raw_key"]
    assert not record["raw_key"].startswith("mem_")
    assert "quant" in record["raw_key"].lower()
    assert record["summary_short"]
    assert record["summary_medium"]
    assert record["full_content_ref"] == f"full/{record['record_id']}.md"
    assert not Path(record["full_content_ref"]).is_absolute()
    assert record["source_spans"] == ["user", "assistant"]
    assert "quant" in record["tags"]
    assert any("src/strategies/momentum.py" in artifact for artifact in record["artifacts"])

    full_path = tmp_path / "memory_fragmentation" / record["full_content_ref"]
    assert full_path.exists()
    full_text = full_path.read_text(encoding="utf-8")
    assert "[role: user]" in full_text
    assert "[role: assistant]" in full_text
    assert "momentum and volatility" in full_text


def test_sync_turn_skips_trivial_exchanges(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")

    provider.sync_turn("ok", "sure", session_id="session-1")

    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")
    assert records == []


def test_sync_turn_masks_sensitive_text_in_record_and_full_content(tmp_path):
    credential_value = "test-redacted-value"
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")

    provider.sync_turn(
        f"Please remember api_key={credential_value} for the demo service.",
        "I will not store the raw key, but I configured the demo service notes.",
        session_id="session-1",
    )

    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")
    assert len(records) == 1
    serialized = json.dumps(records[0], sort_keys=True)
    assert credential_value not in serialized
    assert records[0]["sensitivity_labels"]

    full_text = (tmp_path / "memory_fragmentation" / records[0]["full_content_ref"]).read_text(encoding="utf-8")
    assert credential_value not in full_text
    assert "[REDACTED]" in full_text


def test_prefetch_returns_only_key_summary_ladder_by_default(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a quant strategy with RSI and momentum filters.",
        "Finished the strategy. Touched src/strategies/rsi_momentum.py. Performance: CAGR 18%, Sortino 1.7, max drawdown -8%.",
        session_id="session-1",
    )

    context = provider.prefetch("What did we do for the quant strategy?", session_id="session-1")

    assert "Memory Fragmentation Context" in context
    assert "Injected level: summary" in context
    assert "Raw key:" in context
    assert "Summary:" in context
    assert "Record ID:" in context
    assert "Full content ref:" not in context
    assert str(tmp_path) not in context
    assert "[role: user]" not in context
    assert "[role: assistant]" not in context


def test_embedding_semantic_recall_finds_paraphrase_without_lexical_overlap(tmp_path, monkeypatch):
    _enable_fake_embeddings(tmp_path, monkeypatch)
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Create a balanced allocation planner for retirement baskets.",
        "Built optimizer notes in reports/allocation.md with downside stability review.",
        session_id="session-1",
    )
    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")
    assert records[0]["embedding"]["state"] == "embedded"
    assert records[0]["embedding"]["provider"] == "fake"
    assert "vector" in records[0]["embedding"]

    context = provider.prefetch("quant strategy drawdown metrics", session_id="session-1")

    assert "Memory Fragmentation Context" in context
    assert "Why retrieved:" in context
    assert "vector" in context
    assert "allocation.md" in context


def test_embedding_neighbors_are_scope_safe(tmp_path, monkeypatch):
    _enable_fake_embeddings(tmp_path, monkeypatch)
    alice = MemoryFragmentationProvider()
    alice.initialize("session-alice", hermes_home=str(tmp_path), platform="cli", user_id="alice")
    alice.sync_turn(
        "Capture shared semantic architecture notes for Alice.",
        "Recorded shared semantic design details in reports/alice.md.",
        session_id="session-alice",
    )

    bob = MemoryFragmentationProvider()
    bob.initialize("session-bob", hermes_home=str(tmp_path), platform="cli", user_id="bob")
    bob.sync_turn(
        "Capture shared semantic architecture notes for Bob.",
        "Recorded shared semantic design details in reports/bob.md.",
        session_id="session-bob",
    )

    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")
    alice_record, bob_record = records
    assert alice_record["embedding"]["state"] == "embedded"
    assert bob_record["embedding"]["state"] == "embedded"
    assert bob_record.get("semantic_neighbors") == []
    bob_context = bob.prefetch("Alice shared semantic architecture", session_id="session-bob")
    assert "reports/alice.md" not in bob_context
    assert "reports/bob.md" in bob_context
    assert "error" in _tool_payload(
        bob,
        "memory_fragmentation_get",
        {"record_id": alice_record["record_id"], "detail_level": "full"},
    )


def test_sensitive_records_are_not_embedded_even_when_embeddings_enabled(tmp_path, monkeypatch):
    _enable_fake_embeddings(tmp_path, monkeypatch)
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Set api_key=test-redacted-value for shared semantic service.",
        "Stored only safe setup notes.",
        session_id="session-1",
    )

    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")

    assert records[0]["sensitivity_labels"]
    assert records[0]["embedding"]["state"] == "skipped_sensitive"
    assert "vector" not in records[0]["embedding"]


def test_embedding_failure_does_not_block_write_or_lexical_recall(tmp_path, monkeypatch):
    _enable_fake_embeddings(tmp_path, monkeypatch, fail=True)
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a quant strategy with momentum filters.",
        "Finished quant strategy notes in reports/quant.md.",
        session_id="session-1",
    )
    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")
    assert len(records) == 1
    assert records[0]["embedding"]["state"] == "failed"

    context = provider.prefetch("quant strategy", session_id="session-1")

    assert "quant strategy" in context.lower()
    assert "Why retrieved:" in context


def test_sensitive_delete_search_returns_only_safe_handles(tmp_path):
    credential_value = "test-redacted-value"
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        f"Store api_key={credential_value} for later deletion testing.",
        "Stored safe credential deletion notes.",
        session_id="session-1",
    )

    payload = _tool_payload(
        provider,
        "memory_fragmentation_search",
        {"query": "delete api key credential", "detail_level": "full"},
    )

    assert payload["count"] == 1
    result = payload["results"][0]
    assert set(result) == {"record_id", "raw_key", "sensitivity_labels", "status"}
    assert credential_value not in json.dumps(result)


def test_unrelated_delete_query_does_not_return_sensitive_handles(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Store database password=CorrectHorseBatteryStaple for rotation.",
        "Stored safe database credential rotation notes.",
        session_id="session-1",
    )

    payload = _tool_payload(
        provider,
        "memory_fragmentation_search",
        {"query": "delete vacation photos", "detail_level": "full"},
    )

    assert payload["count"] == 0


def test_sensitive_query_is_not_sent_to_embedding_backend(tmp_path, monkeypatch):
    backend = RecordingEmbeddingBackend()
    _save_memory_fragmentation_config(
        {"embeddings": {"enabled": True, "provider": "fake", "model": "fake-semantic-v1", "dimensions": 2}},
        str(tmp_path),
    )
    monkeypatch.setattr(mf_module, "_create_embedding_backend", lambda _config: backend)
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a quant strategy with harmless signals.",
        "Finished quant strategy notes in reports/quant.md.",
        session_id="session-1",
    )
    backend.calls.clear()

    credential_value = "test-redacted-value"
    context = provider.prefetch(f"find quant strategy api_key={credential_value}", session_id="session-1")

    assert context
    assert backend.calls == []


def test_remote_lazy_embedding_rebuild_is_skipped_for_existing_records(tmp_path, monkeypatch):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Create a balanced allocation planner for retirement baskets.",
        "Built optimizer notes in reports/allocation.md with downside stability review.",
        session_id="session-1",
    )
    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")
    assert records[0]["embedding"]["state"] == "disabled"

    backend = RecordingEmbeddingBackend()
    backend.name = "openai"
    backend.model = "text-embedding-3-small"
    _save_memory_fragmentation_config(
        {"embeddings": {"enabled": True, "provider": "openai", "model": "text-embedding-3-small", "dimensions": 2}},
        str(tmp_path),
    )
    monkeypatch.setattr(mf_module, "_create_embedding_backend", lambda _config: backend)
    reloaded = MemoryFragmentationProvider()
    reloaded.initialize("session-1", hermes_home=str(tmp_path), platform="cli")

    assert reloaded.prefetch("quant strategy drawdown metrics", session_id="session-1") == ""
    assert backend.calls == []


def test_stale_remote_embedding_metadata_is_not_used_for_vector_recall(tmp_path, monkeypatch):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Archive a grocery recipe note.",
        "Stored unrelated cooking notes in reports/recipe.md.",
        session_id="session-1",
    )
    records_path = tmp_path / "memory_fragmentation" / "fragments.jsonl"
    records = _read_jsonl(records_path)
    records[0]["embedding"] = {
        "state": "embedded",
        "provider": "hashing",
        "model": "old-model",
        "dimensions": 2,
        "text_hash": "stale",
        "vector": [1.0, 0.0],
    }
    records_path.write_text(json.dumps(records[0], ensure_ascii=False) + "\n", encoding="utf-8")

    backend = RecordingEmbeddingBackend()
    backend.name = "openai"
    backend.model = "text-embedding-3-small"
    _save_memory_fragmentation_config(
        {"embeddings": {"enabled": True, "provider": "openai", "model": "text-embedding-3-small", "dimensions": 2}},
        str(tmp_path),
    )
    monkeypatch.setattr(mf_module, "_create_embedding_backend", lambda _config: backend)
    reloaded = MemoryFragmentationProvider()
    reloaded.initialize("session-1", hermes_home=str(tmp_path), platform="cli")

    assert reloaded.prefetch("semantic remote only topic", session_id="session-1") == ""
    assert backend.calls == []


def test_invalid_numeric_embedding_config_does_not_crash_recall(tmp_path):
    _save_memory_fragmentation_config(
        {
            "embeddings": {"enabled": False, "similarity_threshold": "bad"},
            "retrieval_policy": {"bm25_weight": "bad", "vector_weight": "bad"},
        },
        str(tmp_path),
    )
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a quant strategy with momentum filters.",
        "Finished quant strategy notes in reports/quant.md.",
        session_id="session-1",
    )

    context = provider.prefetch("quant strategy", session_id="session-1")

    assert "quant strategy" in context.lower()


def test_nonfinite_numeric_config_does_not_crash_ingestion_or_recall(tmp_path):
    _save_memory_fragmentation_config(
        {
            "max_recall_items": float("inf"),
            "summary_budget_chars": float("inf"),
            "min_turn_chars": float("inf"),
            "embeddings": {"enabled": True, "provider": "hash", "dimensions": float("inf")},
        },
        str(tmp_path),
    )
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a quant strategy with nonfinite config guards.",
        "Finished guarded quant strategy notes in reports/quant.md.",
        session_id="session-1",
    )

    payload = _tool_payload(
        provider,
        "memory_fragmentation_search",
        {"query": "quant strategy", "top_k": float("inf")},
    )

    assert payload["count"] == 1
    record = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")[0]
    assert record["embedding"]["state"] == "embedded"
    assert record["embedding"]["dimensions"] == 64


def test_malformed_nested_config_sections_do_not_crash_recall(tmp_path):
    _save_memory_fragmentation_config(
        {
            "embeddings": True,
            "retrieval_policy": "bad",
            "ingest_policy": "bad",
        },
        str(tmp_path),
    )
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a quant strategy with robust config handling.",
        "Finished quant strategy notes in reports/quant.md.",
        session_id="session-1",
    )

    context = provider.prefetch("quant strategy", session_id="session-1")

    assert "quant strategy" in context.lower()


def test_partial_lexical_overlap_does_not_retrieve_unrelated_memory(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a portal dashboard summary.",
        "Completed generic portal dashboard notes in reports/portal_dashboard.md.",
        session_id="session-1",
    )

    assert provider.prefetch("portal paris weather forecast tomorrow", session_id="session-1") == ""


def test_short_mixed_queries_require_more_than_one_generic_overlap(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a portal dashboard summary.",
        "Completed generic portal dashboard notes in reports/portal_dashboard.md.",
        session_id="session-1",
    )

    assert provider.prefetch("portal weather", session_id="session-1") == ""
    assert provider.prefetch("weather dashboard", session_id="session-1") == ""
    assert "portal dashboard" in provider.prefetch("portal dashboard", session_id="session-1").lower()


def test_string_boolean_config_flags_are_parsed_explicitly(tmp_path, monkeypatch):
    backend = RecordingEmbeddingBackend()
    monkeypatch.setattr(mf_module, "_create_embedding_backend", lambda _config: backend)

    disabled_home = tmp_path / "top_level_disabled"
    _save_memory_fragmentation_config(
        {"enabled": "false", "embeddings": {"enabled": "true", "provider": "fake", "model": "fake-semantic-v1", "dimensions": 2}},
        str(disabled_home),
    )
    disabled = MemoryFragmentationProvider()
    disabled.initialize("session-1", hermes_home=str(disabled_home), platform="cli")
    disabled.sync_turn(
        "Develop a quant strategy with disabled writes.",
        "Finished disabled strategy notes in reports/disabled.md.",
        session_id="session-1",
    )
    assert _read_jsonl(disabled_home / "memory_fragmentation" / "fragments.jsonl") == []

    embedding_disabled_home = tmp_path / "embedding_disabled"
    _save_memory_fragmentation_config(
        {"embeddings": {"enabled": "false", "provider": "fake", "model": "fake-semantic-v1", "dimensions": 2}},
        str(embedding_disabled_home),
    )
    embedding_disabled = MemoryFragmentationProvider()
    embedding_disabled.initialize("session-1", hermes_home=str(embedding_disabled_home), platform="cli")
    embedding_disabled.sync_turn(
        "Develop a quant strategy with local embeddings disabled.",
        "Finished embedding-disabled strategy notes in reports/no_embedding.md.",
        session_id="session-1",
    )

    records = _read_jsonl(embedding_disabled_home / "memory_fragmentation" / "fragments.jsonl")
    assert records[0]["embedding"]["state"] == "disabled"
    assert backend.calls == []


def test_embedding_provider_aliases_and_dimensions_validate_canonically(tmp_path, monkeypatch):
    for alias in ("hash", "local-hashing"):
        home = tmp_path / alias
        _save_memory_fragmentation_config(
            {"embeddings": {"enabled": True, "provider": alias, "model": "hashing-minhash-v1", "dimensions": 16}},
            str(home),
        )
        provider = MemoryFragmentationProvider()
        provider.initialize("session-1", hermes_home=str(home), platform="cli")
        provider.sync_turn(
            "Develop a quant strategy with canonical local embedding aliases.",
            "Finished canonical alias notes in reports/alias.md.",
            session_id="session-1",
        )
        record = _read_jsonl(home / "memory_fragmentation" / "fragments.jsonl")[0]
        assert record["embedding"]["provider"] == "hashing"
        assert mf_module._embedding_metadata_matches(provider._config, record, record["embedding"])

    backend = RecordingEmbeddingBackend()
    backend.name = "openai"
    backend.model = "text-embedding-3-small"
    monkeypatch.setattr(mf_module, "_create_embedding_backend", lambda _config: backend)
    openai_home = tmp_path / "openai_compatible"
    _save_memory_fragmentation_config(
        {"embeddings": {"enabled": True, "provider": "openai-compatible", "model": "text-embedding-3-small", "dimensions": 2}},
        str(openai_home),
    )
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(openai_home), platform="cli")
    provider.sync_turn(
        "Develop a quant strategy with canonical remote embedding aliases.",
        "Finished remote canonical alias notes in reports/remote_alias.md.",
        session_id="session-1",
    )
    record = _read_jsonl(openai_home / "memory_fragmentation" / "fragments.jsonl")[0]
    assert record["embedding"]["provider"] == "openai"
    assert mf_module._embedding_metadata_matches(provider._config, record, record["embedding"])

    record["embedding"]["vector"] = [1.0]
    assert not mf_module._embedding_metadata_matches(provider._config, record, record["embedding"])


def test_boilerplate_short_queries_do_not_retrieve_unrelated_memory(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a quant strategy with momentum filters.",
        "Finished quant strategy notes in reports/quant.md.",
        session_id="session-1",
    )

    assert provider.prefetch("summarize weather", session_id="session-1") == ""
    assert provider.prefetch("what happened weather", session_id="session-1") == ""


def test_lifecycle_status_superseded_records_are_not_recalled(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a quant strategy with stale filters.",
        "Finished stale strategy notes in reports/stale.md.",
        session_id="session-1",
    )
    records_path = tmp_path / "memory_fragmentation" / "fragments.jsonl"
    records = _read_jsonl(records_path)
    records[0]["lifecycle_status"] = "superseded"
    records_path.write_text(json.dumps(records[0], ensure_ascii=False) + "\n", encoding="utf-8")

    assert provider.prefetch("quant stale strategy", session_id="session-1") == ""


def test_v1_records_without_conversation_scope_remain_available_for_cli_scope(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    record = {
        "schema_version": "v1",
        "record_id": "mf_v1_cli",
        "raw_key": "quant strategy v1",
        "summary_short": "User asked for quant strategy v1 work.",
        "summary_medium": "Completed quant strategy v1 notes.",
        "tags": ["quant", "strategy"],
        "entities": [],
        "aliases": [],
        "questions": [],
        "artifacts": ["reports/v1.md"],
        "status": "active",
        "platform": "cli",
        "user_id": "local",
        "agent_identity": "default",
        "sensitivity_labels": [],
    }
    records_path = tmp_path / "memory_fragmentation" / "fragments.jsonl"
    records_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    context = provider.prefetch("quant strategy v1", session_id="session-1")

    assert "quant strategy v1" in context


def test_local_absolute_paths_are_scrubbed_from_records_context_and_embeddings(tmp_path, monkeypatch):
    backend = RecordingEmbeddingBackend()
    _save_memory_fragmentation_config(
        {"embeddings": {"enabled": True, "provider": "fake", "model": "fake-semantic-v1", "dimensions": 2}},
        str(tmp_path),
    )
    monkeypatch.setattr(mf_module, "_create_embedding_backend", lambda _config: backend)
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    local_paths = [
        "C:/Users/Nokron/private/project/secret_report.py",
        r"C:\Users\Nokron\My Projects\secret_report.py",
        r"\\server\share\team\secret_report.py",
        "/cygdrive/c/Users/Nokron/private/secret_report.py",
        "C:/Users/Nokron/ultra_private_repo",
        "C:/Users/Nokron/Secret Vault",
        r"C:\Users\Nokron\Zephyr Vault\extensionless_notes",
        r"C:\Users\Nokron\Secret Vault",
        r"\\server\share\team\team_alpha_vault",
        r"\\server\share\Secret Vault",
        "/home/nokron/private/extensionless_secret",
        "/home/nokron/Secret Vault",
    ]

    provider.sync_turn(
        "Review local files " + ", ".join(local_paths) + " for the dashboard task.",
        "Completed safe local file notes.",
        session_id="session-1",
    )
    context = provider.prefetch("dashboard local file", session_id="session-1")
    serialized = json.dumps(_read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl"), sort_keys=True)
    combined = "\n".join([serialized, context, *backend.calls])

    for local_path in local_paths:
        assert local_path not in combined
    assert "My Projects" not in combined
    assert "ultra_private_repo" not in combined
    assert "Zephyr Vault" not in combined
    assert "Secret Vault" not in combined
    assert "extensionless_notes" not in combined
    assert "team_alpha_vault" not in combined
    assert "extensionless_secret" not in combined
    assert "server" not in combined
    assert "cygdrive" not in combined


def test_pii_is_scrubbed_from_records_safe_handles_and_embeddings(tmp_path, monkeypatch):
    backend = RecordingEmbeddingBackend()
    _save_memory_fragmentation_config(
        {"embeddings": {"enabled": True, "provider": "fake", "model": "fake-semantic-v1", "dimensions": 2}},
        str(tmp_path),
    )
    monkeypatch.setattr(mf_module, "_create_embedding_backend", lambda _config: backend)
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    email = "john.doe@example.com"
    phone = "+1-555-123-4567"

    provider.sync_turn(
        f"Remember support contact {email} and phone {phone} for deletion testing.",
        "Stored safe contact notes.",
        session_id="session-1",
    )
    payload = _tool_payload(
        provider,
        "memory_fragmentation_search",
        {"query": "delete email contact", "detail_level": "full"},
    )
    serialized = json.dumps(_read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl"), sort_keys=True)
    combined = "\n".join([serialized, json.dumps(payload, sort_keys=True), *backend.calls])

    assert payload["count"] == 1
    assert set(payload["results"][0]) == {"record_id", "raw_key", "sensitivity_labels", "status"}
    assert email not in combined
    assert phone not in combined


def test_lazy_embedding_rebuild_enables_semantic_recall_for_existing_records(tmp_path, monkeypatch):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Create a balanced allocation planner for retirement baskets.",
        "Built optimizer notes in reports/allocation.md with downside stability review.",
        session_id="session-1",
    )
    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")
    assert records[0]["embedding"]["state"] == "disabled"

    _enable_fake_embeddings(tmp_path, monkeypatch)
    reloaded = MemoryFragmentationProvider()
    reloaded.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    context = reloaded.prefetch("quant strategy drawdown metrics", session_id="session-1")

    assert "Memory Fragmentation Context" in context
    assert "vector" in context
    assert "allocation.md" in context
    assert _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")[0]["embedding"]["state"] == "disabled"


def test_bm25_ranks_specific_lexical_match_above_generic_overlap(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a portal latency dashboard summary.",
        "Completed generic portal latency dashboard notes in reports/portal_dashboard.md.",
        session_id="session-1",
    )
    provider.sync_turn(
        "Fix the portal latency regression.",
        "Completed portal latency regression notes in reports/portal_latency.md.",
        session_id="session-1",
    )

    payload = _tool_payload(
        provider,
        "memory_fragmentation_search",
        {"query": "portal latency regression", "detail_level": "summary", "top_k": 2},
    )

    assert payload["count"] == 2
    assert "regression" in payload["results"][0]["summary_medium"].lower()
    assert "portal_dashboard.md" in payload["results"][1]["summary_medium"]


def test_prefetch_can_expand_to_full_for_exact_detail_requests(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a quant strategy with RSI and momentum filters.",
        "Finished the strategy. Touched src/strategies/rsi_momentum.py. Performance: CAGR 18%, Sortino 1.7, max drawdown -8%.",
        session_id="session-1",
    )

    context = provider.prefetch("Which files changed in the quant strategy work?", session_id="session-1")

    assert "Injected level: full" in context
    assert "src/strategies/rsi_momentum.py" in context
    assert "[role: assistant]" in context


def test_full_retrieval_preserves_exact_output_formatting(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Save exact output formatting for the migration report.",
        "Exact output:\nline one\n  indented line\nline three",
        session_id="session-1",
    )
    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")

    payload = _tool_payload(
        provider,
        "memory_fragmentation_get",
        {"record_id": records[0]["record_id"], "detail_level": "full"},
    )
    assert "\nExact output:\nline one\n  indented line\nline three\n" in payload["full_content"]

    context = provider.prefetch("exact output migration report", session_id="session-1")
    assert "    Exact output:" in context
    assert "      indented line" in context


def _tool_payload(provider: MemoryFragmentationProvider, tool_name: str, args: dict) -> dict:
    return json.loads(provider.handle_tool_call(tool_name, args))


def test_prefetch_filters_by_user_and_agent_scope_before_scoring(tmp_path):
    alice = MemoryFragmentationProvider()
    alice.initialize(
        "session-alice",
        hermes_home=str(tmp_path),
        platform="telegram",
        user_id="alice",
        agent_identity="coder",
    )
    alice.sync_turn(
        "Develop a quant strategy with private alpha filters.",
        "Completed private alpha quant strategy notes in reports/alice_alpha.md.",
        session_id="session-alice",
    )
    assert "private alpha" in alice.prefetch("quant private alpha", session_id="session-alice")

    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")
    record_id = records[0]["record_id"]

    bob = MemoryFragmentationProvider()
    bob.initialize(
        "session-bob",
        hermes_home=str(tmp_path),
        platform="telegram",
        user_id="bob",
        agent_identity="coder",
    )
    assert bob.prefetch("quant private alpha", session_id="session-bob") == ""
    assert "error" in _tool_payload(
        bob,
        "memory_fragmentation_get",
        {"record_id": record_id, "detail_level": "full"},
    )

    other_agent = MemoryFragmentationProvider()
    other_agent.initialize(
        "session-alice-researcher",
        hermes_home=str(tmp_path),
        platform="telegram",
        user_id="alice",
        agent_identity="researcher",
    )
    assert other_agent.prefetch("quant private alpha", session_id="session-alice-researcher") == ""
    assert "error" in _tool_payload(
        other_agent,
        "memory_fragmentation_get",
        {"record_id": record_id, "detail_level": "full"},
    )


def test_prefetch_and_get_filter_by_gateway_conversation_scope(tmp_path):
    chat_a = MemoryFragmentationProvider()
    chat_a.initialize(
        "session-chat-a",
        hermes_home=str(tmp_path),
        platform="telegram",
        user_id="alice",
        agent_identity="coder",
        chat_id="chat-a",
        chat_type="private",
        thread_id="thread-1",
        gateway_session_key="telegram:chat-a:thread-1",
    )
    chat_a.sync_turn(
        "Develop a quant strategy with chat-specific private alpha filters.",
        "Completed chat-specific alpha notes in reports/chat_a_alpha.md.",
        session_id="session-chat-a",
    )
    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")
    record_id = records[0]["record_id"]
    assert records[0]["conversation_scope"] == "gateway:telegram:chat-a:thread-1"
    assert records[0]["chat_id"] == "chat-a"
    assert "chat-specific alpha" in chat_a.prefetch("quant chat-specific alpha")

    chat_b = MemoryFragmentationProvider()
    chat_b.initialize(
        "session-chat-b",
        hermes_home=str(tmp_path),
        platform="telegram",
        user_id="alice",
        agent_identity="coder",
        chat_id="chat-b",
        chat_type="private",
        thread_id="thread-2",
        gateway_session_key="telegram:chat-b:thread-2",
    )

    assert chat_b.prefetch("quant chat-specific alpha") == ""
    assert "error" in _tool_payload(
        chat_b,
        "memory_fragmentation_get",
        {"record_id": record_id, "detail_level": "full"},
    )

    local_cli = MemoryFragmentationProvider()
    local_cli.initialize(
        "session-cli",
        hermes_home=str(tmp_path),
        platform="cli",
        user_id="alice",
        agent_identity="coder",
    )
    assert local_cli.prefetch("quant chat-specific alpha") == ""


def test_prefetch_unrelated_query_returns_empty_even_for_important_records(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Please remember this decision and preference for the dashboard project.",
        "Implemented the decision and wrote notes to reports/dashboard_decision.md.",
        session_id="session-1",
    )

    assert provider.prefetch("weather paris forecast tomorrow", session_id="session-1") == ""


def test_broad_details_query_stays_summary_only(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a quant strategy with RSI and momentum filters.",
        "Finished the strategy. Touched src/strategies/rsi_momentum.py.",
        session_id="session-1",
    )

    context = provider.prefetch("Show me details about the quant strategy", session_id="session-1")

    assert "Injected level: summary" in context
    assert "Injected level: full" not in context
    assert "[role: user]" not in context
    assert "[role: assistant]" not in context


def test_search_and_get_shape_payloads_by_detail_level(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli", user_id="user-1")
    provider.sync_turn(
        "Develop a quant strategy with RSI and momentum filters.",
        "Finished the strategy. Touched src/strategies/rsi_momentum.py.",
        session_id="session-1",
    )

    key_payload = _tool_payload(
        provider,
        "memory_fragmentation_search",
        {"query": "quant strategy", "detail_level": "key"},
    )
    key_record = key_payload["results"][0]
    assert set(key_record) == {"record_id", "raw_key"}

    summary_payload = _tool_payload(
        provider,
        "memory_fragmentation_search",
        {"query": "quant strategy", "detail_level": "summary"},
    )
    summary_record = summary_payload["results"][0]
    assert "summary_short" in summary_record
    assert "summary_medium" in summary_record
    assert "tags" in summary_record
    assert "artifacts" in summary_record
    assert "user_id" not in summary_record
    assert "full_content_ref" not in summary_record

    record_id = summary_record["record_id"]
    full_payload = _tool_payload(
        provider,
        "memory_fragmentation_get",
        {"record_id": record_id, "detail_level": "full"},
    )
    assert "full_content" in full_payload
    assert "[role: assistant]" in full_payload["full_content"]
    assert "full_content_ref" not in full_payload
    assert "user_id" not in full_payload


def test_sensitive_bearer_password_and_jwt_are_redacted_and_excluded_from_recall(tmp_path):
    bearer = "Bearer abcdefghijklmnopqrstuvwxyz1234567890"
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signaturepart"
    password = "SuperSecretPassword123"
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")

    provider.sync_turn(
        f"Configure demo service with Authorization: {bearer}; jwt={jwt}; my password is {password}.",
        "Stored safe demo notes without raw credentials.",
        session_id="session-1",
    )

    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")
    assert len(records) == 1
    serialized = json.dumps(records[0], sort_keys=True)
    full_text = (tmp_path / "memory_fragmentation" / records[0]["full_content_ref"]).read_text(encoding="utf-8")
    for secret in (bearer, jwt, password):
        assert secret not in serialized
        assert secret not in full_text
    assert records[0]["sensitivity_labels"]
    assert "[REDACTED]" in serialized
    assert provider.prefetch("demo service credentials", session_id="session-1") == ""
    assert "error" in _tool_payload(
        provider,
        "memory_fragmentation_get",
        {"record_id": records[0]["record_id"], "detail_level": "full"},
    )


def test_tampered_full_content_ref_cannot_escape_provider_storage(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("session-1", hermes_home=str(tmp_path), platform="cli")
    provider.sync_turn(
        "Develop a quant strategy with escape-test filters.",
        "Finished the strategy with reports/escape_safe.md.",
        session_id="session-1",
    )
    records_path = tmp_path / "memory_fragmentation" / "fragments.jsonl"
    records = _read_jsonl(records_path)
    outside = tmp_path / "outside_secret.txt"
    outside.write_text("OUTSIDE-SECRET-SHOULD-NOT-BE-READ", encoding="utf-8")
    records[0]["full_content_ref"] = str(outside)
    records_path.write_text(json.dumps(records[0], ensure_ascii=False) + "\n", encoding="utf-8")

    payload = _tool_payload(
        provider,
        "memory_fragmentation_get",
        {"record_id": records[0]["record_id"], "detail_level": "full"},
    )

    assert "OUTSIDE-SECRET-SHOULD-NOT-BE-READ" not in payload.get("full_content", "")
    assert "escape-test filters" in payload.get("full_content", "")


def test_session_switch_updates_cached_session_for_full_source(tmp_path):
    provider = MemoryFragmentationProvider()
    provider.initialize("old-session", hermes_home=str(tmp_path), platform="cli")

    provider.on_session_switch("new-session", parent_session_id="old-session", reset=True)
    provider.sync_turn(
        "Develop a quant strategy after session switch.",
        "Finished switched-session strategy notes.",
    )

    records = _read_jsonl(tmp_path / "memory_fragmentation" / "fragments.jsonl")
    assert records[0]["session_id"] == "new-session"
    full_text = (tmp_path / "memory_fragmentation" / records[0]["full_content_ref"]).read_text(encoding="utf-8")
    assert "Session: new-session" in full_text
