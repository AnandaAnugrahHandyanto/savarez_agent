"""LlmClient unit tests — prompt caching block layout + JSON parsing."""

from __future__ import annotations

import json

import pytest

from hermes_agent.loops.llm_client import LlmClient


class _RecordingMessages:
    def __init__(self, response_text):
        self.response_text = response_text
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        block = type("Block", (), {"text": self.response_text})()
        resp = type("Resp", (), {"content": [block], "usage": {}})()
        return resp


class _RecordingAnthropic:
    def __init__(self, response_text):
        self.messages = _RecordingMessages(response_text)


def test_call_json_marks_long_context_blocks_as_cached():
    fake = _RecordingAnthropic(json.dumps({"intent": "maintenance"}))
    llm = LlmClient(client=fake, model="m")

    parsed, call = llm.call_json(
        cached_context_blocks=["LONG SOP TEXT", "COMPANY CONTEXT"],
        instruction="Short instruction",
        user_payload="hello",
    )

    assert parsed == {"intent": "maintenance"}
    kwargs = fake.messages.last_kwargs
    assert kwargs["model"] == "m"

    blocks = kwargs["system"]
    # First two blocks are cached, last is not.
    assert blocks[0]["text"] == "LONG SOP TEXT"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert blocks[1]["text"] == "COMPANY CONTEXT"
    assert blocks[1]["cache_control"] == {"type": "ephemeral"}
    assert blocks[2]["text"] == "Short instruction"
    assert "cache_control" not in blocks[2]


def test_call_json_increments_call_count():
    fake = _RecordingAnthropic(json.dumps({"x": 1}))
    llm = LlmClient(client=fake, model="m")
    assert llm.call_count == 0
    llm.call_json(cached_context_blocks=["a"], instruction="i", user_payload="u")
    llm.call_json(cached_context_blocks=["a"], instruction="i", user_payload="u")
    assert llm.call_count == 2


def test_call_json_strips_code_fences():
    fenced = "```json\n{\"intent\": \"payment\"}\n```"
    fake = _RecordingAnthropic(fenced)
    llm = LlmClient(client=fake, model="m")
    parsed, _ = llm.call_json(
        cached_context_blocks=["a"], instruction="i", user_payload="u"
    )
    assert parsed == {"intent": "payment"}


def test_call_json_raises_on_non_json():
    fake = _RecordingAnthropic("definitely not json")
    llm = LlmClient(client=fake, model="m")
    with pytest.raises(ValueError, match="non-JSON"):
        llm.call_json(cached_context_blocks=["a"], instruction="i", user_payload="u")


def test_call_json_raises_on_non_object_json():
    fake = _RecordingAnthropic("[1, 2, 3]")
    llm = LlmClient(client=fake, model="m")
    with pytest.raises(ValueError, match="expected object"):
        llm.call_json(cached_context_blocks=["a"], instruction="i", user_payload="u")


def test_empty_context_blocks_are_dropped():
    fake = _RecordingAnthropic(json.dumps({"ok": True}))
    llm = LlmClient(client=fake, model="m")
    llm.call_json(
        cached_context_blocks=["", "real block"],
        instruction="i",
        user_payload="u",
    )
    blocks = fake.messages.last_kwargs["system"]
    # Empty block should NOT be sent. We expect: real-block (cached) + instruction.
    texts = [b["text"] for b in blocks]
    assert texts == ["real block", "i"]
