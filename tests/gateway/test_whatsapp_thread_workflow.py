from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, SendResult
from gateway.session import SessionEntry, SessionSource
from gateway.whatsapp_message_store import append_whatsapp_record


def _make_source(
    *,
    platform: Platform = Platform.WHATSAPP,
    user_id: str = "15550000001",
    chat_id: str = "15551230000@s.whatsapp.net",
    chat_type: str = "dm",
) -> SessionSource:
    return SessionSource(
        platform=platform,
        user_id=user_id,
        chat_id=chat_id,
        user_name="Operator",
        chat_type=chat_type,
    )


def _make_event(
    text: str,
    *,
    participant_role: str | None = "owner_operator",
    command_authority_scope: str | None = "owner_only",
    platform: Platform = Platform.WHATSAPP,
) -> MessageEvent:
    return MessageEvent(
        text=text,
        source=_make_source(platform=platform),
        message_id="evt-1",
        participant_role=participant_role,
        message_classification=(
            "command_capable"
            if participant_role == "owner_operator"
            else "conversational_only"
        ),
        command_authority_scope=command_authority_scope,
    )


def _make_runner(tmp_path):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={
            Platform.WHATSAPP: PlatformConfig(
                enabled=True,
                extra={"allow_admin_from": ["15550000001"]},
            )
        }
    )
    runner.adapters = {Platform.WHATSAPP: MagicMock()}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(
        emit=AsyncMock(),
        emit_collect=AsyncMock(return_value=[]),
        loaded_hooks=False,
    )
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = SessionEntry(
        session_key="agent:main:whatsapp:dm:15551230000",
        session_id="sess-1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        platform=Platform.WHATSAPP,
        chat_type="dm",
        total_tokens=0,
    )
    runner.session_store.load_transcript.return_value = []
    runner.session_store.has_any_sessions.return_value = True
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._queued_events = {}
    runner._session_sources = {}
    runner._session_run_generation = {}
    runner._session_db = MagicMock()
    runner._session_db.get_session_title.return_value = None
    runner._session_db.get_session.return_value = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._show_reasoning = False
    runner._draining = False
    runner._is_user_authorized = lambda _source: True
    runner._set_session_env = lambda _context: None
    runner._should_send_voice_reply = lambda *_args, **_kwargs: False
    runner._send_voice_reply = AsyncMock()
    runner._capture_gateway_honcho_if_configured = lambda *args, **kwargs: None
    runner._emit_gateway_run_progress = AsyncMock()
    return runner


def _append_record(
    base_dir,
    *,
    record_id: str,
    text: str,
    participant_role: str,
    message_id: str,
    effective_event_at: str,
) -> None:
    append_whatsapp_record(
        {
            "record_kind": "conversation_record",
            "record_id": record_id,
            "conversation_key": "whatsapp:dm:15551230000",
            "destination_key": "whatsapp:dm:15551230000",
            "destination_context_type": "direct_message",
            "destination_chat_id": "15551230000@s.whatsapp.net",
            "destination_target_id": "15551230000",
            "group_chat_id": None,
            "dm_counterparty_id": "15551230000",
            "direction": "outbound" if participant_role == "agent" else "inbound",
            "effective_event_at_utc": effective_event_at,
            "record_sequence": int(record_id.split("-")[-1]),
            "participant_role": participant_role,
            "message_classification": (
                "command_capable"
                if participant_role == "owner_operator"
                else "conversational_only"
            ),
            "command_authority_scope": (
                "owner_only" if participant_role == "owner_operator" else "none"
            ),
            "sender_id": "agent" if participant_role == "agent" else "15551230000",
            "sender_name": "Hermes" if participant_role == "agent" else "Vendor",
            "text": text,
            "message_id": message_id,
            "media_types": [],
        },
        effective_event_at=datetime.fromisoformat(
            effective_event_at.replace("Z", "+00:00")
        ),
        base_dir=base_dir,
    )


@pytest.mark.asyncio
async def test_wthread_retrieve_returns_exact_thread_rows(tmp_path, monkeypatch):
    base_dir = tmp_path / ".hermes" / "gateway" / "whatsapp-records"
    base_dir.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    _append_record(
        base_dir,
        record_id="record-1",
        text="First vendor message",
        participant_role="external_party",
        message_id="msg-1",
        effective_event_at="2024-06-02T09:01:00Z",
    )
    _append_record(
        base_dir,
        record_id="record-2",
        text="Follow-up from Hermes",
        participant_role="agent",
        message_id="msg-2",
        effective_event_at="2024-06-02T09:02:00Z",
    )

    runner = _make_runner(tmp_path)
    result = await runner._handle_message(
        _make_event(
            "/wthread retrieve destination_key=whatsapp:dm:15551230000 "
            "range_start_utc=2024-06-02T09:00:00Z "
            "range_end_utc=2024-06-02T10:00:00Z"
        )
    )

    assert "WhatsApp thread workflow" in result
    assert "Status: ready" in result
    assert "Action: retrieve" in result
    assert "Resolved destination_chat_id: 15551230000@s.whatsapp.net" in result
    assert "message_id=msg-1 | First vendor message" in result
    assert "message_id=msg-2 | Follow-up from Hermes" in result


@pytest.mark.asyncio
async def test_wthread_send_requires_confirm_and_shows_preview(tmp_path, monkeypatch):
    base_dir = tmp_path / ".hermes" / "gateway" / "whatsapp-records"
    base_dir.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    _append_record(
        base_dir,
        record_id="record-1",
        text="Prior preserved row",
        participant_role="external_party",
        message_id="msg-1",
        effective_event_at="2024-06-02T09:01:00Z",
    )

    runner = _make_runner(tmp_path)
    runner.adapters[Platform.WHATSAPP].send = AsyncMock()

    result = await runner._handle_message(
        _make_event(
            "/wthread send destination_key=whatsapp:dm:15551230000 "
            'message_text="Checking in on the quote." confirm=false'
        )
    )

    assert "Status: confirmation_required" in result
    assert "Pending message preview: Checking in on the quote." in result
    runner.adapters[Platform.WHATSAPP].send.assert_not_awaited()


@pytest.mark.asyncio
async def test_wthread_send_dispatches_confirmed_message_to_resolved_chat(
    tmp_path, monkeypatch
):
    base_dir = tmp_path / ".hermes" / "gateway" / "whatsapp-records"
    base_dir.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    _append_record(
        base_dir,
        record_id="record-1",
        text="Prior preserved row",
        participant_role="external_party",
        message_id="msg-1",
        effective_event_at="2024-06-02T09:01:00Z",
    )

    runner = _make_runner(tmp_path)
    runner.adapters[Platform.WHATSAPP].send = AsyncMock(
        return_value=SendResult(
            success=True,
            message_id="bridge-msg-9",
            raw_response={
                "dispatch_group_id": "dispatch-123",
                "messageId": "bridge-msg-9",
            },
        )
    )

    result = await runner._handle_message(
        _make_event(
            "/wthread send destination_key=whatsapp:dm:15551230000 "
            'message_text="Checking in on the quote." confirm=true'
        )
    )

    runner.adapters[Platform.WHATSAPP].send.assert_awaited_once_with(
        "15551230000@s.whatsapp.net",
        "Checking in on the quote.",
    )
    assert "Status: sent" in result
    assert "dispatch_group_id: dispatch-123" in result
    assert "message_id: bridge-msg-9" in result


@pytest.mark.asyncio
async def test_wthread_send_surfaces_send_failed_status(tmp_path, monkeypatch):
    base_dir = tmp_path / ".hermes" / "gateway" / "whatsapp-records"
    base_dir.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    _append_record(
        base_dir,
        record_id="record-1",
        text="Prior preserved row",
        participant_role="external_party",
        message_id="msg-1",
        effective_event_at="2024-06-02T09:01:00Z",
    )

    runner = _make_runner(tmp_path)
    runner.adapters[Platform.WHATSAPP].send = AsyncMock(
        return_value=SendResult(success=False, error="bridge down")
    )

    result = await runner._handle_message(
        _make_event(
            "/wthread send destination_key=whatsapp:dm:15551230000 "
            'message_text="Checking in on the quote." confirm=true'
        )
    )

    assert "Status: send_failed" in result
    assert "Error: bridge down" in result


@pytest.mark.asyncio
async def test_wthread_fails_closed_for_non_owner_or_non_whatsapp(tmp_path):
    runner = _make_runner(tmp_path)

    non_owner = await runner._handle_whatsapp_thread_command(
        _make_event(
            "/wthread retrieve destination_key=whatsapp:dm:15551230000 "
            "range_start_utc=2024-06-02T09:00:00Z range_end_utc=2024-06-02T10:00:00Z",
            participant_role="external_party",
            command_authority_scope="none",
        )
    )
    non_whatsapp = await runner._handle_whatsapp_thread_command(
        _make_event(
            "/wthread retrieve destination_key=whatsapp:dm:15551230000 "
            "range_start_utc=2024-06-02T09:00:00Z range_end_utc=2024-06-02T10:00:00Z",
            platform=Platform.DISCORD,
        )
    )

    assert "Status: forbidden" in non_owner
    assert "Status: forbidden" in non_whatsapp
