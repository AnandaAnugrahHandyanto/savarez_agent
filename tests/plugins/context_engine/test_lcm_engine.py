"""Engine tests for the repo-shipped LCM context engine."""

from __future__ import annotations

import json
import time

import pytest

from agent.context_engine import ContextEngine
from plugins.context_engine.lcm.config import LCMConfig
from plugins.context_engine.lcm.dag import SummaryNode
from plugins.context_engine.lcm.engine import LCMEngine
from plugins.context_engine.lcm import escalation as lcm_escalation


@pytest.fixture
def engine(tmp_path):
    config = LCMConfig()
    config.fresh_tail_count = 4
    config.leaf_chunk_tokens = 100
    config.database_path = str(tmp_path / "lcm_test.db")
    instance = LCMEngine(config=config)
    instance._session_id = "test-session"
    instance.context_length = 200000
    instance.threshold_tokens = int(200000 * config.context_threshold)
    return instance


@pytest.fixture
def mock_summary(monkeypatch):
    def _mock(_prompt, _max_tokens, model=""):
        return "Mock summary of conversation.\nExpand for details about: earlier turns"

    monkeypatch.setattr(lcm_escalation, "_call_llm_for_summary", _mock)


class TestEngineABC:
    def test_is_context_engine(self, engine):
        assert isinstance(engine, ContextEngine)

    def test_name(self, engine):
        assert engine.name == "lcm"

    def test_tool_schemas(self, engine):
        names = [schema["name"] for schema in engine.get_tool_schemas()]
        assert names == ["lcm_grep", "lcm_describe", "lcm_expand"]

    def test_should_compress(self, engine):
        assert not engine.should_compress(1000)
        assert engine.should_compress(engine.threshold_tokens)

    def test_update_from_response(self, engine):
        engine.update_from_response({"prompt_tokens": 5000, "completion_tokens": 200, "total_tokens": 5200})
        assert engine.last_prompt_tokens == 5000
        assert engine.last_completion_tokens == 200
        assert engine.last_total_tokens == 5200

    def test_session_reset(self, engine):
        engine.compression_count = 5
        engine.last_prompt_tokens = 9999
        engine.on_session_reset()
        assert engine.compression_count == 0
        assert engine.last_prompt_tokens == 0

    def test_get_status(self, engine):
        status = engine.get_status()
        assert status["engine"] == "lcm"
        assert "store_messages" in status
        assert "dag_nodes" in status

    def test_compress_accepts_focus_topic(self, engine, monkeypatch):
        captured = {}

        def _mock_summary(*, text, source_tokens, token_budget, depth=0, model="", l2_budget_ratio=0.50,
                          l3_truncate_tokens=512, focus_topic=""):
            captured["focus_topic"] = focus_topic
            return "Focused summary\nExpand for details about: database", 1

        monkeypatch.setattr(
            "plugins.context_engine.lcm.engine.summarize_with_escalation",
            _mock_summary,
        )

        messages = _ConversationMixin.make_long_conversation(20)
        engine.compress(messages, focus_topic="database schema")

        assert captured["focus_topic"] == "database schema"


class TestEngineIngest:
    def test_ingest_stores_messages(self, engine):
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        engine._ingest_messages(messages)
        assert engine._store.get_session_count("test-session") == 3

    def test_ingest_idempotent(self, engine):
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ]
        engine._ingest_messages(messages)
        engine._ingest_messages(messages)
        assert engine._store.get_session_count("test-session") == 2


class _ConversationMixin:
    @staticmethod
    def make_long_conversation(n_turns=20):
        messages = [{"role": "system", "content": "You are a helpful assistant."}]
        for i in range(n_turns):
            messages.append({"role": "user", "content": f"Question {i}: " + "x" * 200})
            messages.append({"role": "assistant", "content": f"Answer {i}: " + "y" * 200})
        return messages


class TestEngineCompress(_ConversationMixin):
    def test_compress_short_conversation_noop(self, engine):
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = engine.compress(messages)
        assert result == messages

    def test_compress_preserves_system_and_tail(self, engine, mock_summary):
        messages = self.make_long_conversation(20)
        result = engine.compress(messages)
        assert result[0]["role"] == "system"
        assert result[-1] == messages[-1]
        assert len(result) < len(messages)
        assert engine.compression_count == 1

    def test_compress_creates_dag_node(self, engine, mock_summary):
        engine.compress(self.make_long_conversation(20))
        nodes = engine._dag.get_session_nodes("test-session")
        assert len(nodes) >= 1
        assert nodes[0].depth == 0
        assert nodes[0].source_type == "messages"


class TestPostCompactionIngestion(_ConversationMixin):
    def test_ingest_after_compaction(self, engine, mock_summary):
        messages = self.make_long_conversation(20)
        compressed = engine.compress(messages)
        count_after_compress = engine._store.get_session_count("test-session")
        assert count_after_compress == len(messages)

        compressed.append({"role": "user", "content": "Brand new question"})
        compressed.append({"role": "assistant", "content": "Brand new answer"})

        engine._ingest_messages(compressed)
        count_after_new = engine._store.get_session_count("test-session")
        assert count_after_new == count_after_compress + 2

    def test_ingest_cursor_reset_on_session_reset(self, engine):
        engine._ingest_cursor = 42
        engine.on_session_reset()
        assert engine._ingest_cursor == 0

    def test_multiple_compactions(self, engine, mock_summary):
        messages = self.make_long_conversation(20)
        compressed = engine.compress(messages)
        count1 = engine._store.get_session_count("test-session")

        for i in range(15):
            compressed.append({"role": "user", "content": f"Round2 Q{i}: " + "z" * 200})
            compressed.append({"role": "assistant", "content": f"Round2 A{i}: " + "w" * 200})

        compressed2 = engine.compress(compressed)
        count2 = engine._store.get_session_count("test-session")
        assert count2 == count1 + 30

        compressed2.append({"role": "user", "content": "Final question"})
        engine._ingest_messages(compressed2)
        count3 = engine._store.get_session_count("test-session")
        assert count3 == count2 + 1


class TestStoreIdMapping(_ConversationMixin):
    def test_source_ids_correct_after_second_compaction(self, engine, mock_summary):
        messages = self.make_long_conversation(20)
        compressed = engine.compress(messages)

        for i in range(15):
            compressed.append({"role": "user", "content": f"Round2 Q{i}: " + "z" * 200})
            compressed.append({"role": "assistant", "content": f"Round2 A{i}: " + "w" * 200})

        engine.compress(compressed)
        nodes = engine._dag.get_session_nodes("test-session")
        assert len(nodes) >= 2

        second_node = nodes[1]
        for store_id in second_node.source_ids:
            stored = engine._store.get(store_id)
            assert stored is not None
            assert "Mock summary" not in (stored.get("content") or "")

    def test_repeated_content_maps_to_later_store_rows(self, engine, mock_summary):
        messages = [{"role": "system", "content": "You are a helpful assistant."}]
        for _ in range(20):
            messages.append({"role": "user", "content": "repeat"})
            messages.append({"role": "assistant", "content": "same"})

        compressed = engine.compress(messages)
        first_node = engine._dag.get_session_nodes("test-session")[0]
        first_max = max(first_node.source_ids)

        for _ in range(15):
            compressed.append({"role": "user", "content": "repeat"})
            compressed.append({"role": "assistant", "content": "same"})

        engine.compress(compressed)
        nodes = engine._dag.get_session_nodes("test-session")
        second_node = nodes[1]
        assert second_node.source_ids
        assert all(store_id > first_max for store_id in second_node.source_ids)


class TestSessionRetainDepth:
    def test_retain_depth_zero_deletes_all(self, engine):
        engine._config.new_session_retain_depth = 0
        for depth in range(3):
            engine._dag.add_node(
                SummaryNode(
                    session_id="test-session",
                    depth=depth,
                    summary=f"d{depth} summary",
                    token_count=100,
                    source_token_count=500,
                    source_ids=[],
                    source_type="messages",
                    created_at=time.time(),
                )
            )
        engine.on_session_reset()
        assert engine._dag.get_session_nodes("test-session") == []

    def test_retain_depth_keeps_high_nodes(self, engine):
        engine._config.new_session_retain_depth = 2
        for depth in range(4):
            engine._dag.add_node(
                SummaryNode(
                    session_id="test-session",
                    depth=depth,
                    summary=f"d{depth} summary",
                    token_count=100,
                    source_token_count=500,
                    source_ids=[],
                    source_type="messages",
                    created_at=time.time(),
                )
            )
        engine.on_session_reset()
        remaining = engine._dag.get_session_nodes("test-session")
        assert len(remaining) == 2
        assert all(node.depth >= 2 for node in remaining)

    def test_retain_depth_minus_one_keeps_all(self, engine):
        engine._config.new_session_retain_depth = -1
        for depth in range(3):
            engine._dag.add_node(
                SummaryNode(
                    session_id="test-session",
                    depth=depth,
                    summary=f"d{depth} summary",
                    token_count=100,
                    source_token_count=500,
                    source_ids=[],
                    source_type="messages",
                    created_at=time.time(),
                )
            )
        engine.on_session_reset()
        assert len(engine._dag.get_session_nodes("test-session")) == 3

    def test_carry_over_moves_retained_nodes_into_new_session(self, engine):
        engine._config.new_session_retain_depth = 2
        for depth in range(4):
            engine._dag.add_node(
                SummaryNode(
                    session_id="old-session",
                    depth=depth,
                    summary=f"d{depth} summary",
                    token_count=100,
                    source_token_count=500,
                    source_ids=[],
                    source_type="messages",
                    created_at=time.time(),
                )
            )

        engine._session_id = "old-session"
        engine.on_session_reset()
        moved = engine.carry_over_new_session_context("old-session", "new-session")

        assert moved == 2
        assert engine._dag.get_session_nodes("old-session") == []
        new_nodes = engine._dag.get_session_nodes("new-session")
        assert len(new_nodes) == 2
        assert all(node.depth >= 2 for node in new_nodes)


class TestUnlimitedCondensationDepth:
    def test_unlimited_depth_condenses_beyond_ten(self, engine, mock_summary):
        engine._config.incremental_max_depth = -1
        engine._config.condensation_fanin = 2

        for i in range(3):
            engine._dag.add_node(
                SummaryNode(
                    session_id="test-session",
                    depth=11,
                    summary=f"Deep node {i}",
                    token_count=100,
                    source_token_count=200,
                    source_ids=[],
                    source_type="nodes",
                    created_at=time.time(),
                )
            )

        engine._maybe_condense()
        d12_nodes = engine._dag.get_session_nodes("test-session", depth=12)
        assert len(d12_nodes) >= 1


class TestAssemblyGuardrails:
    def test_max_assembly_tokens_caps_recent_tail(self, tmp_path, monkeypatch):
        config = LCMConfig(
            fresh_tail_count=10,
            database_path=str(tmp_path / "lcm_guardrail.db"),
            max_assembly_tokens=60,
        )
        instance = LCMEngine(config=config)
        instance._session_id = "guardrail-session"
        instance.compression_count = 1

        monkeypatch.setattr(
            "plugins.context_engine.lcm.engine.count_message_tokens",
            lambda msg: len(msg.get("content", "")),
        )

        result = instance._assemble_context(
            {"role": "system", "content": "s" * 10},
            [
                {"role": "user", "content": "a" * 20},
                {"role": "assistant", "content": "b" * 20},
                {"role": "user", "content": "c" * 20},
            ],
        )

        assert [msg["content"] for msg in result[1:]] == ["b" * 20, "c" * 20]

    def test_reserve_tokens_floor_caps_recent_tail(self, tmp_path, monkeypatch):
        config = LCMConfig(
            fresh_tail_count=10,
            database_path=str(tmp_path / "lcm_headroom.db"),
            reserve_tokens_floor=40,
        )
        instance = LCMEngine(config=config)
        instance._session_id = "guardrail-session"
        instance.compression_count = 1
        instance.context_length = 100

        monkeypatch.setattr(
            "plugins.context_engine.lcm.engine.count_message_tokens",
            lambda msg: len(msg.get("content", "")),
        )

        result = instance._assemble_context(
            {"role": "system", "content": "s" * 10},
            [
                {"role": "user", "content": "a" * 20},
                {"role": "assistant", "content": "b" * 20},
                {"role": "user", "content": "c" * 20},
            ],
        )

        assert [msg["content"] for msg in result[1:]] == ["b" * 20, "c" * 20]


class TestEngineTools:
    def test_handle_grep(self, engine):
        engine._store.append("test-session", {"role": "user", "content": "deploy docker containers"})
        result = json.loads(engine.handle_tool_call("lcm_grep", {"query": "docker"}))
        assert "results" in result

    def test_handle_describe_overview(self, engine):
        result = json.loads(engine.handle_tool_call("lcm_describe", {}))
        assert "session_id" in result
        assert "store_message_count" in result

    def test_handle_unknown_tool(self, engine):
        result = json.loads(engine.handle_tool_call("unknown_tool", {}))
        assert "error" in result

    def test_tool_dispatch_is_bound_to_engine_instance(self, tmp_path):
        config_a = LCMConfig(database_path=str(tmp_path / "a.db"))
        config_b = LCMConfig(database_path=str(tmp_path / "b.db"))

        engine_a = LCMEngine(config=config_a)
        engine_a._session_id = "session-a"
        engine_b = LCMEngine(config=config_b)
        engine_b._session_id = "session-b"

        engine_a._store.append("session-a", {"role": "user", "content": "alpha project"})
        engine_b._store.append("session-b", {"role": "user", "content": "beta project"})

        result_a = json.loads(engine_a.handle_tool_call("lcm_grep", {"query": "alpha"}))
        result_b = json.loads(engine_b.handle_tool_call("lcm_grep", {"query": "beta"}))

        assert result_a["total_results"] == 1
        assert result_b["total_results"] == 1
        assert "alpha" in result_a["results"][0]["snippet"]
        assert "beta" in result_b["results"][0]["snippet"]

    def test_describe_and_expand_are_session_scoped(self, engine):
        node_id = engine._dag.add_node(
            SummaryNode(
                session_id="session-a",
                depth=0,
                summary="secret summary",
                token_count=10,
                source_token_count=20,
                source_ids=[],
                source_type="messages",
                created_at=time.time(),
            )
        )

        engine._session_id = "session-b"

        describe = json.loads(engine.handle_tool_call("lcm_describe", {"node_id": node_id}))
        expand = json.loads(engine.handle_tool_call("lcm_expand", {"node_id": node_id}))

        assert "error" in describe
        assert "error" in expand

    def test_describe_overview_includes_sparse_high_depth_nodes(self, engine):
        engine._dag.add_node(
            SummaryNode(
                session_id="test-session",
                depth=2,
                summary="durable summary",
                token_count=100,
                source_token_count=500,
                source_ids=[],
                source_type="messages",
                created_at=time.time(),
            )
        )

        overview = json.loads(engine.handle_tool_call("lcm_describe", {}))
        assert "d2" in overview["depths"]
