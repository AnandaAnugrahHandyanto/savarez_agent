"""Core tests for the repo-shipped LCM context engine."""

from __future__ import annotations

import json

import pytest

from plugins.context_engine import discover_context_engines, load_context_engine
from plugins.context_engine.lcm.config import LCMConfig
from plugins.context_engine.lcm.dag import SummaryDAG, SummaryNode
from plugins.context_engine.lcm.escalation import _deterministic_truncate
from plugins.context_engine.lcm.store import MessageStore
from plugins.context_engine.lcm import tokens as lcm_tokens


class TestDiscovery:
    def test_lcm_is_discoverable(self):
        engines = discover_context_engines()
        names = {name for name, _desc, _available in engines}
        assert "lcm" in names

    def test_load_context_engine_returns_lcm(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
        engine = load_context_engine("lcm")
        assert engine is not None
        assert engine.name == "lcm"
        assert engine._store.db_path == tmp_path / ".hermes" / "lcm.db"


class TestConfig:
    def test_defaults(self):
        config = LCMConfig()
        assert config.fresh_tail_count == 64
        assert config.leaf_chunk_tokens == 20_000
        assert config.context_threshold == 0.75
        assert config.condensation_fanin == 4
        assert config.new_session_retain_depth == 2

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("LCM_FRESH_TAIL_COUNT", "32")
        monkeypatch.setenv("LCM_CONTEXT_THRESHOLD", "0.80")
        monkeypatch.setenv("LCM_INCREMENTAL_MAX_DEPTH", "-1")
        config = LCMConfig.from_env()
        assert config.fresh_tail_count == 32
        assert config.context_threshold == 0.80
        assert config.incremental_max_depth == -1

    def test_removed_placeholder_fields_stay_removed(self):
        config = LCMConfig()
        assert not hasattr(config, "expansion_model")
        assert not hasattr(config, "summary_timeout_ms")
        assert not hasattr(config, "delegation_timeout_ms")


class TestTokens:
    def test_count_tokens_empty(self):
        assert lcm_tokens.count_tokens("") == 0

    def test_char_fallback_is_deterministic(self, monkeypatch):
        monkeypatch.setattr(lcm_tokens, "_encoder", None)
        monkeypatch.setattr(lcm_tokens, "_encoder_checked", True)
        assert lcm_tokens.count_tokens("abcdefgh") == 3

    def test_count_message_tokens(self):
        msg = {"role": "user", "content": "hello world this is a test"}
        assert lcm_tokens.count_message_tokens(msg) > 0

    def test_count_messages_tokens(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        assert lcm_tokens.count_messages_tokens(messages) > 0


class TestMessageStore:
    @pytest.fixture
    def store(self, tmp_path):
        return MessageStore(tmp_path / "test.db")

    def test_append_and_get(self, store):
        store_id = store.append("sess1", {"role": "user", "content": "hello"}, token_estimate=5)
        retrieved = store.get(store_id)
        assert retrieved["role"] == "user"
        assert retrieved["content"] == "hello"
        assert retrieved["token_estimate"] == 5

    def test_append_batch(self, store):
        messages = [
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "three"},
        ]
        ids = store.append_batch("sess1", messages, [1, 2, 3])
        assert len(ids) == 3
        assert ids[0] < ids[1] < ids[2]

    def test_get_range(self, store):
        ids = store.append_batch("sess1", [{"role": "user", "content": f"msg {i}"} for i in range(10)])
        result = store.get_range("sess1", start_id=ids[3], end_id=ids[7])
        assert len(result) == 5

    def test_search(self, store):
        store.append("sess1", {"role": "user", "content": "deploy the docker container"})
        store.append("sess1", {"role": "assistant", "content": "running kubectl"})
        results = store.search("docker", session_id="sess1")
        assert len(results) >= 1
        assert results[0]["role"] == "user"

    def test_pin_unpin(self, store):
        store_id = store.append("sess1", {"role": "user", "content": "important"})
        store.pin(store_id)
        assert store.get(store_id)["pinned"] == 1
        store.unpin(store_id)
        assert store.get(store_id)["pinned"] == 0

    def test_to_openai_msg(self, store):
        store_id = store.append(
            "sess1",
            {
                "role": "assistant",
                "content": "hello",
                "tool_calls": [{"id": "tc1", "function": {"name": "t", "arguments": "{}"}}],
            },
        )
        msg = store.to_openai_msg(store.get(store_id))
        assert msg["role"] == "assistant"
        assert len(msg["tool_calls"]) == 1


class TestSummaryDAG:
    @pytest.fixture
    def dag(self, tmp_path):
        return SummaryDAG(tmp_path / "test.db")

    def test_add_and_get(self, dag):
        node = SummaryNode(
            session_id="s1",
            depth=0,
            summary="FastAPI project setup",
            token_count=10,
            source_token_count=500,
            source_ids=[1, 2, 3],
            source_type="messages",
            expand_hint="FastAPI setup",
        )
        node_id = dag.add_node(node)
        loaded = dag.get_node(node_id)
        assert loaded.summary == "FastAPI project setup"
        assert loaded.source_ids == [1, 2, 3]

    def test_session_nodes(self, dag):
        for i in range(3):
            dag.add_node(
                SummaryNode(
                    session_id="s1",
                    depth=0,
                    summary=f"S{i}",
                    token_count=10,
                    source_ids=[i],
                    source_type="messages",
                )
            )
        dag.add_node(
            SummaryNode(
                session_id="s2",
                depth=0,
                summary="Other",
                token_count=10,
                source_ids=[99],
                source_type="messages",
            )
        )
        assert len(dag.get_session_nodes("s1")) == 3

    def test_count_at_depth(self, dag):
        for i in range(4):
            dag.add_node(
                SummaryNode(
                    session_id="s1",
                    depth=0,
                    summary=f"D0-{i}",
                    token_count=10,
                    source_ids=[i],
                    source_type="messages",
                )
            )
        dag.add_node(
            SummaryNode(
                session_id="s1",
                depth=1,
                summary="D1",
                token_count=20,
                source_ids=[1, 2, 3, 4],
                source_type="nodes",
            )
        )
        assert dag.count_at_depth("s1", 0) == 4
        assert dag.count_at_depth("s1", 1) == 1

    def test_search(self, dag):
        dag.add_node(
            SummaryNode(
                session_id="s1",
                depth=0,
                summary="Docker containers for the API",
                token_count=10,
                source_ids=[1],
                source_type="messages",
            )
        )
        results = dag.search("Docker", session_id="s1")
        assert len(results) >= 1

    def test_describe_subtree(self, dag):
        child1 = dag.add_node(
            SummaryNode(
                session_id="s1",
                depth=0,
                summary="Child 1",
                token_count=10,
                source_ids=[1],
                source_type="messages",
            )
        )
        child2 = dag.add_node(
            SummaryNode(
                session_id="s1",
                depth=0,
                summary="Child 2",
                token_count=15,
                source_ids=[2],
                source_type="messages",
            )
        )
        parent = dag.add_node(
            SummaryNode(
                session_id="s1",
                depth=1,
                summary="Parent",
                token_count=20,
                source_ids=[child1, child2],
                source_type="nodes",
            )
        )
        info = dag.describe_subtree(parent)
        assert info["depth"] == 1
        assert len(info["children"]) == 2

    def test_delete_below_depth(self, dag):
        for depth in range(4):
            dag.add_node(
                SummaryNode(
                    session_id="s1",
                    depth=depth,
                    summary=f"depth {depth}",
                    token_count=10,
                    source_ids=[depth],
                    source_type="messages",
                )
            )
        deleted = dag.delete_below_depth("s1", 2)
        remaining = dag.get_session_nodes("s1")
        assert deleted == 2
        assert all(node.depth >= 2 for node in remaining)

    def test_delete_session_nodes(self, dag):
        dag.add_node(
            SummaryNode(
                session_id="s1",
                depth=0,
                summary="one",
                token_count=10,
                source_ids=[1],
                source_type="messages",
            )
        )
        assert dag.delete_session_nodes("s1") == 1
        assert dag.get_session_nodes("s1") == []


class TestEscalation:
    def test_truncate_long(self):
        result = _deterministic_truncate("A" * 10000, 100)
        assert len(result) < 10000
        assert "deterministic truncation" in result

    def test_truncate_short(self):
        assert _deterministic_truncate("hello", 1000) == "hello"
