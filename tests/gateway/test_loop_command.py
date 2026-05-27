from __future__ import annotations

import json

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.session import SessionSource


def _event(text: str) -> MessageEvent:
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=SessionSource(platform=Platform.TELEGRAM, chat_id="123", chat_type="dm"),
    )


@pytest.mark.asyncio
async def test_loop_gateway_command_uses_core_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = GatewayRunner.__new__(GatewayRunner)

    init = await runner._handle_loop_command(_event("/loop init demo"))
    status = await runner._handle_loop_command(_event("/loop status demo"))

    assert "Loop: demo" in init
    assert "Status: initialized" in init
    assert "Loop: demo" in status
    assert "State:" in status
    assert (tmp_path / ".hermes" / "loops" / "demo" / "prd.json").exists()


@pytest.mark.asyncio
async def test_loop_gateway_command_defaults_to_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = GatewayRunner.__new__(GatewayRunner)

    result = await runner._handle_loop_command(_event("/loop"))

    assert "Loop: fruit-loop" in result
    assert "Status: not started" in result
    assert "Next: /loop init fruit-loop" in result


@pytest.mark.asyncio
async def test_loop_gateway_command_can_mark_story_complete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = GatewayRunner.__new__(GatewayRunner)
    await runner._handle_loop_command(_event("/loop init demo"))
    prd_path = tmp_path / ".hermes" / "loops" / "demo" / "prd.json"
    prd = json.loads(prd_path.read_text(encoding="utf-8"))
    prd["userStories"] = [{"id": "S1", "title": "first", "priority": 1, "status": "running"}]
    prd_path.write_text(json.dumps(prd, indent=2) + "\n", encoding="utf-8")

    result = await runner._handle_loop_command(_event("/loop complete demo S1 shipped"))

    updated = json.loads(prd_path.read_text(encoding="utf-8"))
    assert updated["userStories"][0]["passes"] is True
    assert updated["userStories"][0]["status"] == "passed"
    assert "Stories: 1 total / 0 pending / 1 passed" in result
