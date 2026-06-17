from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


class _DummyProc:
    def __init__(self, pid: int = 4242):
        self.pid = pid


def _task_run_metadata(task_id: str) -> dict:
    with kb.connect() as conn:
        row = conn.execute(
            "SELECT metadata FROM task_runs WHERE task_id = ? ORDER BY id DESC LIMIT 1",
            (task_id,),
        ).fetchone()
    if not row or not row["metadata"]:
        return {}
    return json.loads(row["metadata"])


def test_default_spawn_wraps_worker_in_interactive_runtime_when_script_available(
    kanban_home, monkeypatch, tmp_path
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with kb.connect() as conn:
        task_id = kb.create_task(conn, title="x", assignee="worker")
        kb.claim_task(conn, task_id)
        task = kb.get_task(conn, task_id)
    assert task is not None
    assert task.current_run_id is not None

    popen_calls: list[tuple[list[str], dict]] = []

    def fake_popen(cmd, **kwargs):
        popen_calls.append((cmd, kwargs))
        return _DummyProc()

    monkeypatch.setattr(kb, "_resolve_hermes_argv", lambda: ["/fake/hermes"])
    monkeypatch.setattr(kb, "_kanban_worker_skill_available", lambda *_: False)
    monkeypatch.setattr(kb, "_resolve_worker_cli_toolsets", lambda *_: None)
    monkeypatch.setattr(kb.shutil, "which", lambda name: "/usr/bin/script" if name == "script" else None)
    monkeypatch.setattr(kb.subprocess, "Popen", fake_popen)

    pid = kb._default_spawn(task, str(workspace), board="default")

    assert pid == 4242
    assert len(popen_calls) == 1
    cmd, kwargs = popen_calls[0]
    assert cmd[:2] == ["bash", "-lc"]
    assert "script -q -f -c" in cmd[2]
    assert kwargs["cwd"] == str(workspace)

    env = kwargs["env"]
    assert env["HERMES_KANBAN_TASK"] == task_id
    assert env["HERMES_KANBAN_BOARD"] == "default"
    assert env["HERMES_KANBAN_INTERACTIVE_CONTROL_DIR"].endswith(f"/{task_id}.interactive")
    assert env["HERMES_KANBAN_INTERACTIVE_STDIN_FIFO"].endswith("/stdin.fifo")
    assert env["HERMES_KANBAN_INTERACTIVE_LOG_PATH"].endswith("/pty.log")

    control_dir = Path(env["HERMES_KANBAN_INTERACTIVE_CONTROL_DIR"])
    fifo_path = Path(env["HERMES_KANBAN_INTERACTIVE_STDIN_FIFO"])
    pty_log_path = Path(env["HERMES_KANBAN_INTERACTIVE_LOG_PATH"])
    assert control_dir.is_dir()
    assert fifo_path.exists()
    assert pty_log_path.parent == control_dir
    assert (control_dir / "attach.txt").is_file()
    assert (control_dir / "send.sh").is_file()
    assert (control_dir / "tail.sh").is_file()

    metadata = _task_run_metadata(task_id)
    assert metadata["interactive_runtime"] == "script-pty"
    assert metadata["interactive_control_dir"] == str(control_dir)
    assert metadata["interactive_stdin_fifo"] == str(fifo_path)
    assert metadata["interactive_log_path"] == str(pty_log_path)
    assert metadata["interactive_session_label"] == f"kanban:default:{task_id}"
    assert metadata["interactive_attach_hint"].startswith("tail -f ")
    assert metadata["interactive_send_hint"].startswith("printf '%s")
    assert metadata["spawn_command"].startswith("/fake/hermes -p worker --accept-hooks chat -q")


def test_default_spawn_falls_back_to_plain_spawn_when_interactive_surface_disabled(
    kanban_home, monkeypatch, tmp_path
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with kb.connect() as conn:
        task_id = kb.create_task(conn, title="x", assignee="worker")
        kb.claim_task(conn, task_id)
        task = kb.get_task(conn, task_id)
    assert task is not None

    popen_calls: list[tuple[list[str], dict]] = []

    def fake_popen(cmd, **kwargs):
        popen_calls.append((cmd, kwargs))
        return _DummyProc(5252)

    monkeypatch.setenv("HERMES_KANBAN_DISABLE_INTERACTIVE_SURFACE", "1")
    monkeypatch.setattr(kb, "_resolve_hermes_argv", lambda: ["/fake/hermes"])
    monkeypatch.setattr(kb, "_kanban_worker_skill_available", lambda *_: False)
    monkeypatch.setattr(kb, "_resolve_worker_cli_toolsets", lambda *_: None)
    monkeypatch.setattr(kb.subprocess, "Popen", fake_popen)

    pid = kb._default_spawn(task, str(workspace), board="default")

    assert pid == 5252
    assert len(popen_calls) == 1
    cmd, kwargs = popen_calls[0]
    assert cmd[0] == "/fake/hermes"
    assert "HERMES_KANBAN_INTERACTIVE_CONTROL_DIR" not in kwargs["env"]

    metadata = _task_run_metadata(task_id)
    assert "interactive_runtime" not in metadata
