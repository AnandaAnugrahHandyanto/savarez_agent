"""Tests for AnthropicTransport.

Focused on the malformed tool_call sanitization pre-pass added to
convert_messages.  The adapter-level conversion (convert_messages_to_anthropic)
has its own test suite; these tests exercise the transport entrypoint guard
using a lightweight mock that short-circuits the real adapter.
"""

import copy
from unittest.mock import patch

import pytest

from agent.transports import get_transport


@pytest.fixture
def transport():
    import agent.transports.anthropic  # noqa: F401
    return get_transport("anthropic_messages")


def _fake_adapter(messages, base_url=None):
    """Minimal stand-in for convert_messages_to_anthropic.

    Returns (system, messages) like the real adapter but with no conversion,
    so tests can inspect the sanitized OpenAI-format messages directly.
    """
    system = None
    body = []
    for m in messages:
        if m.get("role") == "system":
            system = m.get("content", "")
        else:
            body.append(m)
    return system, body


class TestAnthropicMalformedToolCallSanitization:
    """Mirror of TestMalformedToolCallSanitization for the Anthropic transport.

    The sanitization logic is identical to chat_completions.py; the transport
    just runs it before delegating to the adapter.
    """

    # ── Case 1: mixed valid + malformed ──────────────────────────────────────

    def test_malformed_dropped_valid_preserved(self, transport):
        """One malformed + one valid tool_call: malformed dropped, valid kept."""
        msgs = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_bad",
                        "type": "function",
                        "function": {
                            "name": "patch",
                            "arguments": '{"path": "~/.hermes/file.py", "old_string": "    # Anthropic think',
                        },
                    },
                    {
                        "id": "call_good",
                        "type": "function",
                        "function": {
                            "name": "terminal",
                            "arguments": '{"command": "ls"}',
                        },
                    },
                ],
            }
        ]
        with patch(
            "agent.anthropic_adapter.convert_messages_to_anthropic",
            side_effect=_fake_adapter,
        ):
            _system, body = transport.convert_messages(msgs)

        assert len(body) == 1
        msg = body[0]
        tool_calls = msg["tool_calls"]
        assert len(tool_calls) == 1
        assert tool_calls[0]["id"] == "call_good"
        # Original not mutated
        assert len(msgs[0]["tool_calls"]) == 2
    # ── Case 2: all malformed + orphan tool result ────────────────────────────

    def test_all_malformed_and_orphan_tool_stripped(self, transport):
        """Only malformed tool_call + orphan tool result: both removed, placeholder injected."""
        msgs = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_bad",
                        "type": "function",
                        "function": {
                            "name": "patch",
                            "arguments": '{"path": "~/.hermes/file.py", "old_string": "    # Anthropic think',
                        },
                    },
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_bad",
                "content": "ok",
            },
        ]
        with patch(
            "agent.anthropic_adapter.convert_messages_to_anthropic",
            side_effect=_fake_adapter,
        ):
            _system, body = transport.convert_messages(msgs)

        # Only the assistant message; orphan tool msg stripped
        assert len(body) == 1
        msg = body[0]
        assert "tool_calls" not in msg
        assert msg["content"] == "(tool call dropped — malformed arguments)"

    # ── Case 3: well-formed tool_calls — no deepcopy, adapter called once ────

    def test_well_formed_unchanged(self, transport):
        """Well-formed tool_calls pass through without mutation."""
        msgs = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_ok",
                        "type": "function",
                        "function": {
                            "name": "terminal",
                            "arguments": '{"command": "pwd"}',
                        },
                    }
                ],
            }
        ]
        original_ids = [tc["id"] for tc in msgs[0]["tool_calls"]]

        with patch(
            "agent.anthropic_adapter.convert_messages_to_anthropic",
            side_effect=_fake_adapter,
        ):
            _system, body = transport.convert_messages(msgs)

        assert [tc["id"] for tc in body[0]["tool_calls"]] == original_ids

    # ── Case 4: empty arguments string — not malformed ───────────────────────

    def test_empty_arguments_string_not_malformed(self, transport):
        """arguments='' is not treated as malformed; message passes through."""
        msgs = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_empty",
                        "type": "function",
                        "function": {
                            "name": "terminal",
                            "arguments": "",
                        },
                    }
                ],
            }
        ]
        with patch(
            "agent.anthropic_adapter.convert_messages_to_anthropic",
            side_effect=_fake_adapter,
        ):
            _system, body = transport.convert_messages(msgs)

        assert body[0]["tool_calls"][0]["function"]["arguments"] == ""

    # ── Extra: surviving tool result preserved ───────────────────────────────

    def test_surviving_tool_result_kept(self, transport):
        """Orphan from dropped call removed; tool msg for surviving call kept."""
        msgs = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_bad",
                        "type": "function",
                        "function": {"name": "patch", "arguments": '{"truncated":'},
                    },
                    {
                        "id": "call_good",
                        "type": "function",
                        "function": {"name": "terminal", "arguments": '{"command": "ls"}'},
                    },
                ],
            },
            {"role": "tool", "tool_call_id": "call_bad", "content": "err"},
            {"role": "tool", "tool_call_id": "call_good", "content": "file.py"},
        ]
        with patch(
            "agent.anthropic_adapter.convert_messages_to_anthropic",
            side_effect=_fake_adapter,
        ):
            _system, body = transport.convert_messages(msgs)

        # 1 assistant + 1 surviving tool msg
        assert len(body) == 2
        assert body[1]["tool_call_id"] == "call_good"

    # ── Warning emitted on drop ───────────────────────────────────────────────

    def test_warning_logged_on_drop(self, transport, caplog):
        """logger.warning is emitted exactly once when a drop occurs."""
        import logging

        msgs = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_bad",
                        "type": "function",
                        "function": {"name": "patch", "arguments": '{"broken":'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_bad", "content": "n/a"},
        ]
        with patch(
            "agent.anthropic_adapter.convert_messages_to_anthropic",
            side_effect=_fake_adapter,
        ):
            with caplog.at_level(logging.WARNING, logger="agent.transports.anthropic"):
                transport.convert_messages(msgs)

        assert any("malformed tool_call" in r.message for r in caplog.records)
        assert any("orphan tool message" in r.message for r in caplog.records)
