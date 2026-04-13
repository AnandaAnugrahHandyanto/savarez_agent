import importlib
import sys
import types
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource


@pytest.mark.asyncio
async def test_handle_message_with_agent_shared_thread_prefixes_sender_once(monkeypatch):
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)

    gateway_run = importlib.import_module("gateway.run")
    GatewayRunner = gateway_run.GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="fake-token")}
    )
    adapter = MagicMock()
    adapter.send = AsyncMock()
    adapter.stop_typing = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=False)
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = SessionEntry(
        session_key="agent:main:telegram:group:-1001:17585",
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="group",
    )
    runner.session_store.load_transcript.return_value = []
    runner.session_store.has_any_sessions.return_value = False
    runner.session_store.append_to_transcript = MagicMock()
    runner.session_store.update_session = MagicMock()
    runner.session_store.config = MagicMock()
    runner.session_store.config.get_reset_policy.return_value = SimpleNamespace(
        notify=False,
        at_hour=0,
        notify_exclude_platforms=[],
    )
    runner._running_agents = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._session_db = None
    runner._is_user_authorized = lambda _source: True
    runner._set_session_env = lambda _context: []
    runner._model = "test-model"
    runner._base_url = ""
    runner._show_reasoning = False
    runner._has_setup_skill = lambda: False
    runner._has_home_channel_for_source = lambda source: True
    runner._resolve_session_agent_runtime = lambda **kwargs: ("test-model", {"api_key": "fake"})
    runner._run_agent = AsyncMock(
        return_value={
            "final_response": "ok",
            "messages": [],
            "tools": [],
            "history_offset": 0,
            "last_prompt_tokens": 0,
        }
    )

    monkeypatch.setattr(gateway_run, "_hermes_home", gateway_run.Path("/tmp"))
    monkeypatch.setattr(gateway_run, "_config_path", "/tmp/nonexistent-config.yaml")
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "fake"})

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1001",
        chat_type="group",
        thread_id="17585",
        user_name="alice",
    )
    event = MessageEvent(text="hello", source=source, message_id="1")

    result = await runner._handle_message_with_agent(event, source, "q")

    assert result == "ok"
    sent_message = runner._run_agent.await_args.kwargs["message"]
    assert sent_message == "[alice] hello"
