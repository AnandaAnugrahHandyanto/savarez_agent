"""Tests for AgentCookie integration in browser_tool.py."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


_AGENTCOOKIE_ENV_VARS = (
    "HERMES_AGENTCOOKIE_ENABLED",
    "AGENTCOOKIE_ENABLED",
    "HERMES_AGENTCOOKIE_PROFILE_DIR",
    "AGENTCOOKIE_PROFILE_DIR",
    "HERMES_AGENTCOOKIE_PLAIN_COOKIES",
    "AGENTCOOKIE_PLAIN_COOKIES",
)


@pytest.fixture(autouse=True)
def _reset_agentcookie_cache(monkeypatch):
    import tools.browser_tool as bt

    for name in _AGENTCOOKIE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    if hasattr(bt, "_cached_agentcookie_config"):
        bt._cached_agentcookie_config = None
    if hasattr(bt, "_agentcookie_config_resolved"):
        bt._agentcookie_config_resolved = False
    yield
    if hasattr(bt, "_cached_agentcookie_config"):
        bt._cached_agentcookie_config = None
    if hasattr(bt, "_agentcookie_config_resolved"):
        bt._agentcookie_config_resolved = False


def test_agentcookie_config_defaults_disabled():
    import tools.browser_tool as bt

    with patch("hermes_cli.config.read_raw_config", return_value={}):
        cfg = bt._get_agentcookie_config()

    assert cfg["enabled"] is False
    assert cfg["profile_dir"] == os.path.expanduser("~/.agentcookie/chrome-profile")
    assert cfg["plain_cookies_db"] == os.path.expanduser("~/.agentcookie/cookies-plain.db")


def test_agentcookie_config_reads_browser_agentcookie_block(tmp_path):
    import tools.browser_tool as bt

    profile = tmp_path / "agc-profile"
    sidecar = tmp_path / "cookies-plain.db"
    raw_cfg = {
        "browser": {
            "agentcookie": {
                "enabled": True,
                "profile_dir": str(profile),
                "plain_cookies_db": str(sidecar),
            }
        }
    }

    with patch("hermes_cli.config.read_raw_config", return_value=raw_cfg):
        cfg = bt._get_agentcookie_config()

    assert cfg == {
        "enabled": True,
        "profile_dir": str(profile),
        "plain_cookies_db": str(sidecar),
    }


def test_agentcookie_env_overrides_config(tmp_path, monkeypatch):
    import tools.browser_tool as bt

    profile = tmp_path / "env-profile"
    sidecar = tmp_path / "env-cookies.db"
    monkeypatch.setenv("HERMES_AGENTCOOKIE_ENABLED", "1")
    monkeypatch.setenv("HERMES_AGENTCOOKIE_PROFILE_DIR", str(profile))
    monkeypatch.setenv("AGENTCOOKIE_PLAIN_COOKIES", str(sidecar))

    with patch("hermes_cli.config.read_raw_config", return_value={"browser": {"agentcookie": {"enabled": False}}}):
        cfg = bt._get_agentcookie_config()

    assert cfg == {
        "enabled": True,
        "profile_dir": str(profile),
        "plain_cookies_db": str(sidecar),
    }


def test_local_browser_command_uses_agentcookie_profile_and_sidecar_env(tmp_path, monkeypatch):
    import tools.browser_tool as bt

    profile = tmp_path / "chrome-profile"
    sidecar = tmp_path / "cookies-plain.db"
    captured = {}

    class FakePopen:
        returncode = 0

        def __init__(self, cmd, stdout, stderr, stdin=None, env=None, **kwargs):
            captured["cmd"] = cmd
            captured["env"] = env or {}
            os.write(stdout, json.dumps({"success": True, "data": {"ok": True}}).encode())

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr(bt, "_find_agent_browser", lambda: "/usr/local/bin/agent-browser")
    monkeypatch.setattr(bt, "_requires_real_termux_browser_install", lambda _cmd: False)
    monkeypatch.setattr(bt, "_chromium_installed", lambda: True)
    monkeypatch.setattr(bt, "_is_local_mode", lambda: True)
    monkeypatch.setattr(bt, "_is_camofox_mode", lambda: False)
    monkeypatch.setattr(bt, "_get_browser_engine", lambda: "auto")
    monkeypatch.setattr(bt, "_get_session_info", lambda task_id: {"session_name": "h_agentcookie"})
    monkeypatch.setattr(
        bt,
        "_get_agentcookie_config",
        lambda: {"enabled": True, "profile_dir": str(profile), "plain_cookies_db": str(sidecar)},
    )
    monkeypatch.setattr(bt.subprocess, "Popen", FakePopen)

    with patch("tools.browser_tool._socket_safe_tmpdir", return_value=str(tmp_path)):
        result = bt._run_browser_command("task", "snapshot", [])

    assert result["success"] is True
    cmd = captured["cmd"]
    assert cmd[:4] == ["/usr/local/bin/agent-browser", "--profile", str(profile), "--session"]
    assert "h_agentcookie" in cmd
    assert captured["env"]["AGENTCOOKIE_PLAIN_COOKIES"] == str(sidecar)


def test_agentcookie_profile_not_added_for_cdp_sessions(tmp_path, monkeypatch):
    import tools.browser_tool as bt

    captured = {}
    monkeypatch.setenv("AGENTCOOKIE_PLAIN_COOKIES", str(tmp_path / "inherited-cookies.db"))
    monkeypatch.setenv("HERMES_AGENTCOOKIE_PROFILE_DIR", str(tmp_path / "inherited-profile"))

    class FakePopen:
        returncode = 0

        def __init__(self, cmd, stdout, stderr, stdin=None, env=None, **kwargs):
            captured["cmd"] = cmd
            captured["env"] = env or {}
            os.write(stdout, json.dumps({"success": True, "data": {"ok": True}}).encode())

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr(bt, "_find_agent_browser", lambda: "/usr/local/bin/agent-browser")
    monkeypatch.setattr(bt, "_requires_real_termux_browser_install", lambda _cmd: False)
    monkeypatch.setattr(bt, "_chromium_installed", lambda: True)
    monkeypatch.setattr(bt, "_is_local_mode", lambda: False)
    monkeypatch.setattr(bt, "_is_camofox_mode", lambda: False)
    monkeypatch.setattr(bt, "_get_browser_engine", lambda: "auto")
    monkeypatch.setattr(
        bt,
        "_get_session_info",
        lambda task_id: {"session_name": "cdp_agentcookie", "cdp_url": "ws://127.0.0.1:9222/devtools/browser/x"},
    )
    monkeypatch.setattr(
        bt,
        "_get_agentcookie_config",
        lambda: {"enabled": True, "profile_dir": str(tmp_path / "profile"), "plain_cookies_db": str(tmp_path / "cookies.db")},
    )
    monkeypatch.setattr(bt.subprocess, "Popen", FakePopen)

    with patch("tools.browser_tool._socket_safe_tmpdir", return_value=str(tmp_path)):
        result = bt._run_browser_command("task", "snapshot", [])

    assert result["success"] is True
    assert "--profile" not in captured["cmd"]
    assert captured["cmd"][1:3] == ["--cdp", "ws://127.0.0.1:9222/devtools/browser/x"]
    assert "AGENTCOOKIE_PLAIN_COOKIES" not in captured["env"]
    assert "HERMES_AGENTCOOKIE_PROFILE_DIR" not in captured["env"]


def test_agentcookie_not_added_for_lightpanda_sessions(tmp_path, monkeypatch):
    import tools.browser_tool as bt

    captured = {}
    monkeypatch.setenv("AGENTCOOKIE_PLAIN_COOKIES", str(tmp_path / "inherited-cookies.db"))
    monkeypatch.setenv("HERMES_AGENTCOOKIE_PROFILE_DIR", str(tmp_path / "inherited-profile"))

    class FakePopen:
        returncode = 0

        def __init__(self, cmd, stdout, stderr, stdin=None, env=None, **kwargs):
            captured["cmd"] = cmd
            captured["env"] = env or {}
            os.write(
                stdout,
                json.dumps({"success": True, "data": {"snapshot": "lightpanda content long enough", "refs": []}}).encode(),
            )

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr(bt, "_find_agent_browser", lambda: "/usr/local/bin/agent-browser")
    monkeypatch.setattr(bt, "_requires_real_termux_browser_install", lambda _cmd: False)
    monkeypatch.setattr(bt, "_chromium_installed", lambda: True)
    monkeypatch.setattr(bt, "_is_local_mode", lambda: True)
    monkeypatch.setattr(bt, "_is_camofox_mode", lambda: False)
    monkeypatch.setattr(bt, "_get_browser_engine", lambda: "lightpanda")
    monkeypatch.setattr(bt, "_get_session_info", lambda task_id: {"session_name": "lp_agentcookie"})
    monkeypatch.setattr(
        bt,
        "_get_agentcookie_config",
        lambda: {"enabled": True, "profile_dir": str(tmp_path / "profile"), "plain_cookies_db": str(tmp_path / "cookies.db")},
    )
    monkeypatch.setattr(bt.subprocess, "Popen", FakePopen)

    with patch("tools.browser_tool._socket_safe_tmpdir", return_value=str(tmp_path)):
        result = bt._run_browser_command("task", "snapshot", [])

    assert result["success"] is True
    assert "--profile" not in captured["cmd"]
    engine_pairs = [captured["cmd"][i : i + 2] for i in range(len(captured["cmd"]) - 1)]
    assert ["--engine", "lightpanda"] in engine_pairs
    assert "AGENTCOOKIE_PLAIN_COOKIES" not in captured["env"]
    assert "HERMES_AGENTCOOKIE_PROFILE_DIR" not in captured["env"]


def test_chrome_fallback_uses_agentcookie_profile_and_sidecar_env(tmp_path, monkeypatch):
    import tools.browser_tool as bt

    profile = tmp_path / "fallback-profile"
    sidecar = tmp_path / "fallback-cookies.db"
    captured = {"cmds": [], "envs": []}

    class FakePopen:
        returncode = 0

        def __init__(self, cmd, stdout, stderr, stdin=None, env=None, **kwargs):
            captured["cmds"].append(cmd)
            captured["envs"].append(env or {})
            command = cmd[-2] if cmd[-1] == "https://example.test/page" else cmd[-1]
            payload = {"success": True, "data": {"command": command}}
            os.write(stdout, json.dumps(payload).encode())

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr(
        bt,
        "_run_browser_command",
        lambda *args, **kwargs: {"success": True, "data": {"result": "https://example.test/page"}},
    )
    monkeypatch.setattr(bt, "_find_agent_browser", lambda: "/usr/local/bin/agent-browser")
    monkeypatch.setattr(bt, "_chromium_installed", lambda: True)
    monkeypatch.setattr(
        bt,
        "_get_agentcookie_config",
        lambda: {"enabled": True, "profile_dir": str(profile), "plain_cookies_db": str(sidecar)},
    )
    monkeypatch.setattr(bt.subprocess, "Popen", FakePopen)

    with patch("tools.browser_tool._socket_safe_tmpdir", return_value=str(tmp_path)):
        result = bt._run_chrome_fallback_command("task", "snapshot", [], 10)

    assert result["success"] is True
    assert [cmd[-1] for cmd in captured["cmds"]] == ["https://example.test/page", "snapshot", "close"]
    for cmd in captured["cmds"]:
        assert cmd[:4] == ["/usr/local/bin/agent-browser", "--profile", str(profile), "--engine"]
        assert "chrome" in cmd
    for env in captured["envs"]:
        assert env["AGENTCOOKIE_PLAIN_COOKIES"] == str(sidecar)
