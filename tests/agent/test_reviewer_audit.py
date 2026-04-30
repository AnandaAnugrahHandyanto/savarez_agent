"""Tests for reviewer audit JSONL logging."""

from __future__ import annotations

import json
import hashlib
import threading

from agent import reviewer_audit
from agent.reviewer_audit import append_reviewer_audit_event


def test_append_reviewer_audit_event_writes_jsonl_and_creates_logs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    append_reviewer_audit_event(
        "review.started",
        "memory",
        session_id="session-1",
        parent_session_id="parent-1",
        platform="slack",
    )

    audit_path = tmp_path / "logs" / "reviewer_audit.jsonl"
    assert audit_path.exists()
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    event = json.loads(lines[0])
    assert event["event"] == "review.started"
    assert event["kind"] == "memory"
    assert event["session_id"] == "session-1"
    assert event["parent_session_id"] == "parent-1"
    assert event["platform"] == "slack"
    assert event["ts"].endswith("Z")


def test_append_reviewer_audit_event_redacts_full_content_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    content = "PRIVATE-SECRET sk-test1234567890abcdef " * 50

    append_reviewer_audit_event("review.tool_result", "memory", content=content)

    raw_line = (tmp_path / "logs" / "reviewer_audit.jsonl").read_text(encoding="utf-8")
    assert "sk-test1234567890abcdef" not in raw_line

    event = json.loads(raw_line)
    assert "content" not in event
    assert event["content_sha256"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert event["content_preview"] == "[redacted-sensitive-content]"


def test_append_reviewer_audit_event_keeps_short_non_sensitive_preview(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    content = "A durable workflow detail " * 10

    append_reviewer_audit_event("review.tool_result", "memory", content=content)

    event = json.loads((tmp_path / "logs" / "reviewer_audit.jsonl").read_text(encoding="utf-8"))
    assert event["content_sha256"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert event["content_preview"].startswith("A durable workflow detail")
    assert len(event["content_preview"]) < len(content)


def test_append_reviewer_audit_event_redacts_non_content_string_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    secret = "sk-test1234567890abcdef"

    append_reviewer_audit_event(
        "review.failed",
        "skill",
        action=f"Skill updated with token {secret}",
        summary=f"Summary mentions {secret}",
        error=f"Provider rejected Authorization: Bearer {secret}",
    )

    raw_line = (tmp_path / "logs" / "reviewer_audit.jsonl").read_text(encoding="utf-8")
    assert secret not in raw_line
    event = json.loads(raw_line)
    assert "***" in event["action"] or "..." in event["action"]
    assert "***" in event["summary"] or "..." in event["summary"]
    assert "***" in event["error"] or "..." in event["error"]


def test_append_reviewer_audit_event_serializes_concurrent_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    threads = [
        threading.Thread(
            target=append_reviewer_audit_event,
            args=("review.completed", "memory"),
            kwargs={"session_id": f"session-{idx}", "status": "no_op"},
        )
        for idx in range(20)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    lines = (tmp_path / "logs" / "reviewer_audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 20
    events = [json.loads(line) for line in lines]
    assert {event["session_id"] for event in events} == {f"session-{idx}" for idx in range(20)}


def test_append_reviewer_audit_event_swallows_write_errors(monkeypatch):
    def boom(*_args, **_kwargs):
        raise PermissionError("nope")

    monkeypatch.setattr(reviewer_audit.Path, "mkdir", boom)

    append_reviewer_audit_event("review.started", "skill", session_id="session-1")
