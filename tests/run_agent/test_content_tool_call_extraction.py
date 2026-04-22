"""Tests for _try_extract_content_tool_calls — fallback parsing of tool calls
embedded as JSON in the content field (e.g. Ollama qwen2.5-coder)."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _make_agent(tool_names):
    """Create a minimal mock agent with the given tool names registered."""
    from run_agent import AIAgent

    agent = MagicMock(spec=AIAgent)
    agent.tools = [
        {"type": "function", "function": {"name": n, "parameters": {}}}
        for n in tool_names
    ]
    agent._try_extract_content_tool_calls = (
        AIAgent._try_extract_content_tool_calls.__get__(agent, AIAgent)
    )
    return agent


class TestContentToolCallExtraction:
    """Verify JSON-in-content tool call extraction."""

    def test_single_tool_call_json_object(self):
        agent = _make_agent(["search"])
        content = '{"name": "search", "arguments": {"query": "weather in Beijing"}}'
        result = agent._try_extract_content_tool_calls(content)

        assert result is not None
        assert len(result) == 1
        assert result[0].function.name == "search"
        args = json.loads(result[0].function.arguments)
        assert args["query"] == "weather in Beijing"

    def test_multiple_tool_calls_json_array(self):
        agent = _make_agent(["search", "read_file"])
        content = json.dumps([
            {"name": "search", "arguments": {"query": "test"}},
            {"name": "read_file", "arguments": {"path": "/tmp/foo.txt"}},
        ])
        result = agent._try_extract_content_tool_calls(content)

        assert result is not None
        assert len(result) == 2
        assert result[0].function.name == "search"
        assert result[1].function.name == "read_file"

    def test_unrecognised_tool_name_returns_none(self):
        agent = _make_agent(["search"])
        content = '{"name": "nonexistent_tool", "arguments": {}}'
        result = agent._try_extract_content_tool_calls(content)
        assert result is None

    def test_plain_text_returns_none(self):
        agent = _make_agent(["search"])
        result = agent._try_extract_content_tool_calls("Hello, how can I help?")
        assert result is None

    def test_invalid_json_returns_none(self):
        agent = _make_agent(["search"])
        result = agent._try_extract_content_tool_calls('{"name": "search", broken}')
        assert result is None

    def test_empty_content_returns_none(self):
        agent = _make_agent(["search"])
        assert agent._try_extract_content_tool_calls("") is None
        assert agent._try_extract_content_tool_calls("   ") is None

    def test_json_without_name_field_returns_none(self):
        agent = _make_agent(["search"])
        result = agent._try_extract_content_tool_calls('{"key": "value"}')
        assert result is None

    def test_arguments_as_string_preserved(self):
        agent = _make_agent(["search"])
        content = '{"name": "search", "arguments": "{\\"query\\": \\"test\\"}"}'
        result = agent._try_extract_content_tool_calls(content)

        assert result is not None
        assert result[0].function.arguments == '{"query": "test"}'

    def test_tool_call_ids_are_unique(self):
        agent = _make_agent(["search"])
        content = json.dumps([
            {"name": "search", "arguments": {"query": "a"}},
            {"name": "search", "arguments": {"query": "b"}},
        ])
        result = agent._try_extract_content_tool_calls(content)

        assert result is not None
        assert len(result) == 2
        assert result[0].id != result[1].id

    def test_unicode_arguments_preserved(self):
        agent = _make_agent(["search"])
        content = '{"name": "search", "arguments": {"query": "\u5317\u4eac\u4eca\u5929\u7684\u5929\u6c14"}}'
        result = agent._try_extract_content_tool_calls(content)

        assert result is not None
        args = json.loads(result[0].function.arguments)
        assert args["query"] == "\u5317\u4eac\u4eca\u5929\u7684\u5929\u6c14"
