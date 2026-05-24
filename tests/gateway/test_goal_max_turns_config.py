from typing import Any
import asyncio

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType, SendResult
from gateway.run import GatewayRunner
from gateway.session import SessionSource, build_session_key
from hermes_cli import goals


class _FakeSessionEntry:
    session_id = "sid-gateway-goal-config"


class _FakeSessionStore:
    def __init__(self):
        self.entry = _FakeSessionEntry()

    def get_or_create_session(self, source):
        return self.entry

    def _generate_session_key(self, source):
        return build_session_key(source)


class _RecordingAdapter:
    def __init__(self):
        self._pending_messages = {}


class _DrainingAdapter(BasePlatformAdapter):
    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token="token"), Platform.DISCORD)
        self.sent = []

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        pass

    async def send(self, chat_id, content, reply_to=None, metadata=None) -> SendResult:
        self.sent.append(content)
        return SendResult(success=True)

    async def get_chat_info(self, chat_id):
        return {}


@pytest.mark.asyncio
async def test_gateway_goal_uses_goals_max_turns_from_full_config(tmp_path, monkeypatch):
    """Gateway /goal should honor top-level goals.max_turns from config.yaml."""
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text("goals:\n  max_turns: 7\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))
    goals._DB_CACHE.clear()

    runner: Any = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.DISCORD: PlatformConfig(enabled=True, token="token")}
    )
    runner.session_store = _FakeSessionStore()
    runner.adapters = {}
    runner._queued_events = {}

    event = MessageEvent(
        text="/goal ship the benchmark",
        message_type=MessageType.TEXT,
        source=SessionSource(
            platform=Platform.DISCORD,
            chat_id="chat-goal-config",
            chat_type="channel",
            user_id="user-goal-config",
        ),
        message_id="msg-goal-config",
    )

    response = await GatewayRunner._handle_goal_command(runner, event)

    try:
        assert "⊙ Goal set (7-turn budget): ship the benchmark" in response
        state = goals.GoalManager("sid-gateway-goal-config").state
        assert state is not None
        assert state.max_turns == 7
    finally:
        goals._DB_CACHE.clear()


@pytest.mark.asyncio
async def test_gateway_goal_resume_queues_continuation(tmp_path, monkeypatch):
    """Gateway /goal resume should restart the loop, not just flip state."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    goals._DB_CACHE.clear()

    runner: Any = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.DISCORD: PlatformConfig(enabled=True, token="token")}
    )
    runner.session_store = _FakeSessionStore()
    runner.adapters = {Platform.DISCORD: _RecordingAdapter()}
    runner._queued_events = {}

    source = SessionSource(
        platform=Platform.DISCORD,
        chat_id="chat-goal-config",
        chat_type="channel",
        user_id="user-goal-config",
    )
    mgr = goals.GoalManager("sid-gateway-goal-config")
    mgr.set("polish /goal resume behavior")
    mgr.pause("user-paused")

    event = MessageEvent(
        text="/goal resume",
        message_type=MessageType.TEXT,
        source=source,
        message_id="msg-goal-resume",
    )

    response = await GatewayRunner._handle_goal_command(runner, event)

    try:
        assert "Goal resumed" in response
        assert "Queued the next /goal continuation turn" in response
        pending = runner.adapters[Platform.DISCORD]._pending_messages
        queued = pending["agent:main:discord:channel:chat-goal-config:user-goal-config"]
        assert queued.text.startswith("[Continuing toward your standing goal]")
        assert "polish /goal resume behavior" in queued.text
    finally:
        goals._DB_CACHE.clear()


@pytest.mark.asyncio
async def test_gateway_goal_resume_continuation_is_drained_by_adapter(tmp_path, monkeypatch):
    """Behavior-level guard: /goal resume should lead to a processed follow-up turn."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    goals._DB_CACHE.clear()

    runner: Any = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.DISCORD: PlatformConfig(enabled=True, token="token")}
    )
    runner.session_store = _FakeSessionStore()
    runner._queued_events = {}

    adapter = _DrainingAdapter()
    runner.adapters = {Platform.DISCORD: adapter}

    source = SessionSource(
        platform=Platform.DISCORD,
        chat_id="chat-goal-config",
        chat_type="channel",
        user_id="user-goal-config",
    )
    mgr = goals.GoalManager("sid-gateway-goal-config")
    mgr.set("prove /goal resume drains")
    mgr.pause("user-paused")

    processed = []

    async def handler(event):
        processed.append(event.text)
        if event.text == "/goal resume":
            return await GatewayRunner._handle_goal_command(runner, event)
        return "continued"

    adapter._message_handler = handler
    await adapter.handle_message(
        MessageEvent(
            text="/goal resume",
            message_type=MessageType.TEXT,
            source=source,
            message_id="msg-goal-resume",
        )
    )

    try:
        for _ in range(50):
            if any(text.startswith("[Continuing toward your standing goal]") for text in processed):
                break
            await asyncio.sleep(0.01)

        assert processed[0] == "/goal resume"
        assert any(text.startswith("[Continuing toward your standing goal]") for text in processed)
        assert any("Queued the next /goal continuation turn" in text for text in adapter.sent)
    finally:
        await adapter.cancel_background_tasks()
        goals._DB_CACHE.clear()
