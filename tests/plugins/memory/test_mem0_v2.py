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
