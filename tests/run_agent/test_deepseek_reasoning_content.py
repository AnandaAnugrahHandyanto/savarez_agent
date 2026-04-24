"""Verify _copy_reasoning_content_for_api injects reasoning_content for DeepSeek.

DeepSeek v4/v4-flash/v4-pro in thinking mode requires `reasoning_content` on
every assistant message in replayed history, otherwise the API returns:

    HTTP 400: The reasoning_content in the thinking mode must be passed back to the API.

This fails on compressed-summary assistant messages and on replays of sessions
whose assistant messages were persisted before the fix (the "poisoned history"
case). Real reasoning is preserved by the earlier `explicit_reasoning` and
`normalized_reasoning` branches; the new DeepSeek branch only fills in the
empty-string placeholder when no reasoning is available.

Related upstream: PR #15228, Issue #15213.
"""

from __future__ import annotations

import pytest

from run_agent import AIAgent


def _make_agent(
    *,
    model: str,
    reasoning_config: dict | None,
    provider: str = "openrouter",
    base_url: str = "https://openrouter.ai/api/v1",
) -> AIAgent:
    """Construct a minimal AIAgent stub for _copy_reasoning_content_for_api.

    The method reads self.model, self.provider, self.base_url, and
    self.reasoning_config. We bypass __init__ and set only those attrs.
    """
    agent = AIAgent.__new__(AIAgent)
    agent.model = model
    agent.provider = provider
    agent.base_url = base_url
    agent.reasoning_config = reasoning_config
    return agent


class TestDeepSeekReasoningContentInjection:
    """Cover the new DeepSeek branch in _copy_reasoning_content_for_api."""

    def test_deepseek_enabled_injects_empty_when_no_reasoning(self):
        """DeepSeek model + thinking on + no stored reasoning → inject ''."""
        agent = _make_agent(
            model="deepseek/deepseek-v4-flash",
            reasoning_config={"enabled": True, "effort": "high"},
        )
        source_msg = {"role": "assistant", "content": "hi"}
        api_msg = {"role": "assistant", "content": "hi"}
        agent._copy_reasoning_content_for_api(source_msg, api_msg)
        assert api_msg["reasoning_content"] == ""

    def test_deepseek_disabled_skips_injection(self):
        """reasoning_effort: none → reasoning_config.enabled=False → do nothing."""
        agent = _make_agent(
            model="deepseek/deepseek-v4-flash",
            reasoning_config={"enabled": False},
        )
        source_msg = {"role": "assistant", "content": "hi"}
        api_msg = {"role": "assistant", "content": "hi"}
        agent._copy_reasoning_content_for_api(source_msg, api_msg)
        assert "reasoning_content" not in api_msg

    def test_non_deepseek_skips_injection(self):
        """Non-DeepSeek models must not get the empty-string injection."""
        agent = _make_agent(
            model="anthropic/claude-sonnet-4.6",
            reasoning_config={"enabled": True, "effort": "high"},
            base_url="https://api.anthropic.com",
        )
        source_msg = {"role": "assistant", "content": "hi"}
        api_msg = {"role": "assistant", "content": "hi"}
        agent._copy_reasoning_content_for_api(source_msg, api_msg)
        assert "reasoning_content" not in api_msg

    def test_deepseek_preserves_real_reasoning(self):
        """Real `reasoning` must win over the empty-string default."""
        agent = _make_agent(
            model="deepseek/deepseek-v4-flash",
            reasoning_config={"enabled": True, "effort": "high"},
        )
        source_msg = {
            "role": "assistant",
            "content": "hi",
            "reasoning": "chain of thought text",
        }
        api_msg = {"role": "assistant", "content": "hi"}
        agent._copy_reasoning_content_for_api(source_msg, api_msg)
        assert api_msg["reasoning_content"] == "chain of thought text"

    def test_deepseek_reasoning_config_none_defaults_enabled(self):
        """reasoning_config=None means default-enabled (chat_completions.py:256)."""
        agent = _make_agent(
            model="deepseek/deepseek-v4-flash",
            reasoning_config=None,
        )
        source_msg = {"role": "assistant", "content": "hi"}
        api_msg = {"role": "assistant", "content": "hi"}
        agent._copy_reasoning_content_for_api(source_msg, api_msg)
        assert api_msg["reasoning_content"] == ""

    def test_deepseek_preserves_explicit_empty_reasoning(self):
        """Pre-existing reasoning_content='' must be preserved (explicit branch)."""
        agent = _make_agent(
            model="deepseek/deepseek-v4-flash",
            reasoning_config={"enabled": True, "effort": "high"},
        )
        source_msg = {
            "role": "assistant",
            "content": "hi",
            "reasoning_content": "",
        }
        api_msg = {"role": "assistant", "content": "hi"}
        agent._copy_reasoning_content_for_api(source_msg, api_msg)
        # Empty string is explicitly preserved by the isinstance(str) branch
        # at line 7493-7495 before the new DeepSeek branch can run.
        assert api_msg["reasoning_content"] == ""
