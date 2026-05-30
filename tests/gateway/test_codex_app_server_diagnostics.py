from __future__ import annotations

import signal

from gateway.codex_app_server_diagnostics import (
    ProcessInfo,
    build_report,
    is_hermes_codex_app_server_command,
    kill_stale_codex,
    threshold_status,
)


HERMES_BIN = "/home/jenny/.hermes/node/bin/codex"
HERMES_NPM_BIN = (
    "/home/jenny/.hermes/node/lib/node_modules/@openai/codex/dist/bin/codex"
)


def proc(pid: int, ppid: int, cmdline: list[str], rss_kb: int = 0) -> ProcessInfo:
    return ProcessInfo(pid=pid, ppid=ppid, cmdline=tuple(cmdline), rss_kb=rss_kb)


def test_exact_command_matching_accepts_only_hermes_codex_app_server_family():
    assert is_hermes_codex_app_server_command([HERMES_BIN, "app-server"])
    assert is_hermes_codex_app_server_command([HERMES_NPM_BIN, "app-server"])

    assert not is_hermes_codex_app_server_command([HERMES_BIN, "exec", "echo hi"])
    assert not is_hermes_codex_app_server_command(["codex", "app-server"])
    assert not is_hermes_codex_app_server_command(["node", HERMES_BIN, "app-server"])
    assert not is_hermes_codex_app_server_command(["ffmpeg", "-i", "x"])
    assert not is_hermes_codex_app_server_command(["npm", "run", "dev"])
    assert not is_hermes_codex_app_server_command(["/usr/bin/node", "server.js"])


def test_stale_classification_uses_descendant_tree_not_generic_codex_names():
    processes = [
        proc(100, 1, ["python", "-m", "gateway.run"]),
        proc(101, 100, ["bash", "-lc", "wrapper"]),
        proc(102, 101, [HERMES_BIN, "app-server"], rss_kb=5000),
        proc(200, 1, [HERMES_BIN, "app-server"], rss_kb=9000),
        proc(300, 1, ["codex", "app-server"], rss_kb=12000),
        proc(301, 1, ["ffmpeg", "-i", "render.mp4"], rss_kb=15000),
    ]

    report = build_report(processes, gateway_pid=100)

    assert [p.pid for p in report.direct_children] == [101]
    assert [p.pid for p in report.current_gateway_codex] == [102]
    assert [p.pid for p in report.stale_codex] == [200]
    assert [p.pid for p in report.codex_processes] == [102, 200]
    assert [p.pid for p in report.top_rss] == [200, 102]


def test_threshold_status_warns_and_criticals_above_configured_counts():
    assert threshold_status(10) == ("ok", None)

    level, message = threshold_status(11)
    assert level == "warning"
    assert "exceeds 10" in message

    level, message = threshold_status(21)
    assert level == "critical"
    assert "exceeds 20" in message


def test_build_report_exposes_threshold_warning():
    processes = [
        proc(100, 1, ["python", "-m", "gateway.run"]),
        *[
            proc(200 + i, 100, [HERMES_BIN, "app-server"], rss_kb=i)
            for i in range(11)
        ],
    ]

    report = build_report(processes, gateway_pid=100)

    assert report.threshold_level == "warning"
    assert report.threshold_message


def test_dry_run_cleanup_does_not_kill():
    report = build_report(
        [
            proc(100, 1, ["python", "-m", "gateway.run"]),
            proc(200, 1, [HERMES_BIN, "app-server"]),
        ],
        gateway_pid=100,
    )
    killed: list[tuple[int, int]] = []

    targets = kill_stale_codex(report, execute=False, killer=lambda pid, sig: killed.append((pid, sig)))

    assert targets == [200]
    assert killed == []


def test_explicit_cleanup_only_targets_stale_classified_processes():
    report = build_report(
        [
            proc(100, 1, ["python", "-m", "gateway.run"]),
            proc(101, 100, [HERMES_BIN, "app-server"]),
            proc(200, 1, [HERMES_BIN, "app-server"]),
            proc(201, 1, ["codex", "app-server"]),
            proc(202, 1, ["ffmpeg", "-i", "x"]),
        ],
        gateway_pid=100,
    )
    killed: list[tuple[int, int]] = []

    targets = kill_stale_codex(report, execute=True, killer=lambda pid, sig: killed.append((pid, sig)))

    assert targets == [200]
    assert killed == [(200, signal.SIGTERM)]
