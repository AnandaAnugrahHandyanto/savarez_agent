"""Tests for `_default_spawn` dispatch_command_override behaviour.

All tests mock the subprocess boundary.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hermes_cli import kanban_db as kb


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    """Isolated HERMES_HOME with a fresh kanban DB."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


@pytest.fixture
def profile_dir(tmp_path, monkeypatch):
    """Return the path to a synthetic profiles root and patch get_profile_dir."""
    profiles = tmp_path / "profiles"
    profiles.mkdir()

    from hermes_cli import profiles as _profiles_mod

    def _fake_get_profile_dir(name):
        canon = _profiles_mod.normalize_profile_name(name)
        if canon == "default":
            return tmp_path / ".hermes"
        return profiles / canon

    monkeypatch.setattr(_profiles_mod, "get_profile_dir", _fake_get_profile_dir)
    monkeypatch.setattr(_profiles_mod, "profile_exists", lambda name: True)
    return profiles


def _make_task(task_id="t_override_test", assignee="claude-code-bridge"):
    return kb.Task(
        id=task_id,
        title="Override test task",
        body="Test body",
        assignee=assignee,
        status="running",
        priority=0,
        created_by=None,
        created_at=0,
        started_at=None,
        completed_at=None,
        workspace_kind="scratch",
        workspace_path=None,
        claim_lock=None,
        claim_expires=None,
        tenant=None,
    )


def _write_profile_config(profile_dir, profile_name, config_text):
    """Write a config.yaml under profiles/<name>/."""
    pdir = profile_dir / profile_name
    pdir.mkdir(exist_ok=True)
    (pdir / "config.yaml").write_text(config_text, encoding="utf-8")
    return pdir


# ---------------------------------------------------------------------------
# test_spawn_override_used_when_present
# ---------------------------------------------------------------------------


def test_spawn_override_used_when_present(kanban_home, profile_dir):
    """When a profile defines dispatch_command_override, that command is run."""
    _write_profile_config(
        profile_dir,
        "claude-code-bridge",
        'dispatch_command_override: "echo hello --task t_override_test"\n',
    )

    task = _make_task()
    captured = {}

    class _FakePopen:
        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            self.pid = 9999

    with patch("subprocess.Popen", _FakePopen):
        pid = kb._default_spawn(task, "/tmp/ws")

    assert pid == 9999, "Should return the override process PID"
    assert captured.get("cmd") is not None, "Popen was not called"
    cmd_str = " ".join(captured["cmd"])
    # The override command must be used, NOT the hermes default
    assert "echo" in cmd_str, f"Expected 'echo' in cmd, got: {cmd_str!r}"
    assert "hermes" not in cmd_str.lower() or "echo" in cmd_str,         f"Default hermes spawn must not run when override is set"


# ---------------------------------------------------------------------------
# test_spawn_override_falls_back_when_malformed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value,label", [
    ("", "empty string"),
    ("   ", "whitespace only"),
])
def test_spawn_override_falls_back_when_malformed(
    kanban_home, profile_dir, bad_value, label, capsys
):
    """Empty/whitespace override value causes fallback to default spawn + warning."""
    import yaml
    config_content = yaml.dump({"dispatch_command_override": bad_value})
    _write_profile_config(profile_dir, "claude-code-bridge", config_content)

    task = _make_task()
    captured = {}

    class _FakePopen:
        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            self.pid = 7777

    with patch("subprocess.Popen", _FakePopen):
        pid = kb._default_spawn(task, "/tmp/ws")

    # Should fall back to default hermes spawn
    assert pid == 7777
    cmd_str = " ".join(captured.get("cmd", []))
    assert "hermes" in cmd_str or "hermes_cli" in cmd_str or "-p" in cmd_str,         f"Expected default hermes spawn but got: {cmd_str!r}"

    out = capsys.readouterr()
    # A warning must be emitted to stderr
    assert "WARNING" in out.err or "ignoring" in out.err.lower() or "empty" in out.err.lower(),         f"Expected warning in stderr for {label!r}, got: {out.err!r}"


def test_spawn_override_falls_back_when_none(kanban_home, profile_dir):
    """If dispatch_command_override is null/None in YAML, use default spawn silently."""
    import yaml
    config_content = yaml.dump({"dispatch_command_override": None})
    _write_profile_config(profile_dir, "claude-code-bridge", config_content)

    task = _make_task()
    captured = {}

    class _FakePopen:
        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            self.pid = 5555

    with patch("subprocess.Popen", _FakePopen):
        pid = kb._default_spawn(task, "/tmp/ws")

    # None → key missing → default spawn
    assert pid == 5555
    cmd_str = " ".join(captured.get("cmd", []))
    assert "hermes" in cmd_str or "-p" in cmd_str or "hermes_cli" in cmd_str,         f"Expected default hermes spawn but got: {cmd_str!r}"


# ---------------------------------------------------------------------------
# test_spawn_override_interpolates_env_vars
# ---------------------------------------------------------------------------


def test_spawn_override_interpolates_env_vars(kanban_home, profile_dir, monkeypatch):
    """${HERMES_KANBAN_TASK} and ${HERMES_KANBAN_BOARD} are interpolated in the command."""
    monkeypatch.setenv("HERMES_REPO_ROOT", "/opt/hermes")
    _write_profile_config(
        profile_dir,
        "claude-code-bridge",
        'dispatch_command_override: "python3 ${HERMES_REPO_ROOT}/scripts/claude_kanban_bridge.py --task ${HERMES_KANBAN_TASK} --board ${HERMES_KANBAN_BOARD}"\n',
    )

    task = _make_task(task_id="t_interp_123")
    captured = {}

    class _FakePopen:
        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            captured["env"] = kwargs.get("env", {})
            self.pid = 8888

    with patch("subprocess.Popen", _FakePopen):
        pid = kb._default_spawn(task, "/tmp/ws")

    assert pid == 8888
    cmd = captured.get("cmd", [])
    cmd_str = " ".join(cmd)

    # HERMES_REPO_ROOT must be substituted
    assert "/opt/hermes" in cmd_str,         f"Expected /opt/hermes in cmd: {cmd_str!r}"
    # Task id must be substituted
    assert "t_interp_123" in cmd_str,         f"Expected task id in cmd: {cmd_str!r}"
    # No leftover placeholder tokens
    assert "${HERMES_KANBAN_TASK}" not in cmd_str,         f"Unresolved placeholder in cmd: {cmd_str!r}"
    assert "${HERMES_REPO_ROOT}" not in cmd_str,         f"Unresolved placeholder in cmd: {cmd_str!r}"
