from pathlib import Path

from tools.memory_tool import MemoryStore


def test_overflow_downshift_queues_pending_index_when_writeback_budget_is_tight(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.memory_tool.get_memory_dir", lambda: tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

    store = MemoryStore(memory_char_limit=500, user_char_limit=300)
    store.load_from_disk()
    store._path_for("memory").write_text("x" * 420, encoding="utf-8")
    store._reload_target("memory")
    result = store.add(
        "memory",
        "## Summary\nLong-form evidence that should downshift while still leaving room for an index.",
    )

    assert result["success"] is False
    assert result["obsidian_downshift"]["success"] is True
    assert result["index_entry"]
    assert result["index_saved"] is False
    assert result["index_queued"] is True
    assert result["index_entry"] not in store.memory_entries
    assert result["pending_index_entries"] == [result["index_entry"]]
    assert Path(result["obsidian_downshift"]["path"]).exists()
    assert (tmp_path / "MEMORY_PENDING_INDEX.md").exists()


def test_pending_index_is_written_back_after_space_is_freed(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.memory_tool.get_memory_dir", lambda: tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

    store = MemoryStore(memory_char_limit=500, user_char_limit=300)
    store.load_from_disk()
    store._path_for("memory").write_text("x" * 420, encoding="utf-8")
    store._reload_target("memory")
    overflow = store.add(
        "memory",
        "## Summary\nLong-form evidence that should downshift while still leaving room for an index.",
    )
    index_entry = overflow["index_entry"]

    shrink = store.replace("memory", "x", "anchor")

    assert shrink["success"] is True
    assert shrink["pending_index_writebacks"] == [index_entry]
    assert index_entry in shrink["entries"]
    assert index_entry in store.memory_entries
    assert (tmp_path / "MEMORY_PENDING_INDEX.md").read_text(encoding="utf-8") == ""
