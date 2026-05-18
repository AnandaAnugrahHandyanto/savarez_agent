"""Tests for worker-block auto-subscribe → comment auto-unblock.

Card: t_0abf738d. Closes affected-flow #1 from t_02048c56: worker self-blocks
pending user input → user comments → worker (or replacement) wakes within
one dispatcher tick rather than sitting dead until manual `kanban unblock`.

Surface under test:
- :func:`hermes_cli.kanban_db.add_auto_unblock_sub` / ``list_auto_unblock_subs``
  / ``remove_auto_unblock_sub`` (new DB-layer helpers backing the auto-wake
  loop).
- :func:`hermes_cli.kanban_db.auto_unblock_on_comment` invoked from inside
  :func:`hermes_cli.kanban_db.dispatch_once` (new dispatcher tick rule).
- :func:`tools.kanban_tools._handle_block` writes a subscription row keyed
  on the worker profile when running under ``HERMES_KANBAN_TASK`` /
  ``HERMES_PROFILE``.

The contract is intentionally permissive: an unblock from this path is
indistinguishable from an explicit ``hermes kanban unblock`` for downstream
consumers (it lands in the same ``ready`` state and the same
parent-completion gating applies). The differentiator is the
``unblocked_by_comment`` event kind, which exists purely for audit.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    """Isolated HERMES_HOME with an empty kanban DB.

    Mirrors the fixture used across ``tests/hermes_cli/test_kanban_*.py``
    so tests in this file can be lifted/dropped without conftest gymnastics.
    """
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb._INITIALIZED_PATHS.clear()
    kb.init_db()
    # Tool-level tests below also need HERMES_KANBAN_TASK to be undefined
    # by default (the per-test monkeypatch.setenv flips it on as needed).
    # Same goes for HERMES_KANBAN_RUN_ID / HERMES_PROFILE which leak from
    # any kanban-worker process that runs the test suite (a self-hosted
    # worker writing this very test file, for instance) — without scrubbing
    # them, _handle_block calls block_task with the parent worker's run id
    # and gets rejected against the test task's actual current_run_id.
    for _leaky in (
        "HERMES_KANBAN_TASK",
        "HERMES_KANBAN_RUN_ID",
        "HERMES_KANBAN_CLAIM_LOCK",
        "HERMES_PROFILE",
    ):
        monkeypatch.delenv(_leaky, raising=False)
    return home


# ---------------------------------------------------------------------------
# DB-layer helpers
# ---------------------------------------------------------------------------


def test_add_auto_unblock_sub_is_idempotent_per_task_profile(kanban_home):
    """Calling add_auto_unblock_sub twice for the same (task, profile)
    leaves a single row — the auto-wake loop must not double-fire."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="x", assignee="default")
        kb.claim_task(conn, t)
        kb.block_task(conn, t, reason="need input")

        kb.add_auto_unblock_sub(conn, task_id=t, notifier_profile="default")
        kb.add_auto_unblock_sub(conn, task_id=t, notifier_profile="default")

        subs = kb.list_auto_unblock_subs(conn, task_id=t)
        assert len(subs) == 1
        assert subs[0]["notifier_profile"] == "default"
        assert subs[0]["task_id"] == t


def test_add_auto_unblock_sub_records_block_event_baseline(kanban_home):
    """The subscription must capture the latest ``blocked`` event id so the
    dispatcher only counts comments that arrive AFTER the block — comments
    that predate the block must not auto-unblock."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="x", assignee="default")
        kb.add_comment(conn, t, author="alex", body="early comment")
        kb.claim_task(conn, t)
        kb.block_task(conn, t, reason="need input")

        kb.add_auto_unblock_sub(conn, task_id=t, notifier_profile="default")

        sub = kb.list_auto_unblock_subs(conn, task_id=t)[0]
        # Find the blocked event id
        rows = conn.execute(
            "SELECT id FROM task_events WHERE task_id=? AND kind='blocked' "
            "ORDER BY id DESC LIMIT 1",
            (t,),
        ).fetchall()
        latest_block_event_id = int(rows[0]["id"])
        assert int(sub["block_event_id"]) == latest_block_event_id


# ---------------------------------------------------------------------------
# Dispatcher tick rule
# ---------------------------------------------------------------------------


def test_auto_unblock_on_comment_promotes_blocked_to_ready(kanban_home):
    """Happy path: subscribed task gets a non-self comment → ready."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="x", assignee="default")
        kb.claim_task(conn, t)
        kb.block_task(conn, t, reason="need input")
        kb.add_auto_unblock_sub(conn, task_id=t, notifier_profile="default")

        kb.add_comment(conn, t, author="alex", body="here's your answer")

        promoted = kb.auto_unblock_on_comment(conn)
        assert promoted == [t]
        assert kb.get_task(conn, t).status == "ready"


def test_auto_unblock_on_comment_emits_audit_event(kanban_home):
    with kb.connect() as conn:
        t = kb.create_task(conn, title="x", assignee="default")
        kb.claim_task(conn, t)
        kb.block_task(conn, t, reason="need input")
        kb.add_auto_unblock_sub(conn, task_id=t, notifier_profile="default")
        kb.add_comment(conn, t, author="alex", body="answer")
        kb.auto_unblock_on_comment(conn)

        kinds = [
            r["kind"]
            for r in conn.execute(
                "SELECT kind FROM task_events WHERE task_id=? ORDER BY id ASC",
                (t,),
            ).fetchall()
        ]
    assert "unblocked_by_comment" in kinds


def test_auto_unblock_on_comment_ignores_self_authored_comment(kanban_home):
    """Loop guard: a worker that comments on its own blocked task while
    its replacement hasn't booted yet must NOT auto-unblock itself. The
    author of the unblocking comment must differ from the subscription's
    ``notifier_profile``."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="x", assignee="default")
        kb.claim_task(conn, t)
        kb.block_task(conn, t, reason="need input")
        kb.add_auto_unblock_sub(conn, task_id=t, notifier_profile="default")

        kb.add_comment(conn, t, author="default", body="my own note")

        promoted = kb.auto_unblock_on_comment(conn)
        assert promoted == []
        assert kb.get_task(conn, t).status == "blocked"


def test_auto_unblock_on_comment_skips_comments_before_block(kanban_home):
    with kb.connect() as conn:
        t = kb.create_task(conn, title="x", assignee="default")
        kb.add_comment(conn, t, author="alex", body="pre-block context")
        kb.claim_task(conn, t)
        kb.block_task(conn, t, reason="need input")
        kb.add_auto_unblock_sub(conn, task_id=t, notifier_profile="default")
        # No new comment after the block.

        promoted = kb.auto_unblock_on_comment(conn)
        assert promoted == []
        assert kb.get_task(conn, t).status == "blocked"


def test_auto_unblock_on_comment_coalesces_multiple_comments(kanban_home):
    """Two comments must yield one unblock, not two state transitions."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="x", assignee="default")
        kb.claim_task(conn, t)
        kb.block_task(conn, t, reason="need input")
        kb.add_auto_unblock_sub(conn, task_id=t, notifier_profile="default")
        kb.add_comment(conn, t, author="alex", body="answer A")
        kb.add_comment(conn, t, author="alex", body="and also B")

        promoted = kb.auto_unblock_on_comment(conn)
        assert promoted == [t]
        unblock_events = conn.execute(
            "SELECT COUNT(*) AS n FROM task_events "
            "WHERE task_id=? AND kind='unblocked_by_comment'",
            (t,),
        ).fetchone()
        assert int(unblock_events["n"]) == 1


def test_auto_unblock_on_comment_removes_subscription_after_promote(kanban_home):
    """After a successful auto-unblock the row is removed so the next
    block-cycle starts fresh and the dispatcher doesn't keep re-checking
    a stale ``blocked → ready`` transition that already happened."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="x", assignee="default")
        kb.claim_task(conn, t)
        kb.block_task(conn, t, reason="need input")
        kb.add_auto_unblock_sub(conn, task_id=t, notifier_profile="default")
        kb.add_comment(conn, t, author="alex", body="answer")
        kb.auto_unblock_on_comment(conn)

        assert kb.list_auto_unblock_subs(conn, task_id=t) == []


def test_auto_unblock_on_comment_no_subscription_is_noop(kanban_home):
    """A blocked task without a subscription must NOT be auto-unblocked.
    Subscription is the explicit opt-in — operator-blocked tasks (no worker
    intent) stay blocked even when somebody comments."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="x", assignee="default")
        kb.claim_task(conn, t)
        kb.block_task(conn, t, reason="operator hold")
        kb.add_comment(conn, t, author="alex", body="any update?")

        promoted = kb.auto_unblock_on_comment(conn)
        assert promoted == []
        assert kb.get_task(conn, t).status == "blocked"


def test_dispatch_once_runs_auto_unblock(kanban_home):
    """The dispatcher tick must include the auto-unblock pass and the
    resulting ready task must be claimable in the same tick."""
    spawned: list[tuple[str, str, str]] = []

    def _spawn(task, workspace_path, board):
        spawned.append((task.id, task.assignee, str(workspace_path)))
        return 12345  # fake pid

    with kb.connect() as conn:
        t = kb.create_task(conn, title="x", assignee="default")
        kb.claim_task(conn, t)
        kb.block_task(conn, t, reason="need input")
        kb.add_auto_unblock_sub(conn, task_id=t, notifier_profile="default")
        kb.add_comment(conn, t, author="alex", body="answer")

        result = kb.dispatch_once(conn, spawn_fn=_spawn)

    assert any(s[0] == t for s in spawned), (
        "auto-unblocked task must spawn in the same tick"
    )
    # The DispatchResult.spawned list mirrors the spawn callback.
    assert any(entry[0] == t for entry in result.spawned)


# ---------------------------------------------------------------------------
# Tool-handler integration
# ---------------------------------------------------------------------------


def test_kanban_block_tool_writes_auto_unblock_sub(monkeypatch, kanban_home):
    """When a worker calls ``kanban_block`` from inside a dispatcher-spawned
    run (HERMES_KANBAN_TASK + HERMES_PROFILE set), a subscription row is
    written transparently. Workers don't have to author it themselves —
    that's the whole point of this card."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="x", assignee="default")
        kb.claim_task(conn, t)

    monkeypatch.setenv("HERMES_KANBAN_TASK", t)
    monkeypatch.setenv("HERMES_PROFILE", "default")

    from tools import kanban_tools as kt
    out = kt._handle_block({"reason": "need input on routing"})
    payload = json.loads(out)
    assert payload.get("ok") is True, payload

    with kb.connect() as conn:
        subs = kb.list_auto_unblock_subs(conn, task_id=t)
    assert len(subs) == 1
    assert subs[0]["notifier_profile"] == "default"


def test_kanban_block_tool_skips_sub_for_review_required_reason(
    monkeypatch, kanban_home
):
    """``review-required`` block reasons must NOT auto-subscribe. Those
    tasks need a human-authored unblock (or an LGTM comment, deferred to
    a follow-up card per the task body). Auto-unblocking on any comment
    would let a chatty reviewer accidentally promote a task that still
    needs explicit sign-off."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="x", assignee="default")
        kb.claim_task(conn, t)

    monkeypatch.setenv("HERMES_KANBAN_TASK", t)
    monkeypatch.setenv("HERMES_PROFILE", "default")

    from tools import kanban_tools as kt
    out = kt._handle_block(
        {"reason": "review-required: 4/4 ACs verified, needs sign-off"}
    )
    payload = json.loads(out)
    assert payload.get("ok") is True, payload

    with kb.connect() as conn:
        subs = kb.list_auto_unblock_subs(conn, task_id=t)
    assert subs == []


def test_kanban_block_tool_outside_worker_does_not_write_sub(
    monkeypatch, kanban_home
):
    """Operator-driven block (CLI / dashboard, no HERMES_KANBAN_TASK) must
    not insert a subscription — auto-unblock is a worker-intent loop, not
    a global behaviour."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="x", assignee="default")
        kb.claim_task(conn, t)

    monkeypatch.delenv("HERMES_KANBAN_TASK", raising=False)
    monkeypatch.delenv("HERMES_PROFILE", raising=False)

    # Call the DB layer directly (mirrors what the CLI does for an
    # operator-driven block — no worker tool involved).
    with kb.connect() as conn:
        assert kb.block_task(conn, t, reason="operator hold")
        subs = kb.list_auto_unblock_subs(conn, task_id=t)
    assert subs == []


