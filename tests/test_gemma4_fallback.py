"""Unit tests for the Gemma-4 content fallback (agent/gemma4_fallback.py).

Pure-logic tests — no agent runtime, no network, no GPU. Run with:
    python -m pytest tests/test_gemma4_fallback.py -q
or standalone:
    python tests/test_gemma4_fallback.py
"""
import json
from types import SimpleNamespace

import pytest

from agent.gemma4_fallback import (
    _gemma_args_to_json,
    apply_gemma_fallback,
    extract_gemma_reasoning,
    parse_gemma_tool_calls,
    strip_gemma_markup,
)

S = '<|"|>'  # string delimiter


# ── _gemma_args_to_json ──────────────────────────────────────────────
class TestArgsToJson:
    def test_empty(self):
        assert json.loads(_gemma_args_to_json("")) == {}

    def test_single_string(self):
        body = f"command:{S}ls -la{S}"
        assert json.loads(_gemma_args_to_json(body)) == {"command": "ls -la"}

    def test_string_and_number(self):
        body = f"command:{S}ls{S},timeout:30"
        assert json.loads(_gemma_args_to_json(body)) == {"command": "ls", "timeout": 30}

    def test_boolean(self):
        body = f"name:{S}x{S},verbose:true,quiet:false"
        assert json.loads(_gemma_args_to_json(body)) == {
            "name": "x", "verbose": True, "quiet": False,
        }

    def test_nested_object_bare_keys(self):
        # escape_keys=False propagates: nested keys are ALSO bare.
        body = f"opts:{{depth:2,label:{S}deep{S}}}"
        assert json.loads(_gemma_args_to_json(body)) == {
            "opts": {"depth": 2, "label": "deep"},
        }

    def test_list_of_strings(self):
        body = f"tags:[{S}a{S},{S}b{S}]"
        assert json.loads(_gemma_args_to_json(body)) == {"tags": ["a", "b"]}

    def test_list_of_objects(self):
        body = f"items:[{{x:1}},{{y:2}}]"
        assert json.loads(_gemma_args_to_json(body)) == {
            "items": [{"x": 1}, {"y": 2}],
        }

    def test_string_value_with_colon(self):
        body = f"url:{S}http://example.com:8080/p{S}"
        assert json.loads(_gemma_args_to_json(body)) == {
            "url": "http://example.com:8080/p",
        }

    def test_string_value_with_comma_and_colon_not_mangled(self):
        # The danger case: a literal that contains ",key:" must NOT be
        # interpreted as a structural key (the per-segment quoting guards this).
        body = f"note:{S}a,b:c{S},n:1"
        assert json.loads(_gemma_args_to_json(body)) == {"note": "a,b:c", "n": 1}

    def test_string_value_with_embedded_quote(self):
        body = f'msg:{S}he said "hi"{S}'
        assert json.loads(_gemma_args_to_json(body)) == {"msg": 'he said "hi"'}

    def test_string_value_with_braces(self):
        body = f"tpl:{S}{{a}}{S}"
        assert json.loads(_gemma_args_to_json(body)) == {"tpl": "{a}"}

    def test_hyphen_dot_key(self):
        body = f"content-type:{S}text/plain{S},a.b:1"
        assert json.loads(_gemma_args_to_json(body)) == {
            "content-type": "text/plain", "a.b": 1,
        }

    def test_none_to_null(self):
        body = "value:None"
        assert json.loads(_gemma_args_to_json(body)) == {"value": None}


# ── parse_gemma_tool_calls ───────────────────────────────────────────
class TestParseToolCalls:
    def test_none(self):
        calls, cleaned = parse_gemma_tool_calls("just a normal reply")
        assert calls == []
        assert cleaned == "just a normal reply"

    def test_single(self):
        c = f"<|tool_call>call:bash{{command:{S}ls{S}}}<tool_call|>"
        calls, cleaned = parse_gemma_tool_calls(c)
        assert len(calls) == 1
        assert calls[0].type == "function"
        assert calls[0].function.name == "bash"
        assert json.loads(calls[0].function.arguments) == {"command": "ls"}
        assert cleaned.strip() == ""

    def test_multiple(self):
        c = (
            f"<|tool_call>call:f{{a:1}}<tool_call|>"
            f"<|tool_call>call:g{{b:2}}<tool_call|>"
        )
        calls, _ = parse_gemma_tool_calls(c)
        assert [k.function.name for k in calls] == ["f", "g"]
        assert json.loads(calls[1].function.arguments) == {"b": 2}

    def test_nested_braces_not_truncated(self):
        c = f"<|tool_call>call:f{{opts:{{b:1}}}}<tool_call|>"
        calls, _ = parse_gemma_tool_calls(c)
        assert json.loads(calls[0].function.arguments) == {"opts": {"b": 1}}

    def test_surrounding_text_preserved(self):
        c = f"Sure!<|tool_call>call:f{{a:1}}<tool_call|>done"
        calls, cleaned = parse_gemma_tool_calls(c)
        assert len(calls) == 1
        assert "Sure!" in cleaned and "done" in cleaned
        assert "<|tool_call>" not in cleaned

    def test_unterminated_tail_stripped(self):
        c = f"text<|tool_call>call:f{{a:1"  # truncated, no closer
        calls, cleaned = parse_gemma_tool_calls(c)
        assert calls == []  # no COMPLETE block
        assert "<|tool_call>" not in cleaned
        assert cleaned == "text"

    def test_malformed_args_fallback_to_empty(self):
        # Name parses, args are garbage -> empty args, tool still recovered.
        c = f"<|tool_call>call:f{{:::}}<tool_call|>"
        calls, _ = parse_gemma_tool_calls(c)
        assert len(calls) == 1
        assert calls[0].function.name == "f"
        assert json.loads(calls[0].function.arguments) == {}


# ── extract_gemma_reasoning ──────────────────────────────────────────
class TestExtractReasoning:
    def test_none(self):
        r, cleaned = extract_gemma_reasoning("plain answer")
        assert r is None
        assert cleaned == "plain answer"

    def test_single_with_label(self):
        c = "<|channel>thought\nI should add two numbers.\n<channel|>The answer is 4."
        r, cleaned = extract_gemma_reasoning(c)
        assert r == "I should add two numbers."
        assert "<|channel>" not in cleaned
        assert "The answer is 4." in cleaned

    def test_multiple(self):
        c = "<|channel>thought\nstep one\n<channel|>x<|channel>thought\nstep two\n<channel|>y"
        r, _ = extract_gemma_reasoning(c)
        assert "step one" in r and "step two" in r

    def test_unterminated_tail_stripped(self):
        c = "answer<|channel>thought\nrambling without a close"
        r, cleaned = extract_gemma_reasoning(c)
        assert r is None  # no complete channel span -> nothing captured
        assert cleaned == "answer"


# ── strip_gemma_markup ───────────────────────────────────────────────
class TestStripMarkup:
    def test_noop_clean(self):
        assert strip_gemma_markup("nothing special") == "nothing special"

    def test_strips_toolcall_and_channel(self):
        c = (
            f"<|channel>thought\nthinking\n<channel|>"
            f"Hello <|tool_call>call:f{{a:1}}<tool_call|> world"
        )
        out = strip_gemma_markup(c)
        assert "<|" not in out and "|>" not in out
        assert "Hello" in out and "world" in out

    def test_strips_residual_string_delimiter(self):
        assert "<|" not in strip_gemma_markup(f"leftover {S}oops{S} text")


# ── apply_gemma_fallback (object mutation) ───────────────────────────
class TestApplyFallback:
    def test_recovers_and_mutates(self):
        msg = SimpleNamespace(
            content=f"<|tool_call>call:bash{{command:{S}ls{S}}}<tool_call|>",
            tool_calls=None,
        )
        assert apply_gemma_fallback(msg) is True
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].function.name == "bash"
        assert "<|tool_call>" not in (msg.content or "")

    def test_noop_when_tool_calls_present(self):
        existing = [SimpleNamespace(id="x", type="function",
                                    function=SimpleNamespace(name="g", arguments="{}"))]
        msg = SimpleNamespace(content="<|tool_call>call:f{a:1}<tool_call|>",
                              tool_calls=existing)
        assert apply_gemma_fallback(msg) is False
        assert msg.tool_calls is existing  # untouched

    def test_noop_when_no_markup(self):
        msg = SimpleNamespace(content="normal answer", tool_calls=None)
        assert apply_gemma_fallback(msg) is False

    def test_leaves_channel_for_reasoning_layer(self):
        msg = SimpleNamespace(
            content=f"<|channel>thought\nx\n<channel|><|tool_call>call:f{{a:1}}<tool_call|>",
            tool_calls=None,
        )
        assert apply_gemma_fallback(msg) is True
        # tool_call markup removed, channel markup preserved for next layer
        assert "<|tool_call>" not in msg.content
        assert "<|channel>" in msg.content


# ── realistic leaked blob (mirrors the Element screenshot) ───────────
def test_realistic_patch_leak():
    blob = (
        "<|channel>thought\nI'll patch the file.\n<channel|>"
        f"<|tool_call>call:patch{{path:{S}/tmp/a.py{S},"
        f"content:{S}print('hi'){S},mode:{S}overwrite{S}}}<tool_call|>"
    )
    msg = SimpleNamespace(content=blob, tool_calls=None)
    assert apply_gemma_fallback(msg) is True
    tc = msg.tool_calls[0]
    assert tc.function.name == "patch"
    args = json.loads(tc.function.arguments)
    assert args == {"path": "/tmp/a.py", "content": "print('hi')", "mode": "overwrite"}
    # reasoning extractable, final content fully clean
    reasoning, _ = extract_gemma_reasoning(msg.content)
    assert reasoning == "I'll patch the file."
    assert strip_gemma_markup(msg.content).strip() == ""


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
