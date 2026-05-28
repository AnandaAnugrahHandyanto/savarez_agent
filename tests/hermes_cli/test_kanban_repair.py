"""Tests for Kanban projection repair / reconciliation CLI behavior."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from hermes_cli import kanban as kanban_cli
from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    """Isolated HERMES_HOME with an empty kanban DB."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _run_cli(*argv: str) -> int:
    """Invoke the `hermes kanban …` argparse surface directly."""
    root = argparse.ArgumentParser()
    subp = root.add_subparsers(dest="cmd")
    kanban_cli.build_parser(subp)
    ns = root.parse_args(["kanban", *argv])
    return kanban_cli.kanban_command(ns)


def _insert_notify_sub(
    conn,
    *,
    task_id: str,
    platform: str = "discord",
    chat_id: str = "forum-1",
    thread_id: str = "thread-1",
    user_id: str | None = "user-1",
    notifier_profile: str | None = "default",
    last_event_id: int = 0,
) -> None:
    conn.execute(
        """
        INSERT INTO kanban_notify_subs (
            task_id, platform, chat_id, thread_id, user_id,
            notifier_profile, created_at, last_event_id
        ) VALUES (?, ?, ?, ?, ?, ?, 1234, ?)
        """,
        (task_id, platform, chat_id, thread_id, user_id, notifier_profile, last_event_id),
    )
    conn.commit()


def test_kanban_repair_json_reports_projection_orphans_without_mutating(kanban_home, capsys):
    """Dry-run repair should report orphaned projection rows without deleting them."""
    with kb.connect() as conn:
        task_id = kb.create_task(conn, title="live projected task")
        _insert_notify_sub(conn, task_id=task_id, chat_id="forum-1", thread_id="thread-live")
        _insert_notify_sub(conn, task_id="t_missing", chat_id="forum-1", thread_id="thread-orphan")

    rc = _run_cli("repair", "--json")

    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] is True
    assert report["projection_subscriptions"]["scanned"] == 2
    assert report["projection_subscriptions"]["orphaned"] == 1
    assert report["projection_subscriptions"]["removed"] == 0
    assert report["projection_subscriptions"]["orphans"] == [
        {
            "task_id": "t_missing",
            "platform": "discord",
            "chat_id": "forum-1",
            "thread_id": "thread-orphan",
        }
    ]

    with kb.connect() as conn:
        rows = kb.list_notify_subs(conn)
    assert {row["task_id"] for row in rows} == {task_id, "t_missing"}


def test_kanban_repair_apply_removes_orphaned_projection_rows_and_reports_count(kanban_home, capsys):
    """Apply mode should remove orphaned projection rows while preserving live rows."""
    with kb.connect() as conn:
        task_id = kb.create_task(conn, title="live projected task")
        _insert_notify_sub(conn, task_id=task_id, chat_id="forum-1", thread_id="thread-live")
        _insert_notify_sub(conn, task_id="t_missing", chat_id="forum-1", thread_id="thread-orphan")

    rc = _run_cli("repair", "--apply", "--json")

    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] is False
    assert report["projection_subscriptions"]["scanned"] == 2
    assert report["projection_subscriptions"]["orphaned"] == 1
    assert report["projection_subscriptions"]["removed"] == 1

    with kb.connect() as conn:
        rows = kb.list_notify_subs(conn)
    assert [(row["task_id"], row["thread_id"]) for row in rows] == [(task_id, "thread-live")]


def test_kanban_repair_reports_ambiguous_projection_bindings_without_mutating(kanban_home, capsys):
    """A single projected source bound to multiple live tasks should be loud.

    Gateway lifecycle shorthand intentionally refuses ambiguous bindings, so the
    reconciler must surface these collisions even though it cannot safely pick a
    winner automatically.
    """
    with kb.connect() as conn:
        first = kb.create_task(conn, title="first live task")
        second = kb.create_task(conn, title="second live task")
        _insert_notify_sub(conn, task_id=first, chat_id="forum-1", thread_id="thread-shared")
        _insert_notify_sub(conn, task_id=second, chat_id="forum-1", thread_id="thread-shared")

    rc = _run_cli("repair", "--json")

    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    projection = report["projection_subscriptions"]
    assert projection["ambiguous"] == 1
    assert projection["ambiguous_bindings"] == [
        {
            "platform": "discord",
            "chat_id": "forum-1",
            "thread_id": "thread-shared",
            "task_ids": sorted([first, second]),
        }
    ]
    assert projection["removed"] == 0

    with kb.connect() as conn:
        rows = kb.list_notify_subs(conn)
    assert {row["task_id"] for row in rows} == {first, second}


def test_kanban_repair_apply_removes_malformed_projection_rows(kanban_home, capsys):
    """Rows without a usable platform/chat target are unrecoverable locally."""
    with kb.connect() as conn:
        live = kb.create_task(conn, title="well formed live task")
        missing_platform = kb.create_task(conn, title="missing platform")
        missing_chat = kb.create_task(conn, title="missing chat")
        _insert_notify_sub(conn, task_id=live, platform="discord", chat_id="forum-1", thread_id="thread-live")
        _insert_notify_sub(conn, task_id=missing_platform, platform="", chat_id="forum-1", thread_id="thread-bad-platform")
        _insert_notify_sub(conn, task_id=missing_chat, platform="discord", chat_id="", thread_id="thread-bad-chat")

    rc = _run_cli("repair", "--apply", "--json")

    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    projection = report["projection_subscriptions"]
    assert projection["malformed"] == 2
    assert projection["removed"] == 2
    assert projection["malformed_rows"] == [
        {
            "task_id": missing_platform,
            "platform": "",
            "chat_id": "forum-1",
            "thread_id": "thread-bad-platform",
            "reason": "missing_platform",
        },
        {
            "task_id": missing_chat,
            "platform": "discord",
            "chat_id": "",
            "thread_id": "thread-bad-chat",
            "reason": "missing_chat_id",
        },
    ]

    with kb.connect() as conn:
        rows = kb.list_notify_subs(conn)
    assert [(row["task_id"], row["platform"], row["chat_id"], row["thread_id"]) for row in rows] == [
        (live, "discord", "forum-1", "thread-live")
    ]


def _write_discord_projection_config(home: Path) -> None:
    board_dir = home / "kanban" / "boards" / "default"
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / "discord-forum-tags.json").write_text(
        json.dumps(
            {
                "forum_channel_id": "forum-1",
                "status_to_tag": {
                    "ready": "ready-tag",
                    "blocked": "blocked-tag",
                    "running": "running-tag",
                    "done": "done-tag",
                },
                "assignee_to_tag": {
                    "default": "hermes-tag",
                    "hermes": "hermes-tag",
                    "daedalus": "daedalus-tag",
                },
            }
        ),
        encoding="utf-8",
    )


def test_kanban_repair_discord_audit_reports_thread_tag_and_title_mismatches(
    kanban_home, monkeypatch, capsys
):
    """Dry-run Discord audit should compare projected thread state to Kanban truth."""
    _write_discord_projection_config(kanban_home)
    with kb.connect() as conn:
        task_id = kb.create_task(
            conn,
            title="Canonical task title",
            assignee="hermes",
            initial_status="blocked",
        )
        _insert_notify_sub(conn, task_id=task_id, chat_id="forum-1", thread_id="thread-live")

    def fake_fetch_thread(thread_id: str) -> dict:
        assert thread_id == "thread-live"
        return {
            "id": "thread-live",
            "name": "● [running] Stale task title",
            "applied_tags": ["running-tag", "daedalus-tag"],
        }

    monkeypatch.setattr(kanban_cli, "_fetch_discord_thread_snapshot", fake_fetch_thread, raising=False)

    rc = _run_cli("repair", "--audit-discord", "--json")

    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] is True
    discord = report["discord_projection"]
    assert discord["scanned"] == 1
    assert discord["mismatched"] == 1
    assert discord["missing"] == 0
    assert discord["mismatches"] == [
        {
            "task_id": task_id,
            "thread_id": "thread-live",
            "chat_id": "forum-1",
            "expected": {
                "name": "🛑 [blocked] Canonical task title",
                "tags": ["blocked-tag", "hermes-tag"],
            },
            "actual": {
                "name": "● [running] Stale task title",
                "tags": ["running-tag", "daedalus-tag"],
            },
            "missing_tags": ["blocked-tag", "hermes-tag"],
            "unexpected_tags": ["running-tag", "daedalus-tag"],
        }
    ]


def test_kanban_repair_discord_audit_reports_missing_threads_without_mutating(
    kanban_home, monkeypatch, capsys
):
    """A vanished Discord thread should be reported, not silently treated as repaired."""
    _write_discord_projection_config(kanban_home)
    with kb.connect() as conn:
        task_id = kb.create_task(conn, title="Gone thread", assignee="hermes")
        _insert_notify_sub(conn, task_id=task_id, chat_id="forum-1", thread_id="thread-gone")

    def fake_fetch_thread(thread_id: str) -> dict | None:
        assert thread_id == "thread-gone"
        return None

    monkeypatch.setattr(kanban_cli, "_fetch_discord_thread_snapshot", fake_fetch_thread, raising=False)

    rc = _run_cli("repair", "--audit-discord", "--json")

    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    discord = report["discord_projection"]
    assert discord["scanned"] == 1
    assert discord["mismatched"] == 0
    assert discord["missing"] == 1
    assert discord["missing_threads"] == [
        {
            "task_id": task_id,
            "thread_id": "thread-gone",
            "chat_id": "forum-1",
            "expected": {
                "name": "▶ [ready] Gone thread",
                "tags": ["ready-tag", "hermes-tag"],
            },
        }
    ]

    with kb.connect() as conn:
        rows = kb.list_notify_subs(conn)
    assert [(row["task_id"], row["thread_id"]) for row in rows] == [(task_id, "thread-gone")]
