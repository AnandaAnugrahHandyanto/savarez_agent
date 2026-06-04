"""Tests for /handoff gateway slash command."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _make_event(text="/handoff"):
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="12345",
        user_id="67890",
        user_name="tester",
        chat_type="dm",
    )
    return MessageEvent(text=text, source=source)


def _make_runner(tmp_path, history=None):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    entry = SimpleNamespace(session_id="20260525_120000_deadbeef", session_key="telegram:12345")
    store = MagicMock()
    store.get_or_create_session.return_value = entry
    store.load_transcript.return_value = history or [
        {"role": "user", "content": "진행하자"},
        {"role": "assistant", "content": "완료"},
    ]
    runner.session_store = store
    runner.adapters = {}
    return runner


@pytest.mark.asyncio
async def test_handoff_command_writes_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    runner = _make_runner(tmp_path)

    result = await runner._handle_handoff_command(_make_event("/handoff"))

    assert "핸드오프 파일을 만들었습니다" in result
    assert "latest" in result
    assert (tmp_path / "handoffs" / "latest").exists()
    runner.session_store.load_transcript.assert_called_once_with("20260525_120000_deadbeef")


@pytest.mark.asyncio
async def test_handoff_status_before_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    runner = _make_runner(tmp_path)

    result = await runner._handle_handoff_command(_make_event("/handoff status"))

    assert "아직 없습니다" in result
    runner.session_store.load_transcript.assert_not_called()


@pytest.mark.asyncio
async def test_handoff_status_after_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    runner = _make_runner(tmp_path)

    await runner._handle_handoff_command(_make_event("/handoff"))
    result = await runner._handle_handoff_command(_make_event("/handoff status"))

    assert "최근 핸드오프 파일" in result
    assert "handoff 읽고 이어가" in result
