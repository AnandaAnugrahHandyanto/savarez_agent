"""Unit tests for tool_eval/scorer.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import pytest
from tool_eval.scorer import (
    TestResult,
    _safe_first_choice,
    _extract_tool_calls,
    _has_text_content,
    _text_content,
    _is_infra_error,
)


# --- _safe_first_choice ---

def test_safe_first_choice_normal():
    raw = {"choices": [{"message": {"content": "hello"}}]}
    assert _safe_first_choice(raw) == {"message": {"content": "hello"}}


def test_safe_first_choice_null_choices():
    assert _safe_first_choice({"choices": None}) is None


def test_safe_first_choice_empty_list():
    assert _safe_first_choice({"choices": []}) is None


def test_safe_first_choice_missing_key():
    assert _safe_first_choice({}) is None


def test_safe_first_choice_not_dict():
    assert _safe_first_choice("not a dict") is None


# --- _extract_tool_calls ---

def _make_tool_response(name: str, args: dict) -> dict:
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args)
                    }
                }]
            }
        }]
    }


def test_extract_tool_calls_standard_shape():
    raw = _make_tool_response("terminal", {"command": "ls"})
    calls = _extract_tool_calls(raw)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "terminal"
    assert calls[0]["function"]["arguments"]["command"] == "ls"


def test_extract_tool_calls_empty_when_null_choices():
    raw = {"choices": None, "error": {"message": "rate limit"}}
    assert _extract_tool_calls(raw) == []


def test_extract_tool_calls_empty_when_no_tools():
    raw = {"choices": [{"message": {"content": "hello", "tool_calls": None}}]}
    assert _extract_tool_calls(raw) == []


def test_extract_tool_calls_multiple():
    raw = {
        "choices": [{
            "message": {
                "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "todo", "arguments": '{"todos": []}'}},
                    {"id": "c2", "type": "function", "function": {"name": "memory", "arguments": '{"action": "add", "target": "user"}'}},
                ]
            }
        }]
    }
    calls = _extract_tool_calls(raw)
    assert len(calls) == 2
    assert calls[0]["function"]["name"] == "todo"
    assert calls[1]["function"]["name"] == "memory"


def test_extract_tool_calls_malformed_json_args():
    raw = {
        "choices": [{
            "message": {
                "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "terminal", "arguments": "NOT JSON"}}]
            }
        }]
    }
    calls = _extract_tool_calls(raw)
    assert len(calls) == 1
    assert calls[0]["function"]["arguments"] == {}


# --- _has_text_content / _text_content ---

def test_text_content_extracts_string():
    raw = {"choices": [{"message": {"content": "Sure, I can help!"}}]}
    assert _text_content(raw) == "Sure, I can help!"


def test_text_content_empty_when_null():
    raw = {"choices": [{"message": {"content": None}}]}
    assert _text_content(raw) == ""


def test_has_text_content_true():
    raw = {"choices": [{"message": {"content": "hello"}}]}
    assert _has_text_content(raw) is True


def test_has_text_content_false_for_tool_call():
    raw = {"choices": [{"message": {"content": None, "tool_calls": [{"function": {"name": "todo"}}]}}]}
    assert _has_text_content(raw) is False


# --- _is_infra_error ---

def test_is_infra_error_rate_limit():
    raw = {"choices": None, "error": {"message": "rate limit exceeded", "code": 429}}
    assert _is_infra_error(raw) is True


def test_is_infra_error_502():
    raw = {"choices": None, "error": {"message": "Bad Gateway", "code": "502"}}
    assert _is_infra_error(raw) is True


def test_is_infra_error_all_null():
    raw = {"id": None, "choices": None, "model": None}
    assert _is_infra_error(raw) is True


def test_is_infra_error_false_for_normal():
    raw = {"choices": [{"message": {"content": "hello"}}], "id": "chatcmpl-123"}
    assert _is_infra_error(raw) is False


def test_is_infra_error_false_for_tool_call():
    raw = _make_tool_response("terminal", {"command": "ls"})
    raw["id"] = "chatcmpl-abc"
    assert _is_infra_error(raw) is False
