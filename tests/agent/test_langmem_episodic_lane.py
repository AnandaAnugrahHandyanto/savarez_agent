"""Tests for the LangMem episodic memory lane."""

import json
from unittest.mock import MagicMock


def _make_provider(tmp_path, user_id="nick"):
    from plugins.memory.langmem import LangMemMemoryProvider
    from plugins.memory.langmem.store import LangMemStore

    provider = LangMemMemoryProvider()
    provider._store = LangMemStore(tmp_path / "langmem.sqlite3")
    provider._store_path = tmp_path / "langmem.sqlite3"
    provider._user_id = user_id
    provider._session_id = "sess-episode"
    provider._model = "anthropic:claude-3-5-haiku-latest"
    provider._enable_deletes = True
    provider._max_existing = 50
    provider._debounce_seconds = 0.0
    provider._manager = MagicMock()
    provider._manager.invoke.return_value = []
    provider._profile_manager = MagicMock()
    provider._profile_manager.invoke.return_value = []
    return provider


def _fake_episode(payload):
    return type("FakeEpisode", (), {"content": payload})()


def test_episode_lane_stores_success_patterns_separately(tmp_path):
    provider = _make_provider(tmp_path)
    provider._episode_manager = MagicMock()
    provider._episode_manager.invoke.return_value = [
        _fake_episode(
            {
                "observation": "User asked to continue the LangMem plan",
                "thoughts": "Task 5 should preserve user facts separately from reusable execution patterns",
                "action": "Implemented an episodic lane with a success heuristic",
                "result": "Focused tests passed",
            }
        )
    ]

    provider.sync_turn(
        "Proceed with the next LangMem task and keep going",
        "Implemented the episodic lane and verified the focused tests pass.",
    )
    if provider._sync_thread:
        provider._sync_thread.join(timeout=5.0)

    rows = provider._store.list_memories("nick")
    episodes = [row for row in rows if row["kind"] == "episode"]
    assert len(episodes) == 1
    assert episodes[0]["source"] == "langmem-episode"
    payload = json.loads(episodes[0]["content"])
    assert payload["action"] == "Implemented an episodic lane with a success heuristic"
    meta = json.loads(episodes[0]["metadata_json"])
    assert meta["lane"] == "episodes"
    assert meta["source_type"] == "episode_sync"


def test_episode_lane_skips_error_turns(tmp_path):
    provider = _make_provider(tmp_path)
    provider._episode_manager = MagicMock()
    provider._episode_manager.invoke.return_value = [
        _fake_episode(
            {
                "observation": "User asked for a task",
                "thoughts": "This should not be stored when the assistant errors",
                "action": "Tried a failing step",
                "result": "Command failed",
            }
        )
    ]

    provider.sync_turn(
        "Proceed",
        "Error: failed to complete the task due to a missing dependency.",
    )
    if provider._sync_thread:
        provider._sync_thread.join(timeout=5.0)

    rows = provider._store.list_memories("nick")
    assert [row for row in rows if row["kind"] == "episode"] == []
    assert provider._episode_manager.invoke.call_count == 0
