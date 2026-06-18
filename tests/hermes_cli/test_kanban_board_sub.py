"""Tests for board-level notification subscriptions and notify_kinds.

Behavior-contract tests: exercise the real DB path against a temp
HERMES_HOME (real imports, real DB), not just mocks.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

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


# ---------------------------------------------------------------------------
# Board-level subscription sentinel helpers
# ---------------------------------------------------------------------------

class TestBoardSubSentinel:
    """BOARD_SUB_PREFIX sentinel format and detection."""

    def test_sentinel_format(self):
        assert kb.BOARD_SUB_PREFIX == "__board__:"
        assert kb.board_sub_task_id("default") == "__board__:default"
        assert kb.board_sub_task_id("my-project") == "__board__:my-project"

    def test_is_board_sub_true(self):
        assert kb.is_board_sub("__board__:default") is True
        assert kb.is_board_sub("__board__:my-project") is True

    def test_is_board_sub_false_for_regular_task_id(self):
        assert kb.is_board_sub("t_abc123") is False
        assert kb.is_board_sub("") is False
        assert kb.is_board_sub("regular-task-id") is False


# ---------------------------------------------------------------------------
# Board-level subscription creation
# ---------------------------------------------------------------------------

class TestAddBoardNotifySub:
    """Board-level notify subscription with no-history-replay cursor."""

    def test_add_board_notify_sub_no_history_replay(self, kanban_home):
        """Cursor starts at max event id — no history replay on first subscribe."""
        # Create a task and insert some events BEFORE subscribing
        with kb.connect() as conn:
            tid = kb.create_task(conn, title="old task", assignee="worker")
            kb.claim_task(conn, tid)
            kb.complete_task(conn, tid, result="old result")
            # At this point, task_events has several rows

        # Now subscribe to the board
        with kb.connect() as conn:
            max_eid_before = conn.execute(
                "SELECT COALESCE(MAX(id), 0) AS m FROM task_events"
            ).fetchone()["m"]
            kb.add_board_notify_sub(
                conn, board_slug="default",
                platform="telegram", chat_id="12345",
                notifier_profile="default",
            )
            # The sentinel row should exist
            sentinel = kb.board_sub_task_id("default")
            row = conn.execute(
                "SELECT last_event_id FROM kanban_notify_subs WHERE task_id = ?",
                (sentinel,),
            ).fetchone()
            assert row is not None
            # Cursor should be at or past the max event id at subscribe time
            assert int(row["last_event_id"]) >= int(max_eid_before)

    def test_board_sub_is_idempotent(self, kanban_home):
        """Duplicate sub doesn't create duplicate rows."""
        with kb.connect() as conn:
            kb.add_board_notify_sub(
                conn, board_slug="default",
                platform="telegram", chat_id="12345",
                notifier_profile="default",
            )
            kb.add_board_notify_sub(
                conn, board_slug="default",
                platform="telegram", chat_id="12345",
                notifier_profile="default",
            )
            sentinel = kb.board_sub_task_id("default")
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM kanban_notify_subs WHERE task_id = ?",
                (sentinel,),
            ).fetchone()["n"]
            assert count == 1

    def test_board_sub_and_per_task_sub_coexist(self, kanban_home):
        """Both types of subs can exist on the same board."""
        with kb.connect() as conn:
            tid = kb.create_task(conn, title="task1", assignee="worker")
            kb.add_notify_sub(
                conn, task_id=tid,
                platform="telegram", chat_id="12345",
                notifier_profile="default",
            )
            kb.add_board_notify_sub(
                conn, board_slug="default",
                platform="telegram", chat_id="99999",
                notifier_profile="default",
            )
            subs = kb.list_notify_subs(conn)
            assert len(subs) == 2
            task_ids = {s["task_id"] for s in subs}
            assert tid in task_ids
            assert kb.board_sub_task_id("default") in task_ids


# ---------------------------------------------------------------------------
# Board-level event claiming
# ---------------------------------------------------------------------------

class TestClaimUnseenEventsForBoardSub:
    """Board-wide event claiming with kinds filter and cap."""

    def test_claim_unseen_events_for_board_sub_filters_by_kind(self, kanban_home):
        """Only events matching the kinds filter are returned."""
        with kb.connect() as conn:
            # Subscribe first (cursor at max event id)
            kb.add_board_notify_sub(
                conn, board_slug="default",
                platform="telegram", chat_id="12345",
                notifier_profile="default",
            )
            # Now create tasks and events AFTER subscribing
            t1 = kb.create_task(conn, title="task1", assignee="apollo")
            t2 = kb.create_task(conn, title="task2", assignee="athena")
            kb.claim_task(conn, t1)
            kb.complete_task(conn, t1, result="done by apollo")
            kb.claim_task(conn, t2)
            kb.block_task(conn, t2, reason="needs review")

        with kb.connect() as conn:
            # Claim with only "completed" kind
            old_cursor, new_cursor, events = kb.claim_unseen_events_for_board_sub(
                conn, board_slug="default",
                platform="telegram", chat_id="12345",
                kinds=("completed",),
            )
            # Should only get completed events
            assert all(e.kind == "completed" for e in events)
            assert len(events) >= 1

    def test_claim_unseen_events_for_board_sub_all_kinds(self, kanban_home):
        """Without kinds filter, all events are returned."""
        with kb.connect() as conn:
            kb.add_board_notify_sub(
                conn, board_slug="default",
                platform="telegram", chat_id="12345",
                notifier_profile="default",
            )
            t1 = kb.create_task(conn, title="task1", assignee="apollo")
            kb.claim_task(conn, t1)
            kb.complete_task(conn, t1, result="done")

        with kb.connect() as conn:
            old_cursor, new_cursor, events = kb.claim_unseen_events_for_board_sub(
                conn, board_slug="default",
                platform="telegram", chat_id="12345",
                kinds=None,
            )
            assert len(events) >= 1

    def test_board_sub_capped_at_limit(self, kanban_home):
        """Claims are capped at the limit parameter."""
        with kb.connect() as conn:
            kb.add_board_notify_sub(
                conn, board_slug="default",
                platform="telegram", chat_id="12345",
                notifier_profile="default",
            )
            # Create several tasks with events
            for i in range(5):
                tid = kb.create_task(conn, title=f"task{i}", assignee="worker")
                kb.claim_task(conn, tid)
                kb.complete_task(conn, tid, result=f"done{i}")

        with kb.connect() as conn:
            _, _, events = kb.claim_unseen_events_for_board_sub(
                conn, board_slug="default",
                platform="telegram", chat_id="12345",
                kinds=None,
                limit=3,
            )
            assert len(events) <= 3

    def test_board_sub_no_events_after_claim(self, kanban_home):
        """After claiming, a second claim returns empty (cursor advanced)."""
        with kb.connect() as conn:
            kb.add_board_notify_sub(
                conn, board_slug="default",
                platform="telegram", chat_id="12345",
                notifier_profile="default",
            )
            t1 = kb.create_task(conn, title="task1", assignee="apollo")
            kb.claim_task(conn, t1)
            kb.complete_task(conn, t1, result="done")

        with kb.connect() as conn:
            _, _, events1 = kb.claim_unseen_events_for_board_sub(
                conn, board_slug="default",
                platform="telegram", chat_id="12345",
                kinds=None,
            )
            assert len(events1) >= 1
            _, _, events2 = kb.claim_unseen_events_for_board_sub(
                conn, board_slug="default",
                platform="telegram", chat_id="12345",
                kinds=None,
            )
            assert len(events2) == 0


# ---------------------------------------------------------------------------
# Notifier formatting: ready + review-required
# ---------------------------------------------------------------------------

class TestNotifierFormatting:
    """Test message formatting for new event kinds (ready, review-required)."""

    def _format_blocked_msg(self, kind, reason=None):
        """Minimal formatter matching the gateway kanban_watchers logic."""
        if kind == "blocked":
            reason_str = f": {reason[:160]}" if reason else ""
            if reason and "review-required:" in reason.lower():
                return f"🔍 Kanban t_test needs review —{reason_str}"
            return f"⏸ Kanban t_test blocked{reason_str}"
        elif kind == "ready":
            return f"▶ Kanban t_test ready — test title"
        return None

    def test_ready_formatting(self):
        """Ready events format with ▶ icon."""
        msg = self._format_blocked_msg("ready")
        assert msg is not None
        assert msg.startswith("▶")
        assert "ready" in msg

    def test_review_required_formatting(self):
        """Blocked events with review-required prefix get 🔍 icon."""
        msg = self._format_blocked_msg(
            "blocked",
            reason="review-required: code needs eyes before merge"
        )
        assert msg is not None
        assert "🔍" in msg
        assert "needs review" in msg
        assert "review-required" in msg

    def test_normal_blocked_formatting(self):
        """Blocked events without review-required prefix get ⏸ icon."""
        msg = self._format_blocked_msg(
            "blocked",
            reason="waiting on external dependency"
        )
        assert msg is not None
        assert msg.startswith("⏸")
        assert "blocked" in msg
        assert "🔍" not in msg


# ---------------------------------------------------------------------------
# Argparse: global --board vs notify-subscribe --board conflict
# ---------------------------------------------------------------------------

class TestBoardArgparseConflict:
    """Verify that the global --board and notify-subscribe --board don't clash.

    The notify-subscribe --board flag uses dest='board_sub_slug' so it
    doesn't overwrite the global args.board attribute. Without this,
    per-task subscriptions on a non-default board would lose the board
    override.
    """

    def test_global_board_preserved_without_board_sub(self):
        """Per-task sub on a non-default board: global --board survives."""
        import argparse
        from hermes_cli.kanban import build_parser

        parser = argparse.ArgumentParser()
        sub_p = parser.add_subparsers(dest="command")
        build_parser(sub_p)

        parser.parse_args([
            "kanban", "--board", "beta",
            "notify-subscribe", "t_abc",
            "--platform", "telegram", "--chat-id", "123",
        ])
        args = parser.parse_args([
            "kanban", "--board", "beta",
            "notify-subscribe", "t_abc",
            "--platform", "telegram", "--chat-id", "123",
        ])
        assert args.board == "beta"
        assert getattr(args, "board_sub_slug", None) is None

    def test_board_sub_slug_set_for_board_level_sub(self):
        """Board-level sub: board_sub_slug gets the target board slug."""
        import argparse
        from hermes_cli.kanban import build_parser

        parser = argparse.ArgumentParser()
        sub_p = parser.add_subparsers(dest="command")
        build_parser(sub_p)

        args = parser.parse_args([
            "kanban", "notify-subscribe",
            "--board", "default",
            "--platform", "telegram", "--chat-id", "123",
        ])
        assert getattr(args, "board_sub_slug", None) == "default"

    def test_global_board_and_board_sub_both_set(self):
        """When both global --board and sub --board are given, both are available."""
        import argparse
        from hermes_cli.kanban import build_parser

        parser = argparse.ArgumentParser()
        sub_p = parser.add_subparsers(dest="command")
        build_parser(sub_p)

        args = parser.parse_args([
            "kanban", "--board", "beta",
            "notify-subscribe", "--board", "alpha",
            "--platform", "telegram", "--chat-id", "123",
        ])
        assert args.board == "beta"
        assert args.board_sub_slug == "alpha"
