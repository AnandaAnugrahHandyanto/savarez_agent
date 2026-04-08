"""Tests for the optional gateway response header (issue #6232).

The ``display.response_header`` config flag prepends a compact
``Model: <model> | Thinking: <level>`` line to assistant replies so that
messaging users (Telegram, Discord, Slack, etc.) can tell at a glance
which model / reasoning level produced a given reply.
"""
from __future__ import annotations

from gateway.run import GatewayRunner


def test_format_response_header_default_reasoning():
    header = GatewayRunner._format_response_header("gpt-5.4", None)
    assert header == "Model: gpt-5.4 | Thinking: default"


def test_format_response_header_none_reasoning():
    header = GatewayRunner._format_response_header(
        "claude-sonnet-4.5", {"enabled": False}
    )
    assert header == "Model: claude-sonnet-4.5 | Thinking: none"


def test_format_response_header_high_reasoning():
    header = GatewayRunner._format_response_header(
        "gpt-5.4", {"enabled": True, "effort": "high"}
    )
    assert header == "Model: gpt-5.4 | Thinking: high"


def test_format_response_header_missing_model():
    header = GatewayRunner._format_response_header(
        None, {"enabled": True, "effort": "medium"}
    )
    assert header == "Model: unknown | Thinking: medium"


def test_format_response_header_empty_model():
    header = GatewayRunner._format_response_header(
        "  ", {"enabled": True, "effort": "low"}
    )
    assert header == "Model: unknown | Thinking: low"
