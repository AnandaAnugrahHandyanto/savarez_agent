from pathlib import Path

import pytest

from alert_remediation.kanban import KanbanCardDraft, create_kanban_card
from hermes_cli import kanban_db as kb


@pytest.fixture
def isolated_kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_KANBAN_DB", raising=False)
    monkeypatch.delenv("HERMES_KANBAN_BOARD", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _draft(initial_status="running"):
    return KanbanCardDraft(
        title="[critical] wireguard on do-wireguard-01: peer handshake stale > 15m",
        body="## Detected alert\nSource: wireguard-watchdog\n",
        assignee="sysadmin",
        idempotency_key="alert:wireguard:do-wireguard-01:stale-handshake",
        initial_status=initial_status,
    )


def test_create_kanban_card_inserts_task_from_draft(isolated_kanban_home):
    result = create_kanban_card(_draft(), created_by="alert-remediation-test")

    assert result.created is True
    assert result.task_id

    with kb.connect() as conn:
        task = kb.get_task(conn, result.task_id)

    assert task is not None
    assert task.title == _draft().title
    assert task.body == _draft().body
    assert task.assignee == "sysadmin"
    assert task.status == "ready"
    assert task.created_by == "alert-remediation-test"
    assert task.idempotency_key == "alert:wireguard:do-wireguard-01:stale-handshake"
    assert result.status == "ready"


def test_create_kanban_card_reuses_existing_task_by_idempotency_key(isolated_kanban_home):
    first = create_kanban_card(_draft(), created_by="alert-remediation-test")
    second = create_kanban_card(_draft(), created_by="alert-remediation-test")

    assert first.created is True
    assert second.created is False
    assert second.task_id == first.task_id

    with kb.connect() as conn:
        tasks = kb.list_tasks(conn)

    assert len(tasks) == 1


def test_create_kanban_card_preserves_blocked_approval_status(isolated_kanban_home):
    result = create_kanban_card(_draft(initial_status="blocked"))

    assert result.created is True
    assert result.status == "blocked"

    with kb.connect() as conn:
        task = kb.get_task(conn, result.task_id)

    assert task is not None
    assert task.status == "blocked"


def test_create_kanban_card_supports_board_argument(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_KANBAN_DB", raising=False)
    monkeypatch.delenv("HERMES_KANBAN_BOARD", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = create_kanban_card(_draft(), board="alerts-pilot")

    assert result.created is True
    with kb.connect(board="alerts-pilot") as conn:
        task = kb.get_task(conn, result.task_id)
    assert task is not None
    assert task.idempotency_key == _draft().idempotency_key
