from __future__ import annotations

import subprocess
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_tailnet_health.py"
MODULE_SPEC = spec_from_file_location("check_tailnet_health_test_module", MODULE_PATH)
assert MODULE_SPEC and MODULE_SPEC.loader
check_tailnet_health = module_from_spec(MODULE_SPEC)
import sys

sys.modules[MODULE_SPEC.name] = check_tailnet_health
MODULE_SPEC.loader.exec_module(check_tailnet_health)


class TestParsePorts:
    def test_parse_ports_ignores_whitespace_and_blanks(self):
        assert check_tailnet_health.parse_ports("3000, 8642,, 9119 ,") == [3000, 8642, 9119]


class TestHealthChecks:
    def test_check_dns_reports_first_line_on_success(self, monkeypatch):
        def fake_run(cmd, timeout=20):
            assert cmd == ["getent", "hosts", "hermes-vps-2.tailfdd900.ts.net"]
            return subprocess.CompletedProcess(cmd, 0, stdout="100.64.0.10 hermes-vps-2\n", stderr="")

        monkeypatch.setattr(check_tailnet_health, "run", fake_run)

        result = check_tailnet_health.check_dns("hermes-vps-2.tailfdd900.ts.net")

        assert result.ok is True
        assert result.detail == "100.64.0.10 hermes-vps-2"

    def test_check_tailscale_ping_accepts_pong_output(self, monkeypatch):
        def fake_run(cmd, timeout=20):
            assert cmd == ["tailscale", "ping", "hermes-vps-2.tailfdd900.ts.net"]
            return subprocess.CompletedProcess(cmd, 0, stdout="pong from hermes-vps-2 via 100.64.0.10\n", stderr="")

        monkeypatch.setattr(check_tailnet_health, "run", fake_run)

        result = check_tailnet_health.check_tailscale_ping("hermes-vps-2.tailfdd900.ts.net")

        assert result.ok is True
        assert result.detail == "pong from hermes-vps-2 via 100.64.0.10"

    def test_check_port_binding_flags_public_bindings(self, monkeypatch):
        def fake_run(cmd, timeout=20):
            assert cmd == ["ss", "-ltn"]
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=(
                    "State  Recv-Q Send-Q Local Address:Port Peer Address:Port\n"
                    "LISTEN 0      128    127.0.0.1:3000   0.0.0.0:*\n"
                    "LISTEN 0      128    0.0.0.0:8642     0.0.0.0:*\n"
                ),
                stderr="",
            )

        monkeypatch.setattr(check_tailnet_health, "run", fake_run)

        results = check_tailnet_health.check_port_binding([3000, 8642, 9119])

        assert [(r.name, r.ok) for r in results] == [
            ("port_3000", True),
            ("port_8642", False),
            ("port_9119", True),
        ]
        assert results[1].detail == "unsafe bind(s): 0.0.0.0:8642"
        assert results[2].detail == "not listening"

    def test_main_returns_degraded_when_any_check_fails(self, monkeypatch, capsys):
        monkeypatch.setattr(check_tailnet_health, "check_dns", lambda peer: check_tailnet_health.CheckResult("dns", True, "ok"))
        monkeypatch.setattr(check_tailnet_health, "check_tailscale_ping", lambda peer: check_tailnet_health.CheckResult("tailscale_ping", False, "no pong"))
        monkeypatch.setattr(
            check_tailnet_health,
            "check_port_binding",
            lambda ports: [check_tailnet_health.CheckResult("port_3000", True, "not listening")],
        )
        monkeypatch.setattr(check_tailnet_health, "parse_ports", lambda raw: [3000])
        monkeypatch.setattr(check_tailnet_health.sys, "argv", ["check_tailnet_health.py"])

        rc = check_tailnet_health.main()
        out = capsys.readouterr().out

        assert rc == 2
        assert "degraded" in out
        assert "tailscale_ping: fail" in out
