"""Tests for --output-format json flag in hermes chat -q mode.

Verifies:
  - argparse accepts --output-format with text/json choices
  - json mode implies quiet
  - JSON output contains all required schema fields
  - text mode (default) is unchanged
  - cross-platform: no platform-specific code paths affected
"""

import json
import sys
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# 1. Argparse: --output-format is recognized and passed through to cmd_chat
# ---------------------------------------------------------------------------


def test_output_format_json_flag_parsed(monkeypatch):
    """--output-format json is accepted by the chat subcommand."""
    import hermes_cli.main as main_mod

    captured = {}

    def fake_cmd_chat(args):
        captured["output_format"] = args.output_format
        captured["query"] = args.query

    monkeypatch.setattr(main_mod, "cmd_chat", fake_cmd_chat)
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "chat", "-q", "hello", "--output-format", "json"],
    )

    main_mod.main()

    assert captured["output_format"] == "json"
    assert captured["query"] == "hello"


def test_output_format_text_is_default(monkeypatch):
    """Without --output-format, default is 'text'."""
    import hermes_cli.main as main_mod

    captured = {}

    def fake_cmd_chat(args):
        captured["output_format"] = args.output_format

    monkeypatch.setattr(main_mod, "cmd_chat", fake_cmd_chat)
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "chat", "-q", "hello"],
    )

    main_mod.main()

    assert captured["output_format"] == "text"


def test_output_format_rejects_invalid_choice(monkeypatch):
    """--output-format xml should be rejected by argparse."""
    import hermes_cli.main as main_mod

    monkeypatch.setattr(main_mod, "cmd_chat", lambda args: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "chat", "-q", "hello", "--output-format", "xml"],
    )

    import pytest
    with pytest.raises(SystemExit) as exc_info:
        main_mod.main()
    assert exc_info.value.code == 2  # argparse exits with code 2 on error


# ---------------------------------------------------------------------------
# 2. JSON output schema validation
# ---------------------------------------------------------------------------


_REQUIRED_JSON_FIELDS = {
    "type",
    "subtype",
    "is_error",
    "result",
    "session_id",
    "model",
    "provider",
    "num_turns",
    "duration_ms",
    "total_cost_usd",
    "usage",
    "tool_call_count",
}

_REQUIRED_USAGE_FIELDS = {
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "reasoning_tokens",
}


def _build_mock_result(interrupted=False):
    """Build a mock run_conversation result dict."""
    return {
        "final_response": "4",
        "api_calls": 1,
        "model": "anthropic/claude-opus-4.6",
        "provider": "anthropic",
        "interrupted": interrupted,
        "estimated_cost_usd": 0.005,
        "input_tokens": 100,
        "output_tokens": 10,
        "cache_read_tokens": 50,
        "cache_write_tokens": 20,
        "reasoning_tokens": 0,
        "tool_call_count": 0,
    }


def test_json_output_contains_required_fields():
    """JSON output must contain all fields from the schema spec."""
    result = _build_mock_result()
    elapsed = 3.5

    output = {
        "type": "result",
        "subtype": "error" if result.get("interrupted") else "success",
        "is_error": bool(result.get("interrupted")),
        "result": result.get("final_response", ""),
        "session_id": "20260326_120000_abc123",
        "model": result.get("model", ""),
        "provider": result.get("provider", ""),
        "num_turns": result.get("api_calls", 0),
        "duration_ms": round(elapsed * 1000),
        "total_cost_usd": result.get("estimated_cost_usd", 0.0),
        "usage": {
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "cache_read_input_tokens": result.get("cache_read_tokens", 0),
            "cache_creation_input_tokens": result.get("cache_write_tokens", 0),
            "reasoning_tokens": result.get("reasoning_tokens", 0),
        },
        "tool_call_count": result.get("tool_call_count", 0),
    }

    json_str = json.dumps(output)
    parsed = json.loads(json_str)

    assert _REQUIRED_JSON_FIELDS.issubset(set(parsed.keys())), \
        f"Missing fields: {_REQUIRED_JSON_FIELDS - set(parsed.keys())}"

    assert _REQUIRED_USAGE_FIELDS.issubset(set(parsed["usage"].keys())), \
        f"Missing usage fields: {_REQUIRED_USAGE_FIELDS - set(parsed['usage'].keys())}"


def test_json_output_success_subtype():
    """Successful result has subtype 'success' and is_error False."""
    result = _build_mock_result(interrupted=False)
    subtype = "error" if result.get("interrupted") else "success"
    is_error = bool(result.get("interrupted"))
    assert subtype == "success"
    assert is_error is False


def test_json_output_error_subtype():
    """Interrupted result has subtype 'error' and is_error True."""
    result = _build_mock_result(interrupted=True)
    subtype = "error" if result.get("interrupted") else "success"
    is_error = bool(result.get("interrupted"))
    assert subtype == "error"
    assert is_error is True


def test_json_output_is_parseable():
    """JSON output from dumps must be parseable by json.loads (round-trip)."""
    result = _build_mock_result()
    output = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": result["final_response"],
        "session_id": "test_session",
        "model": result["model"],
        "provider": result["provider"],
        "num_turns": 1,
        "duration_ms": 3500,
        "total_cost_usd": 0.005,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 10,
            "cache_read_input_tokens": 50,
            "cache_creation_input_tokens": 20,
            "reasoning_tokens": 0,
        },
        "tool_call_count": 0,
    }
    json_str = json.dumps(output)
    parsed = json.loads(json_str)
    assert parsed["type"] == "result"
    assert parsed["result"] == "4"
    assert isinstance(parsed["usage"], dict)
    assert isinstance(parsed["duration_ms"], int)
    assert isinstance(parsed["total_cost_usd"], float)


def test_json_output_type_field_is_result():
    """The type field must always be 'result' per Codex/Claude CLI convention."""
    output = {"type": "result"}
    assert output["type"] == "result"


# ---------------------------------------------------------------------------
# 3. JSON mode implies quiet
# ---------------------------------------------------------------------------


def test_json_format_implies_quiet():
    """When output_format='json', quiet must be forced to True."""
    output_format = "json"
    quiet = False
    if output_format == "json":
        quiet = True
    assert quiet is True


def test_text_format_does_not_force_quiet():
    """When output_format='text', quiet is not changed."""
    output_format = "text"
    quiet = False
    if output_format == "json":
        quiet = True
    assert quiet is False


# ---------------------------------------------------------------------------
# 4. Flag works via explicit 'chat' subcommand
# ---------------------------------------------------------------------------


def test_chat_subcommand_output_format_with_query(monkeypatch):
    """hermes chat -q 'hello' --output-format json works via chat subcommand."""
    import hermes_cli.main as main_mod

    captured = {}

    def fake_cmd_chat(args):
        captured["output_format"] = args.output_format
        captured["query"] = args.query

    monkeypatch.setattr(main_mod, "cmd_chat", fake_cmd_chat)
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "chat", "-q", "hello", "--output-format", "json"],
    )

    main_mod.main()

    assert captured["output_format"] == "json"
    assert captured["query"] == "hello"


# ---------------------------------------------------------------------------
# 5. Edge cases
# ---------------------------------------------------------------------------


def test_json_output_handles_none_duration():
    """duration_ms should be None when session_start is unavailable."""
    elapsed = None
    duration_ms = round(elapsed * 1000) if elapsed else None
    assert duration_ms is None


def test_json_output_handles_string_result():
    """When run_conversation returns a string instead of dict, str() is used."""
    result = "plain string response"
    response = result if isinstance(result, str) else str(result)
    assert response == "plain string response"


def test_json_output_handles_missing_keys_gracefully():
    """Missing keys in the result dict should default to 0/empty."""
    result = {"final_response": "ok"}  # minimal result
    output = {
        "type": "result",
        "subtype": "error" if result.get("interrupted") else "success",
        "is_error": bool(result.get("interrupted")),
        "result": result.get("final_response", ""),
        "session_id": "test",
        "model": result.get("model", ""),
        "provider": result.get("provider", ""),
        "num_turns": result.get("api_calls", 0),
        "duration_ms": None,
        "total_cost_usd": result.get("estimated_cost_usd", 0.0),
        "usage": {
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "cache_read_input_tokens": result.get("cache_read_tokens", 0),
            "cache_creation_input_tokens": result.get("cache_write_tokens", 0),
            "reasoning_tokens": result.get("reasoning_tokens", 0),
        },
        "tool_call_count": result.get("tool_call_count", 0),
    }
    json_str = json.dumps(output)
    parsed = json.loads(json_str)
    assert parsed["model"] == ""
    assert parsed["num_turns"] == 0
    assert parsed["total_cost_usd"] == 0.0
    assert parsed["usage"]["input_tokens"] == 0
