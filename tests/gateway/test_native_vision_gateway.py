"""Tests for gateway native vision passthrough."""
import asyncio
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import gateway.run as gateway_run
from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


class _CapturingAgent:
    last_init = None
    last_run = None

    def __init__(self, *args, **kwargs):
        type(self).last_init = dict(kwargs)
        self.tools = []

    def run_conversation(self, user_message, conversation_history=None, task_id=None, persist_user_message=None, user_message_content=None):
        type(self).last_run = {
            "user_message": user_message,
            "user_message_content": user_message_content,
        }
        return {
            "final_response": "ok",
            "messages": [],
            "api_calls": 1,
            "completed": True,
        }


def _install_fake_agent(monkeypatch):
    from run_agent import AIAgent as RealAIAgent
    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = _CapturingAgent
    fake_run_agent.AIAgent._check_native_vision_support = RealAIAgent._check_native_vision_support
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)


def _make_runner(monkeypatch):
    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {}
    runner._ephemeral_system_prompt = ""
    runner._prefill_messages = []
    runner._reasoning_config = None
    runner._service_tier = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._smart_model_routing = {}
    runner._running_agents = {}
    runner._pending_model_notes = {}
    runner._session_db = None
    runner._agent_cache = {}
    runner._agent_cache_lock = asyncio.Lock()
    runner._session_model_overrides = {}
    runner.hooks = SimpleNamespace(loaded_hooks=False, emit=AsyncMock())
    runner.config = SimpleNamespace(streaming=None, get_connected_platforms=lambda: ["telegram"])
    runner.session_store = SimpleNamespace(
        get_or_create_session=lambda source: SimpleNamespace(
            session_id="session-1",
            session_key="agent:main:telegram:dm:12345",
            created_at=0,
            updated_at=0,
        ),
        load_transcript=lambda session_id: [],
        has_any_sessions=lambda: False,
    )
    runner._get_or_create_gateway_honcho = lambda session_key: (None, None)
    runner._enrich_message_with_vision = AsyncMock(return_value="ENRICHED")
    runner._run_agent = AsyncMock(return_value={
        "final_response": "ok",
        "messages": [],
        "api_calls": 1,
    })
    # Avoid deep GatewayConfig method chains
    _src = _make_source()
    monkeypatch.setattr(gateway_run, "build_session_context", lambda *a, **kw: SimpleNamespace(source=_src))
    monkeypatch.setattr(gateway_run, "build_session_context_prompt", lambda *a, **kw: "")
    return runner


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="12345",
        chat_type="dm",
        user_id="user-1",
    )


@pytest.mark.asyncio
async def test_image_passthrough_for_native_vision_model(monkeypatch, tmp_path):
    """Supported models receive base64 image_url parts in message_content."""
    _install_fake_agent(monkeypatch)
    runner = _make_runner(monkeypatch)

    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_env_path", tmp_path / ".env")
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: {})
    monkeypatch.setattr(gateway_run, "_resolve_gateway_model", lambda config=None: "gpt-4o")
    monkeypatch.setattr(
        gateway_run,
        "_resolve_runtime_agent_kwargs",
        lambda: {
            "provider": "openai",
            "api_mode": "chat_completions",
            "base_url": "https://api.openai.com/v1",
            "api_key": "***",
        },
    )
    monkeypatch.setattr(
        runner,
        "_resolve_session_agent_runtime",
        lambda *a, **kw: ("gpt-4o", {
            "provider": "openai",
            "api_mode": "chat_completions",
            "base_url": "https://api.openai.com/v1",
            "api_key": "***",
        }),
    )

    img_path = tmp_path / "test_image.png"
    img_path.write_bytes(b"fake-png-data")

    event = MessageEvent(
        text="describe this",
        source=_make_source(),
        message_id="m1",
        message_type=gateway_run.MessageType.PHOTO,
        media_urls=[str(img_path)],
        media_types=["image/png"],
    )

    await runner._handle_message_with_agent(event, _make_source(), "quick")

    call_kwargs = runner._run_agent.call_args.kwargs
    msg_content = call_kwargs.get("message_content")
    assert msg_content is not None
    assert msg_content[0] == {"type": "text", "text": "describe this"}
    assert msg_content[1]["type"] == "image_url"
    assert "data:image/png;base64," in msg_content[1]["image_url"]["url"]


@pytest.mark.asyncio
async def test_image_fallback_to_vision_enrichment_for_unsupported_model(monkeypatch, tmp_path):
    """Unsupported models fall back to _enrich_message_with_vision."""
    _install_fake_agent(monkeypatch)
    runner = _make_runner(monkeypatch)

    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_env_path", tmp_path / ".env")
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: {})
    monkeypatch.setattr(gateway_run, "_resolve_gateway_model", lambda config=None: "some-model")
    monkeypatch.setattr(
        gateway_run,
        "_resolve_runtime_agent_kwargs",
        lambda: {
            "provider": "custom",
            "api_mode": "chat_completions",
            "base_url": "https://example.com/v1",
            "api_key": "***",
        },
    )
    monkeypatch.setattr(
        runner,
        "_resolve_session_agent_runtime",
        lambda *a, **kw: ("some-model", {
            "provider": "custom",
            "api_mode": "chat_completions",
            "base_url": "https://example.com/v1",
            "api_key": "***",
        }),
    )

    img_path = tmp_path / "test_image.png"
    img_path.write_bytes(b"fake-png-data")

    event = MessageEvent(
        text="describe this",
        source=_make_source(),
        message_id="m1",
        message_type=gateway_run.MessageType.PHOTO,
        media_urls=[str(img_path)],
        media_types=["image/png"],
    )

    await runner._handle_message_with_agent(event, _make_source(), "quick")

    call_kwargs = runner._run_agent.call_args.kwargs
    assert call_kwargs.get("message_content") is None
    assert "ENRICHED" in call_kwargs["message"]
