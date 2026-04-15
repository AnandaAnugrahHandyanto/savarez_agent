from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.session import SessionSource


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1001234567890",
        chat_name="Mingdom",
        chat_type="group",
        thread_id="14",
        chat_topic="Knowledge",
        user_id="42",
        user_name="Dong",
    )


def _make_event(text: str = "https://example.com/article") -> MessageEvent:
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=_make_source(),
        message_id="77",
        timestamp=datetime(2026, 4, 14, 21, 0, 0),
        topic_cwd="/Users/dongming/projects/dming.brain",
        topic_capture_command=["uv", "run", "brain", "capture", "--topic", "knowledge"],
    )


@pytest.mark.asyncio
async def test_topic_capture_command_runs_cli_and_rewrites_event_text():
    runner = object.__new__(GatewayRunner)
    event = _make_event()

    completed = SimpleNamespace(
        returncode=0,
        stdout=(
            '{"route":"shared_link_ingest","requires_agent_followup":false,'
            '"agent_handoff":"stored link","agent_next_steps":["none"]}'
        ),
        stderr="",
    )

    with patch("gateway.run.asyncio.to_thread", return_value=completed) as to_thread:
        await runner._maybe_apply_topic_capture_command(event, event.source)

    assert "Topic capture command ran before this turn" in event.text
    assert "Original user message:" in event.text
    assert "https://example.com/article" in event.text

    called = to_thread.call_args
    assert called is not None
    assert called.args[0].__name__ == "run"
    command = called.args[1]
    assert command[:6] == ["uv", "run", "brain", "capture", "--topic", "knowledge"]
    assert "--json" in command
    assert "--from-file" in command
    assert "--repo-root" in command
    assert "--message-ref" in command


@pytest.mark.asyncio
async def test_topic_capture_command_skips_slash_commands():
    runner = object.__new__(GatewayRunner)
    event = _make_event("/help")

    with patch("gateway.run.asyncio.to_thread") as to_thread:
        await runner._maybe_apply_topic_capture_command(event, event.source)

    to_thread.assert_not_called()
    assert event.text == "/help"
