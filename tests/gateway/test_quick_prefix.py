"""Quick prefix routing tests for gateway fast chat mode."""

from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import threading

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.hooks import HookRegistry
from gateway.run import (
    GatewayRunner,
    _build_quick_chat_prompt,
    _detect_quick_chat_prefix,
    _format_quick_search_context,
    _resolve_quick_chat_settings,
)
from gateway.session import SessionSource


def test_detect_plain_quick_chat_prefix_strips_bang():
    parsed = _detect_quick_chat_prefix("!호주의 수도가 어디야?")

    assert parsed.enabled is True
    assert parsed.force_search is False
    assert parsed.message == "호주의 수도가 어디야?"


def test_detect_plain_quick_chat_prefix_after_slack_sender_marker():
    parsed = _detect_quick_chat_prefix("[DS] !호주의 수도가 어디야?")

    assert parsed.enabled is True
    assert parsed.force_search is False
    assert parsed.message == "호주의 수도가 어디야?"


def test_detect_search_quick_chat_prefix_after_slack_sender_marker():
    parsed = _detect_quick_chat_prefix("[DS] !?호주 Perth의 인구는 어떻게 돼?")

    assert parsed.enabled is True
    assert parsed.force_search is True
    assert parsed.message == "호주 Perth의 인구는 어떻게 돼?"


def test_detect_search_quick_chat_prefix_strips_bang_question():
    quick = _detect_quick_chat_prefix("!? 최신 OpenAI Codex 모델 목록")

    assert quick.enabled is True
    assert quick.force_search is True
    assert quick.message == "최신 OpenAI Codex 모델 목록"


def test_detect_quick_prefix_can_be_disabled_by_config():
    quick = _detect_quick_chat_prefix(
        "!literal exclamation",
        user_config={"quick_chat": {"enabled": False}},
    )

    assert quick.enabled is False
    assert quick.message == "!literal exclamation"


def test_quick_settings_default_to_codex_mini_on_openai_codex():
    settings = _resolve_quick_chat_settings(
        {},
        provider="openai-codex",
        current_model="gpt-5.5",
    )

    assert settings.model == "gpt-5.4-mini"
    assert settings.enabled_toolsets == ["quick_chat"]
    assert settings.max_iterations == 3
    assert settings.skip_memory is True
    assert settings.skip_context_files is True


def test_quick_settings_inherit_model_outside_openai_codex_without_configured_model():
    settings = _resolve_quick_chat_settings(
        {},
        provider="anthropic",
        current_model="claude-sonnet-4.5",
    )

    assert settings.model == "claude-sonnet-4.5"


def test_quick_prompt_prioritizes_search_for_bang_question():
    prompt = _build_quick_chat_prompt(force_search=True)

    assert "quick chat mode" in prompt.lower()
    assert "web_search" in prompt
    assert "already run" in prompt.lower()
    assert "side-effect" in prompt.lower()


def test_quick_prompt_disables_tools_for_plain_bang():
    prompt = _build_quick_chat_prompt(force_search=False)

    assert "No tools are available" in prompt
    assert "without tool calls" in prompt


@pytest.mark.asyncio
async def test_run_agent_quick_prefix_uses_stateless_mini_agent(monkeypatch):
    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs
            self.model = kwargs.get("model")
            self.session_id = kwargs.get("session_id")
            self.context_compressor = SimpleNamespace(
                last_prompt_tokens=0,
                context_length=0,
            )
            self.session_prompt_tokens = 0
            self.session_completion_tokens = 0
            self.tools = []
            self.is_interrupted = False

        def run_conversation(self, message, **kwargs):
            captured["message"] = message
            captured["conversation_kwargs"] = kwargs
            return {
                "final_response": "캔버라입니다.",
                "messages": [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": "캔버라입니다."},
                ],
                "api_calls": 1,
                "completed": True,
            }

        def interrupt(self, *_args, **_kwargs):
            self.is_interrupted = True

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.SLACK: PlatformConfig(enabled=True, token="x")},
    )
    runner.adapters = {}
    runner.hooks = HookRegistry()
    runner._ephemeral_system_prompt = "HEAVY PROMPT SHOULD NOT BE INCLUDED"
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._agent_cache = OrderedDict()
    runner._agent_cache_lock = threading.Lock()
    runner._running_agents = {}
    runner._draining = False
    runner._session_db = None
    runner.session_store = MagicMock()
    runner.session_store._entries = {}
    runner._prefill_messages = [
        {"role": "assistant", "content": "prefill should not be included"},
    ]
    runner._service_tier = None
    runner._show_reasoning = False
    runner._reasoning_config = None
    runner._get_proxy_url = lambda: None
    runner._resolve_session_agent_runtime = lambda **_kw: (
        "gpt-5.5",
        {
            "api_key": "k",
            "provider": "openai-codex",
            "base_url": None,
            "api_mode": None,
        },
    )
    runner._resolve_session_reasoning_config = lambda **_kw: None
    runner._load_service_tier = lambda: None
    runner._extract_cache_busting_config = lambda _cfg: {}
    runner._is_session_run_current = lambda _key, _gen: True
    runner._consume_pending_native_image_paths = lambda _key: []
    runner._thread_metadata_for_source = lambda _source, event_message_id=None: None
    runner._enforce_agent_cache_cap = lambda: None
    runner._init_cached_agent_for_turn = lambda _agent, _depth: None

    source = SessionSource(
        platform=Platform.SLACK,
        user_id="u",
        chat_id="c",
        user_name="tester",
        chat_type="dm",
    )

    monkeypatch.setattr("gateway.run._load_gateway_config", lambda: {})
    monkeypatch.setattr("gateway.run._reload_runtime_env_preserving_config_authority", lambda: None)
    with patch("run_agent.AIAgent", FakeAgent):
        result = await runner._run_agent(
            "[DS] !호주의 수도가 어디야?",
            "",
            [{"role": "user", "content": "old history should not be included"}],
            source,
            session_id="sess",
            session_key="sk",
        )

    assert result["final_response"] == "캔버라입니다."
    assert captured["message"] == "호주의 수도가 어디야?"
    assert captured["kwargs"]["model"] == "gpt-5.4-mini"
    assert captured["kwargs"]["enabled_toolsets"] == []
    assert captured["kwargs"]["max_iterations"] == 3
    assert captured["kwargs"]["max_tokens"] == 700
    assert captured["kwargs"]["skip_memory"] is True
    assert captured["kwargs"]["skip_context_files"] is True
    assert captured["kwargs"]["prefill_messages"] is None
    assert "HEAVY PROMPT" not in captured["kwargs"]["ephemeral_system_prompt"]


def test_format_quick_search_context_extracts_structured_web_results():
    context = _format_quick_search_context(
        "호주 Perth 인구",
        '{"data":{"web":[{"title":"Perth population","url":"https://example.com/perth","description":"Greater Perth population estimate"}]}}',
    )

    assert "real web_search call was executed" in context
    assert "호주 Perth 인구" in context
    assert "Perth population" in context
    assert "https://example.com/perth" in context


@pytest.mark.asyncio
async def test_run_agent_search_quick_prefix_prefetches_web_search(monkeypatch):
    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs
            self.model = kwargs.get("model")
            self.session_id = kwargs.get("session_id")
            self.context_compressor = SimpleNamespace(
                last_prompt_tokens=0,
                context_length=0,
            )
            self.session_prompt_tokens = 0
            self.session_completion_tokens = 0
            self.tools = []
            self.is_interrupted = False

        def run_conversation(self, message, **kwargs):
            captured["message"] = message
            captured["conversation_kwargs"] = kwargs
            captured["tool_progress_callback"] = getattr(self, "tool_progress_callback", None)
            captured["ephemeral_system_prompt"] = self.__dict__.get("ephemeral_system_prompt") or captured["kwargs"].get("ephemeral_system_prompt")
            return {
                "final_response": "Greater Perth는 약 230만 명대입니다.",
                "messages": [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": "Greater Perth는 약 230만 명대입니다."},
                ],
                "api_calls": 1,
                "completed": True,
            }

        def interrupt(self, *_args, **_kwargs):
            self.is_interrupted = True

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.SLACK: PlatformConfig(enabled=True, token="x")},
    )
    runner.adapters = {}
    runner.hooks = HookRegistry()
    runner._ephemeral_system_prompt = "HEAVY PROMPT SHOULD NOT BE INCLUDED"
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._agent_cache = OrderedDict()
    runner._agent_cache_lock = threading.Lock()
    runner._running_agents = {}
    runner._draining = False
    runner._session_db = None
    runner.session_store = MagicMock()
    runner.session_store._entries = {}
    runner._prefill_messages = []
    runner._service_tier = None
    runner._show_reasoning = False
    runner._reasoning_config = None
    runner._get_proxy_url = lambda: None
    runner._resolve_session_agent_runtime = lambda **_kw: (
        "gpt-5.5",
        {
            "api_key": "k",
            "provider": "openai-codex",
            "base_url": None,
            "api_mode": None,
        },
    )
    runner._resolve_session_reasoning_config = lambda **_kw: None
    runner._load_service_tier = lambda: None
    runner._extract_cache_busting_config = lambda _cfg: {}
    runner._is_session_run_current = lambda _key, _gen: True
    runner._consume_pending_native_image_paths = lambda _key: []
    runner._thread_metadata_for_source = lambda _source, event_message_id=None: None
    runner._enforce_agent_cache_cap = lambda: None
    runner._init_cached_agent_for_turn = lambda _agent, _depth: None

    source = SessionSource(
        platform=Platform.SLACK,
        user_id="u",
        chat_id="c",
        user_name="tester",
        chat_type="dm",
    )

    search_result = '{"data":{"web":[{"title":"Perth population","url":"https://example.com/perth","description":"Greater Perth has about 2.3 million people."}]}}'
    monkeypatch.setattr(
        "gateway.run._load_gateway_config",
        lambda: {"display": {"platforms": {"slack": {"tool_progress": "new"}}}},
    )
    monkeypatch.setattr("gateway.run._reload_runtime_env_preserving_config_authority", lambda: None)
    with patch("run_agent.AIAgent", FakeAgent), patch(
        "tools.web_tools.web_search_tool",
        return_value=search_result,
    ) as mock_search:
        result = await runner._run_agent(
            "[DS] !?호주 Perth의 인구는 어떻게 돼?",
            "",
            [{"role": "user", "content": "old history should not be included"}],
            source,
            session_id="sess",
            session_key="sk",
        )

    assert result["final_response"] == "Greater Perth는 약 230만 명대입니다."
    mock_search.assert_called_once_with("호주 Perth의 인구는 어떻게 돼?", limit=5)
    assert captured["message"] == "호주 Perth의 인구는 어떻게 돼?"
    assert captured["kwargs"]["model"] == "gpt-5.4-mini"
    assert captured["kwargs"]["enabled_toolsets"] == ["quick_chat"]
    assert captured["kwargs"]["skip_memory"] is True
    assert captured["kwargs"]["skip_context_files"] is True
    assert captured["tool_progress_callback"] is not None
    assert "Gateway quick-search context" in captured["ephemeral_system_prompt"]
    assert "Perth population" in captured["ephemeral_system_prompt"]
    assert captured["conversation_kwargs"]["conversation_history"] == []
