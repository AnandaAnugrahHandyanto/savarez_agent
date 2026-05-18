"""Regression tests for the legacy scripts/hermes-gateway helper.

The main `hermes gateway ...` CLI is implemented in hermes_cli.gateway, but this
standalone helper is still shipped as an install/control entrypoint. Keep its
launchd policy aligned with the canonical gateway service so it cannot regress
macOS gateway reliability.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import plistlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = ROOT / "scripts" / "hermes-gateway"


def load_helper():
    loader = importlib.machinery.SourceFileLoader("hermes_gateway_helper", str(HELPER_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_launchd_plist_uses_unconditional_keepalive():
    helper = load_helper()

    plist_text = helper.generate_launchd_plist()
    plist = plistlib.loads(plist_text.encode("utf-8"))

    assert plist["KeepAlive"] is True
    assert "SuccessfulExit" not in plist_text


def test_launchd_stop_uses_bootout_so_keepalive_does_not_respawn(monkeypatch):
    helper = load_helper()
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    helper.launchd_stop()

    assert calls == [["launchctl", "bootout", f"gui/{helper.os.getuid()}/ai.hermes.gateway"]]


def test_launchd_install_bootouts_then_bootstraps_current_plist(monkeypatch, tmp_path):
    helper = load_helper()
    calls: list[list[str]] = []
    plist_path = tmp_path / "ai.hermes.gateway.plist"

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(helper, "get_launchd_plist_path", lambda: plist_path)
    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    helper.install_launchd()

    target = f"gui/{helper.os.getuid()}/ai.hermes.gateway"
    assert plistlib.loads(plist_path.read_bytes())["KeepAlive"] is True
    assert calls == [
        ["launchctl", "bootout", target],
        ["launchctl", "bootstrap", f"gui/{helper.os.getuid()}", str(plist_path)],
        ["launchctl", "kickstart", target],
    ]


def test_launchd_uninstall_bootouts_before_removing_plist(monkeypatch, tmp_path):
    helper = load_helper()
    calls: list[list[str]] = []
    plist_path = tmp_path / "ai.hermes.gateway.plist"
    plist_path.write_text("stale")

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(helper, "get_launchd_plist_path", lambda: plist_path)
    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    helper.uninstall_launchd()

    assert not plist_path.exists()
    assert calls == [["launchctl", "bootout", f"gui/{helper.os.getuid()}/ai.hermes.gateway"]]


def test_launchd_start_bootstraps_then_kickstarts(monkeypatch, tmp_path):
    helper = load_helper()
    calls: list[list[str]] = []
    plist_path = tmp_path / "ai.hermes.gateway.plist"

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(helper, "get_launchd_plist_path", lambda: plist_path)
    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    helper.launchd_start()

    target = f"gui/{helper.os.getuid()}/ai.hermes.gateway"
    assert plist_path.exists()
    assert calls == [
        ["launchctl", "bootstrap", f"gui/{helper.os.getuid()}", str(plist_path)],
        ["launchctl", "kickstart", target],
    ]
