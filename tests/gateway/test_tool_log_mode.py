"""Tests for log mode in gateway tool_progress."""

import asyncio
import importlib
import re
import sys
import time
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult
from gateway.session import SessionSource


class NoSendAdapter(BasePlatformAdapter):
    """Adapter that records sent messages — log mode should result in zero sent."""
    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token="fake-token"), Platform.TELEGRAM)
        self.sent = []

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        return None

    async def send(self, chat_id, content, reply_to=None, metadata=None) -> SendResult:
        self.sent.append(content)
        return SendResult(success=True, message_id="msg-1")

    async def edit_message(self, chat_id, message_id, content) -> SendResult:
        return SendResult(success=True, message_id=message_id)

    async def send_typing(self, chat_id, metadata=None) -> None:
        pass

    async def get_chat_info(self, chat_id: str):
        return {"id": chat_id}


class FakeAgentLog:
    """Fake agent that calls tool_progress_callback twice."""
    def __init__(self, **kwargs):
        self.tool_progress_callback = kwargs.get("tool_progress_callback")
        self.tools = []

    def run_conversation(self, message, conversation_history=None, task_id=None):
        if self.tool_progress_callback:
            self.tool_progress_callback("terminal", "ls -la")
            time.sleep(0.05)
            self.tool_progress_callback("read_file", "setup.py")
        return {"final_response": "done", "messages": [], "api_calls": 1}


def _make_runner(adapter):
    gateway_run = importlib.import_module("gateway.run")
    GatewayRunner = gateway_run.GatewayRunner
    runner = object.__new__(GatewayRunner)
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner._prefill_messages = []
    runner._ephemeral_system_prompt = ""
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._session_db = None
    runner._running_agents = {}
    runner.hooks = MagicMock()
    runner.hooks.loaded_hooks = False
    return runner


@pytest.mark.asyncio
async def test_log_mode_writes_to_file(monkeypatch, tmp_path: Path):
    """log mode writes timestamped tool calls to tool_calls.log and sends nothing to chat."""
    monkeypatch.setenv("HERMES_TOOL_PROGRESS_MODE", "log")

    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)

    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = FakeAgentLog
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)

    adapter = NoSendAdapter()
    runner = _make_runner(adapter)
    gateway_run = importlib.import_module("gateway.run")
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "fake"})

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1001",
        chat_type="private",
        thread_id=None,
    )

    result = await runner._run_agent(
        message="hello",
        context_prompt="",
        history=[],
        source=source,
        session_id="sess-log-1",
        session_key="agent:main:telegram:private:-1001",
    )
    await asyncio.sleep(0.1)  # Allow log_task to finish flushing

    assert result["final_response"] == "done"
    # log mode sends nothing to the chat
    assert adapter.sent == [], f"Expected no messages in log mode, got: {adapter.sent}"

    # tool_calls.log should exist and contain both tool calls
    log_file = tmp_path / "logs" / "tool_calls.log"
    assert log_file.exists(), f"Expected tool_calls.log to exist at {log_file}"

    content = log_file.read_text(encoding="utf-8")
    assert "terminal:" in content
    assert "read_file:" in content
    # Each line should have timestamp format: YYYY-MM-DD HH:MM:SS  tool_name:
    timestamp_pattern = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}  \w+:")
    lines = [l for l in content.strip().split("\n") if l]
    assert len(lines) >= 2, f"Expected at least 2 log lines, got {len(lines)}: {lines}"
    assert all(timestamp_pattern.match(line) for line in lines), \
        f"Not all lines match timestamp format: {lines}"


@pytest.mark.asyncio
async def test_log_mode_creates_no_chat_messages(monkeypatch, tmp_path: Path):
    """Confirm log mode produces zero sent messages across two sessions."""
    monkeypatch.setenv("HERMES_TOOL_PROGRESS_MODE", "log")

    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)

    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = FakeAgentLog
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)

    adapter = NoSendAdapter()
    runner = _make_runner(adapter)
    gateway_run = importlib.import_module("gateway.run")
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "fake"})

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-2001",
        chat_type="private",
        thread_id=None,
    )

    await runner._run_agent(
        message="hello",
        context_prompt="",
        history=[],
        source=source,
        session_id="sess-log-2",
        session_key="agent:main:telegram:private:-2001",
    )

    assert adapter.sent == [], f"log mode should send nothing, got: {adapter.sent}"
    log_file = tmp_path / "logs" / "tool_calls.log"
    assert log_file.exists()


@pytest.mark.asyncio
async def test_all_mode_does_not_create_tool_calls_log(monkeypatch, tmp_path: Path):
    """When tool_progress is 'all', tool_calls.log must NOT be created."""
    monkeypatch.setenv("HERMES_TOOL_PROGRESS_MODE", "all")

    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)

    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = FakeAgentLog
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)

    adapter = NoSendAdapter()
    runner = _make_runner(adapter)
    gateway_run = importlib.import_module("gateway.run")
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "fake"})

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-3001",
        chat_type="private",
        thread_id=None,
    )

    await runner._run_agent(
        message="hello",
        context_prompt="",
        history=[],
        source=source,
        session_id="sess-all-1",
        session_key="agent:main:telegram:private:-3001",
    )

    log_file = tmp_path / "logs" / "tool_calls.log"
    assert not log_file.exists(), \
        "tool_calls.log should NOT exist when mode is 'all' (log file is log-mode only)"
