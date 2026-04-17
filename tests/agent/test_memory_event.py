from agent.memory_event import MemoryEvent


def test_memory_event_serializes_restore_critical_metadata():
    event = MemoryEvent(
        event_id="evt-123",
        action="add",
        target="memory",
        content="Never claim done without proof.",
        source_lane="sqlite_memory",
        target_lanes=["sqlite_memory", "wiki_compiled", "chain_of_shells", "file_anchors"],
        scope="global",
        scope_value=None,
        kind="constraint",
        restore_critical=True,
        provenance_ref="operator:test",
        materialization_status={
            "sqlite_memory": "written",
            "wiki_compiled": "mirrored",
            "chain_of_shells": "written",
            "file_anchors": "written",
        },
        materialization_results={"chain_of_shells": {"path": "/tmp/cos/evt-123.json"}},
        entry_id="entry-123",
        supersedes_entry_id=None,
        created_at="2026-04-17T00:00:00Z",
    )

    payload = event.to_dict()

    assert payload["event_id"] == "evt-123"
    assert payload["restore_critical"] is True
    assert payload["target_lanes"][-2:] == ["chain_of_shells", "file_anchors"]
    assert payload["materialization_status"]["chain_of_shells"] == "written"
    assert payload["materialization_results"]["chain_of_shells"]["path"].endswith("evt-123.json")
