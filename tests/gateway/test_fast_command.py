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
    last_instance = None

    def __init__(self, *args, **kwargs):
        type(self).last_init = dict(kwargs)
        type(self).last_instance = self
        self.tools = []

    def run_conversation(
        self,
        user_message,
        conversation_history=None,
        task_id=None,
        persist_user_message=None,
        persist_user_timestamp=None,
    ):
        type(self).last_run = {
            "user_message": user_message,
            "conversation_history": conversation_history,
            "task_id": task_id,
            "persist_user_message": persist_user_message,
            "persist_user_timestamp": persist_user_timestamp,
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


def test_turn_route_injects_anthropic_speed_without_latency_rewrite():
    runner = _make_runner()
    runner._service_tier = "priority"
    runtime_kwargs = {
        "api_key": "***",
        "base_url": "https://api.anthropic.com",
        "provider": "anthropic",
        "api_mode": "anthropic_messages",
        "command": None,
        "args": [],
        "credential_pool": None,
    }

    route = gateway_run.GatewayRunner._resolve_turn_agent_config(
        runner,
        "hi",
        "claude-opus-4-6",
        runtime_kwargs,
    )

    assert route["model"] == "claude-opus-4-6"
    assert route["runtime"]["provider"] == "anthropic"
    assert route["request_overrides"] == {"speed": "fast"}


def test_turn_route_keeps_opus_for_short_ack_by_default():
    runner = _make_runner()
    runner._service_tier = None
    credential_pool = SimpleNamespace(name="pool")
    runtime_kwargs = {
        "api_key": "***",
        "base_url": "https://openrouter.ai/api/v1",
        "provider": "openrouter",
        "api_mode": "chat_completions",
        "command": None,
        "args": [],
        "credential_pool": credential_pool,
        "request_overrides": {"extra_headers": {"X-Test": "1"}},
    }

    for message in ("Thanks, sounds good", "네", "확인했습니다", "감사합니다", "안녕하세요"):
        route = gateway_run.GatewayRunner._resolve_turn_agent_config(
            runner,
            message,
            "anthropic/claude-opus-4.7",
            runtime_kwargs,
            platform="telegram",
            bucket_key="gateway-session-1",
        )

        assert route["model"] == "anthropic/claude-opus-4.7"
        assert route["runtime"]["credential_pool"] is credential_pool
        assert route["request_overrides"] == {"extra_headers": {"X-Test": "1"}}
        assert route["route_decision"]["enabled"] is False


def test_turn_route_keeps_opus_for_code_tool_and_kanban_requests():
    runner = _make_runner()
    runner._service_tier = None
    runtime_kwargs = {
        "api_key": "***",
        "base_url": "https://api.anthropic.com",
        "provider": "anthropic",
        "api_mode": "anthropic_messages",
        "command": None,
        "args": [],
        "credential_pool": None,
        "config": {
            "bob": {
                "routing": {
                    "experiment": {
                        "enabled": True,
                        "mode": "ab",
                        "rollout": 1.0,
                        "seed": "gateway-test",
                        "treatment_model": "claude-sonnet-4-6",
                    },
                },
            },
        },
    }

    examples = [
        "Fix the failing pytest in gateway/run.py",
        "Use the terminal tool to inspect the repo",
        "Dispatch this to kanban workers",
        "Research the CI failure and open a PR",
        "코드 수정해줘",
        "칸반 워커 디스패치해줘",
        "CI 실패 분석해줘",
        "네 코드 수정해줘",
        "안녕하세요 CI 실패 분석해줘",
    ]

    for message in examples:
        route = gateway_run.GatewayRunner._resolve_turn_agent_config(
            runner,
            message,
            "claude-opus-4-7",
            runtime_kwargs,
            platform="telegram",
            bucket_key="gateway-session-2",
        )
        assert route["model"] == "claude-opus-4-7"
        assert route["route_decision"]["class"] == "complex"


def test_turn_route_does_not_rewrite_non_opus_model():
    runner = _make_runner()
    runner._service_tier = None
    runtime_kwargs = {
        "api_key": "***",
        "base_url": "https://api.openai.com/v1",
        "provider": "openai",
        "api_mode": "chat_completions",
        "command": None,
        "args": [],
        "credential_pool": None,
    }

    route = gateway_run.GatewayRunner._resolve_turn_agent_config(
        runner,
        "ok",
        "gpt-5.4",
        runtime_kwargs,
    )

    assert route["model"] == "gpt-5.4"


def test_turn_route_shadow_carries_proposed_model_metadata_without_routing():
    runner = _make_runner()
    runner._service_tier = None
    runtime_kwargs = {
        "api_key": "***",
        "base_url": "https://openrouter.ai/api/v1",
        "provider": "openrouter",
        "api_mode": "chat_completions",
        "command": None,
        "args": [],
        "credential_pool": None,
        "config": {
            "bob": {
                "routing": {
                    "experiment": {
                        "enabled": True,
                        "mode": "shadow",
                        "rollout": 1.0,
                        "seed": "gateway-test",
                        "treatment_model": "anthropic/claude-sonnet-4.6",
                        "include_platforms": ["telegram"],
                    },
                },
            },
        },
    }

    route = gateway_run.GatewayRunner._resolve_turn_agent_config(
        runner,
        "hi",
        "anthropic/claude-opus-4.7",
        runtime_kwargs,
        platform="telegram",
        bucket_key="gateway-shadow-session",
    )

    assert route["model"] == "anthropic/claude-opus-4.7"
    assert route["route_decision"]["mode"] == "shadow"
    assert route["route_decision"]["arm"] == "treatment"
    assert route["route_decision"]["class"] == "short_chat"
    assert route["route_decision"]["proposed_model"] == "anthropic/claude-sonnet-4.6"
    assert route["route_decision"]["routed"] is False


def test_turn_route_ab_treatment_routes_short_chat():
    runner = _make_runner()
    runner._service_tier = None
    runtime_kwargs = {
        "api_key": "***",
        "base_url": "https://openrouter.ai/api/v1",
        "provider": "openrouter",
        "api_mode": "chat_completions",
        "command": None,
        "args": [],
        "credential_pool": None,
        "config": {
            "bob": {
                "routing": {
                    "experiment": {
                        "enabled": True,
                        "mode": "ab",
                        "rollout": 1.0,
                        "seed": "gateway-test",
                        "treatment_model": "anthropic/claude-sonnet-4.6",
                    },
                },
            },
        },
    }

    route = gateway_run.GatewayRunner._resolve_turn_agent_config(
        runner,
        "ok",
        "anthropic/claude-opus-4.7",
        runtime_kwargs,
        platform="telegram",
        bucket_key="gateway-treatment-session",
    )

    assert route["model"] == "anthropic/claude-sonnet-4.6"
    assert route["route_decision"]["arm"] == "treatment"
    assert route["route_decision"]["routed"] is True


@pytest.mark.asyncio
async def test_run_agent_passes_route_decision_metadata_to_gateway_agent(monkeypatch, tmp_path):
    _install_fake_agent(monkeypatch)
    runner = _make_runner()

    user_config = {
        "bob": {
            "routing": {
                "experiment": {
                    "enabled": True,
                    "mode": "shadow",
                    "rollout": 1.0,
                    "seed": "gateway-test",
                    "treatment_model": "anthropic/claude-sonnet-4.6",
                    "include_platforms": ["telegram"],
                },
            },
        },
    }
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_env_path", tmp_path / ".env")
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: user_config)
    monkeypatch.setattr(gateway_run, "_load_gateway_runtime_config", lambda: user_config)
    monkeypatch.setattr(gateway_run, "_resolve_gateway_model", lambda config=None: "anthropic/claude-opus-4.7")
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
    assert _CapturingAgent.last_init is not None
    assert _CapturingAgent.last_init["model"] == "anthropic/claude-opus-4.7"
    assert _CapturingAgent.last_instance is not None
    turn_route = _CapturingAgent.last_instance.turn_route_decision
    assert turn_route["mode"] == "shadow"
    assert turn_route["proposed_model"] == "anthropic/claude-sonnet-4.6"


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
    # ``_load_service_tier`` was refactored to call ``_load_gateway_runtime_config``
    # (which wraps ``_load_gateway_config`` plus env-expansion).  Since the test
    # stubs ``_load_gateway_config`` to ``{}``, also stub the runtime wrapper
    # directly so the priority routing assertions still exercise the live tier.
    monkeypatch.setattr(
        gateway_run,
        "_load_gateway_runtime_config",
        lambda: {"agent": {"service_tier": "fast"}},
    )
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
    assert _CapturingAgent.last_init is not None
    assert _CapturingAgent.last_init["service_tier"] == "priority"
    assert _CapturingAgent.last_init["request_overrides"] == {"service_tier": "priority"}
