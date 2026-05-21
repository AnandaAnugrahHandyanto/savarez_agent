from types import SimpleNamespace

import pytest

pytest.importorskip("httpx")

import gateway.run as gateway_run
from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _make_event(text="/xsearch status", platform=Platform.DISCORD):
    source = SessionSource(
        platform=platform,
        user_id="user-1",
        chat_id="chat-1",
        user_name="tester",
    )
    return MessageEvent(text=text, source=source)


def _make_runner():
    return object.__new__(gateway_run.GatewayRunner)


@pytest.mark.asyncio
async def test_handle_xsearch_command_uses_platform_key(monkeypatch):
    captured = {}

    def _fake_run(command, *, platform="cli"):
        captured["command"] = command
        captured["platform"] = platform
        return SimpleNamespace(output="ok", reset_session=False)

    monkeypatch.setattr("hermes_cli.xsearch_command.run_xsearch_command", _fake_run)

    result = await _make_runner()._handle_xsearch_command(_make_event())

    assert result == "ok"
    assert captured == {"command": "/xsearch status", "platform": "discord"}
