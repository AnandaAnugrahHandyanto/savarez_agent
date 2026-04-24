"""Verify DeepSeek reasoning_content is extracted from model_extra (#14938).

DeepSeek V4 Flash returns reasoning_content in the API response, but OpenAI
SDK < 1.60 doesn't declare it as a ChatCompletionMessage field. It ends up in
Pydantic's model_extra instead. Without this fix, the reasoning_content is lost
and subsequent requests fail with:
    HTTP 400: The reasoning_content in the thinking mode must be passed back to the API
"""

import types
import pytest


class FakeMessageWithModelExtra:
    """Simulates OpenAI SDK ChatCompletionMessage with reasoning_content in model_extra."""
    def __init__(self, content=None, reasoning_content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls
        self.model_extra = {}
        if reasoning_content is not None:
            self.model_extra["reasoning_content"] = reasoning_content


class FakeMessageWithAttribute:
    """Simulates newer OpenAI SDK where reasoning_content is a real attribute."""
    def __init__(self, content=None, reasoning_content=None, tool_calls=None):
        self.content = content
        self.reasoning_content = reasoning_content
        self.tool_calls = tool_calls
        self.model_extra = {}


class TestExtractReasoning:
    """Test _extract_reasoning handles both model_extra and direct attributes."""

    @pytest.fixture
    def agent(self):
        """Create a minimal AIAgent stub for testing static methods."""
        from run_agent import AIAgent
        # _extract_reasoning is technically an instance method but doesn't use self
        return AIAgent.__new__(AIAgent)

    def test_extract_from_model_extra(self, agent):
        """DeepSeek-style: reasoning_content lives in model_extra."""
        msg = FakeMessageWithModelExtra(
            content="ok",
            reasoning_content="Let me think about this...",
        )
        result = agent._extract_reasoning(msg)
        assert result == "Let me think about this..."

    def test_extract_from_direct_attribute(self, agent):
        """Moonshot/OpenRouter-style: reasoning_content is a direct attribute."""
        msg = FakeMessageWithAttribute(
            content="ok",
            reasoning_content="Thinking process here",
        )
        result = agent._extract_reasoning(msg)
        assert result == "Thinking process here"

    def test_model_extra_takes_precedence_over_attribute(self, agent):
        """If both exist, model_extra wins (newer provider data)."""
        msg = FakeMessageWithAttribute(
            content="ok",
            reasoning_content="from_attribute",
        )
        # Inject model_extra with different value
        msg.model_extra = {"reasoning_content": "from_model_extra"}
        result = agent._extract_reasoning(msg)
        assert result == "from_model_extra"

    def test_no_reasoning_returns_none(self, agent):
        """Message without any reasoning fields returns None."""
        msg = FakeMessageWithModelExtra(content="just content")
        result = agent._extract_reasoning(msg)
        assert result is None

    def test_empty_model_extra(self, agent):
        """Message with empty model_extra returns None."""
        msg = FakeMessageWithModelExtra(content="ok")
        result = agent._extract_reasoning(msg)
        assert result is None

    def test_none_model_extra(self, agent):
        """Message with None model_extra doesn't crash."""
        msg = FakeMessageWithModelExtra(content="ok")
        msg.model_extra = None
        result = agent._extract_reasoning(msg)
        assert result is None
