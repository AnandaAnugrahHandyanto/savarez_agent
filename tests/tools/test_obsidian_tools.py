import json

from tools.obsidian_tools import obsidian_read_tasks_tool


def test_obsidian_read_tasks_returns_only_active_tasks_by_default(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Tasks.md").write_text(
        "# Inbox\n"
        "- [ ] Pay bill 📅 2026-05-20\n"
        "- [/] Call contractor\n"
        "- [x] Old done\n"
        "# Home\n"
        "- [-] Cancelled thing\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

    result = json.loads(obsidian_read_tasks_tool(path="Tasks.md", include_done=False, limit=10))

    assert result["path"] == "Tasks.md"
    assert result["total_tasks"] == 4
    assert result["active_tasks"] == 2
    assert result["matched_tasks"] == 2
    assert result["returned_tasks"] == 2
    assert result["status_counts"] == {"open": 1, "active": 1, "done": 1, "cancelled": 1}
    assert [task["status"] for task in result["tasks"]] == ["open", "active"]
    assert result["tasks"][0]["line"] == 2
    assert result["tasks"][0]["section"] == "Inbox"
    assert result["tasks"][0]["due"] == "2026-05-20"


def test_obsidian_read_tasks_include_done_and_limit(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Tasks.md").write_text(
        "- [ ] One\n"
        "- [x] Two\n"
        "- [-] Three\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

    result = json.loads(obsidian_read_tasks_tool(include_done=True, limit=2))

    assert result["matched_tasks"] == 3
    assert result["returned_tasks"] == 2
    assert result["truncated"] is True
    assert [task["text"] for task in result["tasks"]] == ["One", "Two"]


def test_obsidian_read_tasks_rejects_paths_outside_vault(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

    result = json.loads(obsidian_read_tasks_tool(path="../outside.md"))

    assert "error" in result
    assert "inside Obsidian vault" in result["error"]
    assert result["tasks"] == []
