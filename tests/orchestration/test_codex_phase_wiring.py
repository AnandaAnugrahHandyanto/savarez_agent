import json
import os
import shutil
import subprocess
import textwrap
import uuid
from types import SimpleNamespace
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb


WRAPPER = Path("/home/ubuntu/.hermes/scripts/hermes-codex-phase")
WORK_ROOT = Path("/home/ubuntu/work/hermes-repos")


def _run(cmd, *, cwd, env=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def _make_repo() -> Path:
    if not WRAPPER.exists():
        pytest.skip(f"missing wrapper: {WRAPPER}")
    try:
        WORK_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        pytest.skip(f"cannot create Hermes work root {WORK_ROOT}: {exc}")

    repo = WORK_ROOT / f"pytest-codex-phase-{uuid.uuid4().hex}"
    repo.mkdir(parents=True)
    _run(["git", "init"], cwd=repo)
    _run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    _run(["git", "config", "user.name", "Hermes Test"], cwd=repo)
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")
    phase_dir = repo / ".hermes" / "phases"
    phase_dir.mkdir(parents=True)
    (phase_dir / "phase-001.md").write_text(
        "# Phase 001\n\nDo one bounded thing.\n",
        encoding="utf-8",
    )
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "initial"], cwd=repo)
    _run(
        ["git", "remote", "add", "origin", "git@github.com:nicolaregattieri/test.git"],
        cwd=repo,
    )
    _run(["git", "checkout", "-b", "feature/test"], cwd=repo)
    return repo


def _make_fake_codex(bin_dir: Path, event_body: dict, exit_code: int = 0) -> None:
    script = bin_dir / "codex"
    script.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail
            mkdir -p .hermes/events
            cat > .hermes/events/phase-001-complete.json <<'JSON'
            {json.dumps(event_body)}
            JSON
            echo "fake codex wrote phase event"
            exit {exit_code}
            """
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)


def _make_fake_codex_needs_input(bin_dir: Path) -> None:
    script = bin_dir / "codex"
    script.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            mkdir -p .hermes/events
            cat > .hermes/events/phase-001-needs-input.json <<'JSON'
            {"type":"needs_input","phase":"phase-001","question":"Approve scope?","options":["yes","no"],"risk":"medium"}
            JSON
            echo "fake codex needs input"
            exit 0
            """
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)


def _create_task(hermes_home: Path, repo: Path) -> str:
    os.environ["HERMES_HOME"] = str(hermes_home)
    kb.init_db()
    with kb.connect() as conn:
        return kb.create_task(
            conn,
            title="Run phase 001",
            body="exercise wrapper wiring",
            assignee="codex",
            workspace_kind="dir",
            workspace_path=str(repo),
            created_by="pytest",
        )


def _task_snapshot(task_id: str):
    with kb.connect() as conn:
        task = kb.get_task(conn, task_id)
        comments = kb.list_comments(conn, task_id)
        events = kb.list_events(conn, task_id)
    return task, comments, events


def test_codex_phase_wrapper_marks_kanban_task_done(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    repo = _make_repo()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _make_fake_codex(
        fake_bin,
        {
            "type": "phase_complete",
            "phase": "phase-001",
            "summary": "Phase finished cleanly.",
            "changed_files": ["README.md"],
            "commands_run": ["fake"],
            "tests": {"status": "passed", "details": "fake"},
            "next_request": "review_and_continue",
        },
    )
    task_id = _create_task(hermes_home, repo)

    env = os.environ.copy()
    env["HERMES_HOME"] = str(hermes_home)
    env["HERMES_KANBAN_TASK"] = task_id
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    try:
        result = subprocess.run(
            [str(WRAPPER), str(repo), ".hermes/phases/phase-001.md", "1"],
            cwd=repo,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        assert ".hermes/codex-logs/" in result.stdout

        task, comments, events = _task_snapshot(task_id)
        assert task.status == "done"
        assert "Phase finished cleanly." in (task.result or "")
        assert any("PHASE STARTED: phase-001" in c.body for c in comments)
        assert any("PHASE FINISHED: phase-001" in c.body for c in comments)
        assert any(e.kind == "completed" for e in events)
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_codex_phase_wrapper_blocks_for_review_when_later_phase_exists(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    repo = _make_repo()
    (repo / ".hermes" / "phases" / "phase-002.md").write_text(
        "# Phase 002\n\nNext bounded thing.\n",
        encoding="utf-8",
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _make_fake_codex(
        fake_bin,
        {
            "type": "phase_complete",
            "phase": "phase-001",
            "summary": "Phase one finished.",
            "changed_files": ["README.md"],
            "commands_run": ["fake"],
            "tests": {"status": "passed", "details": "fake"},
            "next_request": "review_and_continue",
        },
    )
    task_id = _create_task(hermes_home, repo)

    env = os.environ.copy()
    env["HERMES_HOME"] = str(hermes_home)
    env["HERMES_KANBAN_TASK"] = task_id
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    try:
        subprocess.run(
            [str(WRAPPER), str(repo), ".hermes/phases/phase-001.md", "1"],
            cwd=repo,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        task, comments, events = _task_snapshot(task_id)
        assert task.status == "blocked"
        conn = kb.connect()
        try:
            run = kb.latest_run(conn, task_id)
        finally:
            conn.close()
        assert run is not None
        assert run.metadata
        assert run.metadata.get("flow_graph", "").endswith("-phase-001-flow.svg")
        assert Path(run.metadata["flow_graph"]).exists()
        assert any("PHASE FINISHED: phase-001" in c.body for c in comments)
        assert any(
            e.kind == "blocked"
            and e.payload
            and "review before next phase" in e.payload.get("reason", "")
            for e in events
        )
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_codex_phase_wrapper_blocks_kanban_task_on_needs_input(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    repo = _make_repo()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _make_fake_codex_needs_input(fake_bin)
    task_id = _create_task(hermes_home, repo)

    env = os.environ.copy()
    env["HERMES_HOME"] = str(hermes_home)
    env["HERMES_KANBAN_TASK"] = task_id
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    try:
        subprocess.run(
            [str(WRAPPER), str(repo), ".hermes/phases/phase-001.md", "1"],
            cwd=repo,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        task, comments, events = _task_snapshot(task_id)
        assert task.status == "blocked"
        assert any("summary: Approve scope?" in c.body for c in comments)
        assert any(
            e.kind == "blocked"
            and e.payload
            and e.payload.get("reason") == "needs input: Approve scope?"
            for e in events
        )
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_gateway_notifier_delivers_phase_terminal_kanban_event(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    kb.init_db()

    with kb.connect() as conn:
        task_id = kb.create_task(
            conn,
            title="Phase task",
            body="notify me",
            assignee="codex",
            created_by="pytest",
        )
        kb.add_notify_sub(
            conn,
            task_id=task_id,
            platform="telegram",
            chat_id="12345",
            thread_id=None,
            user_id="nicola",
        )
        kb.complete_task(
            conn,
            task_id,
            result="phase done",
            summary="phase done",
            metadata={"phase": "phase-001"},
        )

    from gateway.config import Platform
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._running = True
    sent = []

    class FakeAdapter:
        async def send(self, chat_id, content, metadata=None):
            sent.append((chat_id, content, metadata))
            runner._running = False
            return SimpleNamespace(success=True, message_id="m1")

    runner.adapters = {Platform.TELEGRAM: FakeAdapter()}

    async def fast_sleep(_seconds):
        return None

    monkeypatch.setattr("gateway.run.asyncio.sleep", fast_sleep)

    import asyncio

    asyncio.run(runner._kanban_notifier_watcher(interval=1))

    assert sent
    chat_id, content, metadata = sent[0]
    assert chat_id == "12345"
    assert "Hermes Kanban update" in content
    assert f"Task: {task_id}" in content
    assert "Status: done" in content
    assert "phase done" in content
    assert metadata == {}
