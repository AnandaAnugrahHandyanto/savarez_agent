"""Regression guard: preserve thinking blocks on Xiaomi MiMo's /anthropic endpoint.

Xiaomi MiMo's ``token-plan-cn.xiaomimimo.com/anthropic`` route speaks the
Anthropic Messages protocol but, when thinking mode is enabled, requires
``thinking`` blocks from prior assistant turns to round-trip on subsequent
requests.  The generic third-party path strips them (signatures are
Anthropic-proprietary and other proxies cannot validate them), so without a
Xiaomi MiMo-specific carve-out the next tool-call turn fails with HTTP 400::

    The reasoning_content in the thinking mode must be passed back to the API.

Handling mirrors Kimi's ``/coding`` and DeepSeek's ``/anthropic`` endpoints:
strip Anthropic-signed blocks (Xiaomi MiMo can't validate them) but preserve
unsigned blocks that Hermes synthesises from ``reasoning_content``.

See hermes-agent#24884.
"""

from __future__ import annotations

import pytest


class TestXiaomiMiMoAnthropicPreservesThinking:
    """convert_messages_to_anthropic must replay Xiaomi MiMo thinking blocks."""

    @pytest.mark.parametrize(
        "base_url",
        [
            "https://token-plan-cn.xiaomimimo.com/anthropic",
            "https://token-plan-cn.xiaomimimo.com/anthropic/",
            "https://token-plan-cn.xiaomimimo.com/anthropic/v1",
            "https://Token-Plan-CN.XiaomiMiMo.com/anthropic",
        ],
    )
    def test_unsigned_thinking_block_survives_replay(self, base_url: str) -> None:
        """Unsigned thinking (synthesised from reasoning_content) must be preserved."""
        from agent.anthropic_adapter import convert_messages_to_anthropic

        messages = [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "reasoning_content": "planning the tool call",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "skill_view", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "ok"},
        ]
        _system, converted = convert_messages_to_anthropic(
            messages, base_url=base_url
        )

        assistant_msg = next(m for m in converted if m["role"] == "assistant")
        thinking_blocks = [
            b for b in assistant_msg["content"]
            if isinstance(b, dict) and b.get("type") == "thinking"
        ]
        assert len(thinking_blocks) == 1, (
            f"Xiaomi MiMo /anthropic ({base_url}) must preserve unsigned thinking "
            "blocks synthesised from reasoning_content — upstream rejects "
            "replayed tool-call messages without them."
        )
        assert thinking_blocks[0]["thinking"] == "planning the tool call"
        # Synthesised block — never has a signature
        assert "signature" not in thinking_blocks[0]

    def test_unsigned_thinking_preserved_on_non_latest_assistant_turn(self) -> None:
        """Xiaomi MiMo validates history across every prior assistant turn, not just last."""
        from agent.anthropic_adapter import convert_messages_to_anthropic

        messages = [
            {"role": "user", "content": "q1"},
            {
                "role": "assistant",
                "reasoning_content": "r1",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "f", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "ok"},
            {"role": "user", "content": "q2"},
            {
                "role": "assistant",
                "reasoning_content": "r2",
                "tool_calls": [
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "f", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_2", "content": "ok"},
        ]
        _system, converted = convert_messages_to_anthropic(
            messages, base_url="https://token-plan-cn.xiaomimimo.com/anthropic"
        )

        assistants = [m for m in converted if m["role"] == "assistant"]
        assert len(assistants) == 2
        for assistant, expected in zip(assistants, ("r1", "r2")):
            thinking = [
                b for b in assistant["content"]
                if isinstance(b, dict) and b.get("type") == "thinking"
            ]
            assert len(thinking) == 1
            assert thinking[0]["thinking"] == expected

    def test_signed_anthropic_thinking_block_is_stripped(self) -> None:
        """Anthropic-signed blocks (that leaked through) must still be stripped.

        Xiaomi MiMo cannot validate Anthropic-proprietary signatures — the
        strip-signed / keep-unsigned split matches the Kimi and DeepSeek policy.
        """
        from agent.anthropic_adapter import convert_messages_to_anthropic

        messages = [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "thinking",
                        "thinking": "anthropic-signed payload",
                        "signature": "anthropic-sig-xyz",
                    },
                    {"type": "text", "text": "hello"},
                ],
            },
            {"role": "user", "content": "again"},
        ]
        _system, converted = convert_messages_to_anthropic(
            messages, base_url="https://token-plan-cn.xiaomimimo.com/anthropic"
        )

        assistant_msg = next(m for m in converted if m["role"] == "assistant")
        thinking_blocks = [
            b for b in assistant_msg["content"]
            if isinstance(b, dict) and b.get("type") == "thinking"
        ]
        assert thinking_blocks == [], (
            "Signed Anthropic thinking blocks must be stripped on Xiaomi MiMo — "
            "Xiaomi MiMo cannot validate Anthropic-proprietary signatures."
        )

    def test_cache_control_stripped_from_thinking_block(self) -> None:
        """cache_control must still be stripped even when the block is preserved.

        cache markers interfere with signature validation on upstreams that do
        check them, so Hermes strips them everywhere.
        """
        from agent.anthropic_adapter import convert_messages_to_anthropic

        messages = [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "reasoning_content": "r1",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "f", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "ok"},
        ]
        _system, converted = convert_messages_to_anthropic(
            messages, base_url="https://token-plan-cn.xiaomimimo.com/anthropic"
        )
        for m in converted:
            if not isinstance(m.get("content"), list):
                continue
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") in ("thinking", "redacted_thinking"):
                    assert "cache_control" not in b

    def test_openai_compat_xiaomi_base_is_not_matched(self) -> None:
        """A future OpenAI-compatible Xiaomi base must NOT trigger the
        /anthropic branch — the detector should fail closed so an accidental
        misuse doesn't quietly send signed Anthropic blocks to an OpenAI endpoint.
        """
        from agent.anthropic_adapter import _is_xiaomi_mimo_anthropic_endpoint

        assert _is_xiaomi_mimo_anthropic_endpoint("https://token-plan-cn.xiaomimimo.com") is False
        assert _is_xiaomi_mimo_anthropic_endpoint("https://token-plan-cn.xiaomimimo.com/v1") is False
        assert _is_xiaomi_mimo_anthropic_endpoint("https://token-plan-cn.xiaomimimo.com/anthropic") is True
        assert _is_xiaomi_mimo_anthropic_endpoint("https://token-plan-cn.xiaomimimo.com/anthropic/v1") is True
        # Subdomain coverage — Xiaomi may add regional hosts.
        assert _is_xiaomi_mimo_anthropic_endpoint("https://other.xiaomimimo.com/anthropic") is True

    def test_non_xiaomi_third_party_still_strips_all_thinking(self) -> None:
        """MiniMax and other third-party Anthropic endpoints must keep the
        generic strip-all behaviour (they reject unsigned blocks outright).
        """
        from agent.anthropic_adapter import convert_messages_to_anthropic

        messages = [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "reasoning_content": "r1",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "f", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "ok"},
        ]
        _system, converted = convert_messages_to_anthropic(
            messages, base_url="https://api.minimax.io/anthropic"
        )
        assistant_msg = next(m for m in converted if m["role"] == "assistant")
        thinking_blocks = [
            b for b in assistant_msg["content"]
            if isinstance(b, dict) and b.get("type") == "thinking"
        ]
        assert thinking_blocks == [], (
            "Non-Xiaomi third-party endpoints must keep the generic "
            "strip-all-thinking behaviour — unsigned blocks get rejected."
        )
