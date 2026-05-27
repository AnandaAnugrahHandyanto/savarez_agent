"""Tests for Mem0 API v2 compatibility — filters param and dict response unwrapping.

Salvaged from PRs #5301 (qaqcvc) and #5117 (vvvanguards).
"""

import json
import pytest

from plugins.memory.mem0 import Mem0MemoryProvider


class FakeClientV2:
    """Fake Mem0 client that returns v2-style dict responses and captures call kwargs."""

    def __init__(self, search_results=None, all_results=None, search_results_sequence=None, all_results_sequence=None):
        self._search_results = search_results or {"results": []}
        self._all_results = all_results or {"results": []}
        self._search_results_sequence = list(search_results_sequence or [])
        self._all_results_sequence = list(all_results_sequence or [])
        self.captured_search = {}
        self.captured_get_all = {}
        self.search_calls = []
        self.get_all_calls = []
        self.captured_add = []

    def search(self, **kwargs):
        self.captured_search = kwargs
        self.search_calls.append(kwargs)
        if self._search_results_sequence:
            return self._search_results_sequence.pop(0)
        return self._search_results

    def get_all(self, **kwargs):
        self.captured_get_all = kwargs
        self.get_all_calls.append(kwargs)
        if self._all_results_sequence:
            return self._all_results_sequence.pop(0)
        return self._all_results

    def add(self, messages, **kwargs):
        self.captured_add.append({"messages": messages, **kwargs})


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
        client = FakeClientV2(search_results={"results": [{"memory": "hello", "score": 0.9}]})
        provider = self._make_provider(monkeypatch, client)

        provider.handle_tool_call("mem0_search", {"query": "hello", "top_k": 3, "rerank": False})

        assert client.captured_search["query"] == "hello"
        assert client.captured_search["top_k"] == 3
        assert client.captured_search["rerank"] is False
        assert client.captured_search["filters"] == {"user_id": "u123"}
        # Must NOT have bare user_id kwarg
        assert "user_id" not in {k for k in client.captured_search if k != "filters"}

    def test_profile_uses_filters(self, monkeypatch):
        client = FakeClientV2(all_results={"results": [{"memory": "alpha"}]})
        provider = self._make_provider(monkeypatch, client)

        provider.handle_tool_call("mem0_profile", {})

        assert client.captured_get_all["filters"] == {"user_id": "u123"}
        assert "user_id" not in {k for k in client.captured_get_all if k != "filters"}

    def test_prefetch_uses_filters(self, monkeypatch):
        client = FakeClientV2(search_results={"results": [{"memory": "hello"}]})
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

        result = json.loads(provider.handle_tool_call("mem0_conclude", {"conclusion": "user likes dark mode"}))

        assert len(client.captured_add) == 1
        call = client.captured_add[0]
        assert call["user_id"] == "u123"
        assert call["agent_id"] == "hermes"
        assert call["infer"] is False
        assert call["messages"][0]["content"] == "[FACT/CURRENT] user likes dark mode"
        assert call["metadata"]["memory_class"] == "factual"
        assert call["metadata"]["time_scope"] == "current"
        assert result["stored"] == "user likes dark mode"

    def test_read_filters_no_agent_id(self):
        """Read filters should use user_id only — cross-session recall across agents."""
        provider = Mem0MemoryProvider()
        provider._user_id = "u123"
        provider._agent_id = "hermes"
        assert provider._read_filters() == {"user_id": "u123"}

    def test_search_falls_back_to_agent_scope_when_user_wide_empty(self, monkeypatch):
        client = FakeClientV2(
            search_results_sequence=[
                {"results": []},
                {"results": [{"memory": "agent memory", "score": 0.8}]},
            ]
        )
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call("mem0_search", {"query": "hello", "top_k": 3}))

        assert result["count"] == 1
        assert len(client.search_calls) == 2
        assert client.search_calls[0]["filters"] == {"user_id": "u123"}
        assert client.search_calls[1]["filters"] == {"user_id": "u123", "agent_id": "hermes"}

    def test_profile_falls_back_to_agent_scope_when_user_wide_empty(self, monkeypatch):
        client = FakeClientV2(
            all_results_sequence=[
                {"results": []},
                {"results": [{"memory": "agent memory"}]},
            ]
        )
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call("mem0_profile", {}))

        assert result["count"] == 1
        assert len(client.get_all_calls) == 2
        assert client.get_all_calls[0]["filters"] == {"user_id": "u123"}
        assert client.get_all_calls[1]["filters"] == {"user_id": "u123", "agent_id": "hermes"}

    def test_prefetch_falls_back_to_agent_scope_when_user_wide_empty(self, monkeypatch):
        client = FakeClientV2(
            search_results_sequence=[
                {"results": []},
                {"results": [{"memory": "agent memory"}]},
            ]
        )
        provider = self._make_provider(monkeypatch, client)

        provider.queue_prefetch("hello")
        provider._prefetch_thread.join(timeout=2)

        assert len(client.search_calls) == 2
        assert client.search_calls[0]["filters"] == {"user_id": "u123"}
        assert client.search_calls[1]["filters"] == {"user_id": "u123", "agent_id": "hermes"}

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
        client = FakeClientV2(all_results={"results": [{"memory": "alpha"}, {"memory": "beta"}]})
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call("mem0_profile", {}))

        assert result["count"] == 2
        assert "alpha" in result["result"]
        assert "beta" in result["result"]

    def test_profile_list_response_backward_compat(self, monkeypatch):
        """Old API returned bare lists — still works."""
        client = FakeClientV2(all_results=[{"memory": "gamma"}])
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call("mem0_profile", {}))
        assert result["count"] == 1
        assert "gamma" in result["result"]

    def test_search_dict_response(self, monkeypatch):
        client = FakeClientV2(search_results={
            "results": [{"memory": "foo", "score": 0.9}, {"memory": "bar", "score": 0.7}]
        })
        provider = self._make_provider(monkeypatch, client)

        result = json.loads(provider.handle_tool_call(
            "mem0_search", {"query": "test", "top_k": 5}
        ))

        assert result["count"] == 2
        assert result["results"][0]["memory"] == "foo"

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

    def test_default_sync_turn_mode_full(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEM0_API_KEY", "test-key")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        provider = Mem0MemoryProvider()
        provider.initialize("test")

        assert provider._sync_turn_mode == "full"

    def test_legacy_sync_turns_false_maps_to_off(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEM0_API_KEY", "test-key")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "mem0.json").write_text(json.dumps({"sync_turns": False}))

        provider = Mem0MemoryProvider()
        provider.initialize("test")

        assert provider._sync_turn_mode == "off"


class TestMem0ExplicitMemoryFormatting:
    def test_decorate_preference_memory(self):
        assert Mem0MemoryProvider._decorate_explicit_memory(
            "User prefers concise responses.",
            target="user",
        ) == "[PREF] User prefers concise responses."

    def test_decorate_doctrine_memory(self):
        assert Mem0MemoryProvider._decorate_explicit_memory(
            "OpenClaw is retired and should be ignored unless live Hermes residue still matters.",
            target="memory",
        ).startswith("[RULE/TIMELESS]")

    def test_format_memory_for_display_strips_prefix(self):
        assert Mem0MemoryProvider._format_memory_for_display(
            "[FACT/PAST] Previously Dockerized apps were hosted locally."
        ) == "Previously Dockerized apps were hosted locally."

    def test_on_memory_write_mirrors_explicit_metadata(self, monkeypatch):
        client = FakeClientV2()
        provider = Mem0MemoryProvider()
        provider.initialize("test-session")
        provider._user_id = "u123"
        provider._agent_id = "hermes"
        monkeypatch.setattr(provider, "_get_client", lambda: client)

        provider.on_memory_write(
            "add",
            "user",
            "User prefers concise responses.",
            metadata={"tool_name": "memory", "platform": "telegram"},
        )
        assert provider._write_thread is not None
        provider._write_thread.join(timeout=2)

        assert len(client.captured_add) == 1
        call = client.captured_add[0]
        assert call["messages"][0]["content"] == "[PREF] User prefers concise responses."
        assert call["metadata"]["memory_class"] == "preference"
        assert call["metadata"]["time_scope"] == "current"
        assert call["metadata"]["source"] == "builtin_memory_tool"


class TestMem0SyncTurnMode:
    def _make_provider(self, monkeypatch, client, tmp_path, sync_turn_mode="full"):
        monkeypatch.setenv("MEM0_API_KEY", "test-key")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        mem0_cfg = tmp_path / "mem0.json"
        mem0_cfg.write_text(json.dumps({"sync_turn_mode": sync_turn_mode}))
        provider = Mem0MemoryProvider()
        provider.initialize("test-session")
        provider._user_id = "u123"
        provider._agent_id = "hermes"
        monkeypatch.setattr(provider, "_get_client", lambda: client)
        return provider

    def test_sync_turn_mode_off_skips_turn_write(self, monkeypatch, tmp_path):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client, tmp_path, sync_turn_mode="off")

        provider.sync_turn("user said this", "assistant replied", session_id="s1")

        assert provider._sync_thread is None
        assert client.captured_add == []

    def test_sync_turn_mode_full_preserves_existing_behavior(self, monkeypatch, tmp_path):
        client = FakeClientV2()
        provider = self._make_provider(monkeypatch, client, tmp_path, sync_turn_mode="full")

        provider.sync_turn("user said this", "assistant replied", session_id="s1")
        assert provider._sync_thread is not None
        provider._sync_thread.join(timeout=2)

        assert len(client.captured_add) == 1
        call = client.captured_add[0]
        assert call["user_id"] == "u123"
        assert call["agent_id"] == "hermes"
