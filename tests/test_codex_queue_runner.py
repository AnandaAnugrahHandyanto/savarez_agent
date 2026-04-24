from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_queue_runner():
    spec = importlib.util.spec_from_file_location("codex_queue_runner", Path("scripts/codex_queue_runner.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_run_next_uses_auto_switch_runner_for_codex_commands(tmp_path, monkeypatch):
    qr = _load_queue_runner()
    state_file = tmp_path / "state.json"
    qr.ensure_paths(state_file)
    task = qr.add_task(
        state_file,
        "codex exec 'fix bug'",
        str(tmp_path / "repo"),
        "fix bug",
        ["FOO=bar"],
    )

    calls = []

    def fake_execute(command, *, notify_email=None, max_switches=None, cwd=None, env=None, stream_output=True, event_callback=None):
        calls.append(
            {
                "command": command,
                "notify_email": notify_email,
                "max_switches": max_switches,
                "cwd": cwd,
                "env": env,
                "stream_output": stream_output,
            }
        )
        return 0, "switched account and continued"

    monkeypatch.setattr(qr, "run_task_with_auto_switch", fake_execute)
    monkeypatch.setattr(qr, "send_email", lambda *args, **kwargs: None)

    rc = qr.run_next(state_file, notify_email="li@example.com")
    state = qr.read_state(state_file)

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["command"] == "codex exec 'fix bug'"
    assert calls[0]["notify_email"] == "li@example.com"
    assert calls[0]["cwd"] == str((tmp_path / "repo").expanduser())
    assert calls[0]["env"]["FOO"] == "bar"
    assert calls[0]["stream_output"] is False
    assert state["queue"] == []
    assert state["history"][0]["status"] == "done"
    log_path = Path(state["history"][0]["log_file"])
    assert log_path.read_text(encoding="utf-8") == "switched account and continued"


def test_run_next_auto_commits_and_pushes_when_enabled(tmp_path, monkeypatch):
    qr = _load_queue_runner()
    state_file = tmp_path / "state.json"
    qr.ensure_paths(state_file)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "changed.txt").write_text("hello\n", encoding="utf-8")

    qr.add_task(
        state_file,
        "codex exec 'ship it'",
        str(repo),
        "ship it",
        [
            "CODEX_AUTO_GIT_PUSH=1",
            "CODEX_AUTO_GIT_BRANCH=master",
            "CODEX_AUTO_GIT_COMMIT_MESSAGE=chore(codex): sync latest TRS-LogWhisperer-v2 changes",
        ],
    )

    monkeypatch.setattr(qr, "run_task_with_auto_switch", lambda *args, **kwargs: (0, "ok"))
    monkeypatch.setattr(qr, "send_email", lambda *args, **kwargs: None)

    git_calls = []

    class DummyProc:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_git_run(args, cwd):
        git_calls.append((tuple(args), str(cwd)))
        if args[:2] == ["rev-parse", "--is-inside-work-tree"]:
            return DummyProc(0, "true\n")
        if args == ["status", "--porcelain"]:
            return DummyProc(0, " M changed.txt\n")
        if args == ["add", "-A"]:
            return DummyProc(0, "")
        if args == ["branch", "--show-current"]:
            return DummyProc(0, "master\n")
        if args == ["config", "--get", "branch.master.remote"]:
            return DummyProc(0, "github\n")
        if args[:4] == ["-c", "commit.gpgsign=false", "commit", "-m"]:
            return DummyProc(0, "[master abc1234] auto commit\n")
        if args == ["push", "github", "master"]:
            return DummyProc(0, "pushed\n")
        if args == ["rev-parse", "HEAD"]:
            return DummyProc(0, "abc123456789\n")
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setattr(qr, "_git_run", fake_git_run)

    rc = qr.run_next(state_file, notify_email="li@example.com")
    state = qr.read_state(state_file)
    history = state["history"][0]

    assert rc == 0
    assert history["git_sync"]["reason"] == "committed_and_pushed"
    assert history["git_sync"]["remote"] == "github"
    assert history["git_sync"]["branch"] == "master"
    assert history["git_sync"]["commit"] == "abc123456789"
    assert any(call[0] == ("push", "github", "master") for call in git_calls)


def test_run_next_fails_when_auto_push_fails(tmp_path, monkeypatch):
    qr = _load_queue_runner()
    state_file = tmp_path / "state.json"
    qr.ensure_paths(state_file)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    qr.add_task(
        state_file,
        "codex exec 'ship it'",
        str(repo),
        "ship it",
        ["CODEX_AUTO_GIT_PUSH=1"],
    )

    monkeypatch.setattr(qr, "run_task_with_auto_switch", lambda *args, **kwargs: (0, "ok"))
    monkeypatch.setattr(qr, "send_email", lambda *args, **kwargs: None)

    class DummyProc:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_git_run(args, cwd):
        if args[:2] == ["rev-parse", "--is-inside-work-tree"]:
            return DummyProc(0, "true\n")
        if args == ["status", "--porcelain"]:
            return DummyProc(0, " M changed.txt\n")
        if args == ["add", "-A"]:
            return DummyProc(0, "")
        if args == ["branch", "--show-current"]:
            return DummyProc(0, "master\n")
        if args == ["config", "--get", "branch.master.remote"]:
            return DummyProc(0, "github\n")
        if args[:4] == ["-c", "commit.gpgsign=false", "commit", "-m"]:
            return DummyProc(0, "[master abc1234] auto commit\n")
        if args == ["push", "github", "master"]:
            return DummyProc(1, "", "push rejected")
        return DummyProc(0, "")

    monkeypatch.setattr(qr, "_git_run", fake_git_run)

    rc = qr.run_next(state_file, notify_email="li@example.com")
    state = qr.read_state(state_file)
    history = state["history"][0]

    assert rc == 1
    assert history["status"] == "failed"
    assert history["last_error"] == "git push 失败"
    assert history["git_sync"]["reason"] == "git_push_failed"
    assert "push rejected" in history["git_sync"]["push_output"]
