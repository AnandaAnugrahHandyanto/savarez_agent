"""Regression tests for issue #26596 — gateway must honor SOUL.md and
agent.personality from config.yaml instead of always falling back to
DEFAULT_AGENT_IDENTITY.
"""

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import gateway.run as gateway_run
from gateway.config import Platform
from gateway.session import SessionSource


def _make_runner():
    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {}
    runner._ephemeral_system_prompt = ""
    runner._prefill_messages = []
    runner._reasoning_config = None
    runner._session_reasoning_overrides = {}
    runner._show_reasoning = False
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._running_agents = {}
    runner.hooks = MagicMock()
    runner.hooks.emit = AsyncMock()
    runner.hooks.loaded_hooks = []
    runner._session_db = None
    runner._get_or_create_gateway_honcho = lambda session_key: (None, None)
    return runner


class _CapturingAgent:
    last_init = None

    def __init__(self, *args, **kwargs):
        type(self).last_init = dict(kwargs)
        self.tools = []

    def run_conversation(self, user_message: str, conversation_history=None, task_id=None):
        return {"final_response": "ok", "messages": [], "api_calls": 1}


def _install_fake_agent(monkeypatch):
    _CapturingAgent.last_init = None
    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = _CapturingAgent
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)


def _stub_runtime(monkeypatch, hermes_home):
    monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
    monkeypatch.setattr(gateway_run, "_env_path", hermes_home / ".env")
    monkeypatch.setattr(gateway_run, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setattr(
        gateway_run,
        "_resolve_runtime_agent_kwargs",
        lambda: {
            "provider": "openrouter",
            "api_mode": "chat_completions",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "test-key",
        },
    )


def _telegram_source():
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="chat-1",
        chat_name="DM",
        chat_type="dm",
        user_id="user-1",
        user_name="tester",
    )


class TestGatewayPassesSoulIdentity:
    """Bug: gateway never passes load_soul_identity, so AIAgent's default
    False causes DEFAULT_AGENT_IDENTITY to win over SOUL.md."""

    def test_run_agent_passes_load_soul_identity_true(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        (hermes_home / "config.yaml").write_text("", encoding="utf-8")
        _stub_runtime(monkeypatch, hermes_home)
        _install_fake_agent(monkeypatch)

        runner = _make_runner()

        result = asyncio.run(
            runner._run_agent(
                message="who are you",
                context_prompt="",
                history=[],
                source=_telegram_source(),
                session_id="session-1",
                session_key="agent:main:telegram:dm",
            )
        )

        assert result["final_response"] == "ok"
        assert _CapturingAgent.last_init is not None
        assert _CapturingAgent.last_init.get("load_soul_identity") is True


class TestLoadEphemeralSystemPromptPersonality:
    """Bug: agent.personality from config.yaml never reaches the gateway
    ephemeral prompt — only /personality slash commands wire it up."""

    def _load(self, tmp_path, monkeypatch, yaml_body: str) -> str:
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        (hermes_home / "config.yaml").write_text(yaml_body, encoding="utf-8")
        monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
        monkeypatch.delenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", raising=False)
        return gateway_run.GatewayRunner._load_ephemeral_system_prompt()

    def test_named_personality_resolves_at_startup(self, tmp_path, monkeypatch):
        yaml_body = (
            "agent:\n"
            "  personality: pirate\n"
            "  personalities:\n"
            "    pirate: |\n"
            "      Speak like a pirate.\n"
        )
        assert "pirate" in self._load(tmp_path, monkeypatch, yaml_body).lower()

    def test_dict_personality_resolves_system_prompt_field(self, tmp_path, monkeypatch):
        yaml_body = (
            "agent:\n"
            "  personality: scholar\n"
            "  personalities:\n"
            "    scholar:\n"
            "      system_prompt: You are a careful scholar.\n"
            "      tone: formal\n"
        )
        prompt = self._load(tmp_path, monkeypatch, yaml_body)
        assert "careful scholar" in prompt
        assert "formal" in prompt

    def test_explicit_system_prompt_wins_over_personality(self, tmp_path, monkeypatch):
        yaml_body = (
            "agent:\n"
            "  system_prompt: explicit-wins\n"
            "  personality: pirate\n"
            "  personalities:\n"
            "    pirate: arrr\n"
        )
        assert self._load(tmp_path, monkeypatch, yaml_body) == "explicit-wins"

    def test_unknown_personality_falls_back_to_empty(self, tmp_path, monkeypatch):
        yaml_body = (
            "agent:\n"
            "  personality: missing\n"
            "  personalities:\n"
            "    other: noop\n"
        )
        assert self._load(tmp_path, monkeypatch, yaml_body) == ""

    def test_env_var_still_wins(self, tmp_path, monkeypatch):
        yaml_body = (
            "agent:\n"
            "  personality: pirate\n"
            "  personalities:\n"
            "    pirate: arrr\n"
        )
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        (hermes_home / "config.yaml").write_text(yaml_body, encoding="utf-8")
        monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
        monkeypatch.setenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", "from-env")
        assert gateway_run.GatewayRunner._load_ephemeral_system_prompt() == "from-env"


class TestAgentConfigSignatureIncludesSoulFlag:
    """When load_soul_identity flips, cached agents must rebuild — otherwise
    the SOUL.md identity stays invisible until restart."""

    def test_load_soul_identity_changes_signature(self):
        runtime = {"api_key": "k", "base_url": "u", "provider": "p"}
        sig_off = gateway_run.GatewayRunner._agent_config_signature(
            "m", runtime, [], "", load_soul_identity=False,
        )
        sig_on = gateway_run.GatewayRunner._agent_config_signature(
            "m", runtime, [], "", load_soul_identity=True,
        )
        assert sig_off != sig_on

    def test_default_signature_matches_explicit_false(self):
        runtime = {"api_key": "k", "base_url": "u", "provider": "p"}
        sig_default = gateway_run.GatewayRunner._agent_config_signature(
            "m", runtime, [], "",
        )
        sig_off = gateway_run.GatewayRunner._agent_config_signature(
            "m", runtime, [], "", load_soul_identity=False,
        )
        assert sig_default == sig_off
