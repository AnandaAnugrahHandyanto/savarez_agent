import json

import pytest

from gateway.hooks import HookRegistry


@pytest.mark.asyncio
async def test_builtin_awareos_overlay_hook_emits_start_stop(tmp_path, monkeypatch):
    events_path = tmp_path / "awareos_events.jsonl"
    monkeypatch.setenv("AWAREOS_OVERLAY_ENABLED", "1")
    monkeypatch.setenv("AWAREOS_WORK_OVERLAY_EVENTS_PATH", str(events_path))

    reg = HookRegistry()
    reg.discover_and_load()

    ctx = {
        "platform": "telegram",
        "chat_id": "123",
        "message_id": "456",
        "session_id": "sess-abc",
        "session_key": "telegram:123",
        "user_id": "u1",
        "substantive": True,
        "api_calls": 3,
        "tool_names": ["terminal"],
        "response_length": 10,
        "model": "test-model",
    }

    await reg.emit("agent:start", dict(ctx))
    await reg.emit("agent:end", dict(ctx))

    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    start = json.loads(lines[0])
    stop = json.loads(lines[1])
    assert start["action"] == "start"
    assert stop["action"] == "stop"
    assert start["overlay_id"] == stop["overlay_id"]
    assert start["source"]["platform"] == "telegram"
    assert stop["result"]["tool_count"] == 1


@pytest.mark.asyncio
async def test_builtin_awareos_overlay_hook_skips_non_substantive(tmp_path, monkeypatch):
    events_path = tmp_path / "awareos_events.jsonl"
    monkeypatch.setenv("AWAREOS_OVERLAY_ENABLED", "1")
    monkeypatch.setenv("AWAREOS_WORK_OVERLAY_EVENTS_PATH", str(events_path))

    reg = HookRegistry()
    reg.discover_and_load()

    ctx = {
        "platform": "telegram",
        "chat_id": "123",
        "session_id": "sess-abc",
        "session_key": "telegram:123",
        "user_id": "u1",
        "substantive": False,
        "api_calls": 1,
        "tool_names": [],
        "response_length": 2,
    }

    await reg.emit("agent:start", dict(ctx))
    await reg.emit("agent:end", dict(ctx))

    assert not events_path.exists()

