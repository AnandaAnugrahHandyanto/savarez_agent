"""Regression test: Xiaomi MiMo thinking mode reasoning_content echo (#24443).

MiMo's OpenAI-compatible API requires clients to echo back ``reasoning_content``
when continuing a conversation in thinking mode.  Hermes must preserve the field
in conversation history and include it in subsequent requests — identical to the
behaviour already implemented for DeepSeek (#15250) and Kimi (#17400).

Fix covers three paths:

1. ``_needs_mimo_tool_reasoning()`` — new detector that matches on provider id
   ``"xiaomi"``, ``xiaomimimo.com`` base-URL host, or model prefix
   ``"xiaomi/"`` / ``"mimo-"``.
2. ``_needs_thinking_reasoning_pad()`` — ORs in the new detector so all
   downstream branches (``_build_assistant_message`` pad, stale-placeholder
   upgrade, cross-provider leak guard) activate for MiMo automatically.
3. ``_copy_reasoning_content_for_api`` — existing tiers now also fire for MiMo:
   stale ``""`` → ``" "`` upgrade, cross-provider leak guard, unconditional pad.

Refs #24443.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from run_agent import AIAgent


def _make_agent(provider: str = "", model: str = "", base_url: str = "") -> AIAgent:
    agent = object.__new__(AIAgent)
    agent.provider = provider
    agent.model = model
    agent.base_url = base_url
    agent.verbose_logging = False
    agent.reasoning_callback = None
    agent.stream_delta_callback = None
    agent._stream_callback = None
    return agent


_ATTR_ABSENT = object()
_EXPECT_NOT_PRESENT = object()


def _sdk_tool_call(call_id: str = "c1", name: str = "terminal", arguments: str = "{}"):
    return SimpleNamespace(
        id=call_id,
        call_id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
        extra_content=None,
    )


def _build_sdk_message(reasoning_content=_ATTR_ABSENT, **extra):
    kwargs = {"content": "", **extra}
    if reasoning_content is not _ATTR_ABSENT:
        kwargs["reasoning_content"] = reasoning_content
    return SimpleNamespace(**kwargs)


class TestNeedsMimoToolReasoning:
    """_needs_mimo_tool_reasoning() recognises all three detection signals."""

    def test_provider_xiaomi(self) -> None:
        agent = _make_agent(provider="xiaomi", model="mimo-v2.5-pro")
        assert agent._needs_mimo_tool_reasoning() is True

    def test_model_xiaomi_prefix(self) -> None:
        agent = _make_agent(provider="custom", model="xiaomi/mimo-v2.5-pro")
        assert agent._needs_mimo_tool_reasoning() is True

    def test_model_mimo_prefix(self) -> None:
        agent = _make_agent(provider="custom", model="mimo-v2-pro")
        assert agent._needs_mimo_tool_reasoning() is True

    def test_model_mimo_flash(self) -> None:
        agent = _make_agent(provider="custom", model="mimo-v2-flash")
        assert agent._needs_mimo_tool_reasoning() is True

    def test_base_url_host(self) -> None:
        agent = _make_agent(
            provider="custom",
            model="some-model",
            base_url="https://api.xiaomimimo.com/v1",
        )
        assert agent._needs_mimo_tool_reasoning() is True

    def test_provider_case_insensitive(self) -> None:
        agent = _make_agent(provider="Xiaomi", model="mimo-v2.5")
        assert agent._needs_mimo_tool_reasoning() is True

    def test_model_case_insensitive(self) -> None:
        agent = _make_agent(provider="custom", model="MIMO-v2-pro")
        assert agent._needs_mimo_tool_reasoning() is True

    def test_non_mimo_provider(self) -> None:
        agent = _make_agent(
            provider="openrouter",
            model="anthropic/claude-sonnet-4.6",
            base_url="https://openrouter.ai/api/v1",
        )
        assert agent._needs_mimo_tool_reasoning() is False

    def test_empty_everything(self) -> None:
        agent = _make_agent()
        assert agent._needs_mimo_tool_reasoning() is False

    def test_model_containing_mimo_substring_not_prefix(self) -> None:
        """Only prefix match — 'not-mimo-model' must not trigger."""
        agent = _make_agent(provider="custom", model="not-mimo-model")
        assert agent._needs_mimo_tool_reasoning() is False


class TestNeedsThinkingReasoningPadIncludesMimo:
    """_needs_thinking_reasoning_pad() activates for MiMo."""

    def test_mimo_provider_activates_pad(self) -> None:
        agent = _make_agent(provider="xiaomi", model="mimo-v2.5-pro")
        assert agent._needs_thinking_reasoning_pad() is True

    def test_mimo_base_url_activates_pad(self) -> None:
        agent = _make_agent(
            provider="custom", model="mimo-v2-pro",
            base_url="https://api.xiaomimimo.com/v1",
        )
        assert agent._needs_thinking_reasoning_pad() is True

    def test_deepseek_still_activates(self) -> None:
        agent = _make_agent(provider="deepseek", model="deepseek-v4-flash")
        assert agent._needs_thinking_reasoning_pad() is True

    def test_kimi_still_activates(self) -> None:
        agent = _make_agent(provider="kimi-coding", model="kimi-k2.6")
        assert agent._needs_thinking_reasoning_pad() is True

    def test_unrelated_provider_off(self) -> None:
        agent = _make_agent(
            provider="openrouter",
            model="anthropic/claude-sonnet-4.6",
            base_url="https://openrouter.ai/api/v1",
        )
        assert agent._needs_thinking_reasoning_pad() is False


class TestCopyReasoningContentForApiMimo:
    """_copy_reasoning_content_for_api applies all four tiers for MiMo."""

    def test_mimo_tool_call_poisoned_history_gets_space_placeholder(self) -> None:
        agent = _make_agent(provider="xiaomi", model="mimo-v2.5-pro")
        source = {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "c1", "function": {"name": "terminal"}}],
        }
        api_msg: dict = {}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert api_msg.get("reasoning_content") == " "

    def test_mimo_assistant_no_tool_call_gets_padded(self) -> None:
        agent = _make_agent(provider="xiaomi", model="mimo-v2.5-pro")
        source = {"role": "assistant", "content": "hello"}
        api_msg: dict = {}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert api_msg.get("reasoning_content") == " "

    def test_mimo_explicit_reasoning_content_preserved(self) -> None:
        agent = _make_agent(provider="xiaomi", model="mimo-v2.5-pro")
        source = {
            "role": "assistant",
            "reasoning_content": "<think>MiMo chain of thought</think>",
            "tool_calls": [{"id": "c1", "function": {"name": "terminal"}}],
        }
        api_msg: dict = {}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert api_msg["reasoning_content"] == "<think>MiMo chain of thought</think>"

    def test_mimo_stale_empty_placeholder_upgraded_to_space(self) -> None:
        agent = _make_agent(provider="xiaomi", model="mimo-v2.5-pro")
        source = {
            "role": "assistant",
            "content": "",
            "reasoning_content": "",
            "tool_calls": [{"id": "c1", "function": {"name": "terminal"}}],
        }
        api_msg: dict = {}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert api_msg["reasoning_content"] == " "

    def test_mimo_cross_provider_history_padded(self) -> None:
        """Cross-provider tool-call: prior provider's 'reasoning' must not leak."""
        agent = _make_agent(provider="xiaomi", model="mimo-v2.5-pro")
        source = {
            "role": "assistant",
            "content": "",
            "reasoning": "chain of thought from a different provider",
            "tool_calls": [{"id": "c1", "function": {"name": "terminal"}}],
        }
        api_msg: dict = {}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert api_msg["reasoning_content"] == " "

    def test_mimo_base_url_match(self) -> None:
        agent = _make_agent(
            provider="custom", model="mimo-v2-pro",
            base_url="https://api.xiaomimimo.com/v1",
        )
        source = {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "c1", "function": {"name": "terminal"}}],
        }
        api_msg: dict = {}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert api_msg.get("reasoning_content") == " "

    def test_non_mimo_provider_not_padded(self) -> None:
        agent = _make_agent(
            provider="openrouter",
            model="anthropic/claude-sonnet-4.6",
            base_url="https://openrouter.ai/api/v1",
        )
        source = {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "c1", "function": {"name": "terminal"}}],
        }
        api_msg: dict = {}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert "reasoning_content" not in api_msg


class TestBuildAssistantMessageMimo:
    """_build_assistant_message pins replay-safe MiMo tool-call state."""

    @pytest.mark.parametrize(
        "provider,model,base_url,sdk_reasoning_content,expected",
        [
            pytest.param(
                "xiaomi", "mimo-v2.5-pro", "",
                None, " ",
                id="xiaomi-provider-attr-none",
            ),
            pytest.param(
                "xiaomi", "mimo-v2.5-pro", "",
                _ATTR_ABSENT, " ",
                id="xiaomi-provider-attr-absent",
            ),
            pytest.param(
                "custom", "mimo-v2-pro", "",
                _ATTR_ABSENT, " ",
                id="mimo-model-prefix",
            ),
            pytest.param(
                "custom", "xiaomi/mimo-v2.5-pro", "",
                _ATTR_ABSENT, " ",
                id="xiaomi-model-prefix",
            ),
            pytest.param(
                "custom", "mimo-v2-pro", "https://api.xiaomimimo.com/v1",
                _ATTR_ABSENT, " ",
                id="mimo-base-url",
            ),
            pytest.param(
                "openrouter", "anthropic/claude-sonnet-4.6", "https://openrouter.ai/api/v1",
                _ATTR_ABSENT, _EXPECT_NOT_PRESENT,
                id="openrouter-no-pad",
            ),
        ],
    )
    def test_tool_call_reasoning_content_pad(
        self, provider, model, base_url, sdk_reasoning_content, expected,
    ) -> None:
        agent = _make_agent(provider=provider, model=model, base_url=base_url)
        msg_in = _build_sdk_message(
            reasoning_content=sdk_reasoning_content,
            tool_calls=[_sdk_tool_call()],
        )
        msg = agent._build_assistant_message(msg_in, finish_reason="tool_calls")
        if expected is _EXPECT_NOT_PRESENT:
            assert "reasoning_content" not in msg
        else:
            assert msg["reasoning_content"] == expected

    def test_mimo_preserves_real_reasoning_content(self) -> None:
        agent = _make_agent(provider="xiaomi", model="mimo-v2.5-pro")
        msg_in = _build_sdk_message(
            reasoning_content="actual MiMo chain of thought",
            tool_calls=[_sdk_tool_call()],
        )
        msg = agent._build_assistant_message(msg_in, finish_reason="tool_calls")
        assert msg["reasoning_content"] == "actual MiMo chain of thought"

    def test_mimo_streamed_reasoning_promoted_over_pad(self) -> None:
        agent = _make_agent(provider="xiaomi", model="mimo-v2.5-pro")
        msg_in = _build_sdk_message(
            reasoning="streamed MiMo thoughts",
            tool_calls=[_sdk_tool_call()],
        )
        msg = agent._build_assistant_message(msg_in, finish_reason="tool_calls")
        assert msg["reasoning_content"] == "streamed MiMo thoughts"
