"""Tests for reasoning display when streaming is active.

Covers two fixes from issue #5892:
1. _extract_reasoning should walk native Anthropic content blocks with
   type=="thinking" when content is a list.
2. Gateway should send reasoning as a separate message when streaming
   has already delivered the response (already_sent=True).
"""

import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fix 1: _extract_reasoning handles native Anthropic content blocks
# ---------------------------------------------------------------------------

class TestExtractReasoningAnthropicBlocks:
    """_extract_reasoning should find thinking in content block lists."""

    def _make_agent(self):
        """Create a minimal agent-like object with _extract_reasoning."""
        # Import the real method if possible, otherwise build a stub
        from run_agent import AgentLoop
        agent = object.__new__(AgentLoop)
        return agent

    def test_thinking_block_as_object(self):
        """Content block with .type=='thinking' and .thinking attr."""
        agent = self._make_agent()
        block = types.SimpleNamespace(type="thinking", thinking="I need to multiply")
        msg = types.SimpleNamespace(content=[block])
        result = agent._extract_reasoning(msg)
        assert result == "I need to multiply"

    def test_thinking_block_as_dict(self):
        """Content block as dict with type=='thinking'."""
        agent = self._make_agent()
        msg = types.SimpleNamespace(
            content=[{"type": "thinking", "thinking": "Step 1: parse input"}]
        )
        result = agent._extract_reasoning(msg)
        assert result == "Step 1: parse input"

    def test_mixed_blocks_only_thinking_extracted(self):
        """Non-thinking blocks in content list are ignored."""
        agent = self._make_agent()
        msg = types.SimpleNamespace(
            content=[
                {"type": "text", "text": "Hello"},
                {"type": "thinking", "thinking": "Let me reason"},
                {"type": "text", "text": "World"},
            ]
        )
        result = agent._extract_reasoning(msg)
        assert result == "Let me reason"

    def test_structured_reasoning_takes_precedence(self):
        """If .reasoning is present, content blocks are not walked."""
        agent = self._make_agent()
        msg = types.SimpleNamespace(
            reasoning="Direct reasoning field",
            content=[{"type": "thinking", "thinking": "Block reasoning"}],
        )
        result = agent._extract_reasoning(msg)
        assert result == "Direct reasoning field"

    def test_no_thinking_blocks_returns_none(self):
        """Content list without thinking blocks returns None."""
        agent = self._make_agent()
        msg = types.SimpleNamespace(
            content=[{"type": "text", "text": "Just text"}]
        )
        result = agent._extract_reasoning(msg)
        assert result is None
