import datetime as dt
import fcntl
import json
from pathlib import Path

import yaml

import turn_beacon


def configure_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(turn_beacon, "STATE_PATH", tmp_path / "turn-status.json")
    monkeypatch.setattr(turn_beacon, "QUEUE_PATH", tmp_path / "slice-queue.yaml")
    monkeypatch.setattr(turn_beacon, "PAUSE_FLAG_PATH", tmp_path / "queue-paused.flag")
    monkeypatch.setattr(turn_beacon, "AUTO_DISPATCH_COUNT_PATH", tmp_path / "auto-dispatch-count")
    monkeypatch.setattr(turn_beacon, "AUTO_DISPATCH_LIMIT", 5)
    monkeypatch.setattr(turn_beacon, "_find_repo", lambda: Path.cwd())
    monkeypatch.setattr(turn_beacon, "git_snapshot", lambda repo=None: {
        "active_repo": str(Path.cwd()),
        "last_commit_sha": "abc123",
        "last_commit_subject": "test head",
        "working_tree": "clean",
        "dirty_count": 0,
    })
    monkeypatch.setattr(turn_beacon, "commit_count_since", lambda repo, start_sha: 0)


def test_idle_pops_top_slice_silently_and_leaves_running(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    turn_beacon.QUEUE_PATH.write_text(yaml.safe_dump({"queue": [
        {"id": "slice-001", "title": "A", "scope": "Do A", "added_by": "chris", "added_at": "2026-05-13T00:00:00Z"},
        {"id": "slice-002", "title": "B", "scope": "Do B", "added_by": "chris", "added_at": "2026-05-13T00:00:00Z"},
    ]}), encoding="utf-8")
    posts = []
    monkeypatch.setattr(turn_beacon, "_post_auto_dispatch", lambda item, remaining, count: posts.append((item["id"], remaining, count)) or "https://slack/auto-a")
    monkeypatch.setattr(turn_beacon, "_spawn_next_turn", lambda prompt_path, item: 12345)

    state = turn_beacon.mark_finished(turn_id="t1", status="idle_awaiting_prompt", final_response="Done.", messages=[], user_message="manual")

    assert state["status"] == "running"
    assert state["auto_dispatch"]["slice_id"] == "slice-001"
    assert state["auto_dispatch"]["remaining_queue"] == 1
    assert turn_beacon.AUTO_DISPATCH_COUNT_PATH.read_text().strip() == "1"
    assert posts == []
    remaining = yaml.safe_load(turn_beacon.QUEUE_PATH.read_text())["queue"]
    assert [item["id"] for item in remaining] == ["slice-002"]
    written = json.loads(turn_beacon.STATE_PATH.read_text())
    assert written["status"] == "running"


def test_blocked_never_pops_and_resets_counter(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    turn_beacon._write_counter(4)
    turn_beacon.QUEUE_PATH.write_text(yaml.safe_dump({"queue": [{"id": "slice-001", "title": "A", "scope": "Do A"}]}), encoding="utf-8")
    monkeypatch.setattr(turn_beacon, "_post_slack", lambda state: "https://slack/blocked")

    state = turn_beacon.mark_finished(turn_id="t1", status="blocked", blocker="needs human", final_response="Blocker: needs human", messages=[])

    assert state["status"] == "blocked"
    assert turn_beacon.AUTO_DISPATCH_COUNT_PATH.read_text().strip() == "0"
    assert yaml.safe_load(turn_beacon.QUEUE_PATH.read_text())["queue"][0]["id"] == "slice-001"


def test_limit_pause_reason_lands_idle_and_keeps_queue(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    turn_beacon._write_counter(5)
    turn_beacon.QUEUE_PATH.write_text(yaml.safe_dump({"queue": [{"id": "slice-001", "title": "A", "scope": "Do A"}]}), encoding="utf-8")
    posts = []
    monkeypatch.setattr(turn_beacon, "_post_slack", lambda state: posts.append(state) or "https://slack/idle")

    state = turn_beacon.mark_finished(turn_id="t1", status="idle_awaiting_prompt", final_response="Done.", messages=[])

    assert state["status"] == "idle_awaiting_prompt"
    assert state["auto_dispatch_paused_reason"] == "5 consecutive auto-dispatches reached — human ack required"
    assert posts == []
    assert yaml.safe_load(turn_beacon.QUEUE_PATH.read_text())["queue"][0]["id"] == "slice-001"


def test_pause_flag_reason(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    turn_beacon.PAUSE_FLAG_PATH.write_text("pause", encoding="utf-8")
    turn_beacon.QUEUE_PATH.write_text(yaml.safe_dump({"queue": [{"id": "slice-001", "title": "A", "scope": "Do A"}]}), encoding="utf-8")
    monkeypatch.setattr(turn_beacon, "_post_slack", lambda state: "https://slack/idle")

    state = turn_beacon.mark_finished(turn_id="t1", status="idle_awaiting_prompt", final_response="Done.", messages=[])

    assert state["auto_dispatch_paused_reason"] == "queue-paused.flag set"


def test_empty_queue_is_silent(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    turn_beacon.QUEUE_PATH.write_text("queue: []\n", encoding="utf-8")
    posts = []
    monkeypatch.setattr(turn_beacon, "_post_queue_empty", lambda: posts.append("empty") or "https://slack/empty")
    monkeypatch.setattr(turn_beacon, "_post_slack", lambda state: "https://slack/idle")

    state = turn_beacon.mark_finished(turn_id="t1", status="idle_awaiting_prompt", final_response="Done.", messages=[])

    assert state["auto_dispatch_paused_reason"] == "queue empty"
    assert posts == []


def test_locked_queue_does_not_pop(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    turn_beacon.QUEUE_PATH.write_text(yaml.safe_dump({"queue": [{"id": "slice-001", "title": "A", "scope": "Do A"}]}), encoding="utf-8")
    monkeypatch.setattr(turn_beacon, "_post_slack", lambda state: "https://slack/idle")
    with turn_beacon.QUEUE_PATH.open("r+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = turn_beacon.mark_finished(turn_id="t1", status="idle_awaiting_prompt", final_response="Done.", messages=[])
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    assert state["auto_dispatch_paused_reason"] == "slice-queue.yaml locked"
    assert yaml.safe_load(turn_beacon.QUEUE_PATH.read_text())["queue"][0]["id"] == "slice-001"


def test_manual_mark_running_resets_counter_but_auto_child_does_not(monkeypatch, tmp_path):
    configure_paths(monkeypatch, tmp_path)
    turn_beacon._write_counter(3)
    turn_beacon.mark_running("manual", "hi")
    assert turn_beacon.AUTO_DISPATCH_COUNT_PATH.read_text().strip() == "0"

    turn_beacon._write_counter(2)
    monkeypatch.setenv("HERMES_AUTO_DISPATCH", "1")
    turn_beacon.mark_running("auto", "hi")
    assert turn_beacon.AUTO_DISPATCH_COUNT_PATH.read_text().strip() == "2"
