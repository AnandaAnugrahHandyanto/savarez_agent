"""GatewayRunner visible Telegram topic delegate manager tests."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.run import GatewayRunner
from gateway.session import SessionEntry, SessionSource, build_session_key
from gateway.visible_sessions import VisibleSessionHandle, load_visible_session_handles, save_visible_session_handles


PARENT_CHAT = "-1003933169427"
THREAD_ID = "14"


def _parent_source(user_id: str = "6605861022", user_name: str = "alice") -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id=PARENT_CHAT,
        chat_name="Hermes Sessions",
        chat_type="group",
        user_id=user_id,
        user_name=user_name,
        thread_id="1",
    )


def _parent_event(text="/spawn-topic Smoke :: Reply OK", user_id: str = "6605861022", user_name: str = "alice") -> MessageEvent:
    return MessageEvent(text=text, source=_parent_source(user_id=user_id, user_name=user_name), message_id="m-parent")


class _FakeSessionStore:
    def __init__(self, config=None):
        self.config = config or GatewayConfig()
        self.entries = {}
        self.calls = []

    def _generate_session_key(self, source):
        return build_session_key(
            source,
            group_sessions_per_user=self.config.group_sessions_per_user,
            thread_sessions_per_user=self.config.thread_sessions_per_user,
        )

    def get_or_create_session(self, source, force_new=False):
        self.calls.append((source, force_new))
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


def _runner(tmp_path: Path):
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="token")})
    setattr(runner, "session_store", _FakeSessionStore(runner.config))
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
    return runner, adapter


@pytest.mark.asyncio
async def test_create_visible_session_creates_topic_session_override_and_seed(tmp_path):
    runner, adapter = _runner(tmp_path)

    handle = await runner.create_visible_session(
        parent_event=_parent_event(),
        platform="telegram",
        parent_chat_id=PARENT_CHAT,
        topic_name="Delegate Smoke",
        prompt="Reply exactly: VISIBLE_TOPIC_OK",
        provider="xai",
        model="grok-test",
        reasoning_effort="medium",
    )

    child_source, force_new = runner.session_store.calls[-1]
    assert force_new is True
    assert child_source.thread_id == THREAD_ID
    assert child_source.chat_id == PARENT_CHAT
    assert child_source.chat_type == "group"
    assert handle.target == f"telegram:{PARENT_CHAT}:{THREAD_ID}"
    assert handle.session_key == f"agent:main:telegram:group:{PARENT_CHAT}:{THREAD_ID}"
    assert runner._session_model_overrides[handle.session_key] == {
        "provider": "xai",
        "model": "grok-test",
    }
    assert runner._session_reasoning_overrides[handle.session_key] == {
        "enabled": True,
        "effort": "medium",
    }
    assert adapter.dispatch_synthetic_message.await_count == 3
    header_call, seed_visible_call, prompt_call = adapter.dispatch_synthetic_message.await_args_list
    assert header_call.kwargs["mode"] == "send_only"
    assert "Spawned visible child session" in header_call.kwargs["text"]
    assert seed_visible_call.kwargs["mode"] == "send_only"
    assert "Seed prompt from parent to this child agent" in seed_visible_call.kwargs["text"]
    assert "Reply exactly: VISIBLE_TOPIC_OK" in seed_visible_call.kwargs["text"]
    assert prompt_call.kwargs["text"] == "Reply exactly: VISIBLE_TOPIC_OK"
    assert prompt_call.kwargs["mode"] == "interrupt"


@pytest.mark.asyncio
async def test_create_visible_session_seed_visible_message_failure_does_not_block_prompt(tmp_path, caplog):
    runner, adapter = _runner(tmp_path)
    adapter.dispatch_synthetic_message.side_effect = [
        f"agent:main:telegram:group:{PARENT_CHAT}:{THREAD_ID}",
        RuntimeError("telegram send failed"),
        f"agent:main:telegram:group:{PARENT_CHAT}:{THREAD_ID}",
    ]

    handle = await runner.create_visible_session(
        parent_event=_parent_event(),
        platform="telegram",
        parent_chat_id=PARENT_CHAT,
        topic_name="Delegate Smoke",
        prompt="Reply exactly: VISIBLE_TOPIC_OK",
    )

    assert handle.target == f"telegram:{PARENT_CHAT}:{THREAD_ID}"
    assert adapter.dispatch_synthetic_message.await_count == 3
    header_call, seed_visible_call, prompt_call = adapter.dispatch_synthetic_message.await_args_list
    assert header_call.kwargs["mode"] == "send_only"
    assert seed_visible_call.kwargs["mode"] == "send_only"
    assert prompt_call.kwargs["text"] == "Reply exactly: VISIBLE_TOPIC_OK"
    assert prompt_call.kwargs["mode"] == "interrupt"
    assert "Failed to show visible session seed prompt" in caplog.text


@pytest.mark.asyncio
async def test_create_visible_session_header_failure_does_not_block_prompt(tmp_path, caplog):
    runner, adapter = _runner(tmp_path)
    adapter.dispatch_synthetic_message.side_effect = [
        RuntimeError("header send failed"),
        f"agent:main:telegram:group:{PARENT_CHAT}:{THREAD_ID}",
        f"agent:main:telegram:group:{PARENT_CHAT}:{THREAD_ID}",
    ]

    handle = await runner.create_visible_session(
        parent_event=_parent_event(),
        platform="telegram",
        parent_chat_id=PARENT_CHAT,
        topic_name="Delegate Smoke",
        prompt="Reply exactly: VISIBLE_TOPIC_OK",
    )

    assert handle.target == f"telegram:{PARENT_CHAT}:{THREAD_ID}"
    assert adapter.dispatch_synthetic_message.await_count == 3
    header_call, seed_visible_call, prompt_call = adapter.dispatch_synthetic_message.await_args_list
    assert header_call.kwargs["mode"] == "send_only"
    assert seed_visible_call.kwargs["mode"] == "send_only"
    assert prompt_call.kwargs["text"] == "Reply exactly: VISIBLE_TOPIC_OK"
    assert prompt_call.kwargs["mode"] == "interrupt"
    assert "Failed to show visible session header" in caplog.text


@pytest.mark.asyncio
async def test_create_visible_session_prompt_failure_retires_handle_and_overrides(tmp_path):
    runner, adapter = _runner(tmp_path)
    adapter.dispatch_synthetic_message.side_effect = [
        f"agent:main:telegram:group:{PARENT_CHAT}:{THREAD_ID}",
        f"agent:main:telegram:group:{PARENT_CHAT}:{THREAD_ID}",
        RuntimeError("prompt dispatch failed"),
    ]

    with pytest.raises(RuntimeError, match="prompt dispatch failed"):
        await runner.create_visible_session(
            parent_event=_parent_event(),
            platform="telegram",
            parent_chat_id=PARENT_CHAT,
            topic_name="Delegate Smoke",
            prompt="Reply exactly: VISIBLE_TOPIC_OK",
            provider="xai",
            model="grok-test",
            reasoning_effort="medium",
        )

    assert adapter.dispatch_synthetic_message.await_count == 3
    assert load_visible_session_handles(getattr(runner, "_visible_session_registry_path")) == []
    child_key = f"agent:main:telegram:group:{PARENT_CHAT}:{THREAD_ID}"
    assert child_key not in runner._session_model_overrides
    assert child_key not in runner._session_reasoning_overrides


@pytest.mark.asyncio
async def test_prompt_visible_session_uses_persisted_handle_without_creating_topic(tmp_path):
    runner, adapter = _runner(tmp_path)
    session_key = f"agent:main:telegram:group:{PARENT_CHAT}:{THREAD_ID}"
    save_visible_session_handles(
        runner._visible_session_registry_path,
        [
            VisibleSessionHandle(
                platform="telegram",
                chat_id=PARENT_CHAT,
                thread_id=THREAD_ID,
                topic_name="Delegate Smoke",
                session_key=session_key,
                session_id="session-14",
                target=f"telegram:{PARENT_CHAT}:{THREAD_ID}",
                created_by_session_key=build_session_key(_parent_source()),
                created_by_user_id="6605861022",
                created_at=datetime.now(timezone.utc),
            )
        ],
    )

    handle = await runner.prompt_visible_session(
        parent_event=_parent_event(),
        handle=f"telegram:{PARENT_CHAT}:{THREAD_ID}",
        prompt="Follow up with test coverage first.",
        mode="queue",
    )

    assert handle.session_key == session_key
    adapter.create_visible_thread.assert_not_awaited()
    adapter.dispatch_synthetic_message.assert_awaited_once()
    kwargs = adapter.dispatch_synthetic_message.await_args.kwargs
    assert kwargs["text"] == "Follow up with test coverage first."
    assert kwargs["mode"] == "queue"
    assert kwargs["source"].thread_id == THREAD_ID


@pytest.mark.asyncio
async def test_prompt_visible_session_allowed_user_uses_owner_source_when_threads_are_per_user(tmp_path):
    runner, adapter = _runner(tmp_path)
    runner.config.thread_sessions_per_user = True
    runner.config.visible_sessions_allowed_parent_user_ids = ["222"]
    owner_user_id = "111"
    owner_parent = _parent_source(user_id=owner_user_id, user_name="owner")
    child_source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id=PARENT_CHAT,
        chat_name="Hermes Sessions",
        chat_type="group",
        user_id=owner_user_id,
        thread_id=THREAD_ID,
    )
    session_key = build_session_key(child_source, thread_sessions_per_user=True)
    save_visible_session_handles(
        getattr(runner, "_visible_session_registry_path"),
        [
            VisibleSessionHandle(
                platform="telegram",
                chat_id=PARENT_CHAT,
                thread_id=THREAD_ID,
                topic_name="Delegate Smoke",
                session_key=session_key,
                session_id="session-14",
                target=f"telegram:{PARENT_CHAT}:{THREAD_ID}",
                created_by_session_key=build_session_key(owner_parent, thread_sessions_per_user=True),
                created_by_user_id=owner_user_id,
                created_at=datetime.now(timezone.utc),
            )
        ],
    )

    handle = await runner.prompt_visible_session(
        parent_event=_parent_event(user_id="222", user_name="allowed"),
        handle=f"telegram:{PARENT_CHAT}:{THREAD_ID}",
        prompt="Follow up from allowed operator.",
        mode="queue",
    )

    assert handle.session_key == session_key
    kwargs = adapter.dispatch_synthetic_message.await_args.kwargs
    routed_source = kwargs["source"]
    assert routed_source.user_id == owner_user_id
    assert build_session_key(routed_source, thread_sessions_per_user=True) == session_key


@pytest.mark.asyncio
async def test_list_visible_sessions_reads_registry(tmp_path):
    runner, _adapter = _runner(tmp_path)
    handle = VisibleSessionHandle(
        platform="telegram",
        chat_id=PARENT_CHAT,
        thread_id=THREAD_ID,
        topic_name="Delegate Smoke",
        session_key=f"agent:main:telegram:group:{PARENT_CHAT}:{THREAD_ID}",
        session_id="session-14",
        target=f"telegram:{PARENT_CHAT}:{THREAD_ID}",
        created_by_session_key=build_session_key(_parent_source()),
        created_by_user_id="6605861022",
        created_at=datetime.now(timezone.utc),
    )
    save_visible_session_handles(runner._visible_session_registry_path, [handle])

    handles = runner.list_visible_sessions(parent_event=_parent_event())

    assert [h.target for h in handles] == [f"telegram:{PARENT_CHAT}:{THREAD_ID}"]
