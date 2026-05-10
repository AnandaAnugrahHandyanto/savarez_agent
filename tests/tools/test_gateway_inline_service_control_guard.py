"""Regression tests for gateway-origin inline service-control guard."""

import json

from tools.terminal_tool import _gateway_inline_service_control_block, terminal_tool


def test_gateway_process_blocks_hermes_gateway_start(monkeypatch):
    monkeypatch.setenv("HERMES_GATEWAY_PROCESS", "1")

    message = _gateway_inline_service_control_block("hermes gateway start --approved || hermes gateway start", "local")

    assert message is not None
    assert "gateway-origin sessions" in message
    assert "out-of-band" in message


def test_gateway_process_blocks_launchctl_kickstart(monkeypatch):
    monkeypatch.setenv("HERMES_GATEWAY_PROCESS", "1")

    message = _gateway_inline_service_control_block(
        "launchctl kickstart -k gui/501/ai.hermes.gateway", "local"
    )

    assert message is not None
    assert "gateway-origin sessions" in message


def test_non_gateway_process_does_not_block_status_like_command(monkeypatch):
    monkeypatch.delenv("HERMES_GATEWAY_PROCESS", raising=False)
    monkeypatch.delenv("HERMES_GATEWAY_SESSION", raising=False)
    monkeypatch.delenv("HERMES_GATEWAY_INLINE_SERVICE_CONTROL", raising=False)

    assert _gateway_inline_service_control_block("hermes gateway status", "local") is None


def test_terminal_tool_blocks_even_with_force(monkeypatch):
    monkeypatch.setenv("HERMES_GATEWAY_PROCESS", "1")
    monkeypatch.setenv("TERMINAL_ENV", "local")

    result = json.loads(
        terminal_tool(
            "hermes gateway start --approved || hermes gateway start",
            force=True,
            task_id="gateway-inline-service-control-test",
        )
    )

    assert result["status"] == "blocked"
    assert result["exit_code"] == -1
    assert "gateway-origin sessions" in result["error"]
