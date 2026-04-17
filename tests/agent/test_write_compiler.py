import json

from agent.write_compiler import WriteCompiler
from tools.memory_tool import MemoryStore


def test_write_compiler_materializes_restore_critical_sidecars(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    store = MemoryStore()
    store.load_from_disk()
    result = store.add("memory", "Recovery note", kind="constraint", source="test")
    assert result["success"] is True

    compiler = WriteCompiler(hermes_home=hermes_home)
    event = compiler.compile_memory_write(
        action="add",
        target="memory",
        content="Recovery note",
        store_result=result,
        kind="constraint",
        source="test",
        restore_critical=True,
        provenance_ref="operator:test",
    )

    payload = event.to_dict()
    assert payload["restore_critical"] is True
    assert payload["materialization_status"]["chain_of_shells"] == "written"
    assert payload["materialization_status"]["file_anchors"] == "written"

    cos_path = hermes_home / "memory" / "chain-of-shells" / "control-plane-events" / f"{event.event_id}.json"
    anchor_path = hermes_home / "memory" / "file-anchors" / "control-plane-events" / f"{event.event_id}.json"
    latest_path = hermes_home / "state" / "last_memory_event.json"

    assert cos_path.exists()
    assert anchor_path.exists()
    assert latest_path.exists()
    assert json.loads(latest_path.read_text(encoding="utf-8"))["event_id"] == event.event_id
