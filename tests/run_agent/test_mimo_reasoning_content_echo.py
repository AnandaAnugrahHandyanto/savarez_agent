"""Regression tests: MiMo reasoning_content echo-back detection.

MiMo (Xiaomi) thinking-mode models require ``reasoning_content`` to be
echoed back on every assistant turn that carried tool_calls, identical to
the existing DeepSeek / Kimi contract.  Without it the API rejects the
replay with HTTP 400:

    The reasoning_content in the thinking mode must be passed back to the API.

Detection signals: base_url matches ``xiaomimimo.com`` OR ``"mimo"``
appears in the model name.

Refs #24443.
"""
from __future__ import annotations

from run_agent import AIAgent


def _make_agent(provider: str = "", model: str = "", base_url: str = "") -> AIAgent:
    agent = object.__new__(AIAgent)
    agent.provider = provider
    agent.model = model
    agent.base_url = base_url
    agent.verbose_logging = False
    return agent


class TestNeedsMimoToolReasoning:
    def test_mimo_base_url_detected(self):
        agent = _make_agent(base_url="https://api.xiaomimimo.com/v1")
        assert agent._needs_mimo_tool_reasoning() is True

    def test_mimo_in_model_name_detected(self):
        agent = _make_agent(model="mimo-7b-thinking")
        assert agent._needs_mimo_tool_reasoning() is True

    def test_mimo_uppercase_model_name_detected(self):
        agent = _make_agent(model="MiMo-VL-7B-RL")
        assert agent._needs_mimo_tool_reasoning() is True

    def test_unrelated_provider_not_detected(self):
        agent = _make_agent(provider="openai", model="gpt-4o", base_url="https://api.openai.com/v1")
        assert agent._needs_mimo_tool_reasoning() is False

    def test_deepseek_not_detected_as_mimo(self):
        agent = _make_agent(provider="deepseek", base_url="https://api.deepseek.com/v1")
        assert agent._needs_mimo_tool_reasoning() is False


class TestNeedsThinkingReasoningPadIncludesMimo:
    def test_mimo_url_triggers_pad(self):
        agent = _make_agent(base_url="https://api.xiaomimimo.com/v1")
        assert agent._needs_thinking_reasoning_pad() is True

    def test_mimo_model_triggers_pad(self):
        agent = _make_agent(model="mimo-7b")
        assert agent._needs_thinking_reasoning_pad() is True

    def test_unrelated_provider_skips_pad(self):
        agent = _make_agent(provider="anthropic", model="claude-3-5", base_url="https://api.anthropic.com")
        assert agent._needs_thinking_reasoning_pad() is False
