"""Gateway tests for /deep-research workflow tool exposure."""

from __future__ import annotations

import pytest


class _FakeEvent:
    def __init__(self, args: str):
        self.text = f"/deep-research {args}"
        self._args = args

    def get_command_args(self) -> str:
        return self._args


@pytest.mark.asyncio
async def test_gateway_deep_research_sets_ephemeral_workflow_toolset(monkeypatch):
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    event = _FakeEvent("test question")
    seen = {}

    async def fake_handle_message(ev):
        seen["event"] = ev
        return "handled"

    monkeypatch.setattr(runner, "_handle_message", fake_handle_message)

    result = await runner._handle_deep_research_command(event)

    assert result == "handled"
    assert seen["event"] is event
    assert "test question" in event.text
    assert not event.text.startswith("/deep-research")
    assert getattr(event, "ephemeral_toolsets") == ["workflow"]


@pytest.mark.asyncio
async def test_gateway_deep_research_usage_without_question():
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    event = _FakeEvent("")

    result = await runner._handle_deep_research_command(event)

    assert result == "Usage: /deep-research <question>"
