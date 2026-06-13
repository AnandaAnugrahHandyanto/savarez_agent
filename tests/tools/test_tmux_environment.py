"""Tests for the tmux terminal backend.

The tmux backend keeps execution on the local host while routing each Hermes
profile into a profile-scoped tmux session and each agent/task into its own
window. These tests cover config plumbing, isolation-key selection, and the
real tmux command protocol when tmux is installed.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import uuid

import pytest


def test_get_env_config_tmux_uses_host_cwd_and_templates(monkeypatch, tmp_path):
    from tools import terminal_tool

    monkeypatch.setenv("TERMINAL_ENV", "tmux")
    monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
    monkeypatch.setenv("TERMINAL_TMUX_SESSION_TEMPLATE", "jarvis-{profile}")
    monkeypatch.setenv("TERMINAL_TMUX_WINDOW_TEMPLATE", "agent-{agent}")
    monkeypatch.setenv("TERMINAL_TMUX_PRESERVE_SESSION", "false")
    monkeypatch.setenv("TERMINAL_TMUX_HISTORY_LIMIT", "12345")

    config = terminal_tool._get_env_config()

    assert config["env_type"] == "tmux"
    assert config["cwd"] == str(tmp_path)
    assert config["tmux_session_template"] == "jarvis-{profile}"
    assert config["tmux_window_template"] == "agent-{agent}"
    assert config["tmux_preserve_session"] is False
    assert config["tmux_history_limit"] == 12345


def test_tmux_backend_preserves_raw_task_id_for_agent_window_isolation(monkeypatch):
    from tools import terminal_tool

    monkeypatch.setenv("TERMINAL_ENV", "tmux")

    assert terminal_tool._resolve_environment_task_id("agent-child-1", "tmux") == "agent-child-1"
    assert terminal_tool._resolve_environment_task_id(None, "tmux") == "default"


def test_create_environment_constructs_tmux_backend(monkeypatch, tmp_path):
    from tools import terminal_tool

    captured = {}

    class DummyTmuxEnvironment:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(terminal_tool, "_TmuxEnvironment", DummyTmuxEnvironment, raising=False)

    config = {
        "tmux_session_template": "jarvis-{profile}",
        "tmux_window_template": "agent-{agent}",
        "tmux_shell": "/bin/bash",
        "tmux_preserve_session": False,
        "tmux_history_limit": 50000,
    }

    env = terminal_tool._create_environment(
        env_type="tmux",
        image="",
        cwd=str(tmp_path),
        timeout=7,
        local_config=config,
        task_id="agent-123",
    )

    assert isinstance(env, DummyTmuxEnvironment)
    assert captured == {
        "cwd": str(tmp_path),
        "timeout": 7,
        "task_id": "agent-123",
        "session_template": "jarvis-{profile}",
        "window_template": "agent-{agent}",
        "shell": "/bin/bash",
        "preserve_session": False,
        "history_limit": 50000,
    }


def test_file_tools_use_tmux_agent_window_key(monkeypatch, tmp_path):
    from tools import file_tools, terminal_tool

    class DummyEnv:
        cwd = str(tmp_path)

        def execute(self, *args, **kwargs):  # pragma: no cover - not used here
            return {"output": "", "returncode": 0}

    captured = {}

    def fake_create_environment(**kwargs):
        captured.update(kwargs)
        return DummyEnv()

    monkeypatch.setattr(
        terminal_tool,
        "_get_env_config",
        lambda: {
            "env_type": "tmux",
            "cwd": str(tmp_path),
            "timeout": 180,
            "tmux_session_template": "hermes-{profile}",
            "tmux_window_template": "{agent}",
            "tmux_shell": "",
            "tmux_preserve_session": True,
            "tmux_history_limit": 200000,
        },
    )
    monkeypatch.setattr(terminal_tool, "_task_env_overrides", {})
    monkeypatch.setattr(terminal_tool, "_active_environments", {})
    monkeypatch.setattr(terminal_tool, "_last_activity", {})
    monkeypatch.setattr(terminal_tool, "_creation_locks", {})
    monkeypatch.setattr(terminal_tool, "_creation_locks_lock", threading.Lock())
    monkeypatch.setattr(terminal_tool, "_create_environment", fake_create_environment)
    monkeypatch.setattr(terminal_tool, "_start_cleanup_thread", lambda: None)
    monkeypatch.setattr(file_tools, "_file_ops_cache", {})
    monkeypatch.setattr(file_tools, "_file_ops_lock", threading.Lock())

    file_tools._get_file_ops("agent-file")

    assert captured["env_type"] == "tmux"
    assert captured["task_id"] == "agent-file"
    assert captured["local_config"] == {
        "tmux_session_template": "hermes-{profile}",
        "tmux_window_template": "{agent}",
        "tmux_shell": "",
        "tmux_preserve_session": True,
        "tmux_history_limit": 200000,
    }


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is not installed")
def test_tmux_environment_executes_in_agent_window_and_preserves_state(tmp_path):
    from tools.environments.tmux import TmuxEnvironment

    session = f"hermes-test-{uuid.uuid4().hex[:10]}"
    env = TmuxEnvironment(
        cwd=str(tmp_path),
        timeout=10,
        task_id="agent-A",
        session_template=session,
        window_template="{agent}",
        preserve_session=False,
    )

    try:
        first = env.execute(
            "export HERMES_TMUX_TEST=works; mkdir -p subdir; cd subdir; printf 'first'",
            timeout=10,
        )
        assert first["returncode"] == 0
        assert first["output"].strip() == "first"

        second = env.execute(
            "printf '%s:%s' \"$HERMES_TMUX_TEST\" \"$(basename \"$PWD\")\"",
            timeout=10,
        )
        assert second["returncode"] == 0
        assert second["output"].strip() == "works:subdir"

        listed = subprocess.run(
            ["tmux", "list-windows", "-t", session, "-F", "#{window_name}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        assert "agent-A" in listed.stdout.splitlines()
    finally:
        env.cleanup()
        subprocess.run(["tmux", "kill-session", "-t", session], check=False)
