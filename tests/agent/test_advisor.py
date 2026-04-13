"""Tests for the Anthropic Advisor Tool integration.

Tests cover:
- Tool injection in build_anthropic_kwargs
- Response normalization (server_tool_use, advisor_tool_result)
- Message history round-tripping
- Auto-effort reduction
- Advisor block stripping when disabled
- pause_turn stop reason mapping
"""

import json
import pytest
from types import SimpleNamespace

from agent.anthropic_adapter import (
    build_anthropic_kwargs,
    convert_messages_to_anthropic,
    normalize_anthropic_response,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASIC_MESSAGES = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Build a worker pool in Go."},
]

ADVISOR_ENABLED = {
    "enabled": True,
    "model": "claude-opus-4-6",
    "max_uses": 0,
    "caching": False,
    "auto_effort": True,
}

ADVISOR_DISABLED = {"enabled": False}


# ---------------------------------------------------------------------------
# Tool injection tests
# ---------------------------------------------------------------------------

class TestAdvisorToolInjection:
    """Tests for advisor tool injection in build_anthropic_kwargs."""

    def test_advisor_tool_injected_when_enabled(self):
        kwargs = build_anthropic_kwargs(
            model="claude-sonnet-4-6",
            messages=BASIC_MESSAGES,
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            advisor_config=ADVISOR_ENABLED,
        )
        tools = kwargs.get("tools", [])
        advisor_tools = [t for t in tools if t.get("type") == "advisor_20260301"]
        assert len(advisor_tools) == 1
        assert advisor_tools[0]["name"] == "advisor"
        assert advisor_tools[0]["model"] == "claude-opus-4-6"

    def test_advisor_tool_not_injected_when_disabled(self):
        kwargs = build_anthropic_kwargs(
            model="claude-sonnet-4-6",
            messages=BASIC_MESSAGES,
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            advisor_config=ADVISOR_DISABLED,
        )
        tools = kwargs.get("tools")
        assert tools is None or not any(
            t.get("type") == "advisor_20260301" for t in tools
        )

    def test_advisor_tool_not_injected_without_config(self):
        kwargs = build_anthropic_kwargs(
            model="claude-sonnet-4-6",
            messages=BASIC_MESSAGES,
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            advisor_config=None,
        )
        tools = kwargs.get("tools")
        assert tools is None

    def test_advisor_beta_header_added(self):
        kwargs = build_anthropic_kwargs(
            model="claude-sonnet-4-6",
            messages=BASIC_MESSAGES,
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            advisor_config=ADVISOR_ENABLED,
        )
        headers = kwargs.get("extra_headers", {})
        beta = headers.get("anthropic-beta", "")
        assert "advisor-tool-2026-03-01" in beta

    def test_advisor_max_uses(self):
        config = {**ADVISOR_ENABLED, "max_uses": 3}
        kwargs = build_anthropic_kwargs(
            model="claude-sonnet-4-6",
            messages=BASIC_MESSAGES,
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            advisor_config=config,
        )
        tools = kwargs.get("tools", [])
        advisor = [t for t in tools if t.get("type") == "advisor_20260301"][0]
        assert advisor["max_uses"] == 3

    def test_advisor_max_uses_zero_omitted(self):
        """max_uses=0 means unlimited — should not appear in the tool def."""
        kwargs = build_anthropic_kwargs(
            model="claude-sonnet-4-6",
            messages=BASIC_MESSAGES,
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            advisor_config=ADVISOR_ENABLED,
        )
        tools = kwargs.get("tools", [])
        advisor = [t for t in tools if t.get("type") == "advisor_20260301"][0]
        assert "max_uses" not in advisor

    def test_advisor_caching(self):
        config = {**ADVISOR_ENABLED, "caching": True}
        kwargs = build_anthropic_kwargs(
            model="claude-sonnet-4-6",
            messages=BASIC_MESSAGES,
            tools=None,
            max_tokens=4096,
            reasoning_config={"enabled": True, "effort": "medium"},
            advisor_config=config,
        )
        tools = kwargs.get("tools", [])
        advisor = [t for t in tools if t.get("type") == "advisor_20260301"][0]
        assert advisor["caching"] == {"type": "ephemeral", "ttl": "5m"}
        # clear_thinking should be set to preserve advisor cache stability
        assert kwargs.get("clear_thinking") == {"keep": "all"}

    def test_advisor_not_injected_for_third_party_endpoint(self):
        """Third-party Anthropic endpoints should not get the advisor tool."""
        kwargs = build_anthropic_kwargs(
            model="claude-sonnet-4-6",
            messages=BASIC_MESSAGES,
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            advisor_config=ADVISOR_ENABLED,
            base_url="https://api.minimax.io/anthropic/v1",
        )
        tools = kwargs.get("tools")
        assert tools is None or not any(
            t.get("type") == "advisor_20260301" for t in tools
        )


# ---------------------------------------------------------------------------
# Auto-effort reduction
# ---------------------------------------------------------------------------

class TestAdvisorAutoEffort:

    def test_auto_effort_reduces_high_to_medium(self):
        kwargs = build_anthropic_kwargs(
            model="claude-sonnet-4-6",
            messages=BASIC_MESSAGES,
            tools=None,
            max_tokens=4096,
            reasoning_config={"enabled": True, "effort": "high"},
            advisor_config=ADVISOR_ENABLED,
        )
        assert kwargs.get("output_config", {}).get("effort") == "medium"

    def test_auto_effort_no_reduction_when_already_low(self):
        kwargs = build_anthropic_kwargs(
            model="claude-sonnet-4-6",
            messages=BASIC_MESSAGES,
            tools=None,
            max_tokens=4096,
            reasoning_config={"enabled": True, "effort": "low"},
            advisor_config=ADVISOR_ENABLED,
        )
        # Low effort should not be changed
        assert kwargs.get("output_config", {}).get("effort") == "low"

    def test_auto_effort_disabled_preserves_effort(self):
        config = {**ADVISOR_ENABLED, "auto_effort": False}
        kwargs = build_anthropic_kwargs(
            model="claude-sonnet-4-6",
            messages=BASIC_MESSAGES,
            tools=None,
            max_tokens=4096,
            reasoning_config={"enabled": True, "effort": "high"},
            advisor_config=config,
        )
        assert kwargs.get("output_config", {}).get("effort") == "high"


# ---------------------------------------------------------------------------
# Response normalization
# ---------------------------------------------------------------------------

class TestAdvisorResponseNormalization:

    def _make_response(self, blocks, stop_reason="end_turn"):
        return SimpleNamespace(
            content=blocks,
            stop_reason=stop_reason,
            usage=SimpleNamespace(input_tokens=100, output_tokens=50),
        )

    def test_advisor_blocks_captured(self):
        blocks = [
            SimpleNamespace(type="text", text="Let me consult..."),
            SimpleNamespace(type="server_tool_use", id="srvtoolu_123", name="advisor", input={}),
            SimpleNamespace(
                type="advisor_tool_result",
                tool_use_id="srvtoolu_123",
                content=SimpleNamespace(type="advisor_result", text="Use channels."),
            ),
            SimpleNamespace(type="text", text="Here's the implementation."),
        ]
        msg, reason = normalize_anthropic_response(self._make_response(blocks))
        assert msg.advisor_blocks is not None
        assert len(msg.advisor_blocks) == 2
        assert msg.advisor_blocks[0]["type"] == "server_tool_use"
        assert msg.advisor_blocks[1]["type"] == "advisor_tool_result"

    def test_advisor_blocks_not_in_tool_calls(self):
        blocks = [
            SimpleNamespace(type="server_tool_use", id="srvtoolu_123", name="advisor", input={}),
            SimpleNamespace(
                type="advisor_tool_result",
                tool_use_id="srvtoolu_123",
                content=SimpleNamespace(type="advisor_result", text="Plan."),
            ),
        ]
        msg, _ = normalize_anthropic_response(self._make_response(blocks))
        assert msg.tool_calls is None

    def test_advisor_text_content_preserved(self):
        blocks = [
            SimpleNamespace(type="text", text="Before advisor."),
            SimpleNamespace(type="server_tool_use", id="srv1", name="advisor", input={}),
            SimpleNamespace(
                type="advisor_tool_result",
                tool_use_id="srv1",
                content=SimpleNamespace(type="advisor_result", text="Advice."),
            ),
            SimpleNamespace(type="text", text="After advisor."),
        ]
        msg, _ = normalize_anthropic_response(self._make_response(blocks))
        assert "Before advisor." in msg.content
        assert "After advisor." in msg.content

    def test_pause_turn_mapped(self):
        blocks = [
            SimpleNamespace(type="server_tool_use", id="srv1", name="advisor", input={}),
        ]
        msg, reason = normalize_anthropic_response(
            self._make_response(blocks, stop_reason="pause_turn")
        )
        assert reason == "pause_turn"


# ---------------------------------------------------------------------------
# Message round-trip
# ---------------------------------------------------------------------------

class TestAdvisorMessageRoundTrip:

    def test_advisor_blocks_preserved_in_round_trip(self):
        messages = [
            {"role": "system", "content": "Test."},
            {"role": "user", "content": "Build it."},
            {
                "role": "assistant",
                "content": "Let me think.",
                "advisor_blocks": [
                    {"type": "server_tool_use", "id": "srvtoolu_1", "name": "advisor", "input": {}},
                    {
                        "type": "advisor_tool_result",
                        "tool_use_id": "srvtoolu_1",
                        "content": {"type": "advisor_result", "text": "Use pattern X."},
                    },
                ],
            },
        ]
        _, ant_messages = convert_messages_to_anthropic(
            messages, include_advisor_blocks=True
        )
        assistant_content = ant_messages[1]["content"]
        types = [b["type"] for b in assistant_content if isinstance(b, dict)]
        assert "server_tool_use" in types
        assert "advisor_tool_result" in types

    def test_advisor_blocks_stripped_when_disabled(self):
        messages = [
            {"role": "system", "content": "Test."},
            {"role": "user", "content": "Build it."},
            {
                "role": "assistant",
                "content": "Let me think.",
                "advisor_blocks": [
                    {"type": "server_tool_use", "id": "srvtoolu_1", "name": "advisor", "input": {}},
                    {
                        "type": "advisor_tool_result",
                        "tool_use_id": "srvtoolu_1",
                        "content": {"type": "advisor_result", "text": "Use pattern X."},
                    },
                ],
            },
        ]
        _, ant_messages = convert_messages_to_anthropic(
            messages, include_advisor_blocks=False
        )
        assistant_content = ant_messages[1]["content"]
        types = [b["type"] for b in assistant_content if isinstance(b, dict)]
        assert "server_tool_use" not in types
        assert "advisor_tool_result" not in types

    def test_advisor_blocks_before_tool_calls_in_round_trip(self):
        """advisor_blocks must appear before client tool_use blocks.

        When an assistant turn calls the advisor AND then calls a client tool,
        the Anthropic API requires the content order to be:
          server_tool_use → advisor_tool_result → tool_use (client)
        Swapping them causes HTTP 400: 'tool_use ids found without tool_result'.
        """
        messages = [
            {"role": "system", "content": "Test."},
            {"role": "user", "content": "Build it."},
            {
                "role": "assistant",
                "content": "Consulting advisor then running terminal.",
                "advisor_blocks": [
                    {"type": "server_tool_use", "id": "srvtoolu_X", "name": "advisor", "input": {}},
                    {
                        "type": "advisor_tool_result",
                        "tool_use_id": "srvtoolu_X",
                        "content": {"type": "advisor_result", "text": "Use approach A."},
                    },
                ],
                "tool_calls": [
                    {
                        "id": "toolu_client_1",
                        "type": "function",
                        "function": {"name": "terminal", "arguments": '{"command": "ls"}'},
                    }
                ],
            },
            # tool_result must follow so the orphan-strip doesn't remove the tool_use
            {"role": "tool", "tool_call_id": "toolu_client_1", "content": "file1.py\nfile2.py"},
        ]
        _, ant_messages = convert_messages_to_anthropic(
            messages, include_advisor_blocks=True
        )
        assistant_content = ant_messages[1]["content"]
        types = [b["type"] for b in assistant_content if isinstance(b, dict)]
        # server_tool_use and advisor_tool_result MUST come before tool_use
        assert "server_tool_use" in types, "server_tool_use should be in assistant content"
        assert "advisor_tool_result" in types, "advisor_tool_result should be in assistant content"
        assert "tool_use" in types, "tool_use should be in assistant content"
        srv_idx = types.index("server_tool_use")
        adv_idx = types.index("advisor_tool_result")
        use_idx = types.index("tool_use")
        assert srv_idx < use_idx, "server_tool_use must come before tool_use"
        assert adv_idx < use_idx, "advisor_tool_result must come before tool_use"

    def test_redacted_result_round_trips(self):
        """advisor_redacted_result with encrypted_content must survive round-trip."""
        messages = [
            {"role": "system", "content": "Test."},
            {"role": "user", "content": "Build it."},
            {
                "role": "assistant",
                "content": "Consulting advisor.",
                "advisor_blocks": [
                    {"type": "server_tool_use", "id": "srvtoolu_2", "name": "advisor", "input": {}},
                    {
                        "type": "advisor_tool_result",
                        "tool_use_id": "srvtoolu_2",
                        "content": {
                            "type": "advisor_redacted_result",
                            "encrypted_content": "opaque-encrypted-blob-abc123",
                        },
                    },
                ],
            },
        ]
        _, ant_messages = convert_messages_to_anthropic(
            messages, include_advisor_blocks=True
        )
        assistant_content = ant_messages[1]["content"]
        result_block = [
            b for b in assistant_content
            if isinstance(b, dict) and b.get("type") == "advisor_tool_result"
        ]
        assert len(result_block) == 1
        assert result_block[0]["content"]["type"] == "advisor_redacted_result"
        assert result_block[0]["content"]["encrypted_content"] == "opaque-encrypted-blob-abc123"


# ---------------------------------------------------------------------------
# Beta header composition
# ---------------------------------------------------------------------------

class TestAdvisorBetaHeaders:

    def test_advisor_and_fast_mode_combined(self):
        """Both fast_mode and advisor betas should be in a single header."""
        kwargs = build_anthropic_kwargs(
            model="claude-opus-4-6",
            messages=BASIC_MESSAGES,
            tools=None,
            max_tokens=4096,
            reasoning_config=None,
            advisor_config=ADVISOR_ENABLED,
            fast_mode=True,
        )
        beta = kwargs.get("extra_headers", {}).get("anthropic-beta", "")
        assert "fast-mode-2026-02-01" in beta
        assert "advisor-tool-2026-03-01" in beta
        assert kwargs.get("speed") == "fast"
