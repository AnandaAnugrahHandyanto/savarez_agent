"""Tests for the LangMem local SQLite store."""

import pytest


def test_store_round_trip(tmp_path):
    from plugins.memory.langmem.store import LangMemStore

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_many(
        "u1",
        [{
            "id": "a",
            "content": "Nick prefers concise answers",
            "metadata": {
                "lane": "preferences",
                "source_type": "test",
                "first_seen_session_id": "sess-1",
                "last_seen_session_id": "sess-1",
                "confirmation_count": 1,
                "tags": ["preference"],
            },
        }],
        session_id="sess-1",
    )
    rows = store.list_memories("u1")
    assert len(rows) == 1
    assert rows[0]["content"] == "Nick prefers concise answers"
    assert rows[0]["id"] == "a"
    assert rows[0]["deleted_at"] is None

    import json
    meta = json.loads(rows[0]["metadata_json"])
    assert meta["lane"] == "preferences"
    assert meta["source_type"] == "test"


def test_store_search_is_user_scoped(tmp_path):
    from plugins.memory.langmem.store import LangMemStore

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_many("alice", [{"id": "a", "content": "likes dark mode"}])
    store.upsert_many("bob", [{"id": "b", "content": "likes light mode"}])

    hits = store.search_memories("alice", "dark mode")
    assert len(hits) == 1
    assert hits[0]["id"] == "a"

    hits = store.search_memories("bob", "dark mode")
    assert len(hits) == 0


def test_reconcile_many_only_soft_deletes_explicit_delete_ids(tmp_path):
    from plugins.memory.langmem.store import LangMemStore

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_many("u1", [
        {"id": "keep", "content": "Nick wants browser-verified fixes"},
        {"id": "old", "content": "Nick prefers long essays"},
    ])

    # Reconcile with upsert of 'keep' only, and empty delete_ids.
    # 'old' must NOT be soft-deleted — omission ≠ deletion.
    store.reconcile_many(
        "u1",
        upserts=[{"id": "keep", "content": "Nick wants browser-verified fixes"}],
        delete_ids=[],
    )

    rows = {row["id"]: row for row in store.list_memories("u1")}
    assert "old" in rows, "'old' should still exist (omission != deletion)"
    assert rows["old"]["deleted_at"] is None, "'old' must not be soft-deleted"
    assert "keep" in rows


def test_reconcile_many_explicit_delete_soft_deletes(tmp_path):
    from plugins.memory.langmem.store import LangMemStore

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_many("u1", [
        {"id": "x", "content": "stale fact"},
        {"id": "y", "content": "good fact"},
    ])

    store.reconcile_many("u1", upserts=[], delete_ids=["x"])

    rows = {row["id"]: row for row in store.list_memories("u1", include_deleted=True)}
    assert rows["x"]["deleted_at"] is not None, "'x' should be soft-deleted"
    assert rows["y"]["deleted_at"] is None, "'y' should be unaffected"

    # list_memories excludes deleted by default
    live = [r["id"] for r in store.list_memories("u1")]
    assert "x" not in live
    assert "y" in live


def test_upsert_updates_content(tmp_path):
    from plugins.memory.langmem.store import LangMemStore

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_many("u1", [{"id": "m1", "content": "old content"}])
    store.upsert_many("u1", [{"id": "m1", "content": "new content"}])

    rows = store.list_memories("u1")
    assert len(rows) == 1
    assert rows[0]["content"] == "new content"


def test_upsert_revives_soft_deleted(tmp_path):
    from plugins.memory.langmem.store import LangMemStore

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_many("u1", [{"id": "m1", "content": "fact"}])
    store.delete_memory("u1", "m1")

    # Upserting again should clear deleted_at
    store.upsert_many("u1", [{"id": "m1", "content": "fact updated"}])
    rows = store.list_memories("u1")
    assert len(rows) == 1
    assert rows[0]["deleted_at"] is None


def test_search_returns_empty_on_no_match(tmp_path):
    from plugins.memory.langmem.store import LangMemStore

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_many("u1", [{"id": "a", "content": "Nick likes TypeScript"}])
    hits = store.search_memories("u1", "python")
    assert hits == []


def test_search_does_not_return_deleted(tmp_path):
    from plugins.memory.langmem.store import LangMemStore

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_many("u1", [{"id": "del", "content": "old preference deleted"}])
    store.delete_memory("u1", "del")

    hits = store.search_memories("u1", "old preference")
    assert all(h["id"] != "del" for h in hits)


def test_auto_generated_id(tmp_path):
    from plugins.memory.langmem.store import LangMemStore

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_many("u1", [{"content": "no explicit id"}])
    rows = store.list_memories("u1")
    assert len(rows) == 1
    assert rows[0]["id"]  # should be auto-generated UUID


def test_upsert_tracks_first_and_last_seen_sessions(tmp_path):
    from plugins.memory.langmem.store import LangMemStore
    import json

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_many(
        "u1",
        [{"id": "m1", "content": "Nick prefers concise answers", "metadata": {"lane": "preferences", "source_type": "sync_turn"}}],
        session_id="sess-1",
    )
    store.upsert_many(
        "u1",
        [{"id": "m1", "content": "Nick prefers concise answers", "metadata": {"lane": "preferences", "source_type": "sync_turn"}}],
        session_id="sess-2",
    )

    row = store.get_memory("u1", "m1")
    meta = json.loads(row["metadata_json"])
    assert meta["first_seen_session_id"] == "sess-1"
    assert meta["last_seen_session_id"] == "sess-2"


def test_upsert_increments_confirmation_count(tmp_path):
    from plugins.memory.langmem.store import LangMemStore
    import json

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_many("u1", [{"id": "m1", "content": "Nick likes dark mode"}], session_id="sess-1")
    store.upsert_many("u1", [{"id": "m1", "content": "Nick likes dark mode"}], session_id="sess-2")

    row = store.get_memory("u1", "m1")
    meta = json.loads(row["metadata_json"])
    assert meta["confirmation_count"] == 2


def test_profile_upsert_writes_profile_metadata(tmp_path):
    from plugins.memory.langmem.store import LangMemStore
    import json

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_profile("u1", {"preferred_name": "Nick"}, session_id="sess-profile")

    row = store.get_memory("u1", "profile:u1")
    meta = json.loads(row["metadata_json"])
    assert meta["lane"] == "profile"
    assert meta["source_type"] == "profile_sync"
    assert meta["last_seen_session_id"] == "sess-profile"


def test_search_prefers_confirmed_memory(tmp_path):
    from plugins.memory.langmem.store import LangMemStore

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_many(
        "u1",
        [{"id": "low", "content": "Nick prefers dark mode UI", "metadata": {"lane": "preferences", "source_type": "sync_turn"}}],
        session_id="sess-1",
    )
    store.upsert_many(
        "u1",
        [{"id": "high", "content": "Nick prefers dark mode UI", "metadata": {"lane": "preferences", "source_type": "sync_turn"}}],
        session_id="sess-1",
    )
    store.upsert_many(
        "u1",
        [{"id": "high", "content": "Nick prefers dark mode UI", "metadata": {"lane": "preferences", "source_type": "sync_turn"}}],
        session_id="sess-2",
    )
    store.upsert_many(
        "u1",
        [{"id": "high", "content": "Nick prefers dark mode UI", "metadata": {"lane": "preferences", "source_type": "sync_turn"}}],
        session_id="sess-3",
    )

    hits = store.search_memories("u1", "dark mode", limit=5)
    assert [row["id"] for row in hits[:2]] == ["high", "low"]


def test_search_prefers_recent_memory_when_text_matches(tmp_path):
    from plugins.memory.langmem.store import LangMemStore

    store = LangMemStore(tmp_path / "langmem.sqlite3")
    store.upsert_many(
        "u1",
        [{"id": "older", "content": "Nick wants browser verified fixes", "metadata": {"lane": "preferences", "source_type": "sync_turn"}}],
        session_id="sess-old",
    )
    store._conn.execute(
        "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
        (1.0, 1.0, "older"),
    )
    store._conn.commit()
    store.upsert_many(
        "u1",
        [{"id": "newer", "content": "Nick wants browser verified fixes", "metadata": {"lane": "preferences", "source_type": "sync_turn"}}],
        session_id="sess-new",
    )

    hits = store.search_memories("u1", "browser verified fixes", limit=5)
    assert [row["id"] for row in hits[:2]] == ["newer", "older"]


def test_langmem_plugin_dir_is_discoverable():
    from plugins.memory import find_provider_dir

    path = find_provider_dir("langmem")
    assert path is not None
    assert path.name == "langmem"
