import json
import sqlite3

from tools.memory_tool import MemoryStore, memory_tool


def test_add_over_limit_archives_without_failing(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    store = MemoryStore(memory_char_limit=10, user_char_limit=10)
    store.load_from_disk()

    first = json.loads(memory_tool("add", target="memory", content="small", store=store))
    assert first["success"] is True
    assert first["curated"] is True

    overflow = json.loads(
        memory_tool("add", target="memory", content="this entry cannot fit", store=store)
    )

    assert overflow["success"] is True
    assert overflow["archived"] is True
    assert overflow["curated"] is False
    assert "prompt-injected curated snapshot" in overflow["message"]

    memory_file = tmp_path / "memories" / "MEMORY.md"
    assert memory_file.read_text(encoding="utf-8") == "small"

    db_path = tmp_path / "memories" / "memory_archive.sqlite3"
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT target, content, curated, deleted_at FROM memory_archive ORDER BY id"
        ).fetchall()
    assert rows == [
        ("memory", "small", 1, None),
        ("memory", "this entry cannot fit", 0, None),
    ]


def test_search_retrieves_archived_overflow_memory(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    store = MemoryStore(memory_char_limit=8, user_char_limit=8)
    store.load_from_disk()
    memory_tool("add", target="user", content="tiny", store=store)
    memory_tool("add", target="user", content="prefers cap-safe durable memory", store=store)

    result = json.loads(
        memory_tool("search", target="user", content="durable", store=store)
    )

    assert result["success"] is True
    assert any("cap-safe durable memory" in m["content"] for m in result["matches"])


def test_remove_tombstones_archived_memory(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    store = MemoryStore(memory_char_limit=100, user_char_limit=100)
    store.load_from_disk()
    memory_tool("add", target="user", content="forget this zebra preference", store=store)

    removed = json.loads(memory_tool("remove", target="user", old_text="zebra", store=store))
    assert removed["success"] is True

    result = json.loads(memory_tool("search", target="user", content="zebra", store=store))
    assert result["matches"] == []

    db_path = tmp_path / "memories" / "memory_archive.sqlite3"
    with sqlite3.connect(db_path) as conn:
        deleted_at = conn.execute("SELECT deleted_at FROM memory_archive").fetchone()[0]
    assert deleted_at is not None


def test_replace_tombstones_old_archive_and_archives_new_memory(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    store = MemoryStore(memory_char_limit=100, user_char_limit=100)
    store.load_from_disk()
    memory_tool("add", target="user", content="prefers oldword memory", store=store)

    replaced = json.loads(
        memory_tool(
            "replace",
            target="user",
            old_text="oldword",
            content="prefers newword memory",
            store=store,
        )
    )
    assert replaced["success"] is True

    old_result = json.loads(memory_tool("search", target="user", content="oldword", store=store))
    new_result = json.loads(memory_tool("search", target="user", content="newword", store=store))

    assert old_result["matches"] == []
    assert any("newword" in m["content"] for m in new_result["matches"])


def test_add_refused_by_drift_does_not_archive(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    store = MemoryStore(memory_char_limit=100, user_char_limit=100)
    store.load_from_disk()
    memory_file = tmp_path / "memories" / "MEMORY.md"
    memory_file.write_text("manual edit that is too long for limit" * 10, encoding="utf-8")

    result = json.loads(memory_tool("add", target="memory", content="should not archive", store=store))
    assert result["success"] is False

    # The archive file may not exist because no accepted memory write occurred.
    db_path = tmp_path / "memories" / "memory_archive.sqlite3"
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute("SELECT content FROM memory_archive").fetchall()
        assert rows == []
