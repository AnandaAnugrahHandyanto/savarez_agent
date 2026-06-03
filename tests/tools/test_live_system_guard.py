from __future__ import annotations

import json

from tools import approval
from tools.live_system_guard import check_live_gateway_system_command


def test_guard_inactive_outside_gateway(monkeypatch):
    monkeypatch.delenv("HERMES_LIVE_SYSTEM_GUARD", raising=False)
    monkeypatch.delenv("HERMES_GATEWAY_SESSION", raising=False)
    monkeypatch.delenv("HERMES_SESSION_PLATFORM", raising=False)
    monkeypatch.delenv("INVOCATION_ID", raising=False)

    assert check_live_gateway_system_command(
        "/usr/bin/systemctl restart hermes-gateway"
    ) is None


def test_blocks_absolute_systemctl_restart_inside_gateway(monkeypatch):
    monkeypatch.setenv("HERMES_LIVE_SYSTEM_GUARD", "1")

    result = check_live_gateway_system_command(
        "/usr/bin/systemctl restart hermes-gateway"
    )

    assert result is not None
    assert result["pattern_key"] == "live_gateway_system_guard"
    assert "safe-restart" in result["message"]


def test_blocks_wrapped_systemctl_stop_inside_gateway(monkeypatch):
    monkeypatch.setenv("HERMES_LIVE_SYSTEM_GUARD", "1")

    result = check_live_gateway_system_command(
        "bash -lc 'sudo /usr/bin/systemctl stop hermes-gateway.service'"
    )

    assert result is not None
    assert "systemctl stop" in result["description"]


def test_blocks_service_restart_inside_gateway(monkeypatch):
    monkeypatch.setenv("HERMES_LIVE_SYSTEM_GUARD", "1")

    result = check_live_gateway_system_command("service hermes-gateway restart")

    assert result is not None
    assert "service hermes-gateway restart" in result["description"]


def test_blocks_process_killers_inside_gateway(monkeypatch):
    monkeypatch.setenv("HERMES_LIVE_SYSTEM_GUARD", "1")

    assert check_live_gateway_system_command("pkill -f hermes-gateway") is not None
    assert check_live_gateway_system_command("killall hermes") is not None


def test_allows_readonly_status_and_safe_helper_inside_gateway(monkeypatch):
    monkeypatch.setenv("HERMES_LIVE_SYSTEM_GUARD", "1")

    assert check_live_gateway_system_command("systemctl status hermes-gateway") is None
    assert check_live_gateway_system_command(
        "/usr/local/sbin/hermes-gateway-safe-restart"
    ) is None
    assert check_live_gateway_system_command("systemctl restart nginx") is None


def test_terminal_tool_blocks_before_execution(monkeypatch):
    monkeypatch.setenv("HERMES_LIVE_SYSTEM_GUARD", "1")
    monkeypatch.setenv("TERMINAL_ENV", "local")

    from tools import terminal_tool

    result = json.loads(
        terminal_tool.terminal_tool("/usr/bin/systemctl restart hermes-gateway")
    )

    assert result["status"] == "blocked"
    assert result["pattern_key"] == "live_gateway_system_guard"


def test_execute_code_guard_blocks_obvious_systemctl_even_when_approval_off(
    monkeypatch,
):
    monkeypatch.setenv("HERMES_LIVE_SYSTEM_GUARD", "1")
    monkeypatch.setattr(approval, "_get_approval_mode", lambda: "off")

    result = approval.check_execute_code_guard(
        "import subprocess\n"
        "subprocess.run(['/usr/bin/systemctl', 'restart', 'hermes-gateway'])",
        "local",
    )

    assert result["approved"] is False
    assert result["pattern_key"] == "live_gateway_system_guard"


def test_execute_code_guard_allows_isolated_backends(monkeypatch):
    monkeypatch.setenv("HERMES_LIVE_SYSTEM_GUARD", "1")

    result = approval.check_execute_code_guard(
        "import subprocess\n"
        "subprocess.run(['/usr/bin/systemctl', 'restart', 'hermes-gateway'])",
        "docker",
    )

    assert result["approved"] is True
