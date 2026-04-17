import json

from tools.memory_tool import MemoryStore, memory_tool


def test_memory_tool_returns_canonical_memory_event(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    store = MemoryStore()
    store.load_from_disk()

    result = json.loads(
        memory_tool(
            action="add",
            target="memory",
            content="Restore-critical fact",
            store=store,
            restore_critical=True,
            provenance_ref="operator:test",
        )
    )

    assert result["success"] is True
    assert result["memory_event"]["restore_critical"] is True
    assert result["memory_event"]["materialization_status"]["chain_of_shells"] == "written"
