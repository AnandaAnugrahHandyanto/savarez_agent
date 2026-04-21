"""Tests for gateway /fast support and Priority Processing routing."""

import logging
import sys
import threading
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import yaml

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

    def run_conversation(self, user_message, conversation_history=None, task_id=None, persist_user_message=None):
        type(self).last_run = {
            "user_message": user_message,
            "conversation_history": conversation_history,
            "task_id": task_id,
            "persist_user_message": persist_user_message,
        }
        return {
            "final_response": "ok",
            "messages": [],
            "api_calls": 1,
            "completed": True,
        }


def _install_fake_agent(monkeypatch):
    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = _CapturingAgent
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)


def _make_runner():
    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {}
    runner._ephemeral_system_prompt = ""
    runner._prefill_messages = []
    runner._reasoning_config = None
    runner._service_tier = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._smart_model_routing = {}
    runner._gateway_model_routing = {}
    runner._running_agents = {}
    runner._pending_model_notes = {}
    runner._session_db = None
    runner._agent_cache = {}
    runner._agent_cache_lock = threading.Lock()
    runner._session_model_overrides = {}
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


def _make_event(text: str) -> MessageEvent:
    return MessageEvent(text=text, source=_make_source(), message_id="m1")


def test_turn_route_injects_priority_processing_without_changing_runtime():
    runner = _make_runner()
    runner._service_tier = "priority"
    runtime_kwargs = {
        "api_key": "***",
        "base_url": "https://openrouter.ai/api/v1",
        "provider": "openrouter",
        "api_mode": "chat_completions",
        "command": None,
        "args": [],
        "credential_pool": None,
    }

    with patch("agent.smart_model_routing.resolve_turn_route", return_value={
        "model": "gpt-5.4",
        "runtime": dict(runtime_kwargs),
        "label": None,
        "signature": ("gpt-5.4", "openrouter", "https://openrouter.ai/api/v1", "chat_completions", None, ()),
    }):
        route = gateway_run.GatewayRunner._resolve_turn_agent_config(runner, "hi", "gpt-5.4", runtime_kwargs)

    assert route["runtime"]["provider"] == "openrouter"
    assert route["runtime"]["api_mode"] == "chat_completions"
    assert route["request_overrides"] == {"service_tier": "priority"}


def test_turn_route_skips_priority_processing_for_unsupported_models():
    runner = _make_runner()
    runner._service_tier = "priority"
    runtime_kwargs = {
        "api_key": "***",
        "base_url": "https://openrouter.ai/api/v1",
        "provider": "openrouter",
        "api_mode": "chat_completions",
        "command": None,
        "args": [],
        "credential_pool": None,
    }

    with patch("agent.smart_model_routing.resolve_turn_route", return_value={
        "model": "gpt-5.3-codex",
        "runtime": dict(runtime_kwargs),
        "label": None,
        "signature": ("gpt-5.3-codex", "openrouter", "https://openrouter.ai/api/v1", "chat_completions", None, ()),
    }):
        route = gateway_run.GatewayRunner._resolve_turn_agent_config(runner, "hi", "gpt-5.3-codex", runtime_kwargs)

    assert route["request_overrides"] is None
    assert route["routing_reason"] == "default"


def test_turn_route_escalates_complex_telegram_prompt_to_strong_model(caplog):
    runner = _make_runner()
    runner._gateway_model_routing = {
        "enabled": True,
        "platforms": ["telegram", "slack"],
        "strong_model": {"provider": "openai-codex", "model": "gpt-5.4"},
    }
    runtime_kwargs = {
        "api_key": "gemini-key",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "provider": "openrouter",
        "api_mode": "chat_completions",
        "command": None,
        "args": [],
        "credential_pool": None,
    }
    source = _make_source()

    with caplog.at_level(logging.INFO, logger="gateway.run"), patch("hermes_cli.runtime_provider.resolve_runtime_provider", return_value={
        "api_key": "***",
        "base_url": "https://chatgpt.com/backend-api/codex",
        "provider": "codex",
        "api_mode": "responses",
        "command": None,
        "args": [],
        "credential_pool": None,
    }):
        route = gateway_run.GatewayRunner._resolve_turn_agent_config(
            runner,
            "debug this traceback please",
            "google/gemini-2.5-flash",
            runtime_kwargs,
            source=source,
        )

    assert route["model"] == "gpt-5.4"
    assert route["runtime"]["provider"] == "codex"
    assert route["routing_reason"] == "gateway_complex_turn"
    assert "Gateway turn route:" in caplog.text
    assert "effective_model=gpt-5.4" in caplog.text
    assert "reason=gateway_complex_turn" in caplog.text


def test_turn_route_keeps_explicit_session_override_ahead_of_auto_escalation(caplog):
    runner = _make_runner()
    runner._gateway_model_routing = {
        "enabled": True,
        "platforms": ["telegram", "slack"],
        "strong_model": {"provider": "openai-codex", "model": "gpt-5.4"},
    }
    source = _make_source()
    session_key = runner._session_key_for_source(source)
    runner._session_model_overrides[session_key] = {
        "model": "manual/model",
        "provider": "openrouter",
    }
    runtime_kwargs = {
        "api_key": "manual-key",
        "base_url": "https://openrouter.ai/api/v1",
        "provider": "openrouter",
        "api_mode": "chat_completions",
        "command": None,
        "args": [],
        "credential_pool": None,
    }

    with caplog.at_level(logging.INFO, logger="gateway.run"):
        route = gateway_run.GatewayRunner._resolve_turn_agent_config(
            runner,
            "debug this traceback please",
            "manual/model",
            runtime_kwargs,
            source=source,
        )

    assert route["model"] == "manual/model"
    assert route["runtime"]["provider"] == "openrouter"
    assert route["routing_reason"] == "session_override"
    assert "effective_model=manual/model" in caplog.text
    assert "reason=session_override" in caplog.text


@pytest.mark.asyncio
async def test_handle_fast_command_persists_config(monkeypatch, tmp_path):
    runner = _make_runner()

    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: {})
    monkeypatch.setattr(gateway_run, "_resolve_gateway_model", lambda config=None: "gpt-5.4")

    response = await runner._handle_fast_command(_make_event("/fast fast"))

    assert "FAST" in response
    assert runner._service_tier == "priority"

    saved = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert saved["agent"]["service_tier"] == "fast"


@pytest.mark.asyncio
async def test_run_agent_passes_priority_processing_to_gateway_agent(monkeypatch, tmp_path):
    _install_fake_agent(monkeypatch)
    runner = _make_runner()

    (tmp_path / "config.yaml").write_text("agent:\n  service_tier: fast\n", encoding="utf-8")
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_env_path", tmp_path / ".env")
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: {})
    monkeypatch.setattr(gateway_run, "_resolve_gateway_model", lambda config=None: "gpt-5.4")
    monkeypatch.setattr(
        gateway_run,
        "_resolve_runtime_agent_kwargs",
        lambda: {
            "provider": "openrouter",
            "api_mode": "chat_completions",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "***",
        },
    )

    import hermes_cli.tools_config as tools_config
    monkeypatch.setattr(tools_config, "_get_platform_tools", lambda user_config, platform_key: {"core"})

    _CapturingAgent.last_init = None
    result = await runner._run_agent(
        message="hi",
        context_prompt="",
        history=[],
        source=_make_source(),
        session_id="session-1",
        session_key="agent:main:telegram:dm:12345",
    )

    assert result["final_response"] == "ok"
    assert _CapturingAgent.last_init["service_tier"] == "priority"
    assert _CapturingAgent.last_init["request_overrides"] == {"service_tier": "priority"}
