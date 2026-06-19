"""Regression test: Cerebras reasoning_content stripping.

Cerebras API returns ``reasoning_tokens`` in responses but rejects
``reasoning_content`` in input messages with HTTP 400::

    messages.2.assistant.reasoning_content: property 'reasoning_content'
    is unsupported

``copy_reasoning_content_for_api`` must strip ``reasoning_content`` for
providers that don't enforce thinking-mode echo-back (i.e. when
``_needs_thinking_reasoning_pad()`` returns ``False``).

Refs #45655.
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


# ---------------------------------------------------------------------------
# copy_reasoning_content_for_api — Cerebras stripping
# ---------------------------------------------------------------------------


class TestCerebrasReasoningContentStripping:
    """copy_reasoning_content_for_api strips reasoning_content for Cerebras."""

    def test_strips_non_empty_reasoning_content_for_cerebras(self):
        """Non-empty reasoning_content must be stripped for Cerebras."""
        agent = _make_agent(
            provider="custom:cerebras",
            model="gpt-oss-120b",
            base_url="https://api.cerebras.ai/v1",
        )
        source = {
            "role": "assistant",
            "reasoning_content": "Some reasoning from Cerebras",
        }
        api_msg: dict = {"role": "assistant"}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert "reasoning_content" not in api_msg

    def test_strips_reasoning_promotion_for_cerebras(self):
        """'reasoning' field must NOT be promoted to reasoning_content for Cerebras."""
        agent = _make_agent(
            provider="custom:cerebras",
            model="gpt-oss-120b",
            base_url="https://api.cerebras.ai/v1",
        )
        source = {
            "role": "assistant",
            "reasoning": "Some internal reasoning text",
        }
        api_msg: dict = {"role": "assistant"}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert "reasoning_content" not in api_msg

    def test_preserves_empty_reasoning_content_for_cerebras(self):
        """Empty reasoning_content is harmless — preserve it (matches non-thinking behavior)."""
        agent = _make_agent(
            provider="custom:cerebras",
            model="gpt-oss-120b",
            base_url="https://api.cerebras.ai/v1",
        )
        source = {
            "role": "assistant",
            "reasoning_content": "",
        }
        api_msg: dict = {"role": "assistant"}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert api_msg.get("reasoning_content") == ""

    def test_preserves_reasoning_content_for_deepseek(self):
        """DeepSeek must still receive reasoning_content (regression guard)."""
        agent = _make_agent(
            provider="deepseek",
            model="deepseek-v4-pro",
            base_url="https://api.deepseek.com/v1",
        )
        source = {
            "role": "assistant",
            "reasoning_content": "DeepSeek reasoning",
        }
        api_msg: dict = {"role": "assistant"}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert api_msg["reasoning_content"] == "DeepSeek reasoning"

    def test_preserves_reasoning_content_for_kimi(self):
        """Kimi must still receive reasoning_content (regression guard)."""
        agent = _make_agent(
            provider="kimi-coding",
            model="kimi-k2",
            base_url="https://api.kimi.com/v1",
        )
        source = {
            "role": "assistant",
            "reasoning_content": "Kimi reasoning",
        }
        api_msg: dict = {"role": "assistant"}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert api_msg["reasoning_content"] == "Kimi reasoning"

    def test_preserves_reasoning_content_for_mimo(self):
        """MiMo must still receive reasoning_content (regression guard)."""
        agent = _make_agent(
            provider="xiaomi",
            model="mimo-v2.5-pro",
            base_url="https://api.xiaomimimo.com/v1",
        )
        source = {
            "role": "assistant",
            "reasoning_content": "MiMo reasoning",
        }
        api_msg: dict = {"role": "assistant"}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert api_msg["reasoning_content"] == "MiMo reasoning"

    def test_strips_for_unknown_custom_provider(self):
        """Unknown custom providers should also have reasoning_content stripped."""
        agent = _make_agent(
            provider="custom:sambanova",
            model="Llama-4-Maverick-17B-128E-Instruct",
            base_url="https://api.sambanova.ai/v1",
        )
        source = {
            "role": "assistant",
            "reasoning_content": "Some reasoning",
        }
        api_msg: dict = {"role": "assistant"}
        agent._copy_reasoning_content_for_api(source, api_msg)
        assert "reasoning_content" not in api_msg
