import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from gateway.config import Platform
from gateway.run import GatewayRunner
from hermes_cli import kanban_db as kb
from tools.kanban_tools import _handle_create


class RecordingAdapter:
    def __init__(self):
        self.sent = []

    async def send(self, chat_id, text, metadata=None):
        self.sent.append({"chat_id": chat_id, "text": text, "metadata": metadata or {}})


class DisconnectedAdapters(dict):
    """Expose a platform during collection, then simulate disconnect on get()."""

    def get(self, key, default=None):
        return None


async def _run_one_notifier_tick(monkeypatch, runner):
    real_sleep = asyncio.sleep

    async def fake_sleep(delay):
        if delay == 5:
            return None
        runner._running = False
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    await runner._kanban_notifier_watcher(interval=1)


def _make_runner(adapter, platform=Platform.TELEGRAM):
    runner = GatewayRunner.__new__(GatewayRunner)
    runner._running = True
    runner.adapters = {platform: adapter}
    runner._kanban_sub_fail_counts = {}
    return runner


def _advance_subscription_to_now(tid, platform="telegram", chat_id="chat-1", thread_id=None):
    conn = kb.connect()
    try:
        cursor = conn.execute("SELECT COALESCE(MAX(id), 0) FROM task_events WHERE task_id = ?", (tid,)).fetchone()[0]
        kb.advance_notify_cursor(
            conn,
            task_id=tid,
            platform=platform,
            chat_id=chat_id,
            thread_id=thread_id,
            new_cursor=int(cursor or 0),
        )
    finally:
        conn.close()


def _create_completed_subscription(summary="done once"):
    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="notify once", assignee="worker")
        kb.add_notify_sub(conn, task_id=tid, platform="telegram", chat_id="chat-1")
    finally:
        conn.close()
    _advance_subscription_to_now(tid)
    conn = kb.connect()
    try:
        kb.complete_task(conn, tid, summary=summary)
        return tid
    finally:
        conn.close()


def _unseen_terminal_events(tid):
    conn = kb.connect()
    try:
        _, events = kb.unseen_events_for_sub(
            conn,
            task_id=tid,
            platform="telegram",
            chat_id="chat-1",
            kinds=["completed", "blocked", "gave_up", "crashed", "timed_out"],
        )
        return events
    finally:
        conn.close()


def test_kanban_notifier_dedupes_board_slugs_pointing_to_same_db(tmp_path, monkeypatch):
    db_path = tmp_path / "shared-kanban.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()
    kb.write_board_metadata("alias-a", name="Alias A")
    kb.write_board_metadata("alias-b", name="Alias B")

    tid = _create_completed_subscription()

    adapter = RecordingAdapter()
    runner = _make_runner(adapter)

    asyncio.run(_run_one_notifier_tick(monkeypatch, runner))

    assert len(adapter.sent) == 1
    assert "Kanban" in adapter.sent[0]["text"]
    assert tid in adapter.sent[0]["text"]


def test_kanban_create_records_gateway_spawn_origin_for_notifications(tmp_path, monkeypatch):
    db_path = tmp_path / "spawn-origin.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    monkeypatch.setenv("HERMES_PROFILE", "hemogrypm")
    kb.init_db()

    agent = SimpleNamespace(
        platform="discord",
        _chat_id="channel-123",
        _chat_name="ops",
        _chat_type="thread",
        _thread_id="thread-456",
        _user_id="user-789",
        _user_name="Vivian",
        session_id="session-abc",
        _gateway_session_key="agent:main:discord:thread:channel-123:thread-456",
    )

    result = json.loads(_handle_create(
        {"title": "spawned from thread", "assignee": "hemogryqa"},
        agent=agent,
    ))

    assert result["ok"] is True
    conn = kb.connect()
    try:
        subs = kb.list_notify_subs(conn, result["task_id"])
    finally:
        conn.close()
    assert len(subs) == 1
    assert subs[0]["platform"] == "discord"
    assert subs[0]["chat_id"] == "channel-123"
    assert subs[0]["thread_id"] == "thread-456"
    assert subs[0]["user_id"] == "user-789"
    assert subs[0]["notifier_profile"] == "hemogrypm"

    conn = kb.connect()
    try:
        origin_events = [
            ev for ev in kb.list_events(conn, result["task_id"])
            if ev.kind == "origin_recorded"
        ]
    finally:
        conn.close()
    assert len(origin_events) == 1
    assert origin_events[0].payload is not None
    origin = origin_events[0].payload["origin"]
    assert origin["platform"] == "discord"
    assert origin["chat_id"] == "channel-123"
    assert origin["thread_id"] == "thread-456"
    assert origin["user_id"] == "user-789"
    assert origin["user_name"] == "Vivian"
    assert origin["source_session_id"] == "session-abc"


def test_kanban_notifier_mentions_requester_in_origin_thread(tmp_path, monkeypatch):
    db_path = tmp_path / "origin-thread-mention.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()

    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="notify origin", assignee="worker")
        kb.add_notify_sub(
            conn,
            task_id=tid,
            platform="discord",
            chat_id="channel-1",
            thread_id="thread-1",
            user_id="user-1",
        )
        cursor = conn.execute("SELECT COALESCE(MAX(id), 0) FROM task_events WHERE task_id = ?", (tid,)).fetchone()[0]
        kb.advance_notify_cursor(
            conn,
            task_id=tid,
            platform="discord",
            chat_id="channel-1",
            thread_id="thread-1",
            new_cursor=int(cursor or 0),
        )
        kb.complete_task(conn, tid, summary="ready for review")
    finally:
        conn.close()

    adapter = RecordingAdapter()
    runner = _make_runner(adapter, platform=Platform.DISCORD)

    asyncio.run(_run_one_notifier_tick(monkeypatch, runner))

    assert len(adapter.sent) == 1
    assert adapter.sent[0]["chat_id"] == "channel-1"
    assert adapter.sent[0]["metadata"] == {"thread_id": "thread-1"}
    assert "<@user-1>" in adapter.sent[0]["text"]


def test_kanban_notifier_reports_created_running_and_dispatched(tmp_path, monkeypatch):
    db_path = tmp_path / "status-events.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()

    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="status pipeline", assignee="worker")
        kb.add_notify_sub(conn, task_id=tid, platform="telegram", chat_id="chat-1")
        assert kb.claim_task(conn, tid) is not None
        kb._set_worker_pid(conn, tid, 4242)
    finally:
        conn.close()

    adapter = RecordingAdapter()
    runner = _make_runner(adapter)
    asyncio.run(_run_one_notifier_tick(monkeypatch, runner))

    texts = [m["text"] for m in adapter.sent]
    assert len(texts) == 3
    assert "created" in texts[0].lower()
    assert "running" in texts[1].lower()
    assert "dispatched" in texts[2].lower()


def test_kanban_create_inherits_parent_origin_subscription_and_dispatches(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "inherit-origin.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()

    conn = kb.connect()
    try:
        parent = kb.create_task(conn, title="parent", assignee="hemogrypm")
        kb.add_notify_sub(
            conn,
            task_id=parent,
            platform="discord",
            chat_id="channel-1",
            thread_id="thread-1",
            user_id="user-1",
            notifier_profile="hemogrypm",
        )
    finally:
        conn.close()

    calls = []

    class FakeDispatchResult:
        spawned = []
        promoted = 0

    def fake_dispatch_once(conn, **kwargs):
        calls.append(kwargs)
        return FakeDispatchResult()

    monkeypatch.setattr(kb, "dispatch_once", fake_dispatch_once)

    result = json.loads(_handle_create(
        {"title": "child", "assignee": "hemogryqa", "parents": [parent]},
    ))

    assert result["ok"] is True
    assert result["inherited_notify_subs"] == 1
    assert result["dispatch"] is None
    assert calls == []

    conn = kb.connect()
    try:
        subs = kb.list_notify_subs(conn, result["task_id"])
    finally:
        conn.close()
    assert len(subs) == 1
    assert subs[0]["platform"] == "discord"
    assert subs[0]["chat_id"] == "channel-1"
    assert subs[0]["thread_id"] == "thread-1"
    assert subs[0]["user_id"] == "user-1"
    assert subs[0]["notifier_profile"] == "hemogrypm"


@pytest.mark.parametrize(
    ("event_kind", "writer"),
    [
        ("blocked", "block_task"),
        ("crashed", "append_event"),
        ("timed_out", "append_event"),
        ("gave_up", "append_event"),
    ],
)
def test_kanban_notifier_mentions_requester_for_block_and_error_events(
    tmp_path, monkeypatch, event_kind, writer
):
    db_path = tmp_path / f"origin-{event_kind}.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()

    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title=f"notify {event_kind}", assignee="worker")
        kb.add_notify_sub(
            conn,
            task_id=tid,
            platform="discord",
            chat_id="channel-1",
            thread_id="thread-1",
            user_id="user-1",
        )
        cursor = conn.execute("SELECT COALESCE(MAX(id), 0) FROM task_events WHERE task_id = ?", (tid,)).fetchone()[0]
        kb.advance_notify_cursor(
            conn,
            task_id=tid,
            platform="discord",
            chat_id="channel-1",
            thread_id="thread-1",
            new_cursor=int(cursor or 0),
        )
        if writer == "block_task":
            assert kb.block_task(conn, tid, reason="review-required: needs human decision") is True
        else:
            kb._append_event(conn, tid, kind=event_kind)
    finally:
        conn.close()

    adapter = RecordingAdapter()
    runner = _make_runner(adapter, platform=Platform.DISCORD)

    asyncio.run(_run_one_notifier_tick(monkeypatch, runner))

    assert len(adapter.sent) == 1
    assert adapter.sent[0]["chat_id"] == "channel-1"
    assert adapter.sent[0]["metadata"] == {"thread_id": "thread-1"}
    assert "<@user-1>" in adapter.sent[0]["text"]
    assert event_kind.replace("_", " ") in adapter.sent[0]["text"].lower()


def test_kanban_notifier_claim_prevents_second_watcher_send(tmp_path, monkeypatch):
    db_path = tmp_path / "single-owner.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()

    tid = _create_completed_subscription()

    adapter1 = RecordingAdapter()
    adapter2 = RecordingAdapter()

    asyncio.run(_run_one_notifier_tick(monkeypatch, _make_runner(adapter1)))
    asyncio.run(_run_one_notifier_tick(monkeypatch, _make_runner(adapter2)))

    assert len(adapter1.sent) == 1
    assert adapter2.sent == []


def test_kanban_notifier_rewinds_claim_if_adapter_disconnects(tmp_path, monkeypatch):
    db_path = tmp_path / "adapter-disconnect.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()
    tid = _create_completed_subscription()

    runner = GatewayRunner.__new__(GatewayRunner)
    runner._running = True
    runner.adapters = DisconnectedAdapters({Platform.TELEGRAM: RecordingAdapter()})
    runner._kanban_sub_fail_counts = {}

    asyncio.run(_run_one_notifier_tick(monkeypatch, runner))

    assert [ev.kind for ev in _unseen_terminal_events(tid)] == ["completed"]


def test_kanban_db_path_is_test_isolated_from_real_home():
    hermes_home = Path(kb.kanban_home())
    production_db = Path.home() / ".hermes" / "kanban.db"
    assert kb.kanban_db_path().resolve() != production_db.resolve()

    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="x", assignee="worker")
        kb.add_notify_sub(conn, task_id=tid, platform="telegram", chat_id="chat-1")
    finally:
        conn.close()

    assert kb.kanban_db_path().resolve().is_relative_to(hermes_home.resolve())
    assert kb.kanban_db_path().resolve() != production_db.resolve()


class FailingAdapter:
    """Adapter whose send() always raises, simulating a transient send error."""

    def __init__(self):
        self.attempts = 0

    async def send(self, chat_id, text, metadata=None):
        self.attempts += 1
        raise RuntimeError("simulated send failure")


def test_kanban_notifier_rewinds_claim_on_send_exception(tmp_path, monkeypatch):
    """A raising adapter rewinds the claim so the next tick can retry.

    This is the second rewind path (distinct from the adapter-disconnect path
    in test_kanban_notifier_rewinds_claim_if_adapter_disconnects). Here the
    adapter is connected and the send call actually fires; the claim must
    still rewind so the event isn't lost when send() raises mid-tick.
    """
    db_path = tmp_path / "send-failure.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()
    tid = _create_completed_subscription()

    adapter = FailingAdapter()
    runner = _make_runner(adapter)

    asyncio.run(_run_one_notifier_tick(monkeypatch, runner))

    # Send was attempted (so we exercised the failure path, not just the
    # disconnect path) and the claim was rewound — the unseen-events query
    # still returns the event for retry on the next tick.
    assert adapter.attempts >= 1, "send should have been attempted at least once"
    assert [ev.kind for ev in _unseen_terminal_events(tid)] == ["completed"]


def test_notifier_redelivers_same_kind_on_dispatch_cycle(tmp_path, monkeypatch):
    """A retry cycle (crashed → reclaimed → crashed) notifies the user twice.

    Before #21398 the notifier auto-unsubscribed on any terminal event kind
    (gave_up / crashed / timed_out), so the second crash in a respawn cycle
    silently dropped — the subscription was already gone. This test pins the
    new contract: subscription survives non-final terminal events; the
    cursor handles dedup.

    Two crashes ten seconds apart on the same task — both should land on
    the adapter.
    """
    db_path = tmp_path / "redeliver-cycle.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()

    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="cycle test", assignee="worker")
        kb.add_notify_sub(conn, task_id=tid, platform="telegram", chat_id="chat-1")
        cursor = conn.execute("SELECT COALESCE(MAX(id), 0) FROM task_events WHERE task_id = ?", (tid,)).fetchone()[0]
        kb.advance_notify_cursor(
            conn,
            task_id=tid,
            platform="telegram",
            chat_id="chat-1",
            new_cursor=int(cursor or 0),
        )
        # First crash — fired by the dispatcher when the worker PID dies.
        kb._append_event(conn, tid, kind="crashed")
    finally:
        conn.close()

    adapter = RecordingAdapter()
    runner = _make_runner(adapter)
    asyncio.run(_run_one_notifier_tick(monkeypatch, runner))

    # First crash delivered.
    assert len(adapter.sent) == 1
    assert "crashed" in adapter.sent[0]["text"].lower()

    # Subscription survives — the cursor advanced past event #1, but the
    # row is still there.
    conn = kb.connect()
    try:
        subs = kb.list_notify_subs(conn, tid)
        assert len(subs) == 1, (
            "Subscription must survive a crashed event so a respawn-cycle "
            "second crash also notifies the user (issue #21398)."
        )

        # Second crash — same task, same dispatcher (or a respawn). Append
        # another event to simulate the dispatcher firing crashed a second
        # time during retry.
        kb._append_event(conn, tid, kind="crashed")
    finally:
        conn.close()

    # New tick: the second event has a fresh id past the cursor advance,
    # so it gets claimed and delivered.
    runner = _make_runner(adapter)
    asyncio.run(_run_one_notifier_tick(monkeypatch, runner))

    assert len(adapter.sent) == 2, (
        f"Second crashed event should also notify; got {len(adapter.sent)} "
        f"deliveries (texts: {[d['text'] for d in adapter.sent]})"
    )
    assert "crashed" in adapter.sent[1]["text"].lower()
