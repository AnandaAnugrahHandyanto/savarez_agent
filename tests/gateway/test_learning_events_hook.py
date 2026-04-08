import json

import pytest

from gateway.builtin_hooks import learning_events


@pytest.mark.asyncio
async def test_learning_events_writes_compact_command_event(tmp_path, monkeypatch):
    monkeypatch.setattr(learning_events, "get_hermes_home", lambda: tmp_path)

    await learning_events.handle(
        "command:reset",
        {
            "platform": "telegram",
            "session_key": "agent:main:telegram:dm:1",
            "command": "reset",
            "args": "force now",
        },
    )

    out = tmp_path / "gateway_learning_events.jsonl"
    assert out.exists()
    row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert row["event_type"] == "command:reset"
    assert row["platform"] == "telegram"
    assert row["command"] == "reset"


@pytest.mark.asyncio
async def test_learning_events_ignores_untracked_event_types(tmp_path, monkeypatch):
    monkeypatch.setattr(learning_events, "get_hermes_home", lambda: tmp_path)

    await learning_events.handle("agent:start", {"platform": "telegram"})

    out = tmp_path / "gateway_learning_events.jsonl"
    assert not out.exists()
