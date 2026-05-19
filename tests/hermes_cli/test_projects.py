from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb
from hermes_cli import projects


@pytest.fixture(autouse=True)
def hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_KANBAN_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_KANBAN_DB", raising=False)
    monkeypatch.delenv("HERMES_KANBAN_BOARD", raising=False)
    kb._INITIALIZED_PATHS.clear()
    yield tmp_path
    kb._INITIALIZED_PATHS.clear()


def test_add_and_resolve_project_by_slug_and_slack_channel(hermes_home):
    args = argparse.Namespace(
        slug="cotm",
        board="cotm",
        name="COTM",
        repo="/tmp/cotm",
        workspace="worktree",
        slack_channel="C123",
        slack_name="project-cotm",
        assignee="orchestrator",
        mention_user="U999",
        json=False,
    )
    assert projects.add_project(args) == 0
    assert (hermes_home / "projects.yaml").exists()

    slug, project = projects.resolve_project("cotm")
    assert slug == "cotm"
    assert project["board"] == "cotm"
    assert project["slack"]["channel_id"] == "C123"

    slug, project = projects.resolve_project("C123", platform="slack")
    assert slug == "cotm"
    assert project["default_assignee"] == "orchestrator"

    slug, _ = projects.resolve_project("#project-cotm", platform="slack")
    assert slug == "cotm"


def test_route_creates_board_task_and_notification(hermes_home):
    projects.save_registry({
        "version": 1,
        "projects": {
            "cotm": {
                "name": "COTM",
                "board": "cotm",
                "repo": "/tmp/cotm",
                "default_workspace": "worktree",
                "default_assignee": "orchestrator",
                "slack": {"channel_id": "C123", "channel_name": "project-cotm"},
                "context": ["No DB schema changes unless explicitly authorized."],
            }
        },
    })
    args = argparse.Namespace(
        project=None,
        platform="slack",
        chat_id="C123",
        thread_id="177",
        user_id="U999",
        assignee=None,
        workspace=None,
        title=None,
        json=False,
        text=["Fix", "the", "flaky", "auth", "tests"],
    )
    assert projects.route_project(args) == 0

    conn = kb.connect(board="cotm")
    try:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
        assert len(rows) == 1
        task = dict(rows[0])
        assert task["title"] == "Fix the flaky auth tests"
        assert task["assignee"] == "orchestrator"
        assert task["workspace_kind"] == "worktree"
        assert "No DB schema changes" in task["body"]
        subs = kb.list_notify_subs(conn, task["id"])
        assert len(subs) == 1
        assert subs[0]["platform"] == "slack"
        assert subs[0]["chat_id"] == "C123"
        assert subs[0]["thread_id"] == "177"
    finally:
        conn.close()


def test_run_slash_route_outputs_task_id(hermes_home):
    projects.save_registry({
        "version": 1,
        "projects": {"cotm": {"board": "cotm", "slack": {"channel_id": "C123"}}},
    })
    out = projects.run_slash("route --chat-id C123 ship the router")
    assert "Routed cotm -> cotm/t_" in out
