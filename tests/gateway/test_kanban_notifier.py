import asyncio
import json
from pathlib import Path


from gateway.config import Platform
from gateway.run import GatewayRunner
from hermes_cli import kanban_db as kb


class RecordingAdapter:
    def __init__(self):
        self.sent = []
        self.thread_updates = []
        self.documents = []

    async def send(self, chat_id, text, metadata=None):
        self.sent.append({"chat_id": chat_id, "text": text, "metadata": metadata or {}})

    async def update_thread_metadata(self, thread_id, *, name=None, applied_tags=None):
        self.thread_updates.append({
            "thread_id": thread_id,
            "name": name,
            "applied_tags": list(applied_tags or []),
        })
        return True

    async def send_document(self, chat_id, file_path, caption=None, file_name=None, reply_to=None, metadata=None):
        self.documents.append({
            "chat_id": chat_id,
            "file_path": file_path,
            "metadata": metadata or {},
        })

    def extract_local_files(self, text):
        return [], text


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


def _create_completed_subscription(summary="done once"):
    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="notify once", assignee="worker")
        kb.add_notify_sub(conn, task_id=tid, platform="telegram", chat_id="chat-1")
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


def test_discord_kanban_notifier_syncs_forum_card_metadata_before_final_unsubscribe(tmp_path, monkeypatch):
    """Terminal Discord notifications must update forum title/tags before unsubscribe.

    Regression coverage for completed tasks whose notification row is deleted
    after delivery: after that point repair/audit cannot infer the thread binding,
    so the gateway has to mutate the Discord card while the subscription still
    exists.
    """
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_DB", str(home / "kanban.db"))
    kb.init_db()
    board_dir = home / "kanban" / "boards" / "default"
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / "discord-forum-tags.json").write_text(
        json.dumps({
            "status_to_tag": {"done": "done-tag", "blocked": "blocked-tag"},
            "assignee_to_tag": {"hermes": "hermes-tag", "default": "default-tag"},
        }),
        encoding="utf-8",
    )

    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="ship projection sync", assignee="hermes")
        kb.add_notify_sub(
            conn,
            task_id=tid,
            platform="discord",
            chat_id="forum-1",
            thread_id="thread-1",
        )
        kb.complete_task(conn, tid, summary="done")
    finally:
        conn.close()

    adapter = RecordingAdapter()
    asyncio.run(_run_one_notifier_tick(monkeypatch, _make_runner(adapter, Platform.DISCORD)))

    assert adapter.thread_updates == [{
        "thread_id": "thread-1",
        "name": "✅ [done] ship projection sync",
        "applied_tags": ["done-tag", "hermes-tag"],
    }]
    assert len(adapter.sent) == 1

    conn = kb.connect()
    try:
        assert kb.list_notify_subs(conn, tid) == []
    finally:
        conn.close()


def test_discord_kanban_notifier_prefers_configured_status_emoji(tmp_path, monkeypatch):
    """Forum thread titles should use board-configured emoji, not ASCII fallbacks."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_DB", str(home / "kanban.db"))
    kb.init_db()
    board_dir = home / "kanban" / "boards" / "default"
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / "discord-forum-tags.json").write_text(
        json.dumps({
            "tags": {"running": {"emoji": "🟨"}},
            "status_to_tag": {"running": "running-tag"},
            "assignee_to_tag": {"hermes": "hermes-tag"},
        }),
        encoding="utf-8",
    )

    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="keep the emoji", assignee="hermes")
        assert kb.claim_task(conn, tid, claimer="test") is not None
        kb.add_notify_sub(
            conn,
            task_id=tid,
            platform="discord",
            chat_id="forum-1",
            thread_id="thread-1",
        )
        # Any notifier tick for a non-terminal event should still reconcile
        # the live Discord forum card metadata for the running task.
        kb._append_event(conn, tid, kind="blocked")
    finally:
        conn.close()

    adapter = RecordingAdapter()
    asyncio.run(_run_one_notifier_tick(monkeypatch, _make_runner(adapter, Platform.DISCORD)))

    assert adapter.thread_updates[0]["name"] == "🟨 [running] keep the emoji"


def test_discord_kanban_notifier_artifacts_use_existing_thread_metadata(tmp_path, monkeypatch):
    """Artifact uploads must target the task thread, not the parent forum.

    A Discord forum subscription stores ``chat_id`` as the parent forum and
    ``thread_id`` as the actual Kanban card thread. The text notification and
    all follow-up artifact uploads must receive the same metadata; otherwise
    Discord creates a sibling forum post named after the uploaded artifact.
    """
    home = tmp_path / ".hermes"
    home.mkdir()
    artifact = home / "cache" / "documents" / "implementation-handoff-addendum-2026-05-30.md"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("handoff", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_DB", str(home / "kanban.db"))
    monkeypatch.setenv("HERMES_MEDIA_ALLOW_DIRS", str(home))
    kb.init_db()

    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="artifact routing", assignee="hephaestus")
        kb.add_notify_sub(
            conn,
            task_id=tid,
            platform="discord",
            chat_id="forum-1",
            thread_id="thread-1",
        )
        kb.complete_task(
            conn,
            tid,
            summary="done",
            metadata={"artifacts": [str(artifact)]},
        )
    finally:
        conn.close()

    adapter = RecordingAdapter()
    asyncio.run(_run_one_notifier_tick(monkeypatch, _make_runner(adapter, Platform.DISCORD)))

    assert adapter.sent[0]["metadata"] == {"thread_id": "thread-1"}
    assert adapter.documents == [{
        "chat_id": "forum-1",
        "file_path": str(artifact),
        "metadata": {"thread_id": "thread-1"},
    }]
