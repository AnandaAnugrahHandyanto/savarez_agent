import asyncio
from unittest.mock import AsyncMock, MagicMock

import run_agent
from gateway.config import Platform
from gateway.run import GatewayRunner
from gateway.session import SessionSource


class _StubAgent:
    def __init__(self, *args, **kwargs):
        self.tools = []
        self.tool_progress_callback = None
        self.step_callback = None
        self.stream_delta_callback = None
        self.interim_assistant_callback = None
        self.status_callback = None
        self.reasoning_config = None
        self.service_tier = None
        self.request_overrides = None
        self.background_review_callback = None

    def run_conversation(self, user_message, system_message=None, conversation_history=None, task_id=None):
        return {
            "final_response": "ok",
            "messages": [],
            "api_calls": 1,
            "tools": [],
            "completed": True,
        }


def _make_runner():
    runner = GatewayRunner.__new__(GatewayRunner)
    runner.adapters = {}
    runner._ephemeral_system_prompt = ""
    runner._prefill_messages = []
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._running_agents = {}
    runner._smart_model_routing = {}
    runner._session_db = None
    runner._agent_cache_lock = None
    runner._agent_cache = None
    runner.hooks = MagicMock()
    runner.hooks.emit = AsyncMock()
    runner.hooks.loaded_hooks = []
    runner._load_reasoning_config = lambda: {}
    runner._load_service_tier = lambda: None
    runner._resolve_session_agent_runtime = lambda **kwargs: ("test/model", {})
    runner._resolve_turn_agent_config = lambda message, model, runtime: {
        "model": model,
        "runtime": runtime,
    }
    runner._agent_config_signature = lambda *args, **kwargs: "sig"
    return runner


def test_run_agent_accepts_delivery_metadata_without_unboundlocalerror(monkeypatch):
    """Regression: explicit delivery_metadata must not leave _progress_thread_id undefined."""
    runner = _make_runner()
    source = SessionSource(
        platform=Platform.SLACK,
        chat_id="C123",
        chat_type="channel",
        user_id="U123",
    )

    monkeypatch.setattr(run_agent, "AIAgent", _StubAgent)

    result = asyncio.run(
        runner._run_agent(
            message="ping",
            context_prompt="",
            history=[],
            source=source,
            session_id="session-1",
            session_key="slack:channel:C123",
            event_message_id="1712345678.9",
            delivery_metadata={"thread_id": "1712345678.9"},
        )
    )

    assert result["final_response"] == "ok"
