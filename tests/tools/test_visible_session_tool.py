import asyncio
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.run import GatewayRunner
from gateway.session import SessionEntry, SessionSource, build_session_key
from tools.visible_session_tool import LIVE_GATEWAY_ERROR, _parent_event as _tool_parent_event, visible_session_tool


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
    setattr(runner, "session_store", _FakeSessionStore())
    setattr(runner, "_session_model_overrides", {})
    setattr(runner, "_session_reasoning_overrides", {})
    setattr(runner, "_visible_session_registry_path", tmp_path / "visible_sessions.json")
    adapter = MagicMock()
    adapter.create_visible_thread = AsyncMock(
        return_value={
            "platform": "telegram",
            "chat_id": "-1001",
            "thread_id": "14",
            "topic_name": "Delegate Smoke",
            "target": "telegram:-1001:14",
        }
    )
    adapter.dispatch_synthetic_message = AsyncMock(return_value="agent:main:telegram:group:-1001:14")
    runner.adapters = {Platform.TELEGRAM: adapter}
    return runner


def _start_gateway_loop_thread():
    loop_ready = threading.Event()
    stop_loop = threading.Event()
    observed = {}

    def _loop_worker(loop):
        asyncio.set_event_loop(loop)
        observed["gateway_thread_id"] = threading.get_ident()
        loop_ready.set()

        async def _wait_for_stop():
            while not stop_loop.is_set():
                await asyncio.sleep(0.01)

        loop.create_task(_wait_for_stop())
        loop.run_forever()

    gateway_loop = asyncio.new_event_loop()
    gateway_thread = threading.Thread(target=_loop_worker, args=(gateway_loop,), daemon=True)
    gateway_thread.start()
    assert loop_ready.wait(timeout=2), "gateway loop did not start"
    return gateway_loop, gateway_thread, stop_loop, observed


def _stop_gateway_loop_thread(loop, thread, stop_evt):
    stop_evt.set()

    async def _drain_pending_tasks():
        current = asyncio.current_task()
        pending = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    try:
        asyncio.run_coroutine_threadsafe(_drain_pending_tasks(), loop).result(timeout=1)
    except Exception:
        pass

    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=2)
    loop.close()


def test_visible_session_tool_requires_live_gateway(monkeypatch):
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: None)

    out = json.loads(visible_session_tool({"action": "list", "parent_chat_id": "-1001"}))

    assert out["error"] == LIVE_GATEWAY_ERROR


def test_visible_session_tool_parent_event_preserves_chat_type_from_trusted_session_key(monkeypatch):
    monkeypatch.setattr(
        "tools.visible_session_tool.get_trusted_session_context",
        lambda: {
            "platform": "telegram",
            "chat_id": "12345",
            "thread_id": "14",
            "user_id": "6605861022",
            "user_name": "alice",
            "session_key": "agent:main:telegram:dm:12345:14",
        },
    )

    event = _tool_parent_event({})

    assert event.source.chat_type == "dm"
    assert event.source.chat_id == "12345"
    assert event.source.thread_id == "14"


def test_visible_session_tool_denies_without_trusted_gateway_context(monkeypatch):
    handle = SimpleNamespace(
        platform="telegram",
        chat_id="-1001",
        thread_id="14",
        topic_name="Review",
        session_key="agent:main:telegram:group:-1001:14",
        session_id="session-14",
        target="telegram:-1001:14",
    )
    runner = SimpleNamespace(
        create_visible_session=AsyncMock(return_value=handle),
        prompt_visible_session=AsyncMock(),
        list_visible_sessions=lambda parent_event=None: [],
    )
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)
    monkeypatch.setattr("tools.visible_session_tool.get_trusted_session_context", lambda: None)

    out = json.loads(
        visible_session_tool(
            {
                "action": "create",
                "platform": "telegram",
                "parent_chat_id": "-1001",
                "topic_name": "Review",
                "prompt": "check tests",
            }
        )
    )

    assert out["error"] == "visible_session requires gateway session context"


def test_visible_session_tool_create_calls_runner(monkeypatch):
    handle = SimpleNamespace(
        platform="telegram",
        chat_id="-1001",
        thread_id="14",
        topic_name="Review",
        session_key="agent:main:telegram:group:-1001:14",
        session_id="session-14",
        target="telegram:-1001:14",
    )
    gateway_loop, gateway_thread, stop_loop, _observed = _start_gateway_loop_thread()
    runner = SimpleNamespace(
        _gateway_loop=gateway_loop,
        create_visible_session=AsyncMock(return_value=handle),
        prompt_visible_session=AsyncMock(),
        list_visible_sessions=lambda parent_event=None: [],
    )
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)
    monkeypatch.setattr(
        "tools.visible_session_tool.get_trusted_session_context",
        lambda: {
            "platform": "telegram",
            "chat_id": "-1001",
            "thread_id": "1",
            "user_id": "6605861022",
            "user_name": "alice",
            "session_key": "agent:main:telegram:group:-1001:1",
        },
    )

    try:
        out = json.loads(
            visible_session_tool(
                {
                    "action": "create",
                    "platform": "telegram",
                    "parent_chat_id": "-1001",
                    "topic_name": "Review",
                    "prompt": "check tests",
                }
            )
        )

        assert out["ok"] is True
        assert out["action"] == "create"
        assert out["handle"]["target"] == "telegram:-1001:14"
        runner.create_visible_session.assert_awaited_once()
    finally:
        _stop_gateway_loop_thread(gateway_loop, gateway_thread, stop_loop)


def test_visible_session_tool_list_returns_handles(monkeypatch):
    runner = SimpleNamespace(
        create_visible_session=AsyncMock(),
        prompt_visible_session=AsyncMock(),
        list_visible_sessions=lambda parent_event=None: [
            SimpleNamespace(
                platform="telegram",
                chat_id="-1001",
                thread_id="14",
                topic_name="Review",
                session_key="agent:main:telegram:group:-1001:14",
                session_id="session-14",
                target="telegram:-1001:14",
            )
        ],
    )
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)
    monkeypatch.setattr(
        "tools.visible_session_tool.get_trusted_session_context",
        lambda: {
            "platform": "telegram",
            "chat_id": "-1001",
            "thread_id": "1",
            "user_id": "6605861022",
            "user_name": "alice",
            "session_key": "agent:main:telegram:group:-1001:1",
        },
    )

    out = json.loads(visible_session_tool({"action": "list", "platform": "telegram", "parent_chat_id": "-1001"}))

    assert out["ok"] is True
    assert out["action"] == "list"
    assert len(out["handles"]) == 1
    assert out["handles"][0]["target"] == "telegram:-1001:14"


@pytest.mark.asyncio
async def test_visible_session_tool_forged_parent_chat_cannot_bypass_same_parent(monkeypatch, tmp_path):
    runner = _runner(tmp_path)
    gateway_loop, gateway_thread, stop_loop, _observed = _start_gateway_loop_thread()
    runner._gateway_loop = gateway_loop
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)
    monkeypatch.setattr(
        "tools.visible_session_tool.get_trusted_session_context",
        lambda: {
            "platform": "telegram",
            "chat_id": "-1001",  # trusted source chat
            "thread_id": "1",
            "user_id": "6605861022",
            "user_name": "alice",
            "session_key": "agent:main:telegram:group:-1001:1",
        },
    )

    try:
        out = json.loads(
            visible_session_tool(
                {
                    "action": "create",
                    "platform": "telegram",
                    "parent_chat_id": "-9999",  # forged target request
                    "topic_name": "Review",
                    "prompt": "check tests",
                }
            )
        )

        assert "same parent chat" in out["error"]
    finally:
        _stop_gateway_loop_thread(gateway_loop, gateway_thread, stop_loop)


@pytest.mark.asyncio
async def test_visible_session_tool_cross_chat_requires_allowlist(monkeypatch, tmp_path):
    cfg = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="token")},
        visible_sessions_allowed_parent_chats=["-1002"],
    )
    runner = _runner(tmp_path, cfg)
    gateway_loop, gateway_thread, stop_loop, _observed = _start_gateway_loop_thread()
    runner._gateway_loop = gateway_loop
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)
    monkeypatch.setattr(
        "tools.visible_session_tool.get_trusted_session_context",
        lambda: {
            "platform": "telegram",
            "chat_id": "-1001",  # trusted source is chat A
            "thread_id": "1",
            "user_id": "6605861022",
            "user_name": "alice",
            "session_key": "agent:main:telegram:group:-1001:1",
        },
    )

    try:
        out = json.loads(
            visible_session_tool(
                {
                    "action": "create",
                    "platform": "telegram",
                    "parent_chat_id": "-1003",  # chat B not allowlisted
                    "topic_name": "Review",
                    "prompt": "check tests",
                }
            )
        )

        assert "not allowed in parent chat" in out["error"]
    finally:
        _stop_gateway_loop_thread(gateway_loop, gateway_thread, stop_loop)


def test_visible_session_tool_profile_workdir_errors_are_clear(monkeypatch, tmp_path):
    runner = _runner(tmp_path)
    gateway_loop, gateway_thread, stop_loop, _observed = _start_gateway_loop_thread()
    runner._gateway_loop = gateway_loop
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)
    monkeypatch.setattr(
        "tools.visible_session_tool.get_trusted_session_context",
        lambda: {
            "platform": "telegram",
            "chat_id": "-1001",
            "thread_id": "1",
            "user_id": "6605861022",
            "user_name": "alice",
            "session_key": "agent:main:telegram:group:-1001:1",
        },
    )

    try:
        profile_out = json.loads(
            visible_session_tool(
                {
                    "action": "create",
                    "parent_chat_id": "-1001",
                    "topic_name": "Review",
                    "prompt": "check tests",
                    "profile": "other-profile",
                }
            )
        )
        assert "Profiles are process-level today" in profile_out["error"]

        workdir_out = json.loads(
            visible_session_tool(
                {
                    "action": "create",
                    "parent_chat_id": "-1001",
                    "topic_name": "Review",
                    "prompt": "check tests",
                    "workdir": "/tmp/any",
                }
            )
        )
        assert "workdir overrides are not session-local in v1" in workdir_out["error"]
    finally:
        _stop_gateway_loop_thread(gateway_loop, gateway_thread, stop_loop)


def test_visible_session_tool_create_runs_on_gateway_loop_thread(monkeypatch):
    gateway_loop, gateway_thread, stop_loop, observed = _start_gateway_loop_thread()

    async def _create_visible_session(**_kwargs):
        observed["runner_loop"] = asyncio.get_running_loop()
        observed["runner_thread_id"] = threading.get_ident()
        return SimpleNamespace(
            platform="telegram",
            chat_id="-1001",
            thread_id="14",
            topic_name="Review",
            session_key="agent:main:telegram:group:-1001:14",
            session_id="session-14",
            target="telegram:-1001:14",
        )

    runner = SimpleNamespace(
        _gateway_loop=gateway_loop,
        create_visible_session=AsyncMock(side_effect=_create_visible_session),
        prompt_visible_session=AsyncMock(),
        list_visible_sessions=lambda parent_event=None: [],
    )
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)
    monkeypatch.setattr(
        "tools.visible_session_tool.get_trusted_session_context",
        lambda: {
            "platform": "telegram",
            "chat_id": "-1001",
            "thread_id": "1",
            "user_id": "6605861022",
            "user_name": "alice",
            "session_key": "agent:main:telegram:group:-1001:1",
        },
    )

    try:
        out = json.loads(
            visible_session_tool(
                {
                    "action": "create",
                    "platform": "telegram",
                    "parent_chat_id": "-1001",
                    "topic_name": "Review",
                    "prompt": "check tests",
                }
            )
        )
        assert out["ok"] is True
        assert observed["runner_loop"] is gateway_loop
        assert observed["runner_thread_id"] == observed["gateway_thread_id"]
    finally:
        _stop_gateway_loop_thread(gateway_loop, gateway_thread, stop_loop)


def test_visible_session_tool_requires_live_gateway_loop_for_async_actions(monkeypatch):
    runner = SimpleNamespace(
        _gateway_loop=None,
        create_visible_session=AsyncMock(),
        prompt_visible_session=AsyncMock(),
        list_visible_sessions=lambda parent_event=None: [],
    )
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)
    monkeypatch.setattr(
        "tools.visible_session_tool.get_trusted_session_context",
        lambda: {
            "platform": "telegram",
            "chat_id": "-1001",
            "thread_id": "1",
            "user_id": "6605861022",
            "user_name": "alice",
            "session_key": "agent:main:telegram:group:-1001:1",
        },
    )

    out = json.loads(
        visible_session_tool(
            {
                "action": "create",
                "platform": "telegram",
                "parent_chat_id": "-1001",
                "topic_name": "Review",
                "prompt": "check tests",
            }
        )
    )

    assert out["error"] == "visible_session requires live gateway event loop"


def test_visible_session_tool_rejects_stopped_gateway_loop(monkeypatch):
    loop = asyncio.new_event_loop()
    runner = SimpleNamespace(
        _gateway_loop=loop,
        create_visible_session=AsyncMock(),
        prompt_visible_session=AsyncMock(),
        list_visible_sessions=lambda parent_event=None: [],
    )
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)
    monkeypatch.setattr(
        "tools.visible_session_tool.get_trusted_session_context",
        lambda: {
            "platform": "telegram",
            "chat_id": "-1001",
            "thread_id": "1",
            "user_id": "6605861022",
            "user_name": "alice",
            "session_key": "agent:main:telegram:group:-1001:1",
        },
    )

    try:
        out = json.loads(
            visible_session_tool(
                {
                    "action": "create",
                    "platform": "telegram",
                    "parent_chat_id": "-1001",
                    "topic_name": "Review",
                    "prompt": "check tests",
                }
            )
        )
        assert out["error"] == "visible_session requires live gateway event loop"
    finally:
        loop.close()


def test_visible_session_tool_rejects_closed_gateway_loop(monkeypatch):
    loop = asyncio.new_event_loop()
    loop.close()
    runner = SimpleNamespace(
        _gateway_loop=loop,
        create_visible_session=AsyncMock(),
        prompt_visible_session=AsyncMock(),
        list_visible_sessions=lambda parent_event=None: [],
    )
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)
    monkeypatch.setattr(
        "tools.visible_session_tool.get_trusted_session_context",
        lambda: {
            "platform": "telegram",
            "chat_id": "-1001",
            "thread_id": "1",
            "user_id": "6605861022",
            "user_name": "alice",
            "session_key": "agent:main:telegram:group:-1001:1",
        },
    )

    out = json.loads(
        visible_session_tool(
            {
                "action": "create",
                "platform": "telegram",
                "parent_chat_id": "-1001",
                "topic_name": "Review",
                "prompt": "check tests",
            }
        )
    )

    assert out["error"] == "visible_session requires live gateway event loop"


def test_visible_session_tool_list_async_runs_on_gateway_loop_thread(monkeypatch):
    gateway_loop, gateway_thread, stop_loop, observed = _start_gateway_loop_thread()

    async def _list_visible_sessions(**_kwargs):
        observed["runner_loop"] = asyncio.get_running_loop()
        observed["runner_thread_id"] = threading.get_ident()
        return [
            SimpleNamespace(
                platform="telegram",
                chat_id="-1001",
                thread_id="14",
                topic_name="Review",
                session_key="agent:main:telegram:group:-1001:14",
                session_id="session-14",
                target="telegram:-1001:14",
            )
        ]

    runner = SimpleNamespace(
        _gateway_loop=gateway_loop,
        create_visible_session=AsyncMock(),
        prompt_visible_session=AsyncMock(),
        list_visible_sessions=AsyncMock(side_effect=_list_visible_sessions),
    )
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)
    monkeypatch.setattr(
        "tools.visible_session_tool.get_trusted_session_context",
        lambda: {
            "platform": "telegram",
            "chat_id": "-1001",
            "thread_id": "1",
            "user_id": "6605861022",
            "user_name": "alice",
            "session_key": "agent:main:telegram:group:-1001:1",
        },
    )

    try:
        out = json.loads(visible_session_tool({"action": "list", "platform": "telegram", "parent_chat_id": "-1001"}))
        assert out["ok"] is True
        assert len(out["handles"]) == 1
        assert observed["runner_loop"] is gateway_loop
        assert observed["runner_thread_id"] == observed["gateway_thread_id"]
    finally:
        _stop_gateway_loop_thread(gateway_loop, gateway_thread, stop_loop)


@pytest.mark.asyncio
async def test_visible_session_tool_list_and_prompt_are_scoped_to_creating_parent(monkeypatch, tmp_path):
    runner = _runner(tmp_path)
    gateway_loop, gateway_thread, stop_loop, _observed = _start_gateway_loop_thread()
    runner._gateway_loop = gateway_loop
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)

    parent_a = {
        "platform": "telegram",
        "chat_id": "-1001",
        "thread_id": "1",
        "user_id": "6605861022",
        "user_name": "alice",
        "session_key": "agent:main:telegram:group:-1001:1",
    }
    parent_b = {
        "platform": "telegram",
        "chat_id": "-1001",
        "thread_id": "2",
        "user_id": "777777",
        "user_name": "intruder",
        "session_key": "agent:main:telegram:group:-1001:2",
    }

    try:
        monkeypatch.setattr("tools.visible_session_tool.get_trusted_session_context", lambda: parent_a)
        created = json.loads(
            visible_session_tool(
                {
                    "action": "create",
                    "platform": "telegram",
                    "parent_chat_id": "-1001",
                    "topic_name": "Scoped Delegate",
                    "prompt": "start",
                }
            )
        )
        assert created["ok"] is True
        handle = created["handle"]["target"]

        own_list = json.loads(visible_session_tool({"action": "list"}))
        assert own_list["ok"] is True
        assert len(own_list["handles"]) == 1
        assert own_list["handles"][0]["target"] == handle

        own_prompt = json.loads(visible_session_tool({"action": "prompt", "handle": handle, "prompt": "follow-up"}))
        assert own_prompt["ok"] is True

        monkeypatch.setattr("tools.visible_session_tool.get_trusted_session_context", lambda: parent_b)
        other_list = json.loads(visible_session_tool({"action": "list"}))
        assert other_list["ok"] is True
        assert other_list["handles"] == []

        other_prompt = json.loads(visible_session_tool({"action": "prompt", "handle": handle, "prompt": "hijack"}))
        assert "Not authorized to prompt this visible session handle" in other_prompt["error"]
    finally:
        _stop_gateway_loop_thread(gateway_loop, gateway_thread, stop_loop)


@pytest.mark.asyncio
async def test_visible_session_tool_allowlisted_parent_session_key_can_access_cross_parent(monkeypatch, tmp_path):
    runner = _runner(tmp_path)
    monkeypatch.setattr(
        runner.config,
        "visible_sessions_allowed_parent_session_keys",
        ["agent:main:telegram:group:-1001:2"],
        raising=False,
    )
    gateway_loop, gateway_thread, stop_loop, _observed = _start_gateway_loop_thread()
    runner._gateway_loop = gateway_loop
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)

    parent_a = {
        "platform": "telegram",
        "chat_id": "-1001",
        "thread_id": "1",
        "user_id": "6605861022",
        "user_name": "alice",
        "session_key": "agent:main:telegram:group:-1001:1",
    }
    parent_b = {
        "platform": "telegram",
        "chat_id": "-1001",
        "thread_id": "2",
        "user_id": "777777",
        "user_name": "reviewer",
        "session_key": "agent:main:telegram:group:-1001:2",
    }

    try:
        monkeypatch.setattr("tools.visible_session_tool.get_trusted_session_context", lambda: parent_a)
        created = json.loads(
            visible_session_tool(
                {
                    "action": "create",
                    "platform": "telegram",
                    "parent_chat_id": "-1001",
                    "topic_name": "Scoped Delegate",
                    "prompt": "start",
                }
            )
        )
        handle = created["handle"]["target"]

        monkeypatch.setattr("tools.visible_session_tool.get_trusted_session_context", lambda: parent_b)
        listed = json.loads(visible_session_tool({"action": "list"}))
        assert listed["ok"] is True
        assert len(listed["handles"]) == 1
        assert listed["handles"][0]["target"] == handle

        prompted = json.loads(visible_session_tool({"action": "prompt", "handle": handle, "prompt": "review"}))
        assert prompted["ok"] is True
    finally:
        _stop_gateway_loop_thread(gateway_loop, gateway_thread, stop_loop)


@pytest.mark.asyncio
async def test_visible_session_tool_status_and_close_retire_handle_for_quota(monkeypatch, tmp_path):
    cfg = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="token")},
        visible_sessions_max_active_per_parent=1,
    )
    runner = _runner(tmp_path, cfg)
    gateway_loop, gateway_thread, stop_loop, _observed = _start_gateway_loop_thread()
    runner._gateway_loop = gateway_loop
    monkeypatch.setattr("tools.visible_session_tool._gateway_runner_ref", lambda: runner)
    monkeypatch.setattr(
        "tools.visible_session_tool.get_trusted_session_context",
        lambda: {
            "platform": "telegram",
            "chat_id": "-1001",
            "thread_id": "1",
            "user_id": "6605861022",
            "user_name": "alice",
            "session_key": "agent:main:telegram:group:-1001:1",
        },
    )

    try:
        created = json.loads(
            visible_session_tool(
                {
                    "action": "create",
                    "platform": "telegram",
                    "parent_chat_id": "-1001",
                    "topic_name": "Scoped Delegate",
                    "prompt": "start",
                }
            )
        )
        handle = created["handle"]["target"]

        status = json.loads(visible_session_tool({"action": "status", "handle": handle}))
        assert status["ok"] is True
        assert status["handle"]["target"] == handle

        over_limit = json.loads(
            visible_session_tool(
                {
                    "action": "create",
                    "platform": "telegram",
                    "parent_chat_id": "-1001",
                    "topic_name": "Second Delegate",
                    "prompt": "start",
                }
            )
        )
        assert "Visible session limit reached" in over_limit["error"]

        closed = json.loads(visible_session_tool({"action": "close", "handle": handle}))
        assert closed["ok"] is True
        assert closed["handle"]["target"] == handle
        assert json.loads(visible_session_tool({"action": "list"}))["handles"] == []

        recreated = json.loads(
            visible_session_tool(
                {
                    "action": "create",
                    "platform": "telegram",
                    "parent_chat_id": "-1001",
                    "topic_name": "Replacement Delegate",
                    "prompt": "start",
                }
            )
        )
        assert recreated["ok"] is True
    finally:
        _stop_gateway_loop_thread(gateway_loop, gateway_thread, stop_loop)
