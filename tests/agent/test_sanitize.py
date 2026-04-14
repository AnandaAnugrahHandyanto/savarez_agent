"""Tests for agent/sanitize.py — text sanitization utilities."""

import pytest
from agent.sanitize import (
    sanitize_surrogates,
    sanitize_messages_surrogates,
    strip_non_ascii,
    sanitize_messages_non_ascii,
    sanitize_tools_non_ascii,
    sanitize_structure_non_ascii,
)


# --- sanitize_surrogates ---

class TestSanitizeSurrogates:
    def test_clean_text_passes_through(self):
        assert sanitize_surrogates("hello world") == "hello world"

    def test_lone_high_surrogate_replaced(self):
        assert sanitize_surrogates("bad \ud800 text") == "bad \ufffd text"

    def test_lone_low_surrogate_replaced(self):
        assert sanitize_surrogates("bad \udc00 text") == "bad \ufffd text"

    def test_empty_string(self):
        assert sanitize_surrogates("") == ""

    def test_multiple_surrogates(self):
        result = sanitize_surrogates("\ud800\ud900\udfff")
        assert "\ud800" not in result
        assert "\ud900" not in result
        assert "\udfff" not in result


# --- sanitize_messages_surrogates ---

class TestSanitizeMessagesSurrogates:
    def test_clean_messages_unchanged(self):
        messages = [{"role": "user", "content": "clean"}]
        assert sanitize_messages_surrogates(messages) is False
        assert messages[0]["content"] == "clean"

    def test_content_surrogate_sanitized(self):
        messages = [{"role": "user", "content": "bad \ud800 text"}]
        assert sanitize_messages_surrogates(messages) is True
        assert "\ud800" not in messages[0]["content"]

    def test_content_list_text_sanitized(self):
        messages = [{"role": "user", "content": [{"type": "text", "text": "bad \ud800"}]}]
        assert sanitize_messages_surrogates(messages) is True
        assert "\ud800" not in messages[0]["content"][0]["text"]

    def test_name_field_sanitized(self):
        messages = [{"role": "tool", "name": "bad\ud800name", "content": "ok"}]
        assert sanitize_messages_surrogates(messages) is True
        assert "\ud800" not in messages[0]["name"]

    def test_tool_calls_sanitized(self):
        messages = [{
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call\ud800id",
                "function": {"name": "bad\ud800fn", "arguments": '{"a":"\ud800"}'},
            }],
        }]
        assert sanitize_messages_surrogates(messages) is True
        tc = messages[0]["tool_calls"][0]
        assert "\ud800" not in tc["id"]
        assert "\ud800" not in tc["function"]["name"]
        assert "\ud800" not in tc["function"]["arguments"]

    def test_non_dict_messages_skipped(self):
        messages = ["not a dict", {"role": "user", "content": "ok"}]
        assert sanitize_messages_surrogates(messages) is False


# --- strip_non_ascii ---

class TestStripNonAscii:
    def test_ascii_only_unchanged(self):
        assert strip_non_ascii("hello 123") == "hello 123"

    def test_non_ascii_removed(self):
        assert strip_non_ascii("hello \u00e9 world") == "hello  world"

    def test_mixed_content(self):
        assert strip_non_ascii("price \u00a51000") == "price 1000"

    def test_empty_string(self):
        assert strip_non_ascii("") == ""


# --- sanitize_messages_non_ascii ---

class TestSanitizeMessagesNonAscii:
    def test_clean_messages_unchanged(self):
        messages = [{"role": "user", "content": "clean"}]
        assert sanitize_messages_non_ascii(messages) is False

    def test_content_sanitized(self):
        messages = [{"role": "user", "content": "hello \u00e9"}]
        assert sanitize_messages_non_ascii(messages) is True
        assert "\u00e9" not in messages[0]["content"]

    def test_content_list_sanitized(self):
        messages = [{"role": "user", "content": [{"type": "text", "text": "\u00e9"}]}]
        assert sanitize_messages_non_ascii(messages) is True
        assert "\u00e9" not in messages[0]["content"][0]["text"]

    def test_name_sanitized(self):
        messages = [{"role": "tool", "name": "caf\u00e9", "content": "ok"}]
        assert sanitize_messages_non_ascii(messages) is True
        assert "\u00e9" not in messages[0]["name"]

    def test_tool_call_arguments_sanitized(self):
        messages = [{
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "function": {"arguments": '{"key": "val\u00e9"}'},
            }],
        }]
        assert sanitize_messages_non_ascii(messages) is True
        assert "\u00e9" not in messages[0]["tool_calls"][0]["function"]["arguments"]


# --- sanitize_tools_non_ascii / sanitize_structure_non_ascii ---

class TestSanitizeStructureNonAscii:
    def test_clean_structure_unchanged(self):
        data = [{"name": "tool1", "input": "hello"}]
        assert sanitize_structure_non_ascii(data) is False

    def test_nested_dict_sanitized(self):
        data = {"key": "value \u00e9", "nested": {"inner": "\u00e9"}}
        assert sanitize_structure_non_ascii(data) is True
        assert all("\u00e9" not in str(v) for v in data.values())

    def test_list_sanitized(self):
        data = ["clean", "bad\u00e9", {"key": "\u00e9"}]
        assert sanitize_structure_non_ascii(data) is True
        for item in data:
            if isinstance(item, str):
                assert "\u00e9" not in item

    def test_sanitize_tools_non_ascii_delegates(self):
        tools = [{"function": {"name": "tool\u00e9"}}]
        assert sanitize_tools_non_ascii(tools) is True
        assert "\u00e9" not in tools[0]["function"]["name"]

    def test_deeply_nested_sanitized(self):
        data = {"a": [{"b": {"c": "deep\u00e9"}}]}
        assert sanitize_structure_non_ascii(data) is True
        assert "\u00e9" not in data["a"][0]["b"]["c"]
