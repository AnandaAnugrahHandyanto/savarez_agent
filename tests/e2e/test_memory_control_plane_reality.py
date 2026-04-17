import json

from agent.recall_assembler import RecallAssembler
from agent.write_compiler import WriteCompiler
from tools.memory_tool import MemoryStore


class _FakeDB:
    def search_messages(self, **kwargs):
        return [
            {
                "session_id": "sess-1",
                "content": "We agreed the control plane needed one proof surface.",
                "session_started": 1710000000,
                "source": "cli",
                "model": "gpt-test",
            }
        ]

    def get_session(self, session_id):
        return {"session_id": session_id, "parent_session_id": None, "started_at": 1710000000}


def test_memory_control_plane_write_then_recall_roundtrip(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    store = MemoryStore()
    store.load_from_disk()
    result = store.add("memory", "One proof surface beats scattered checks.", kind="constraint", source="test")
    assert result["success"] is True

    compiler = WriteCompiler(hermes_home=hermes_home)
    event = compiler.compile_memory_write(
        action="add",
        target="memory",
        content="One proof surface beats scattered checks.",
        store_result=result,
        kind="constraint",
        source="test",
        restore_critical=True,
        provenance_ref="operator:test",
    )

    assembler = RecallAssembler(memory_store=store, session_db=_FakeDB(), hermes_home=hermes_home)
    bundle = assembler.assemble(
        query="what is the proof surface?",
        current_session_id=None,
        clerk_context="",
    )

    latest_event = json.loads((hermes_home / "state" / "last_memory_event.json").read_text(encoding="utf-8"))
    latest_receipt = json.loads((hermes_home / "state" / "last_recall_receipt.json").read_text(encoding="utf-8"))

    assert latest_event["event_id"] == event.event_id
    assert latest_receipt["receipt_id"] == bundle.receipt.receipt_id
    assert "sqlite_memory" in latest_receipt["lanes_used"]
