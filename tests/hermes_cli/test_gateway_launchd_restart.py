"""Regression tests for macOS launchd gateway restart recovery."""

import subprocess

from hermes_cli import gateway as gw


def _patch_launchd_basics(monkeypatch, tmp_path, *, pid=12345, exited=True):
    plist = tmp_path / "ai.hermes.gateway.plist"
    plist.write_text("<plist/>", encoding="utf-8")

    monkeypatch.setattr(gw, "get_launchd_label", lambda: "ai.hermes.gateway")
    monkeypatch.setattr(gw, "_launchd_domain", lambda: "gui/501")
    monkeypatch.setattr(gw, "get_launchd_plist_path", lambda: plist)
    monkeypatch.setattr(gw, "_get_restart_drain_timeout", lambda: 1.0)
    monkeypatch.setattr(gw, "_request_gateway_self_restart", lambda actual_pid: actual_pid == pid)
    monkeypatch.setattr(gw, "_wait_for_gateway_exit", lambda timeout, force_after: exited)

    import gateway.status as status

    monkeypatch.setattr(status, "get_running_pid", lambda: pid)


def test_launchd_restart_self_restart_waits_then_kickstarts(monkeypatch, tmp_path, capsys):
    """A successful self-restart request must still explicitly revive launchd.

    Regression for the 2026-06-05 Telegram outage: the update path requested a
    gateway self-restart, returned immediately, and Telegram never came back.
    """
    _patch_launchd_basics(monkeypatch, tmp_path, exited=True)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(gw.subprocess, "run", fake_run)

    gw.launchd_restart()

    assert ["launchctl", "kickstart", "gui/501/ai.hermes.gateway"] in calls
    assert ["launchctl", "kickstart", "-k", "gui/501/ai.hermes.gateway"] not in calls
    out = capsys.readouterr().out
    assert "Service restart requested" in out
    assert "Service restarted" in out


def test_launchd_restart_self_restart_bootstraps_if_job_unloaded(monkeypatch, tmp_path):
    """If kickstart reports the job is missing, bootstrap the plist and start."""
    _patch_launchd_basics(monkeypatch, tmp_path, exited=True)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if (
            cmd == ["launchctl", "kickstart", "gui/501/ai.hermes.gateway"]
            and calls.count(cmd) == 1
        ):
            raise subprocess.CalledProcessError(3, cmd, stderr="Could not find service")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(gw.subprocess, "run", fake_run)

    gw.launchd_restart()

    assert [
        "launchctl",
        "bootstrap",
        "gui/501",
        str(tmp_path / "ai.hermes.gateway.plist"),
    ] in calls
    assert ["launchctl", "kickstart", "gui/501/ai.hermes.gateway"] in calls


def test_launchd_restart_self_restart_force_kicks_if_drain_times_out(monkeypatch, tmp_path):
    """If the old gateway does not exit, force launchd to restart the job."""
    _patch_launchd_basics(monkeypatch, tmp_path, exited=False)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(gw.subprocess, "run", fake_run)

    gw.launchd_restart()

    assert ["launchctl", "kickstart", "-k", "gui/501/ai.hermes.gateway"] in calls
