"""Tests for read-only quick chat utility tools."""

import json

from tools.safe_tools import safe_calculator_tool, safe_time_tool


def test_safe_calculator_evaluates_arithmetic_without_eval_surface():
    result = json.loads(safe_calculator_tool("(2 + 3) * 4"))

    assert result == {"ok": True, "expression": "(2 + 3) * 4", "result": 20}


def test_safe_calculator_rejects_function_calls():
    result = json.loads(safe_calculator_tool("__import__('os').system('id')"))

    assert result["ok"] is False
    assert "Unsupported" in result["error"] or "Only" in result["error"]


def test_safe_time_returns_requested_timezone():
    result = json.loads(safe_time_tool("UTC"))

    assert result["ok"] is True
    assert result["timezone"] == "UTC"
    assert result["iso"].endswith("+00:00")
    assert isinstance(result["unix"], int)


def test_safe_time_rejects_unknown_timezone():
    result = json.loads(safe_time_tool("Not/AZone"))

    assert result == {"ok": False, "error": "Unknown timezone: Not/AZone"}
