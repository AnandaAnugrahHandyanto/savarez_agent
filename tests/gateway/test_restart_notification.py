"""Tests for /restart notification — the gateway notifies the requester on comeback."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

import gateway.run as gateway_run
from gateway.config import Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.session import SessionEntry, build_session_key
from tests.gateway.restart_test_helpers import (
    make_restart_runner,
    make_restart_source,
)


def make_restart_notify_payload(source):
    payload = {
        "platform": source.platform.value if source.platform else None,
        "chat_id": source.chat_id,
        "chat_type": source.chat_type,
        "session_key": build_session_key(source),
    }
    if source.user_id:
        payload["user_id"] = source.user_id
    if source.thread_id is not None:
        payload["thread_id"] = source.thread_id
    return payload


# ── _handle_restart_command writes .restart_notify.json ──────────────────


@pytest.mark.asyncio
async def test_restart_command_writes_notify_file(tmp_path, monkeypatch):
    """When /restart fires, the requester's routing info is persisted to disk."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    runner, _adapter = make_restart_runner()
    runner.request_restart = MagicMock(return_value=True)

    source = make_restart_source(chat_id="42")
    event = MessageEvent(
        text="/restart",
        message_type=MessageType.TEXT,
        source=source,
        message_id="m1",
    )

    result = await runner._handle_restart_command(event)
    assert "Restarting" in result

    notify_path = tmp_path / ".restart_notify.json"
    assert notify_path.exists()
    data = json.loads(notify_path.read_text())
    assert data["platform"] == "telegram"
    assert data["chat_id"] == "42"
    assert data["chat_type"] == source.chat_type
    assert data["user_id"] == source.user_id
    assert data["session_key"] == build_session_key(source)
    assert "thread_id" not in data  # no thread → omitted


@pytest.mark.asyncio
async def test_restart_command_uses_service_restart_under_systemd(tmp_path, monkeypatch):
    """Under systemd (INVOCATION_ID set), /restart uses via_service=True."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setenv("INVOCATION_ID", "abc123")

    runner, _adapter = make_restart_runner()
    runner.request_restart = MagicMock(return_value=True)

    source = make_restart_source(chat_id="42")
    event = MessageEvent(
        text="/restart",
        message_type=MessageType.TEXT,
        source=source,
        message_id="m1",
    )

    await runner._handle_restart_command(event)
    runner.request_restart.assert_called_once_with(detached=False, via_service=True)


@pytest.mark.asyncio
async def test_restart_command_uses_detached_without_systemd(tmp_path, monkeypatch):
    """Without systemd, /restart uses the detached subprocess approach."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.delenv("INVOCATION_ID", raising=False)

    runner, _adapter = make_restart_runner()
    runner.request_restart = MagicMock(return_value=True)

    source = make_restart_source(chat_id="42")
    event = MessageEvent(
        text="/restart",
        message_type=MessageType.TEXT,
        source=source,
        message_id="m1",
    )

    await runner._handle_restart_command(event)
    runner.request_restart.assert_called_once_with(detached=True, via_service=False)


@pytest.mark.asyncio
async def test_restart_command_preserves_thread_id(tmp_path, monkeypatch):
    """Thread ID is saved when the requester is in a threaded chat."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    runner, _adapter = make_restart_runner()
    runner.request_restart = MagicMock(return_value=True)

    source = make_restart_source(chat_id="99")
    source.thread_id = "topic_7"

    event = MessageEvent(
        text="/restart",
        message_type=MessageType.TEXT,
        source=source,
        message_id="m2",
    )

    await runner._handle_restart_command(event)

    data = json.loads((tmp_path / ".restart_notify.json").read_text())
    assert data["thread_id"] == "topic_7"
    assert data["session_key"] == build_session_key(source)


# ── _send_restart_notification ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_restart_notification_delivers_and_cleans_up(tmp_path, monkeypatch):
    """On startup, the notification is sent and the file is removed."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    notify_path = tmp_path / ".restart_notify.json"
    notify_path.write_text(json.dumps({
        "platform": "telegram",
        "chat_id": "42",
    }))

    runner, adapter = make_restart_runner()
    adapter.send = AsyncMock()

    await runner._send_restart_notification()

    adapter.send.assert_called_once()
    call_args = adapter.send.call_args
    assert call_args[0][0] == "42"  # chat_id
    assert "restarted" in call_args[0][1].lower()
    assert call_args[1].get("metadata") is None  # no thread
    assert not notify_path.exists()


@pytest.mark.asyncio
async def test_send_restart_notification_with_thread(tmp_path, monkeypatch):
    """Thread ID is passed as metadata so the message lands in the right topic."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    notify_path = tmp_path / ".restart_notify.json"
    notify_path.write_text(json.dumps({
        "platform": "telegram",
        "chat_id": "99",
        "thread_id": "topic_7",
    }))

    runner, adapter = make_restart_runner()
    adapter.send = AsyncMock()

    await runner._send_restart_notification()

    call_args = adapter.send.call_args
    assert call_args[1]["metadata"] == {"thread_id": "topic_7"}
    assert not notify_path.exists()


@pytest.mark.asyncio
async def test_send_restart_notification_prompts_to_continue_same_chat_session(
    tmp_path, monkeypatch
):
    """Restart comeback message should proactively surface the latest same-channel session."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    source = make_restart_source(chat_id="42")
    notify_path = tmp_path / ".restart_notify.json"
    notify_path.write_text(json.dumps(make_restart_notify_payload(source)))

    runner, adapter = make_restart_runner()
    adapter.send = AsyncMock()
    entry = SessionEntry(
        session_key=build_session_key(source),
        session_id="20260426_010203_abcdef12",
        created_at=datetime(2026, 4, 26, 1, 2, 3),
        updated_at=datetime(2026, 4, 26, 1, 5, 0),
        origin=source,
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner.session_store.list_sessions.return_value = [entry]

    await runner._send_restart_notification()

    sent = adapter.send.call_args[0][1]
    assert "restarted" in sent.lower()
    assert "last conversation in this chat" in sent
    assert "Reply `continue`" in sent
    assert "20260426_010203_abcdef12" in sent
    assert not notify_path.exists()


@pytest.mark.asyncio
async def test_send_restart_notification_uses_newest_same_chat_session(
    tmp_path, monkeypatch
):
    """When multiple same-chat sessions exist, mention the most recently updated one."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    source = make_restart_source(chat_id="42")
    notify_path = tmp_path / ".restart_notify.json"
    notify_path.write_text(json.dumps(make_restart_notify_payload(source)))

    runner, adapter = make_restart_runner()
    adapter.send = AsyncMock()
    older = SessionEntry(
        session_key=build_session_key(source),
        session_id="older_session",
        created_at=datetime(2026, 4, 26, 1, 2, 3),
        updated_at=datetime(2026, 4, 26, 1, 5, 0),
        origin=source,
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    newer = SessionEntry(
        session_key=build_session_key(source),
        session_id="newer_session",
        created_at=datetime(2026, 4, 26, 2, 2, 3),
        updated_at=datetime(2026, 4, 26, 2, 5, 0),
        origin=source,
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner.session_store.list_sessions.return_value = [older, newer]

    await runner._send_restart_notification()

    sent = adapter.send.call_args[0][1]
    assert "newer_session" in sent
    assert "older_session" not in sent
    assert not notify_path.exists()


@pytest.mark.asyncio
async def test_send_restart_notification_sanitizes_session_id_backticks(
    tmp_path, monkeypatch
):
    """Unexpected backticks in session IDs should not break Markdown code spans."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    source = make_restart_source(chat_id="42")
    notify_path = tmp_path / ".restart_notify.json"
    notify_path.write_text(json.dumps(make_restart_notify_payload(source)))

    runner, adapter = make_restart_runner()
    adapter.send = AsyncMock()
    entry = SessionEntry(
        session_key=build_session_key(source),
        session_id="bad`session",
        created_at=datetime(2026, 4, 26, 1, 2, 3),
        updated_at=datetime(2026, 4, 26, 1, 5, 0),
        origin=source,
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner.session_store.list_sessions.return_value = [entry]

    await runner._send_restart_notification()

    sent = adapter.send.call_args[0][1]
    assert "bad`session" not in sent
    assert "badʼsession" in sent
    assert not notify_path.exists()


@pytest.mark.asyncio
async def test_send_restart_notification_resume_pending_session_says_transcript_intact(
    tmp_path, monkeypatch
):
    """If restart interrupted the session, tell the user the transcript is intact."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    source = make_restart_source(chat_id="42")
    notify_path = tmp_path / ".restart_notify.json"
    notify_path.write_text(json.dumps(make_restart_notify_payload(source)))

    runner, adapter = make_restart_runner()
    adapter.send = AsyncMock()
    entry = SessionEntry(
        session_key=build_session_key(source),
        session_id="interrupted_session",
        created_at=datetime(2026, 4, 26, 1, 2, 3),
        updated_at=datetime(2026, 4, 26, 1, 5, 0),
        origin=source,
        platform=Platform.TELEGRAM,
        chat_type="dm",
        resume_pending=True,
        resume_reason="restart_timeout",
    )
    runner.session_store.list_sessions.return_value = [entry]

    await runner._send_restart_notification()

    sent = adapter.send.call_args[0][1]
    assert "interrupted conversation in this chat" in sent
    assert "kept the transcript intact" in sent
    assert "interrupted_session" in sent
    assert not notify_path.exists()


@pytest.mark.asyncio
async def test_send_restart_notification_ignores_other_chat_sessions(tmp_path, monkeypatch):
    """Continuity prompt must not leak or suggest a different chat's session."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    notify_path = tmp_path / ".restart_notify.json"
    notify_path.write_text(json.dumps({
        "platform": "telegram",
        "chat_id": "42",
    }))

    runner, adapter = make_restart_runner()
    adapter.send = AsyncMock()
    other_source = make_restart_source(chat_id="99")
    other_entry = SessionEntry(
        session_key=build_session_key(other_source),
        session_id="other_session",
        created_at=datetime(2026, 4, 26, 1, 2, 3),
        updated_at=datetime(2026, 4, 26, 1, 5, 0),
        origin=other_source,
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner.session_store.list_sessions.return_value = [other_entry]

    await runner._send_restart_notification()

    sent = adapter.send.call_args[0][1]
    assert "restarted" in sent.lower()
    assert "last conversation in this chat" not in sent
    assert "other_session" not in sent
    assert not notify_path.exists()


@pytest.mark.asyncio
async def test_send_restart_notification_ignores_same_chat_different_group_user_session(
    tmp_path, monkeypatch
):
    """Same group chat alone is insufficient; restart continuity must match the full session key."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    notify_source = make_restart_source(chat_id="42", chat_type="group")
    notify_source.user_id = "u1"
    notify_path = tmp_path / ".restart_notify.json"
    notify_path.write_text(json.dumps(make_restart_notify_payload(notify_source)))

    runner, adapter = make_restart_runner()
    adapter.send = AsyncMock()
    other_user_source = make_restart_source(chat_id="42", chat_type="group")
    other_user_source.user_id = "u2"
    entry = SessionEntry(
        session_key=build_session_key(other_user_source),
        session_id="other_user_session",
        created_at=datetime(2026, 4, 26, 1, 2, 3),
        updated_at=datetime(2026, 4, 26, 1, 5, 0),
        origin=other_user_source,
        platform=Platform.TELEGRAM,
        chat_type="group",
    )
    runner.session_store.list_sessions.return_value = [entry]

    await runner._send_restart_notification()

    sent = adapter.send.call_args[0][1]
    assert "last conversation in this chat" not in sent
    assert "other_user_session" not in sent
    assert not notify_path.exists()


@pytest.mark.asyncio
async def test_send_restart_notification_ignores_non_matching_thread_sessions(
    tmp_path, monkeypatch
):
    """Forum-topic/thread restarts only surface sessions from the same thread."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    notify_source = make_restart_source(chat_id="42")
    notify_source.thread_id = "topic_7"
    notify_path = tmp_path / ".restart_notify.json"
    notify_path.write_text(json.dumps(make_restart_notify_payload(notify_source)))

    runner, adapter = make_restart_runner()
    adapter.send = AsyncMock()
    source = make_restart_source(chat_id="42")
    source.thread_id = "topic_9"
    entry = SessionEntry(
        session_key=build_session_key(source),
        session_id="wrong_thread_session",
        created_at=datetime(2026, 4, 26, 1, 2, 3),
        updated_at=datetime(2026, 4, 26, 1, 5, 0),
        origin=source,
        platform=Platform.TELEGRAM,
        chat_type="group",
    )
    runner.session_store.list_sessions.return_value = [entry]

    await runner._send_restart_notification()

    sent = adapter.send.call_args[0][1]
    assert "last conversation in this chat" not in sent
    assert "wrong_thread_session" not in sent
    assert adapter.send.call_args[1]["metadata"] == {"thread_id": "topic_7"}
    assert not notify_path.exists()


@pytest.mark.asyncio
async def test_send_restart_notification_ignores_suspended_sessions(tmp_path, monkeypatch):
    """Suspended sessions are forced-wipe candidates, not restart-continuity candidates."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    source = make_restart_source(chat_id="42")
    notify_path = tmp_path / ".restart_notify.json"
    notify_path.write_text(json.dumps(make_restart_notify_payload(source)))

    runner, adapter = make_restart_runner()
    adapter.send = AsyncMock()
    entry = SessionEntry(
        session_key=build_session_key(source),
        session_id="suspended_session",
        created_at=datetime(2026, 4, 26, 1, 2, 3),
        updated_at=datetime(2026, 4, 26, 1, 5, 0),
        origin=source,
        platform=Platform.TELEGRAM,
        chat_type="dm",
        suspended=True,
    )
    runner.session_store.list_sessions.return_value = [entry]

    await runner._send_restart_notification()

    sent = adapter.send.call_args[0][1]
    assert "last conversation in this chat" not in sent
    assert "suspended_session" not in sent
    assert not notify_path.exists()


@pytest.mark.asyncio
async def test_send_restart_notification_noop_when_no_file(tmp_path, monkeypatch):
    """Nothing happens if there's no pending restart notification."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    runner, adapter = make_restart_runner()
    adapter.send = AsyncMock()

    await runner._send_restart_notification()

    adapter.send.assert_not_called()


@pytest.mark.asyncio
async def test_send_restart_notification_skips_when_adapter_missing(tmp_path, monkeypatch):
    """If the requester's platform isn't connected, clean up without crashing."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    notify_path = tmp_path / ".restart_notify.json"
    notify_path.write_text(json.dumps({
        "platform": "discord",  # runner only has telegram adapter
        "chat_id": "42",
    }))

    runner, _adapter = make_restart_runner()

    await runner._send_restart_notification()

    # File cleaned up even though we couldn't send
    assert not notify_path.exists()


@pytest.mark.asyncio
async def test_send_restart_notification_cleans_up_on_send_failure(
    tmp_path, monkeypatch
):
    """If the adapter.send() raises, the file is still cleaned up."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    notify_path = tmp_path / ".restart_notify.json"
    notify_path.write_text(json.dumps({
        "platform": "telegram",
        "chat_id": "42",
    }))

    runner, adapter = make_restart_runner()
    adapter.send = AsyncMock(side_effect=RuntimeError("network down"))

    await runner._send_restart_notification()

    assert not notify_path.exists()  # cleaned up despite error


@pytest.mark.asyncio
async def test_send_restart_notification_cleans_up_malformed_notify_file(
    tmp_path, monkeypatch
):
    """Corrupt restart-notification state should not crash startup or persist forever."""
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    notify_path = tmp_path / ".restart_notify.json"
    notify_path.write_text("{not-json")

    runner, adapter = make_restart_runner()
    adapter.send = AsyncMock()

    await runner._send_restart_notification()

    adapter.send.assert_not_called()
    assert not notify_path.exists()
