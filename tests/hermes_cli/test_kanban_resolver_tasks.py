"""Tests for one-step resolver task creation for blocked Kanban cards."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _block_task(conn, title: str = "blocked task") -> str:
    task_id = kb.create_task(conn, title=title, assignee="dev")
    kb.claim_task(conn, task_id)
    assert kb.block_task(
        conn,
        task_id,
        reason="tests cannot run until the shared fix lands",
        expected_run_id=kb.get_task(conn, task_id).current_run_id,
    )
    assert kb.get_task(conn, task_id).status == "blocked"
    return task_id


def _latest_block_event_payload(conn, task_id: str) -> dict:
    row = conn.execute(
        "SELECT payload FROM task_events WHERE task_id = ? AND kind = 'blocked' "
        "ORDER BY id DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    assert row is not None
    import json

    return json.loads(row["payload"])


def test_create_resolver_task_links_blocked_card_and_auto_promotes_after_resolver_done(kanban_home: Path) -> None:
    with kb.connect() as conn:
        blocked = _block_task(conn)

        resolver_id = kb.create_resolver_task(
            conn,
            blocked,
            title="fix shared compile failure",
            body="Repair the compile error so dependent tests can run.",
            assignee="builder",
            created_by="operator",
            idempotency_key="compile-fix",
        )

        resolver = kb.get_task(conn, resolver_id)
        assert resolver is not None
        assert resolver.title == "fix shared compile failure"
        assert resolver.assignee == "builder"
        assert resolver.status == "ready"
        assert kb.parent_ids(conn, blocked) == [resolver_id]

        payload = _latest_block_event_payload(conn, blocked)
        assert payload["blocked_by"] == [resolver_id]
        assert payload["auto_unblock_when_blockers_done"] is True

        assert kb.recompute_ready(conn) == 0
        assert kb.get_task(conn, blocked).status == "blocked"

        assert kb.complete_task(conn, resolver_id, result="fixed")
        # complete_task() immediately recomputes dependents; the blocked card
        # should already be ready before the next dispatcher tick.
        assert kb.get_task(conn, blocked).status == "ready"
        assert kb.recompute_ready(conn) == 0


def test_create_resolver_task_is_idempotent_for_same_operation(kanban_home: Path) -> None:
    with kb.connect() as conn:
        blocked = _block_task(conn)

        first = kb.create_resolver_task(
            conn,
            blocked,
            title="fix flaky dependency",
            assignee="qa",
            created_by="operator",
            idempotency_key="flaky-dependency",
        )
        second = kb.create_resolver_task(
            conn,
            blocked,
            title="fix flaky dependency",
            assignee="qa",
            created_by="operator",
            idempotency_key="flaky-dependency",
        )

        assert second == first
        assert kb.parent_ids(conn, blocked) == [first]
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM task_links WHERE parent_id = ? AND child_id = ?",
            (first, blocked),
        ).fetchone()["n"] == 1
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE idempotency_key = ?",
            (f"resolver:{blocked}:flaky-dependency",),
        ).fetchone()["n"] == 1


def test_create_resolver_task_rejects_non_blocked_or_missing_task(kanban_home: Path) -> None:
    with kb.connect() as conn:
        ready = kb.create_task(conn, title="not blocked")
        with pytest.raises(ValueError, match="expected 'blocked'"):
            kb.create_resolver_task(conn, ready, title="resolver", assignee="dev")
        with pytest.raises(ValueError, match="not found"):
            kb.create_resolver_task(conn, "t_missing", title="resolver", assignee="dev")
