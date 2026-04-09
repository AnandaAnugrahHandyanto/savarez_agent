"""Tests for Mem0 API v2 compatibility — filters param and dict response unwrapping.

Salvaged from PRs #5301 (qaqcvc) and #5117 (vvvanguards).
"""

import json
from pathlib import Path

import pytest

from plugins.memory.mem0 import (
    Mem0MemoryProvider,
    _CURATE_DELETE_THRESHOLD,
    _CURATE_UPDATE_THRESHOLD,
    _load_config,
    _normalize_config_values,
)


class FakeClientV2:
    """Fake Mem0 client that returns v2-style dict responses and captures call kwargs."""

    def __init__(self, search_results=None, all_results=None):
        self._search_results = search_results or {"results": []}
        self._all_results = all_results or {"results": []}
        self.captured_search = {}
        self.captured_get_all = {}
        self.captured_add = []
        self.captured_update = []
        self.captured_delete = []

    def search(self, **kwargs):
        self.captured_search = kwargs
        return self._search_results

    def get_all(self, **kwargs):
        self.captured_get_all = kwargs
        return self._all_results

    def add(self, messages, **kwargs):
        self.captured_add.append({"messages": messages, **kwargs})

    def update(self, memory_id, **kwargs):
        self.captured_update.append({"memory_id": memory_id, **kwargs})
        return {"memory_id": memory_id, **kwargs}

    def delete(self, memory_id):
        self.captured_delete.append(memory_id)
        return {"memory_id": memory_id, "deleted": True}


# ---------------------------------------------------------------------------
# Filter migration: bare user_id= -> filters={}
# ---------------------------------------------------------------------------


class TestMem0FiltersV2:
    """All API calls must use filters={} instead of bare user_id= kwargs."""

    def _make_provider(self, monkeypatch, client):
        provider = Mem0MemoryProvider()
        provider.initialize("test-session")
        provider._user_id = "u123"
        provider._agent_id = "hermes"
        provider._auto_capture = True
        monkeypatch.setattr(provider, "_get_client", lambda: client)
        return provider

    def test_search_uses_filters(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client)

        provider.handle_tool_call("mem0_search", {"query": "hello", "top_k": 3, "rerank": False})

        assert client.captured_search["query"] == "hello"
        assert client.captured_search["top_k"] == 3
        assert client.captured_search["rerank"] is False
        assert client.captured_search["filters"] == {"user_id": "u123"}
        # Must NOT have bare user_id kwarg
        assert "user_id" not in {k for k in client.captured_search if k != "filters"}

    def test_profile_uses_filters(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client)

        provider.handle_tool_call("mem0_profile", {})

        assert client.captured_get_all["filters"] == {"user_id": "u123"}
        assert "user_id" not in {k for k in client.captured_get_all if k != "filters"}

    def test_prefetch_uses_filters(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client)

        provider.queue_prefetch("hello")
        provider._prefetch_thread.join(timeout=2)

        assert client.captured_search["query"] == "hello"
        assert client.captured_search["filters"] == {"user_id": "u123"}
        assert "user_id" not in {k for k in client.captured_search if k != "filters"}

    def test_sync_turn_uses_write_filters(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client)

        provider.sync_turn("user said this", "assistant replied", session_id="s1")
        provider._sync_thread.join(timeout=2)

        assert len(client.captured_add) == 1
        call = client.captured_add[0]
        assert call["user_id"] == "u123"
        assert call["agent_id"] == "hermes"

    def test_conclude_uses_write_filters(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client)

        provider.handle_tool_call("mem0_conclude", {"conclusion": "user likes dark mode"})

        assert len(client.captured_add) == 1
        call = client.captured_add[0]
        assert call["user_id"] == "u123"
        assert call["agent_id"] == "hermes"
        assert call["infer"] is False

    def test_read_filters_no_agent_id(self):
        """Read filters should use user_id only — cross-session recall across agents."""
        provider = Mem0MemoryProvider()
        provider._user_id = "u123"
        provider._agent_id = "hermes"
        assert provider._read_filters() == {"user_id": "u123"}

    def test_write_filters_include_agent_id(self):
        """Write filters should include agent_id for attribution."""
        provider = Mem0MemoryProvider()
        provider._user_id = "u123"
        provider._agent_id = "hermes"
        assert provider._write_filters() == {"user_id": "u123", "agent_id": "hermes"}


# ---------------------------------------------------------------------------
# Dict response unwrapping (API v2 wraps in {"results": [...]})
# ---------------------------------------------------------------------------


class TestMem0ResponseUnwrapping:
    """API v2 returns {"results": [...]} dicts; we must extract the list."""

    def _make_provider(self, monkeypatch, client):
        provider = Mem0MemoryProvider()
        provider.initialize("test-session")
        monkeypatch.setattr(provider, "_get_client", lambda: client)
        return provider

    def test_profile_dict_response(self, monkeypatch):
        client = FakeClientV2(all_results={"results": [
            {"id": "m1", "memory": "alpha"},
            {"memory_id": "m2", "memory": "beta"},
        ]})
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call("mem0_profile", {}))

        assert result["count"] == 2
        assert "alpha" in result["result"]
        assert "beta" in result["result"]
        assert result["items"][0]["id"] == "m1"
        assert result["items"][1]["id"] == "m2"

    def test_profile_list_response_backward_compat(self, monkeypatch):
        """Old API returned bare lists — still works."""
        client = FakeClientV2(all_results=[{"memory": "gamma"}])
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call("mem0_profile", {}))
        assert result["count"] == 1
        assert "gamma" in result["result"]

    def test_search_dict_response(self, monkeypatch):
        client = FakeClientV2(search_results={
            "results": [
                {"id": "m1", "memory": "foo", "score": 0.9},
                {"memory_id": "m2", "memory": "bar", "score": 0.7},
            ]
        })
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call(
            "mem0_search", {"query": "test", "top_k": 5}
        ))

        assert result["count"] == 2
        assert result["results"][0]["memory"] == "foo"
        assert result["results"][0]["id"] == "m1"
        assert result["results"][1]["id"] == "m2"

    def test_search_list_response_backward_compat(self, monkeypatch):
        """Old API returned bare lists — still works."""
        client = FakeClientV2(search_results=[{"memory": "baz", "score": 0.8}])
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call(
            "mem0_search", {"query": "test"}
        ))
        assert result["count"] == 1

    def test_unwrap_results_edge_cases(self):
        """_unwrap_results handles all shapes gracefully."""
        assert Mem0MemoryProvider._unwrap_results({"results": [1, 2]}) == [1, 2]
        assert Mem0MemoryProvider._unwrap_results([3, 4]) == [3, 4]
        assert Mem0MemoryProvider._unwrap_results({}) == []
        assert Mem0MemoryProvider._unwrap_results(None) == []
        assert Mem0MemoryProvider._unwrap_results("unexpected") == []

    def test_prefetch_dict_response(self, monkeypatch):
        client = FakeClientV2(search_results={
            "results": [{"memory": "user prefers dark mode"}]
        })
        provider = Mem0MemoryProvider()
        provider.initialize("test-session")
        monkeypatch.setattr(provider, "_get_client", lambda: client)

        provider.queue_prefetch("preferences")
        provider._prefetch_thread.join(timeout=2)
        result = provider.prefetch("preferences")

        assert "dark mode" in result


# ---------------------------------------------------------------------------
# Default preservation
# ---------------------------------------------------------------------------


class TestMem0Defaults:
    """Ensure we don't break existing users' defaults."""

    def test_default_user_id_hermes_user(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEM0_API_KEY", "test-key")
        monkeypatch.delenv("MEM0_USER_ID", raising=False)
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        provider = Mem0MemoryProvider()
        provider.initialize("test")

        assert provider._user_id == "hermes-user"

    def test_default_agent_id_hermes(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEM0_API_KEY", "test-key")
        monkeypatch.delenv("MEM0_AGENT_ID", raising=False)
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        provider = Mem0MemoryProvider()
        provider.initialize("test")

        assert provider._agent_id == "hermes"


class TestMem0LifecycleTools:
    """Explicit Mem0 lifecycle tools should expose update/delete functionality."""

    def _make_provider(self, monkeypatch, client):
        provider = Mem0MemoryProvider()
        provider.initialize("test-session")
        provider._user_id = "u123"
        provider._agent_id = "hermes"
        monkeypatch.setattr(provider, "_get_client", lambda: client)
        return provider

    def test_update_tool_updates_memory_by_id(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call(
            "mem0_update", {"memory_id": "m1", "text": "corrected fact"}
        ))

        assert client.captured_update == [{"memory_id": "m1", "text": "corrected fact"}]
        assert result["result"] == "Memory updated."
        assert result["id"] == "m1"

    def test_delete_tool_deletes_memory_by_id(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call("mem0_delete", {"memory_id": "m1"}))

        assert client.captured_delete == ["m1"]
        assert result["result"] == "Memory deleted."
        assert result["id"] == "m1"


class TestMem0ConfigNormalization:
    """Config should normalize bool-ish values from setup/env input."""

    def test_load_config_coerces_rerank_string_to_bool(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("MEM0_API_KEY", "test-key")
        (tmp_path / "mem0.json").write_text(
            json.dumps({"user_id": "u1", "agent_id": "a1", "rerank": "false"}),
            encoding="utf-8",
        )

        cfg = _load_config()

        assert cfg["rerank"] is False

    def test_initialize_coerces_rerank_string_to_bool(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("MEM0_API_KEY", "test-key")
        (tmp_path / "mem0.json").write_text(
            json.dumps({"user_id": "u1", "agent_id": "a1", "rerank": "true"}),
            encoding="utf-8",
        )

        provider = Mem0MemoryProvider()
        provider.initialize("test")

        assert provider._rerank is True
        assert isinstance(provider._rerank, bool)

    def test_save_config_writes_rerank_as_boolean(self, tmp_path):
        provider = Mem0MemoryProvider()

        provider.save_config({"user_id": "u1", "agent_id": "a1", "rerank": "false"}, tmp_path)

        saved = json.loads((Path(tmp_path) / "mem0.json").read_text(encoding="utf-8"))
        assert saved["rerank"] is False
        assert isinstance(saved["rerank"], bool)


# ---------------------------------------------------------------------------
# Hobby-plan tuning: configurable knobs for usage saving
# ---------------------------------------------------------------------------


class TestHobbyPlanConfigNormalization:
    """_normalize_config_values handles the four new knobs correctly."""

    def test_defaults_applied(self):
        cfg = _normalize_config_values({})
        assert cfg["top_k"] == 3
        assert cfg["search_threshold"] == 0.5
        assert cfg["auto_capture"] is False
        assert cfg["auto_recall"] is True

    def test_camel_case_aliases_mapped(self):
        cfg = _normalize_config_values({
            "topK": 5,
            "searchThreshold": 0.7,
            "autoCapture": "true",
            "autoRecall": "false",
        })
        assert cfg["top_k"] == 5
        assert cfg["search_threshold"] == 0.7
        assert cfg["auto_capture"] is True
        assert cfg["auto_recall"] is False
        # camelCase keys removed
        assert "topK" not in cfg
        assert "searchThreshold" not in cfg
        assert "autoCapture" not in cfg
        assert "autoRecall" not in cfg

    def test_snake_case_takes_precedence_over_camel(self):
        cfg = _normalize_config_values({
            "top_k": 10,
            "topK": 20,
            "auto_capture": True,
            "autoCapture": False,
        })
        assert cfg["top_k"] == 10
        assert cfg["auto_capture"] is True

    def test_top_k_clamped(self):
        assert _normalize_config_values({"top_k": 0})["top_k"] == 1
        assert _normalize_config_values({"top_k": 100})["top_k"] == 50
        assert _normalize_config_values({"top_k": "garbage"})["top_k"] == 3

    def test_search_threshold_clamped(self):
        assert _normalize_config_values({"search_threshold": -0.5})["search_threshold"] == 0.0
        assert _normalize_config_values({"search_threshold": 1.5})["search_threshold"] == 1.0
        assert _normalize_config_values({"search_threshold": "garbage"})["search_threshold"] == 0.5

    def test_string_coercion_for_numeric_fields(self):
        cfg = _normalize_config_values({"top_k": "7", "search_threshold": "0.8"})
        assert cfg["top_k"] == 7
        assert cfg["search_threshold"] == 0.8


class TestHobbyPlanConfigLoading:
    """New knobs load from mem0.json including camelCase aliases."""

    def test_load_config_picks_up_new_knobs(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("MEM0_API_KEY", "test-key")
        (tmp_path / "mem0.json").write_text(json.dumps({
            "top_k": 5,
            "search_threshold": 0.8,
            "auto_capture": True,
            "auto_recall": False,
        }), encoding="utf-8")

        cfg = _load_config()
        assert cfg["top_k"] == 5
        assert cfg["search_threshold"] == 0.8
        assert cfg["auto_capture"] is True
        assert cfg["auto_recall"] is False

    def test_load_config_camel_case_from_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("MEM0_API_KEY", "test-key")
        (tmp_path / "mem0.json").write_text(json.dumps({
            "topK": 8,
            "searchThreshold": 0.3,
            "autoCapture": "true",
            "autoRecall": "false",
        }), encoding="utf-8")

        cfg = _load_config()
        assert cfg["top_k"] == 8
        assert cfg["search_threshold"] == 0.3
        assert cfg["auto_capture"] is True
        assert cfg["auto_recall"] is False

    def test_initialize_wires_knobs_to_provider(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("MEM0_API_KEY", "test-key")
        (tmp_path / "mem0.json").write_text(json.dumps({
            "top_k": 7,
            "search_threshold": 0.6,
            "auto_capture": True,
            "auto_recall": False,
        }), encoding="utf-8")

        provider = Mem0MemoryProvider()
        provider.initialize("test")
        assert provider._top_k == 7
        assert provider._search_threshold == 0.6
        assert provider._auto_capture is True
        assert provider._auto_recall is False


class TestAutoRecallGate:
    """queue_prefetch is gated by auto_recall."""

    def _make_provider(self, monkeypatch, client, *, auto_recall=True, top_k=3,
                       search_threshold=0.5):
        provider = Mem0MemoryProvider()
        provider.initialize("test-session")
        provider._user_id = "u123"
        provider._agent_id = "hermes"
        provider._auto_recall = auto_recall
        provider._top_k = top_k
        provider._search_threshold = search_threshold
        monkeypatch.setattr(provider, "_get_client", lambda: client)
        return provider

    def test_prefetch_skipped_when_auto_recall_false(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client, auto_recall=False)

        provider.queue_prefetch("hello")

        # Thread should not be started at all
        assert provider._prefetch_thread is None
        assert client.captured_search == {}

    def test_prefetch_runs_when_auto_recall_true(self, monkeypatch):
        client = FakeClientV2(search_results={
            "results": [{"memory": "user likes tests"}]
        })
        provider = self._make_provider(monkeypatch, client, auto_recall=True)

        provider.queue_prefetch("hello")
        provider._prefetch_thread.join(timeout=2)

        assert client.captured_search["query"] == "hello"

    def test_prefetch_uses_configured_top_k(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client, top_k=7)

        provider.queue_prefetch("hello")
        provider._prefetch_thread.join(timeout=2)

        assert client.captured_search["top_k"] == 7


class TestSearchThresholdFiltering:
    """Prefetch filters results by search_threshold when scores are present."""

    def _make_provider(self, monkeypatch, client, *, search_threshold=0.5):
        provider = Mem0MemoryProvider()
        provider.initialize("test-session")
        provider._user_id = "u123"
        provider._auto_recall = True
        provider._search_threshold = search_threshold
        monkeypatch.setattr(provider, "_get_client", lambda: client)
        return provider

    def test_results_below_threshold_filtered(self, monkeypatch):
        client = FakeClientV2(search_results={"results": [
            {"memory": "high", "score": 0.9},
            {"memory": "low", "score": 0.3},
        ]})
        provider = self._make_provider(monkeypatch, client, search_threshold=0.5)

        provider.queue_prefetch("test")
        provider._prefetch_thread.join(timeout=2)
        result = provider.prefetch("test")

        assert "high" in result
        assert "low" not in result

    def test_results_without_score_pass_through(self, monkeypatch):
        client = FakeClientV2(search_results={"results": [
            {"memory": "no score"},
            {"memory": "has score", "score": 0.2},
        ]})
        provider = self._make_provider(monkeypatch, client, search_threshold=0.5)

        provider.queue_prefetch("test")
        provider._prefetch_thread.join(timeout=2)
        result = provider.prefetch("test")

        assert "no score" in result
        assert "has score" not in result

    def test_threshold_zero_passes_everything(self, monkeypatch):
        client = FakeClientV2(search_results={"results": [
            {"memory": "a", "score": 0.01},
            {"memory": "b", "score": 0.0},
        ]})
        provider = self._make_provider(monkeypatch, client, search_threshold=0.0)

        provider.queue_prefetch("test")
        provider._prefetch_thread.join(timeout=2)
        result = provider.prefetch("test")

        assert "a" in result
        assert "b" in result

    def test_filter_by_threshold_unit(self):
        provider = Mem0MemoryProvider()
        provider._search_threshold = 0.5
        results = [
            {"memory": "a", "score": 0.9},
            {"memory": "b", "score": 0.4},
            {"memory": "c"},  # no score — passes through
            {"memory": "d", "score": 0.5},  # exactly at threshold — passes
        ]
        filtered = provider._filter_by_threshold(results)
        memories = [r["memory"] for r in filtered]
        assert memories == ["a", "c", "d"]


class TestAutoCaptureGate:
    """sync_turn is gated by auto_capture."""

    def _make_provider(self, monkeypatch, client, *, auto_capture=False):
        provider = Mem0MemoryProvider()
        provider.initialize("test-session")
        provider._user_id = "u123"
        provider._agent_id = "hermes"
        provider._auto_capture = auto_capture
        monkeypatch.setattr(provider, "_get_client", lambda: client)
        return provider

    def test_sync_turn_skipped_when_auto_capture_false(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client, auto_capture=False)

        provider.sync_turn("user said this", "assistant replied", session_id="s1")

        # Thread should not be started at all
        assert provider._sync_thread is None
        assert len(client.captured_add) == 0

    def test_sync_turn_runs_when_auto_capture_true(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client, auto_capture=True)

        provider.sync_turn("user said this", "assistant replied", session_id="s1")
        provider._sync_thread.join(timeout=2)

        assert len(client.captured_add) == 1



# ---------------------------------------------------------------------------
# Mem0 curation: on_memory_write dedupe/update/delete/conclude
# ---------------------------------------------------------------------------


class TestMem0Curation:
    """Test _curate_memory_write: search Mem0 → decide → update/delete/conclude."""

    def _make_provider(self, monkeypatch, client):
        provider = Mem0MemoryProvider()
        provider.initialize("test-session")
        provider._user_id = "u123"
        provider._agent_id = "hermes"
        monkeypatch.setattr(provider, "_get_client", lambda: client)
        return provider

    # -- Genuinely new fact → conclude ------------------------------------

    def test_new_fact_no_existing_memories_concludes(self, monkeypatch):
        """No existing memories → conclude as new fact."""
        client = FakeClientV2(search_results={"results": []})
        provider = self._make_provider(monkeypatch, client)

        result = provider._curate_memory_write("I prefer dark mode")

        assert result["action"] == "concluded"
        assert len(client.captured_add) == 1
        call = client.captured_add[0]
        assert call["messages"] == [{"role": "user", "content": "I prefer dark mode"}]
        assert call["infer"] is False

    def test_new_fact_low_similarity_concludes(self, monkeypatch):
        """Existing memories with low similarity → conclude as new fact."""
        client = FakeClientV2(search_results={"results": [
            {"id": "m1", "memory": "User uses Linux", "score": 0.3},
        ]})
        provider = self._make_provider(monkeypatch, client)

        result = provider._curate_memory_write("I prefer dark mode")

        assert result["action"] == "concluded"
        assert len(client.captured_add) == 1
        assert client.captured_update == []

    # -- Corrected/reworded fact → update ---------------------------------

    def test_similar_fact_updates_existing(self, monkeypatch):
        """Semantically similar but reworded fact → update existing memory."""
        client = FakeClientV2(search_results={"results": [
            {"id": "m1", "memory": "User prefers light mode", "score": 0.8},
        ]})
        provider = self._make_provider(monkeypatch, client)

        result = provider._curate_memory_write("I prefer dark mode")

        assert result["action"] == "updated"
        assert result["id"] == "m1"
        assert client.captured_update == [{"memory_id": "m1", "text": "I prefer dark mode"}]
        assert client.captured_add == []  # No conclude — updated instead

    # -- Exact duplicate → skip -------------------------------------------

    def test_exact_duplicate_skips(self, monkeypatch):
        """Exact same text already in Mem0 → skip (no write)."""
        client = FakeClientV2(search_results={"results": [
            {"id": "m1", "memory": "I prefer dark mode", "score": 0.99},
        ]})
        provider = self._make_provider(monkeypatch, client)

        result = provider._curate_memory_write("I prefer dark mode")

        assert result["action"] == "skipped"
        assert client.captured_add == []
        assert client.captured_update == []
        assert client.captured_delete == []

    def test_exact_duplicate_case_insensitive(self, monkeypatch):
        """Case-insensitive exact match → skip."""
        client = FakeClientV2(search_results={"results": [
            {"id": "m1", "memory": "I Prefer Dark Mode", "score": 0.95},
        ]})
        provider = self._make_provider(monkeypatch, client)

        result = provider._curate_memory_write("i prefer dark mode")

        assert result["action"] == "skipped"

    # -- Stale duplicate cleanup → delete ---------------------------------

    def test_stale_duplicates_deleted_during_update(self, monkeypatch):
        """When updating, additional high-similarity results are deleted."""
        client = FakeClientV2(search_results={"results": [
            {"id": "m1", "memory": "User prefers light mode", "score": 0.82},
            {"id": "m2", "memory": "User likes light theme", "score": 0.90},
            {"id": "m3", "memory": "Something unrelated", "score": 0.4},
        ]})
        provider = self._make_provider(monkeypatch, client)

        result = provider._curate_memory_write("I prefer dark mode")

        assert result["action"] == "updated"
        assert result["id"] == "m1"
        # m2 scores above DELETE threshold → deleted as stale duplicate
        assert "m2" in result["deleted_ids"]
        assert client.captured_delete == ["m2"]
        # m3 below DELETE threshold → kept
        assert "m3" not in result.get("deleted_ids", [])

    def test_no_stale_duplicates_when_extras_below_threshold(self, monkeypatch):
        """Additional results below DELETE threshold are not deleted."""
        client = FakeClientV2(search_results={"results": [
            {"id": "m1", "memory": "User prefers light mode", "score": 0.8},
            {"id": "m2", "memory": "Something moderate", "score": 0.6},
        ]})
        provider = self._make_provider(monkeypatch, client)

        result = provider._curate_memory_write("I prefer dark mode")

        assert result["action"] == "updated"
        assert result.get("deleted_ids", []) == []
        assert client.captured_delete == []

    # -- on_memory_write integration --------------------------------------

    def test_on_memory_write_triggers_curate_for_add(self, monkeypatch):
        """on_memory_write with action='add' triggers curation."""
        client = FakeClientV2(search_results={"results": []})
        provider = self._make_provider(monkeypatch, client)

        provider.on_memory_write("add", "user", "I prefer dark mode")
        # Join the background thread to ensure it completes
        if provider._curate_thread:
            provider._curate_thread.join(timeout=2)

        assert len(client.captured_add) == 1

    def test_on_memory_write_triggers_curate_for_replace(self, monkeypatch):
        """on_memory_write with action='replace' triggers curation."""
        client = FakeClientV2(search_results={"results": []})
        provider = self._make_provider(monkeypatch, client)

        provider.on_memory_write("replace", "user", "I prefer dark mode")
        if provider._curate_thread:
            provider._curate_thread.join(timeout=2)

        assert len(client.captured_add) == 1

    def test_on_memory_write_skips_remove_action(self, monkeypatch):
        """on_memory_write with action='remove' does nothing."""
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client)

        provider.on_memory_write("remove", "user", "something")

        assert provider._curate_thread is None
        assert client.captured_add == []

    def test_on_memory_write_skips_empty_content(self, monkeypatch):
        """on_memory_write with empty content does nothing."""
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client)

        provider.on_memory_write("add", "user", "")

        assert provider._curate_thread is None

    def test_on_memory_write_skips_when_breaker_open(self, monkeypatch):
        """on_memory_write does nothing when circuit breaker is tripped."""
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client)
        # Trip the circuit breaker
        provider._consecutive_failures = 10
        provider._breaker_open_until = float("inf")

        provider.on_memory_write("add", "user", "fact")

        assert provider._curate_thread is None

    # -- Error handling ---------------------------------------------------

    def test_curate_search_failure_returns_failed(self, monkeypatch):
        """Search failure in curate → returns failed, doesn't crash."""
        client = FakeClientV2()
        client.search = lambda **kw: (_ for _ in ()).throw(RuntimeError("API down"))
        provider = self._make_provider(monkeypatch, client)

        result = provider._curate_memory_write("some fact")

        assert result["action"] == "failed"

    def test_curate_conclude_failure_returns_failed(self, monkeypatch):
        """Conclude failure after no match → returns failed."""
        client = FakeClientV2(search_results={"results": []})
        client.add = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("write fail"))
        provider = self._make_provider(monkeypatch, client)

        result = provider._curate_memory_write("some fact")

        assert result["action"] == "failed"

    def test_curate_update_failure_returns_failed(self, monkeypatch):
        """Update failure → returns failed, doesn't attempt delete."""
        client = FakeClientV2(search_results={"results": [
            {"id": "m1", "memory": "old version", "score": 0.9},
            {"id": "m2", "memory": "duplicate", "score": 0.95},
        ]})
        client.update = lambda **kw: (_ for _ in ()).throw(RuntimeError("update fail"))
        provider = self._make_provider(monkeypatch, client)

        result = provider._curate_memory_write("new version")

        assert result["action"] == "failed"
        # Should NOT attempt to delete m2 since update failed
        assert client.captured_delete == []

    # -- Threshold sanity -------------------------------------------------

    def test_threshold_constants_are_reasonable(self):
        """Thresholds are in (0, 1] and UPDATE < DELETE."""
        assert 0 < _CURATE_UPDATE_THRESHOLD < 1
        assert 0 < _CURATE_DELETE_THRESHOLD <= 1
        assert _CURATE_UPDATE_THRESHOLD < _CURATE_DELETE_THRESHOLD

class TestManualToolsUnaffected:
    """Manual tools (mem0_search, mem0_conclude, etc.) work regardless of auto_* settings."""

    def _make_provider(self, monkeypatch, client):
        provider = Mem0MemoryProvider()
        provider.initialize("test-session")
        provider._user_id = "u123"
        provider._agent_id = "hermes"
        provider._auto_capture = False
        provider._auto_recall = False
        monkeypatch.setattr(provider, "_get_client", lambda: client)
        return provider

    def test_mem0_search_works_when_auto_recall_off(self, monkeypatch):
        client = FakeClientV2(search_results={
            "results": [{"id": "m1", "memory": "test fact", "score": 0.9}]
        })
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call(
            "mem0_search", {"query": "test", "top_k": 5}
        ))
        assert result["count"] == 1
        assert result["results"][0]["memory"] == "test fact"

    def test_mem0_conclude_works_when_auto_capture_off(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call(
            "mem0_conclude", {"conclusion": "user likes dark mode"}
        ))
        assert result["result"] == "Fact stored."
        assert len(client.captured_add) == 1

    def test_mem0_profile_works_when_auto_recall_off(self, monkeypatch):
        client = FakeClientV2(all_results={"results": [
            {"id": "m1", "memory": "a fact"}
        ]})
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call("mem0_profile", {}))
        assert result["count"] == 1

    def test_mem0_update_works_when_auto_settings_off(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call(
            "mem0_update", {"memory_id": "m1", "text": "corrected"}
        ))
        assert result["result"] == "Memory updated."

    def test_mem0_delete_works_when_auto_settings_off(self, monkeypatch):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call(
            "mem0_delete", {"memory_id": "m1"}
        ))
        assert result["result"] == "Memory deleted."


class TestConfigSchemaDocumentation:
    """Config schema includes the new knobs with correct defaults."""

    def test_schema_includes_all_new_keys(self):
        provider = Mem0MemoryProvider()
        schema = provider.get_config_schema()
        keys = [s["key"] for s in schema]
        assert "top_k" in keys
        assert "search_threshold" in keys
        assert "auto_capture" in keys
        assert "auto_recall" in keys

    def test_schema_defaults(self):
        provider = Mem0MemoryProvider()
        schema = {s["key"]: s for s in provider.get_config_schema()}
        assert schema["top_k"]["default"] == "3"
        assert schema["search_threshold"]["default"] == "0.5"
        assert schema["auto_capture"]["default"] == "false"
        assert schema["auto_recall"]["default"] == "true"

    def test_save_config_normalizes_new_knobs(self, tmp_path):
        provider = Mem0MemoryProvider()
        provider.save_config({
            "topK": 5,
            "searchThreshold": 0.7,
            "autoCapture": "true",
            "autoRecall": "false",
        }, tmp_path)

        saved = json.loads((Path(tmp_path) / "mem0.json").read_text(encoding="utf-8"))
        assert saved["top_k"] == 5
        assert saved["search_threshold"] == 0.7
        assert saved["auto_capture"] is True
        assert saved["auto_recall"] is False
        assert "topK" not in saved
