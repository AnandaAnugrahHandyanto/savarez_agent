"""Tests for the local Telegram reaction feedback event store."""

from __future__ import annotations

import hashlib
import json

from gateway import reaction_feedback


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_record_sent_message_indexes_target_without_raw_text(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    reaction_feedback.record_sent_message(
        platform="telegram",
        chat_id="-1001",
        thread_id="777",
        message_id="42",
        content="private assistant content",
        metadata={"session_id": "sess-1", "session_key": "telegram:-1001:777"},
    )

    data = _read_json(reaction_feedback.sent_index_path())
    entry = data["messages"]["telegram:-1001:42"]

    assert entry["chat_id"] == "-1001"
    assert entry["thread_id"] == "777"
    assert entry["message_id"] == "42"
    assert entry["session_id"] == "sess-1"
    assert entry["session_key"] == "telegram:-1001:777"
    assert entry["content_chars"] == len("private assistant content")
    assert entry["content_sha256"] == hashlib.sha256(b"private assistant content").hexdigest()
    assert "private assistant content" not in json.dumps(data, ensure_ascii=False)


def test_lookup_sent_message_returns_copy(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    reaction_feedback.record_sent_message(
        platform="telegram",
        chat_id="123",
        message_id="9",
        content="hello",
    )

    entry = reaction_feedback.lookup_sent_message("telegram", "123", "9")
    assert entry is not None
    entry["message_id"] = "mutated"

    assert reaction_feedback.lookup_sent_message("telegram", "123", "9")["message_id"] == "9"


def test_normalize_feedback_maps_v0_semantics():
    assert reaction_feedback.normalize_feedback(["👍"])["semantic"] == "useful"
    assert reaction_feedback.normalize_feedback(["❤️"])["semantic"] == "useful"
    assert reaction_feedback.normalize_feedback(["👎"])["semantic"] == "miss"
    assert reaction_feedback.normalize_feedback(["🤔"])["semantic"] == "unclear"
    assert reaction_feedback.normalize_feedback(["⏰"])["semantic"] == "bad_timing"
    assert reaction_feedback.normalize_feedback(["📏"])["semantic"] == "too_long"
    assert reaction_feedback.normalize_feedback(["🧪"])["semantic"] == "other"
    assert reaction_feedback.normalize_feedback([])["semantic"] == "cleared"


def test_record_feedback_appends_normalized_event_without_raw_actor_or_text(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    reaction_feedback.record_sent_message(
        platform="telegram",
        chat_id="-1001",
        thread_id="777",
        message_id="42",
        content="assistant text that must not be copied",
        metadata={"session_id": "sess-1", "session_key": "telegram:-1001:777"},
    )

    event = reaction_feedback.record_feedback(
        platform="telegram",
        chat_id="-1001",
        message_id="42",
        actor_user_id="123456",
        old_emojis=[],
        new_emojis=["👎"],
        update_id="u1",
    )

    events = _read_jsonl(reaction_feedback.events_path())
    assert events == [event]
    assert event["schema_version"] == reaction_feedback.SCHEMA_VERSION
    assert event["event_type"] == "reaction_feedback"
    assert event["route"] == {"chat_id": "-1001", "thread_id": "777", "message_id": "42"}
    assert event["reaction"]["semantic"] == "miss"
    assert event["reaction"]["emoji"] == "👎"
    assert event["target"]["known"] is True
    assert event["target"]["session_id"] == "sess-1"
    assert event["privacy"] == {"raw_text_stored": False, "actor_user_id_stored": False}
    assert event["actor"]["user_id_hash"] == hashlib.sha256(b"telegram:123456").hexdigest()

    serialized = json.dumps(event, ensure_ascii=False)
    assert "assistant text that must not be copied" not in serialized
    assert "123456" not in serialized
    assert event["no_auto_apply"] is True


def test_record_feedback_cleared_reaction_keeps_old_emoji(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    event = reaction_feedback.record_feedback(
        platform="telegram",
        chat_id="123",
        message_id="5",
        actor_user_id="42",
        old_emojis=["👍"],
        new_emojis=[],
    )

    assert event["reaction"]["semantic"] == "cleared"
    assert event["reaction"]["action"] == "cleared"
    assert event["reaction"]["old_emojis"] == ["👍"]
    assert event["target"]["known"] is False
