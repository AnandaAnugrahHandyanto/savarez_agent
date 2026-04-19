import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform, StreamingConfig
from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.session import SessionSource


def _make_source(platform=Platform.TELEGRAM):
    return SessionSource(
        platform=platform,
        chat_id="6493121275",
        chat_name="Test Chat",
        chat_type="dm",
        user_id="6493121275",
        user_name="Tyler",
        thread_id=None,
    )


@pytest.mark.asyncio
async def test_gateway_clarify_callback_round_trip():
    runner = GatewayRunner.__new__(GatewayRunner)
    adapter = MagicMock()
    adapter.send = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._pending_clarify = {}
    source = _make_source()

    callback = runner._build_clarify_callback(
        source=source,
        session_key="telegram:6493121275",
        loop=asyncio.get_running_loop(),
        metadata=None,
    )

    result_box = {}

    def worker():
        result_box["result"] = callback("Pick a color", ["red", "blue"])

    thread = threading.Thread(target=worker)
    thread.start()

    for _ in range(20):
        if runner._pending_clarify:
            break
        await asyncio.sleep(0.05)

    for _ in range(20):
        if adapter.send.await_count:
            break
        await asyncio.sleep(0.05)

    assert "telegram:6493121275" in runner._pending_clarify
    adapter.send.assert_awaited_once()
    sent_text = adapter.send.await_args.args[1]
    assert "Pick a color" in sent_text
    assert "1. red" in sent_text
    assert "2. blue" in sent_text

    entry = runner._pending_clarify["telegram:6493121275"]
    entry["response"] = "blue"
    entry["event"].set()

    thread.join(timeout=2)
    assert result_box["result"] == "blue"
    assert "telegram:6493121275" not in runner._pending_clarify


@pytest.mark.asyncio
async def test_handle_pending_clarify_consumes_numeric_reply():
    runner = GatewayRunner.__new__(GatewayRunner)
    runner._pending_clarify = {
        "telegram:6493121275": {
            "question": "Pick a color",
            "choices": ["red", "blue"],
            "response": None,
            "event": threading.Event(),
            "user_id": "6493121275",
        }
    }
    event = MessageEvent(
        text="2",
        message_type=MessageType.TEXT,
        source=_make_source(),
    )

    result = await runner._handle_pending_clarify(event, "telegram:6493121275")

    assert result == ""
    entry = runner._pending_clarify["telegram:6493121275"]
    assert entry["response"] == "blue"
    assert entry["event"].is_set()


@pytest.mark.asyncio
async def test_run_agent_wires_clarify_callback_to_agent(monkeypatch):
    runner = GatewayRunner.__new__(GatewayRunner)
    runner.adapters = {}
    runner.config = MagicMock()
    runner.config.streaming = StreamingConfig()
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._session_model_overrides = {}
    runner._agent_cache = {}
    runner._agent_cache_lock = None
    runner._provider_routing = {
        "only": None,
        "ignore": None,
        "order": None,
        "sort": None,
        "require_parameters": False,
        "data_collection": None,
    }
    runner._fallback_model = None
    runner._prefill_messages = None
    runner._ephemeral_system_prompt = ""
    runner._session_db = None
    runner._pending_clarify = {}
    runner.hooks = MagicMock()
    runner.hooks.loaded_hooks = False
    runner._load_reasoning_config = lambda: None
    runner._load_service_tier = lambda: None
    runner._resolve_session_agent_runtime = lambda **kw: (
        "anthropic/claude-sonnet-4",
        {
            "api_key": "test-key",
            "base_url": "https://openrouter.ai/api/v1",
            "provider": "openrouter",
            "api_mode": "chat_completions",
        },
    )
    runner._resolve_turn_agent_config = lambda message, model, runtime: {
        "model": model,
        "runtime": runtime,
        "request_overrides": None,
    }
    runner._build_clarify_callback = lambda **kw: (lambda question, choices: "blue")
    runner._get_proxy_url = lambda: None

    class FakeAgent:
        def __init__(self, *args, **kwargs):
            self.clarify_callback = None
            self.tools = []

        def run_conversation(self, user_message=None, **kwargs):
            return {
                "final_response": self.clarify_callback("Pick a color", ["red", "blue"]),
                "messages": [],
                "api_calls": 1,
                "completed": True,
            }

    monkeypatch.setattr("gateway.run._load_gateway_config", lambda: {"display": {}})

    source = _make_source()
    with patch("run_agent.AIAgent", FakeAgent), patch(
        "hermes_cli.tools_config._get_platform_tools", return_value=[]
    ):
        result = await runner._run_agent(
            message="hello",
            context_prompt="",
            history=[],
            source=source,
            session_id="session-1",
            session_key="telegram:6493121275",
        )

    assert result["final_response"] == "blue"
