"""Regression tests for Anthropic text-block invoke salvage."""

from __future__ import annotations

import json
from types import SimpleNamespace


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(name: str = "read_file"):
    return SimpleNamespace(
        type="tool_use",
        id="toolu_1",
        name=name,
        input={"path": "/tmp/structured.txt"},
    )


def _response(*blocks, stop_reason: str = "end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


def _transport():
    from agent.transports.anthropic import AnthropicTransport

    return AnthropicTransport()


def test_promotes_complete_invoke_text_block_to_tool_call():
    raw = """I'll inspect it.
<function_calls>
<invoke name="read_file">
<parameter name="path">"/tmp/example.txt"</parameter>
<parameter name="limit">20</parameter>
<parameter name="follow_symlinks">true</parameter>
</invoke>
</function_calls>"""

    result = _transport().normalize_response(_response(_text_block(raw)))

    assert result.finish_reason == "tool_calls"
    assert result.content == "I'll inspect it."
    assert result.tool_calls is not None
    assert len(result.tool_calls) == 1
    call = result.tool_calls[0]
    assert call.name == "read_file"
    assert json.loads(call.arguments) == {
        "path": "/tmp/example.txt",
        "limit": 20,
        "follow_symlinks": True,
    }


def test_salvage_strips_markup_when_invoke_is_the_only_text():
    raw = """<antml:function_calls>
<invoke name="terminal"><parameter name="command">git status --short</parameter></invoke>
</antml:function_calls>"""

    result = _transport().normalize_response(_response(_text_block(raw)))

    assert result.finish_reason == "tool_calls"
    assert result.content is None
    assert result.tool_calls is not None
    assert result.tool_calls[0].name == "terminal"
    assert json.loads(result.tool_calls[0].arguments) == {"command": "git status --short"}


def test_incomplete_invoke_text_is_not_promoted():
    raw = '<function_calls><invoke name="terminal"><parameter name="command">echo hi'

    result = _transport().normalize_response(_response(_text_block(raw)))

    assert result.finish_reason == "stop"
    assert result.tool_calls is None
    assert result.content == raw


def test_structured_tool_use_blocks_take_precedence_over_text_salvage():
    raw = """<function_calls>
<invoke name="terminal"><parameter name="command">echo wrong</parameter></invoke>
</function_calls>"""

    result = _transport().normalize_response(
        _response(_text_block(raw), _tool_use_block()),
        strip_tool_prefix=False,
    )

    assert result.finish_reason == "stop"
    assert result.content == raw
    assert result.tool_calls is not None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "toolu_1"
    assert result.tool_calls[0].name == "read_file"
    assert json.loads(result.tool_calls[0].arguments) == {"path": "/tmp/structured.txt"}
