from pathlib import Path

from agent.transports.content_tool_calls import (
    FORMATS,
    RawCall,
    _deterministic_call_id,
)

FIX = Path("tests/fixtures/content_tool_calls")


def test_rawcall_is_frozen():
    rc = RawCall(name="web_search", arguments={"q": "x"}, span="<tool_call>...</tool_call>")
    assert rc.name == "web_search"


def test_deterministic_id_stable_and_prefixed():
    a = _deterministic_call_id("web_search", '{"q":"x"}', 0)
    b = _deterministic_call_id("web_search", '{"q":"x"}', 0)
    assert a == b
    assert a.startswith("call_")
    assert len(a) == len("call_") + 12


def test_registry_registered_after_import():
    names = {f.name for f in FORMATS}
    assert {"tool_call_json", "bare_json_object", "kimi_k2", "minimax_invoke", "gemma_function"} <= names


def test_tool_call_json_extracts():
    from agent.transports.content_tool_calls import find_tool_call_json

    calls = find_tool_call_json((FIX / "tool_call_json.txt").read_text())
    assert len(calls) == 1
    assert calls[0].name == "web_search"
    assert calls[0].arguments == {"query": "hermes nousresearch"}


def test_tool_call_json_ignores_prose():
    from agent.transports.content_tool_calls import find_tool_call_json

    assert find_tool_call_json("talking about <tool_call> tags") == []


def test_bare_json_whole_content_promotes():
    from agent.transports.content_tool_calls import find_bare_json_object

    calls = find_bare_json_object((FIX / "bare_json_object.txt").read_text())
    assert len(calls) == 1
    assert calls[0].name == "web_search"
    assert calls[0].arguments == {"query": "北京今天的天气"}


def test_bare_json_embedded_rejected():
    from agent.transports.content_tool_calls import find_bare_json_object

    assert find_bare_json_object('here: {"name":"web_search","arguments":{}} ok') == []


def test_bare_json_extra_keys_rejected():
    from agent.transports.content_tool_calls import find_bare_json_object

    assert find_bare_json_object('{"name":"web_search","arguments":{},"description":"x"}') == []


def test_bare_json_oversized_rejected():
    from agent.transports.content_tool_calls import find_bare_json_object

    assert find_bare_json_object('{"name":"web_search","arguments":{"q":"' + "x" * 50000 + '"}}') == []


def test_kimi_k2_extracts():
    from agent.transports.content_tool_calls import find_kimi_k2

    calls = find_kimi_k2((FIX / "kimi_k2_tokens.txt").read_text())
    assert len(calls) == 1
    assert calls[0].name == "web_search"
    assert calls[0].arguments == {"query": "hermes nousresearch"}


def test_kimi_k2_absent_returns_empty():
    from agent.transports.content_tool_calls import find_kimi_k2

    assert find_kimi_k2("normal answer") == []
