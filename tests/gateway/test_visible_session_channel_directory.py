"""Visible topic delegate channel-directory persistence tests."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.run import GatewayRunner
from gateway.session import SessionEntry, SessionSource, build_session_key
from gateway.visible_sessions import VisibleSessionHandle


PARENT_CHAT = "-1003933169427"
THREAD_ID = "14"


def _parent_event():
    from gateway.platforms.base import MessageEvent

    return MessageEvent(
        text="/spawn-topic Smoke :: Reply OK",
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id=PARENT_CHAT,
            chat_name="Hermes Sessions",
            chat_type="group",
            user_id="6605861022",
            user_name="alice",
            thread_id="1",
        ),
    )


def test_upsert_visible_topic_target_updates_channel_directory(tmp_path, monkeypatch):
    from gateway import channel_directory

    monkeypatch.setattr(channel_directory, "DIRECTORY_PATH", tmp_path / "channel_directory.json")

    channel_directory.upsert_channel_directory_entry(
        platform="telegram",
        entry={
            "id": f"{PARENT_CHAT}:{THREAD_ID}",
            "name": "Hermes Sessions / Delegate Smoke",
            "type": "group",
            "thread_id": THREAD_ID,
        },
    )

    data = json.loads((tmp_path / "channel_directory.json").read_text())
    assert data["platforms"]["telegram"] == [
        {
            "id": f"{PARENT_CHAT}:{THREAD_ID}",
            "name": "Hermes Sessions / Delegate Smoke",
            "type": "group",
            "thread_id": THREAD_ID,
        }
    ]


class _FakeSessionStore:
    def _generate_session_key(self, source):
        return build_session_key(source)

    def get_or_create_session(self, source, force_new=False):
        key = build_session_key(source)
        return SessionEntry(
            session_key=key,
            session_id="session-14",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            origin=source,
            display_name=source.chat_name,
            platform=source.platform,
            chat_type=source.chat_type,
        )


@pytest.mark.asyncio
async def test_create_visible_session_registers_topic_target(tmp_path, monkeypatch):
    from gateway import channel_directory

    monkeypatch.setattr(channel_directory, "DIRECTORY_PATH", tmp_path / "channel_directory.json")
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="token")})
    runner.session_store = _FakeSessionStore()
    runner._session_model_overrides = {}
    runner._session_reasoning_overrides = {}
    runner._visible_session_registry_path = tmp_path / "visible_sessions.json"
    adapter = MagicMock()
    adapter.create_visible_thread = AsyncMock(
        return_value={
            "platform": "telegram",
            "chat_id": PARENT_CHAT,
            "thread_id": THREAD_ID,
            "topic_name": "Delegate Smoke",
            "target": f"telegram:{PARENT_CHAT}:{THREAD_ID}",
        }
    )
    adapter.dispatch_synthetic_message = AsyncMock(return_value=f"agent:main:telegram:group:{PARENT_CHAT}:{THREAD_ID}")
    runner.adapters = {Platform.TELEGRAM: adapter}

    await runner.create_visible_session(
        parent_event=_parent_event(),
        platform="telegram",
        parent_chat_id=PARENT_CHAT,
        topic_name="Delegate Smoke",
        prompt="Reply OK",
    )

    directory = json.loads((tmp_path / "channel_directory.json").read_text())
    assert directory["platforms"]["telegram"][0]["id"] == f"{PARENT_CHAT}:{THREAD_ID}"
    assert directory["platforms"]["telegram"][0]["name"] == "Hermes Sessions / Delegate Smoke"
