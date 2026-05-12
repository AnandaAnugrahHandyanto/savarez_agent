"""Tests for gateway /fast support and Priority Processing routing."""

import sys
import threading
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

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

    route = gateway_run.GatewayRunner._resolve_turn_agent_config(runner, "hi", "gpt-5.3-codex", runtime_kwargs)

    assert route["request_overrides"] == {}


def test_turn_route_uses_configured_simple_model_for_short_chat():
    runner = _make_runner()
    runner._smart_model_routing = {
        "enabled": True,
        "max_simple_chars": 160,
        "max_simple_words": 28,
        "cheap_model": {"model": "mlx-community/Qwen3.5-4B-MLX-4bit"},
    }
    runtime_kwargs = {
        "api_key": "***",
        "base_url": "http://localhost:8080/v1",
        "provider": "custom",
        "api_mode": "chat_completions",
        "command": None,
        "args": [],
        "credential_pool": None,
    }

    route = gateway_run.GatewayRunner._resolve_turn_agent_config(
        runner,
        "is it my turn?",
        "mlx-community/Qwen3.6-35B-A3B-nvfp4",
        runtime_kwargs,
    )

    assert route["model"] == "mlx-community/Qwen3.5-4B-MLX-4bit"
    assert route["runtime"]["base_url"] == "http://localhost:8080/v1"
    assert route["smart_model_route"] == "simple"


def test_topic_model_config_uses_custom_provider_runtime():
    model, runtime = gateway_run.GatewayRunner._apply_topic_model_config(
        "large-model",
        {"provider": "custom", "base_url": "http://old/v1", "api_mode": "chat_completions"},
        {
            "custom_providers": [
                {
                    "name": "mlx-vlm",
                    "base_url": "http://localhost:8080/v1",
                    "api_key": "mlx-local",
                    "api_mode": "chat_completions",
                }
            ]
        },
        {
            "provider": "mlx-vlm",
            "model": "mlx-community/Qwen3.5-4B-MLX-4bit",
        },
    )

    assert model == "mlx-community/Qwen3.5-4B-MLX-4bit"
    assert runtime["provider"] == "mlx-vlm"
    assert runtime["base_url"] == "http://localhost:8080/v1"
    assert runtime["api_key"] == "mlx-local"


def test_topic_model_config_resolves_builtin_provider_runtime(monkeypatch):
    def _fake_resolve_runtime_provider(**kwargs):
        assert kwargs["requested"] == "anthropic"
        assert kwargs["target_model"] == "claude-opus-4-6"
        return {
            "provider": "anthropic",
            "base_url": "https://api.anthropic.com",
            "api_key": "anthropic-key",
            "api_mode": "anthropic_messages",
            "command": None,
            "args": [],
            "credential_pool": None,
        }

    monkeypatch.setattr(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        _fake_resolve_runtime_provider,
    )

    model, runtime = gateway_run.GatewayRunner._apply_topic_model_config(
        "global-model",
        {
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "openrouter-key",
            "api_mode": "chat_completions",
        },
        {},
        {"provider": "anthropic", "model": "claude-opus-4-6"},
    )

    assert model == "claude-opus-4-6"
    assert runtime["provider"] == "anthropic"
    assert runtime["base_url"] == "https://api.anthropic.com"
    assert runtime["api_key"] == "anthropic-key"
    assert runtime["api_mode"] == "anthropic_messages"


def test_topic_toolsets_override_platform_defaults():
    enabled = gateway_run.GatewayRunner._resolve_topic_toolsets(
        {
            "platform_toolsets": {"telegram": ["hermes-telegram"]},
            "mcp_servers": {
                "github": {"enabled": True},
                "sqlite-state": {"enabled": True},
            },
        },
        "telegram",
        {"toolsets": ["memory", "session_search", "no_mcp"]},
    )

    assert enabled == ["memory", "session_search"]


def test_turn_route_preserves_topic_runtime_token_budget():
    runner = _make_runner()
    runtime_kwargs = {
        "api_key": "***",
        "base_url": "http://localhost:8082/v1",
        "provider": "mlx-vlm-small",
        "api_mode": "chat_completions",
        "command": None,
        "args": [],
        "credential_pool": None,
        "max_tokens": 512,
    }

    route = gateway_run.GatewayRunner._resolve_turn_agent_config(
        runner,
        "tell me a short joke",
        "mlx-community/Qwen3.5-4B-MLX-4bit",
        runtime_kwargs,
    )

    assert route["runtime"]["max_tokens"] == 512
    assert route["signature"][-1] == 512


def test_turn_route_ignores_malformed_smart_routing_thresholds():
    runner = _make_runner()
    runner._smart_model_routing = {
        "enabled": True,
        "max_simple_chars": "short",
        "max_simple_words": "few",
        "cheap_model": {"model": "cheap-model"},
    }
    runtime_kwargs = {
        "api_key": "***",
        "base_url": "http://localhost:8080/v1",
        "provider": "custom",
        "api_mode": "chat_completions",
        "command": None,
        "args": [],
        "credential_pool": None,
    }

    route = gateway_run.GatewayRunner._resolve_turn_agent_config(
        runner,
        "quick thought?",
        "large-model",
        runtime_kwargs,
    )

    assert route["model"] == "cheap-model"
    assert route["smart_model_route"] == "simple"


def test_session_model_override_wins_over_topic_runtime(monkeypatch):
    runner = _make_runner()
    runner._session_model_overrides["topic-session"] = {
        "model": "large-model",
        "provider": "mlx-vlm-large",
        "api_key": "large-key",
        "base_url": "http://localhost:8080/v1",
        "api_mode": "chat_completions",
    }
    monkeypatch.setattr(
        gateway_run,
        "_resolve_runtime_agent_kwargs",
        lambda: {
            "provider": "global",
            "api_mode": "chat_completions",
            "base_url": "http://global/v1",
            "api_key": "global-key",
            "args": [],
            "command": None,
            "credential_pool": None,
        },
    )

    model, runtime = runner._resolve_effective_agent_runtime(
        session_key="topic-session",
        user_config={
            "custom_providers": [
                {
                    "name": "mlx-vlm-small",
                    "base_url": "http://localhost:8082/v1",
                    "api_key": "small-key",
                    "api_mode": "chat_completions",
                    "max_tokens": 512,
                }
            ]
        },
        topic_config={"provider": "mlx-vlm-small", "model": "small-model"},
    )

    assert model == "large-model"
    assert runtime["provider"] == "mlx-vlm-large"
    assert runtime["base_url"] == "http://localhost:8080/v1"
    assert "max_tokens" not in runtime


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
async def test_footer_status_does_not_toggle_config(monkeypatch, tmp_path):
    runner = _make_runner()
    config = {"display": {"runtime_footer": {"enabled": False}}}

    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: config)

    response = await runner._handle_footer_command(_make_event("/footer status"))

    assert "Runtime footer: **OFF**" in response
    assert not (tmp_path / "config.yaml").exists()


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
