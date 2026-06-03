"""Dashboard Kanban Viewer API tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def client(monkeypatch, _isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

    client = TestClient(app)
    client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
    return client


def test_kanban_viewer_lists_boards_with_live_counts(client):
    from hermes_cli import kanban_db as kb

    kb.create_board("release", name="Release Train", description="Ship the next release")
    with kb.connect_closing(board="release") as conn:
        ready = kb.create_task(
            conn,
            title="Cut release candidate",
            assignee="builder",
            created_by="tester",
            priority=10,
            initial_status="running",
            board="release",
        )
        blocked = kb.create_task(
            conn,
            title="Wait for signing keys",
            assignee="ops",
            created_by="tester",
            initial_status="running",
            board="release",
        )
        kb.block_task(conn, blocked, reason="keys unavailable")
        kb.complete_task(conn, ready, result="rc cut")

    resp = client.get("/api/kanban/boards")

    assert resp.status_code == 200
    boards = resp.json()["boards"]
    release = next(board for board in boards if board["slug"] == "release")
    assert release["name"] == "Release Train"
    assert release["description"] == "Ship the next release"
    assert release["counts"]["done"] == 1
    assert release["counts"]["blocked"] == 1
    assert release["total_tasks"] == 2


def test_kanban_viewer_task_payload_includes_relationships_recent_events_and_filters(client):
    from hermes_cli import kanban_db as kb

    kb.create_board("product", name="Product")
    with kb.connect_closing(board="product") as conn:
        parent = kb.create_task(
            conn,
            title="Design API",
            body="Define the viewer payload contract",
            assignee="architect",
            created_by="tester",
            priority=5,
            initial_status="running",
            session_id="sess-1",
            board="product",
        )
        child = kb.create_task(
            conn,
            title="Build UI",
            body="Render kanban cards",
            assignee="frontend",
            created_by="tester",
            priority=3,
            parents=[parent],
            initial_status="running",
            session_id="sess-1",
            board="product",
        )
        other = kb.create_task(
            conn,
            title="Other session task",
            assignee="other",
            created_by="tester",
            initial_status="running",
            session_id="sess-2",
            board="product",
        )
        kb.add_comment(conn, child, "reviewer", "Looks good")
        kb.complete_task(conn, parent, result="contract ready")
        kb.archive_task(conn, other)

    resp = client.get("/api/kanban/tasks?board=product&session_id=sess-1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["board"]["slug"] == "product"
    assert data["counts"]["done"] == 1
    ids = {task["id"] for task in data["tasks"]}
    assert ids == {parent, child}
    child_payload = next(task for task in data["tasks"] if task["id"] == child)
    assert child_payload["parents"] == [parent]
    assert child_payload["comments_count"] == 1
    assert child_payload["recent_events"]
    assert child_payload["status"] == "todo"
    assert "Other session task" not in {task["title"] for task in data["tasks"]}


def test_kanban_viewer_rejects_invalid_filters(client):
    resp = client.get("/api/kanban/tasks?board=Product With Spaces&status=sideways")

    assert resp.status_code == 400
