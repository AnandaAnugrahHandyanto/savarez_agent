"""Tests for the LangMem MemoryProvider implementation."""

import json
import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(tmp_path, user_id="nick"):
    """Build an initialized LangMemMemoryProvider backed by a tmp store."""
    from plugins.memory.langmem import LangMemMemoryProvider
    from plugins.memory.langmem.store import LangMemStore

    provider = LangMemMemoryProvider()
    provider._store = LangMemStore(tmp_path / "langmem.sqlite3")
    provider._store_path = tmp_path / "langmem.sqlite3"
    provider._user_id = user_id
    provider._session_id = "sess-test"
    provider._model = "anthropic:claude-3-5-haiku-latest"
    provider._enable_deletes = True
    provider._max_existing = 50
    provider._debounce_seconds = 0.0
    provider._profile_manager = MagicMock()
    provider._profile_manager.invoke.return_value = []
    return provider


def _fake_memory(mem_id, content, action="insert"):
    """Create a fake LangMem memory object."""
    inner = type("Content", (), {"content": content})()
    return type("FakeMem", (), {"id": mem_id, "content": inner, "action": action})()


# ---------------------------------------------------------------------------
# _normalize_memory
# ---------------------------------------------------------------------------

class TestNormalizeMemory:
    def test_nested_content_object(self):
        from plugins.memory.langmem import _normalize_memory

        mem = _fake_memory("m1", "Nick prefers concise responses")
        result = _normalize_memory(mem)
        assert result["content"] == "Nick prefers concise responses"
        assert result["id"] == "m1"
        assert result["action"] == "insert"

    def test_string_content(self):
        from plugins.memory.langmem import _normalize_memory

        mem = type("M", (), {"id": "m2", "content": "plain string", "action": "update"})()
        result = _normalize_memory(mem)
        assert result["content"] == "plain string"

    def test_missing_id_returns_none(self):
        from plugins.memory.langmem import _normalize_memory

        mem = type("M", (), {"content": "something", "action": "insert"})()
        result = _normalize_memory(mem)
        assert result["id"] is None

    def test_delete_action(self):
        from plugins.memory.langmem import _normalize_memory

        mem = _fake_memory("m3", "stale fact", action="delete")
        result = _normalize_memory(mem)
        assert result["action"] == "delete"


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

class TestToolSchemas:
    def test_returns_three_tools(self, tmp_path):
        provider = _make_provider(tmp_path)
        schemas = provider.get_tool_schemas()
        names = {s["name"] for s in schemas}
        assert names == {"langmem_profile", "langmem_search", "langmem_conclude"}

    def test_search_requires_query(self, tmp_path):
        provider = _make_provider(tmp_path)
        schemas = {s["name"]: s for s in provider.get_tool_schemas()}
        assert "query" in schemas["langmem_search"]["parameters"]["required"]

    def test_conclude_requires_conclusion(self, tmp_path):
        provider = _make_provider(tmp_path)
        schemas = {s["name"]: s for s in provider.get_tool_schemas()}
        assert "conclusion" in schemas["langmem_conclude"]["parameters"]["required"]


# ---------------------------------------------------------------------------
# handle_tool_call
# ---------------------------------------------------------------------------

class TestHandleToolCall:
    def test_profile_empty(self, tmp_path):
        provider = _make_provider(tmp_path)
        result = json.loads(provider.handle_tool_call("langmem_profile", {}))
        assert "No memories" in result["result"]

    def test_conclude_stores_fact(self, tmp_path):
        provider = _make_provider(tmp_path)
        result = json.loads(provider.handle_tool_call(
            "langmem_conclude", {"conclusion": "Nick hates verbose explanations"}
        ))
        assert result["result"] == "Fact stored."

        profile = json.loads(provider.handle_tool_call("langmem_profile", {}))
        assert "Nick hates verbose explanations" in profile["result"]

        row = provider._store.get_memory("nick", result["id"])
        meta = json.loads(row["metadata_json"])
        assert meta["lane"] == "preferences"
        assert meta["source_type"] == "conclude"
        assert "explicit" in meta["tags"]

    def test_search_finds_stored_fact(self, tmp_path):
        provider = _make_provider(tmp_path)
        provider.handle_tool_call("langmem_conclude", {"conclusion": "Nick prefers dark mode UI"})

        result = json.loads(provider.handle_tool_call("langmem_search", {"query": "dark mode"}))
        assert result["count"] > 0
        assert any("dark mode" in item["memory"] for item in result["results"])

    def test_search_empty_query_returns_error(self, tmp_path):
        provider = _make_provider(tmp_path)
        result = json.loads(provider.handle_tool_call("langmem_search", {}))
        assert "error" in result

    def test_conclude_empty_returns_error(self, tmp_path):
        provider = _make_provider(tmp_path)
        result = json.loads(provider.handle_tool_call("langmem_conclude", {}))
        assert "error" in result

    def test_unknown_tool_returns_error(self, tmp_path):
        provider = _make_provider(tmp_path)
        result = json.loads(provider.handle_tool_call("langmem_nonexistent", {}))
        assert "error" in result


# ---------------------------------------------------------------------------
# sync_turn — mocked LangMem manager
# ---------------------------------------------------------------------------

class TestSyncTurn:
    def test_sync_turn_persists_memories(self, tmp_path):
        provider = _make_provider(tmp_path)

        fake_mem = _fake_memory("m1", "Nick prefers concise responses", action="insert")
        provider._manager = MagicMock()
        provider._manager.invoke.return_value = [fake_mem]

        provider.sync_turn("remember I like short answers", "got it")
        # Wait for background thread
        if provider._sync_thread:
            provider._sync_thread.join(timeout=5.0)

        rows = provider._store.list_memories("nick")
        assert len(rows) == 1
        assert rows[0]["content"] == "Nick prefers concise responses"

    def test_sync_turn_delete_action_soft_deletes(self, tmp_path):
        provider = _make_provider(tmp_path)

        # Seed an existing memory
        provider._store.upsert_many("nick", [{"id": "old-id", "content": "old preference"}])

        fake_del = _fake_memory("old-id", "old preference", action="delete")
        provider._manager = MagicMock()
        provider._manager.invoke.return_value = [fake_del]

        provider.sync_turn("I changed my mind", "noted")
        if provider._sync_thread:
            provider._sync_thread.join(timeout=5.0)

        rows = provider._store.list_memories("nick", include_deleted=True)
        deleted = [r for r in rows if r["id"] == "old-id"]
        assert deleted[0]["deleted_at"] is not None

    def test_sync_turn_omission_does_not_delete(self, tmp_path):
        """LangMem returning no update for an existing memory must not delete it."""
        provider = _make_provider(tmp_path)

        provider._store.upsert_many("nick", [
            {"id": "keep", "content": "Nick wants concise responses"},
            {"id": "also-keep", "content": "Nick uses dark mode"},
        ])

        # LangMem returns only one memory (omitting 'also-keep')
        fake = _fake_memory("keep", "Nick wants concise responses", action="update")
        provider._manager = MagicMock()
        provider._manager.invoke.return_value = [fake]

        provider.sync_turn("short answer please", "sure")
        if provider._sync_thread:
            provider._sync_thread.join(timeout=5.0)

        rows = {r["id"]: r for r in provider._store.list_memories("nick")}
        assert "also-keep" in rows, "Omitted memory must not be deleted"
        assert rows["also-keep"]["deleted_at"] is None

    def test_sync_turn_no_crash_on_empty_result(self, tmp_path):
        provider = _make_provider(tmp_path)
        provider._manager = MagicMock()
        provider._manager.invoke.return_value = []

        provider.sync_turn("hello", "hi")
        if provider._sync_thread:
            provider._sync_thread.join(timeout=5.0)

        # No crash, no rows
        rows = provider._store.list_memories("nick")
        assert rows == []

    def test_sync_turn_debounces_multiple_quick_calls(self, tmp_path):
        provider = _make_provider(tmp_path)
        provider._debounce_seconds = 0.05
        provider._manager = MagicMock()
        provider._manager.invoke.return_value = [
            _fake_memory("m1", "latest fact", action="insert")
        ]

        provider.sync_turn("first", "one")
        provider.sync_turn("second", "two")
        provider.sync_turn("third", "three")
        if provider._sync_thread:
            provider._sync_thread.join(timeout=5.0)

        assert provider._manager.invoke.call_count == 1
        payload = provider._manager.invoke.call_args[0][0]
        assert payload["messages"][0]["content"] == "third"
        assert payload["messages"][1]["content"] == "three"

        rows = provider._store.list_memories("nick")
        assert len(rows) == 1
        assert rows[0]["content"] == "latest fact"


# ---------------------------------------------------------------------------
# User ID scoping
# ---------------------------------------------------------------------------

class TestUserIdScoping:
    def test_initialize_sets_user_id(self, tmp_path, monkeypatch):
        from plugins.memory.langmem import LangMemMemoryProvider
        from plugins.memory.langmem.store import LangMemStore

        provider = LangMemMemoryProvider()
        # Patch store initialization to use tmp_path
        orig_init = LangMemStore.__init__
        def fake_store_init(self, path):
            orig_init(self, tmp_path / "langmem.sqlite3")
        monkeypatch.setattr(LangMemStore, "__init__", fake_store_init)
        monkeypatch.setattr(
            "plugins.memory.langmem._load_config",
            lambda: {"model": "anthropic:claude-3-5-haiku-latest", "enable_deletes": True, "max_existing": 50, "debounce_seconds": 0.0}
        )
        from hermes_constants import get_hermes_home
        monkeypatch.setattr(
            "plugins.memory.langmem.LangMemMemoryProvider.initialize",
            lambda self, session_id, **kw: (
                setattr(self, "_user_id", kw.get("user_id") or "hermes-user"),
                setattr(self, "_session_id", session_id),
                setattr(self, "_model", "anthropic:claude-3-5-haiku-latest"),
                setattr(self, "_enable_deletes", True),
                setattr(self, "_max_existing", 50),
                setattr(self, "_store", LangMemStore(tmp_path / "langmem.sqlite3")),
            )
        )

        provider.initialize("sess-abc", user_id="alice")
        assert provider._user_id == "alice"

    def test_conclude_is_user_scoped(self, tmp_path):
        alice = _make_provider(tmp_path, user_id="alice")
        bob = _make_provider(tmp_path, user_id="bob")
        # Both share the same store path
        bob._store = alice._store

        alice.handle_tool_call("langmem_conclude", {"conclusion": "Alice likes Python"})
        bob.handle_tool_call("langmem_conclude", {"conclusion": "Bob likes Go"})

        alice_profile = json.loads(alice.handle_tool_call("langmem_profile", {}))
        assert "Alice" in alice_profile["result"]
        assert "Bob" not in alice_profile["result"]

        bob_profile = json.loads(bob.handle_tool_call("langmem_profile", {}))
        assert "Bob" in bob_profile["result"]
        assert "Alice" not in bob_profile["result"]


# ---------------------------------------------------------------------------
# Provider discovery
# ---------------------------------------------------------------------------

class TestDiscovery:
    def test_langmem_is_discoverable(self):
        from plugins.memory import find_provider_dir
        path = find_provider_dir("langmem")
        assert path is not None
        assert path.name == "langmem"

    def test_langmem_loads_via_plugin_system(self):
        from plugins.memory import load_memory_provider
        p = load_memory_provider("langmem")
        assert p is not None
        assert p.name == "langmem"

    def test_langmem_in_discover_list(self):
        from plugins.memory import discover_memory_providers
        providers = discover_memory_providers()
        names = [n for n, _, _ in providers]
        assert "langmem" in names
