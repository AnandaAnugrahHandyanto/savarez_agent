from agent.recall_assembler import RecallAssembler
from tools.memory_tool import MemoryStore


class _FakeDB:
    def search_messages(self, **kwargs):
        return [
            {
                "session_id": "sess-1",
                "content": "Last week we decided proof receipts need one canonical format.",
                "session_started": 1710000000,
                "source": "cli",
                "model": "gpt-test",
            }
        ]

    def get_session(self, session_id):
        return {"session_id": session_id, "parent_session_id": None, "started_at": 1710000000}


def test_recall_assembler_combines_memory_session_and_clerk_lanes(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    store = MemoryStore()
    store.load_from_disk()
    store.add("memory", "Never claim done without proof.", kind="constraint", source="test")

    assembler = RecallAssembler(memory_store=store, session_db=_FakeDB())
    bundle = assembler.assemble(
        query="what did we decide about proof before reset?",
        current_session_id=None,
        clerk_context="next: verify the proof receipt path",
    )

    assert "Never claim done without proof." in bundle.context_block
    assert "proof receipt" in bundle.context_block.lower()
    assert "next: verify the proof receipt path" in bundle.context_block.lower()
    assert "sqlite_memory" in bundle.receipt.lanes_used
    assert "session_search" in bundle.receipt.lanes_used
    assert "clerk_reset" in bundle.receipt.lanes_used
