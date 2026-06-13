from __future__ import annotations

import sys
import threading
import time
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import gateway.run as gateway_run
from gateway.config import Platform
from gateway.platforms.base import SendResult
from gateway.session import SessionSource


class _ProgressAgent:
    def __init__(self, *args, **kwargs):
        self.tools = []
        self.tool_progress_callback = None
        self.is_interrupted = False

    def run_conversation(self, user_message, conversation_history=None, task_id=None, persist_user_message=None):
        assert self.tool_progress_callback is not None
        self.tool_progress_callback(
            "tool.started",
            tool_name="read_file",
            preview="gateway/run.py",
            args={"path": "gateway/run.py"},
        )
        # Give the async progress sender a chance to drain the queue before
        # _run_agent cancels it in the finally block.
        time.sleep(0.45)
        return {
            "final_response": "ok",
            "messages": [],
            "api_calls": 1,
            "completed": True,
        }


class _ProgressAdapter:
    name = "test-progress"
    MAX_MESSAGE_LENGTH = 4000

    def __init__(self):
        self.sent: list[str] = []
        self.edited: list[str] = []
        self._pending_messages = {}

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        self.sent.append(content)
        return SendResult(success=True, message_id=f"msg-{len(self.sent)}")

    async def edit_message(self, chat_id, message_id, content, metadata=None):
        self.edited.append(content)
        return SendResult(success=True, message_id=message_id)

    async def send_typing(self, chat_id, metadata=None):
        return None

    def get_pending_message(self, session_key):
        return None


def _install_progress_agent(monkeypatch):
    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = _ProgressAgent
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)


def _make_runner(adapter: _ProgressAdapter):
    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._ephemeral_system_prompt = ""
    runner._prefill_messages = []
    runner._reasoning_config = None
    runner._service_tier = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._running_agents = {}
    runner._pending_model_notes = {}
    runner._session_db = None
    runner._agent_cache = {}
    runner._agent_cache_lock = threading.Lock()
    runner._session_model_overrides = {}
    runner._draining = False
    runner._update_runtime_status = lambda status: None
    runner.hooks = SimpleNamespace(loaded_hooks=False)
    runner.config = SimpleNamespace(streaming=None)
    runner.session_store = SimpleNamespace(
        get_or_create_session=lambda source: SimpleNamespace(session_id="session-1"),
        load_transcript=lambda session_id: [],
    )
    runner._get_or_create_gateway_honcho = lambda session_key: (None, None)
    runner._enrich_message_with_vision = AsyncMock(return_value="ENRICHED")
    return runner


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="12345",
        chat_type="dm",
        user_id="user-1",
    )


@pytest.mark.asyncio
async def test_gateway_tool_progress_event_path_preserves_rendered_text(monkeypatch, tmp_path):
    _install_progress_agent(monkeypatch)
    adapter = _ProgressAdapter()
    runner = _make_runner(adapter)

    (tmp_path / "config.yaml").write_text("display:\n  tool_progress: all\n", encoding="utf-8")
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_env_path", tmp_path / ".env")
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: {"display": {"tool_progress": "all"}})
    monkeypatch.setattr(
        gateway_run,
        "_load_gateway_runtime_config",
        lambda: {"display": {"tool_progress": "all"}},
    )
    monkeypatch.setattr(gateway_run, "_resolve_gateway_model", lambda config=None: "gpt-5.5")
    monkeypatch.setattr(
        gateway_run,
        "_resolve_runtime_agent_kwargs",
        lambda: {
            "provider": "openai-codex",
            "api_mode": "codex_responses",
            "base_url": None,
            "api_key": "***",
        },
    )

    import hermes_cli.tools_config as tools_config

    monkeypatch.setattr(tools_config, "_get_platform_tools", lambda user_config, platform_key: {"file"})
    monkeypatch.setenv("HERMES_AGENT_NOTIFY_INTERVAL", "0")

    result = await runner._run_agent(
        message="hi",
        context_prompt="",
        history=[],
        source=_make_source(),
        session_id="session-1",
        session_key="agent:main:telegram:dm:12345",
    )

    assert result["final_response"] == "ok"
    assert adapter.sent
    assert adapter.sent[0] == '⚙️ read_file: "gateway/run.py"'
