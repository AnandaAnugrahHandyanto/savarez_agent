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


def test_create_task_persists_origin_report_to_metadata(kanban_home):
    metadata = {
        "origin": {
            "platform": "slack",
            "chat_id": "C0B67947LMA",
            "thread_id": "1779768050.823539",
        },
        "report_to": {
            "platform": "slack",
            "chat_id": "C0B67947LMA",
            "thread_id": "1779768050.823539",
        },
        "routing": {
            "version": "slack-kanban-routing.v1",
            "matched_key": "slack:C0B67947LMA:1779768050.823539",
            "board": "invest-system-build",
        },
    }

    with kb.connect() as conn:
        task_id = kb.create_task(conn, title="routed", metadata=metadata)
        task = kb.get_task(conn, task_id)
        events = kb.list_events(conn, task_id)

    assert task.metadata == metadata
    assert events[0].payload["metadata"] == metadata


def test_initial_blocked_task_stays_blocked_after_ready_recompute(kanban_home):
    metadata = {
        "routing": {
            "version": "slack-kanban-routing.v1",
            "protected_scope": True,
            "matched_terms": ["m1"],
        }
    }

    with kb.connect() as conn:
        task_id = kb.create_task(
            conn,
            title="protected route",
            initial_status="blocked",
            metadata=metadata,
        )
        promoted = kb.recompute_ready(conn)
        task = kb.get_task(conn, task_id)
        events = kb.list_events(conn, task_id)

    assert promoted == 0
    assert task is not None
    assert task.status == "blocked"
    assert any(event.kind == "blocked" for event in events)
