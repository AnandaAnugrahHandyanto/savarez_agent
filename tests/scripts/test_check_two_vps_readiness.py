from __future__ import annotations

import subprocess
import sys

from scripts import check_two_vps_readiness as readiness


def test_validate_runs_both_steps(monkeypatch, capsys):
    calls = []

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=f"ok:{cmd[1]}", stderr="")

    monkeypatch.setenv("HERMES_NODE_ROLE", "executor")
    monkeypatch.setattr(readiness.subprocess, "run", fake_run)
    args = readiness.build_parser().parse_args([
        "--schema",
        "/tmp/schema.sql",
        "--peer",
        "peer.example",
        "--ports",
        "80,443",
        "--expect-role",
        "executor",
    ])

    readiness.validate(args)
    out = capsys.readouterr().out

    assert "[schema] ok:" in out
    assert "[tailnet] ok:" in out
    assert "readiness healthy" in out
    assert calls[0][0] == sys.executable
    assert calls[1][0] == sys.executable
    assert "validate_memory_schema.py" in calls[0][1]
    assert "check_tailnet_health.py" in calls[1][1]


def test_validate_reports_failure(monkeypatch, capsys):
    def fake_run(cmd, capture_output, text):
        if "validate_memory_schema.py" in cmd[1]:
            return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="schema broken")
        return subprocess.CompletedProcess(cmd, 0, stdout="healthy", stderr="")

    monkeypatch.setattr(readiness.subprocess, "run", fake_run)
    args = readiness.build_parser().parse_args(["--peer", "peer.example"])

    try:
        readiness.validate(args)
    except readiness.ValidationError as exc:
        assert "schema" in str(exc)
    else:
        raise AssertionError("expected ValidationError")

    err = capsys.readouterr().err
    assert "schema broken" in err


def test_validate_rejects_executor_role_mismatch(monkeypatch):
    monkeypatch.setenv("HERMES_NODE_ROLE", "canonical")
    args = readiness.build_parser().parse_args(["--expect-role", "executor", "--skip-schema", "--skip-tailnet"])

    try:
        readiness.validate(args)
    except readiness.ValidationError as exc:
        assert "role mismatch" in str(exc)
    else:
        raise AssertionError("expected ValidationError")


def test_validate_allows_executor_role_gate(monkeypatch, capsys):
    monkeypatch.setenv("HERMES_NODE_ROLE", "executor")

    def fake_run(cmd, capture_output, text):
        return subprocess.CompletedProcess(cmd, 0, stdout=f"ok:{cmd[1]}", stderr="")

    monkeypatch.setattr(readiness.subprocess, "run", fake_run)
    args = readiness.build_parser().parse_args(["--expect-role", "executor", "--peer", "peer.example"])

    readiness.validate(args)
    out = capsys.readouterr().out
    assert "readiness healthy" in out
