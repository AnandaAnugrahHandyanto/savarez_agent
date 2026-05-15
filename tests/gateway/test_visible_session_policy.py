import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig, load_gateway_config
from gateway.platforms.base import MessageEvent
from gateway.run import GatewayRunner
from gateway.session import SessionEntry, SessionSource, build_session_key
from gateway.visible_sessions import VisibleSessionHandle, save_visible_session_handles

PARENT_CHAT = "-1003933169427"
THREAD_ID = "14"


def _parent_source(thread_id: str = "1") -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id=PARENT_CHAT,
        chat_name="Hermes Sessions",
        chat_type="group",
        user_id="6605861022",
        user_name="alice",
        thread_id=thread_id,
    )


def _parent_event(thread_id: str = "1") -> MessageEvent:
    return MessageEvent(text="/spawn-topic Smoke :: Reply OK", source=_parent_source(thread_id), message_id="m-parent")


class _FakeSessionStore:
    def __init__(self):
        self.entries = {}

    def _generate_session_key(self, source):
        return build_session_key(source)

    def get_or_create_session(self, source, force_new=False):
        key = self._generate_session_key(source)
        entry = SessionEntry(
            session_key=key,
            session_id=f"session-{source.thread_id}",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            origin=source,
            display_name=source.chat_name,
            platform=source.platform,
            chat_type=source.chat_type,
        )
        self.entries[key] = entry
        return entry


def _runner(tmp_path: Path, config: GatewayConfig | None = None):
    runner = object.__new__(GatewayRunner)
    runner.config = config or GatewayConfig(platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="token")})
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
    return runner


@pytest.mark.asyncio
async def test_visible_session_policy_blocks_when_disabled(tmp_path):
    cfg = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="token")},
        visible_sessions_enabled=False,
    )
    runner = _runner(tmp_path, cfg)

    with pytest.raises(ValueError, match="disabled"):
        await runner.create_visible_session(
            parent_event=_parent_event(),
            platform="telegram",
            parent_chat_id=PARENT_CHAT,
            topic_name="Blocked",
            prompt="test",
        )


@pytest.mark.asyncio
async def test_visible_session_policy_enforces_max_active(tmp_path):
    cfg = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="token")},
        visible_sessions_max_active_per_parent=1,
    )
    runner = _runner(tmp_path, cfg)
    parent_key = build_session_key(_parent_source())
    save_visible_session_handles(
        runner._visible_session_registry_path,
        [
            VisibleSessionHandle(
                platform="telegram",
                chat_id=PARENT_CHAT,
                thread_id="9",
                topic_name="Existing",
                session_key=f"agent:main:telegram:group:{PARENT_CHAT}:9",
                session_id="session-9",
                target=f"telegram:{PARENT_CHAT}:9",
                created_by_session_key=parent_key,
                created_by_user_id="6605861022",
                created_at=datetime.now(timezone.utc),
            )
        ],
    )

    with pytest.raises(ValueError, match="limit reached"):
        await runner.create_visible_session(
            parent_event=_parent_event(),
            platform="telegram",
            parent_chat_id=PARENT_CHAT,
            topic_name="Too many",
            prompt="test",
        )


@pytest.mark.asyncio
async def test_visible_session_policy_blocks_nested_spawns_by_default(tmp_path):
    runner = _runner(tmp_path)
    save_visible_session_handles(
        runner._visible_session_registry_path,
        [
            VisibleSessionHandle(
                platform="telegram",
                chat_id=PARENT_CHAT,
                thread_id="77",
                topic_name="Nested Parent",
                session_key=f"agent:main:telegram:group:{PARENT_CHAT}:77",
                session_id="session-77",
                target=f"telegram:{PARENT_CHAT}:77",
                created_by_session_key=build_session_key(_parent_source()),
                created_by_user_id="6605861022",
                created_at=datetime.now(timezone.utc),
            )
        ],
    )

    with pytest.raises(ValueError, match="Nested"):
        await runner.create_visible_session(
            parent_event=_parent_event(thread_id="77"),
            platform="telegram",
            parent_chat_id=PARENT_CHAT,
            topic_name="Nested Child",
            prompt="test",
        )


def test_visible_session_config_round_trips_cross_parent_allowlists():
    cfg = GatewayConfig.from_dict(
        {
            "visible_sessions_allowed_parent_session_keys": [" agent:main:telegram:group:-1:2 "],
            "visible_sessions_allowed_parent_user_ids": [" 6605861022 "],
        }
    )

    assert cfg.visible_sessions_allowed_parent_session_keys == ["agent:main:telegram:group:-1:2"]
    assert cfg.visible_sessions_allowed_parent_user_ids == ["6605861022"]
    assert cfg.to_dict()["visible_sessions_allowed_parent_session_keys"] == ["agent:main:telegram:group:-1:2"]
    assert cfg.to_dict()["visible_sessions_allowed_parent_user_ids"] == ["6605861022"]


def test_visible_session_policy_keys_load_from_config_yaml(monkeypatch, tmp_path):
    (tmp_path / "config.yaml").write_text(
        "\n".join(
            [
                "visible_sessions_enabled: false",
                "visible_sessions_allowed_platforms: [telegram]",
                "visible_sessions_allowed_parent_chats: ['-1001']",
                "visible_sessions_allowed_parent_session_keys: ['agent:main:telegram:group:-1001:1']",
                "visible_sessions_allowed_parent_user_ids: ['6605861022']",
                "visible_sessions_max_active_per_parent: 3",
                "visible_sessions_allow_nested: true",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("gateway.config.get_hermes_home", lambda: tmp_path)

    cfg = load_gateway_config()

    assert cfg.visible_sessions_enabled is False
    assert cfg.visible_sessions_allowed_platforms == ["telegram"]
    assert cfg.visible_sessions_allowed_parent_chats == ["-1001"]
    assert cfg.visible_sessions_allowed_parent_session_keys == ["agent:main:telegram:group:-1001:1"]
    assert cfg.visible_sessions_allowed_parent_user_ids == ["6605861022"]
    assert cfg.visible_sessions_max_active_per_parent == 3
    assert cfg.visible_sessions_allow_nested is True


@pytest.mark.asyncio
async def test_visible_session_close_removes_handle_from_policy_accounting(tmp_path):
    cfg = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="token")},
        visible_sessions_max_active_per_parent=1,
    )
    runner = _runner(tmp_path, cfg)
    handle = await runner.create_visible_session(
        parent_event=_parent_event(),
        platform="telegram",
        parent_chat_id=PARENT_CHAT,
        topic_name="First",
        prompt="test",
    )

    with pytest.raises(ValueError, match="limit reached"):
        await runner.create_visible_session(
            parent_event=_parent_event(),
            platform="telegram",
            parent_chat_id=PARENT_CHAT,
            topic_name="Second",
            prompt="test",
        )

    closed = await runner.close_visible_session(parent_event=_parent_event(), handle=handle.target)
    assert closed.target == handle.target
    assert runner.list_visible_sessions(parent_event=_parent_event()) == []
    assert handle.session_key not in runner._session_model_overrides
    assert handle.session_key not in runner._session_reasoning_overrides

    runner._session_model_overrides[handle.session_key] = {"provider": "stale"}
    runner._session_reasoning_overrides[handle.session_key] = {"effort": "high"}
    replacement = await runner.create_visible_session(
        parent_event=_parent_event(),
        platform="telegram",
        parent_chat_id=PARENT_CHAT,
        topic_name="Replacement",
        prompt="test",
    )
    assert replacement.target == handle.target
    assert replacement.session_key not in runner._session_model_overrides
    assert replacement.session_key not in runner._session_reasoning_overrides


@pytest.mark.asyncio
async def test_visible_session_create_quota_is_serialized(tmp_path):
    cfg = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="token")},
        visible_sessions_max_active_per_parent=1,
    )
    runner = _runner(tmp_path, cfg)
    counter = {"value": 0}

    async def _create_thread(_chat_id, topic_name):
        await asyncio.sleep(0.01)
        counter["value"] += 1
        thread_id = str(100 + counter["value"])
        return {
            "platform": "telegram",
            "chat_id": PARENT_CHAT,
            "thread_id": thread_id,
            "topic_name": topic_name,
            "target": f"telegram:{PARENT_CHAT}:{thread_id}",
        }

    runner.adapters[Platform.TELEGRAM].create_visible_thread = AsyncMock(side_effect=_create_thread)

    results = await asyncio.gather(
        runner.create_visible_session(
            parent_event=_parent_event(),
            platform="telegram",
            parent_chat_id=PARENT_CHAT,
            topic_name="First",
            prompt="test",
        ),
        runner.create_visible_session(
            parent_event=_parent_event(),
            platform="telegram",
            parent_chat_id=PARENT_CHAT,
            topic_name="Second",
            prompt="test",
        ),
        return_exceptions=True,
    )

    successes = [item for item in results if not isinstance(item, Exception)]
    failures = [item for item in results if isinstance(item, Exception)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert "limit reached" in str(failures[0])
    assert len(runner.list_visible_sessions(parent_event=_parent_event())) == 1
