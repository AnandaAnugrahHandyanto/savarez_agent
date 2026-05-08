"""Tests for hermes_cli.kanban_checkin — agent check-in utilities."""

from __future__ import annotations

import json
import time

import pytest

from hermes_cli.kanban_checkin import (
    build_checkin_prompt,
    parse_checkin_response,
    find_stale_tasks,
    CheckinResult,
)


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

class TestBuildCheckinPrompt:
    def test_no_history(self):
        prompt = build_checkin_prompt([])
        assert "[AUTOMATED CHECK-IN]" in prompt
        assert "<checkin>" in prompt
        assert "No previous check-ins recorded." in prompt
        assert "<status_report>" in prompt   # example in format block
        assert "progressing" in prompt
        assert "completed" in prompt
        assert "blocked" in prompt

    def test_with_history(self):
        history = [
            {"created_at": "2026-05-08T10:00:00Z", "summary": "Started fetching data."},
            {"created_at": "2026-05-08T10:30:00Z", "summary": "Fetched 50/100 records."},
        ]
        prompt = build_checkin_prompt(history)
        assert "Started fetching data." in prompt
        assert "Fetched 50/100 records." in prompt

    def test_max_three_history_entries(self):
        history = [
            {"created_at": f"2026-05-08T{h:02d}:00:00Z", "summary": f"Step {h}"}
            for h in range(6)
        ]
        prompt = build_checkin_prompt(history)
        # Only last 3 entries (3, 4, 5) should appear
        assert "Step 3" in prompt
        assert "Step 4" in prompt
        assert "Step 5" in prompt
        assert "Step 0" not in prompt
        assert "Step 1" not in prompt
        assert "Step 2" not in prompt

    def test_prompt_contains_instructions(self):
        prompt = build_checkin_prompt([])
        assert "assume a reasonable answer and proceed" in prompt
        assert "try a different one right now" in prompt
        assert "exhausted alternatives" in prompt


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

class TestParseCheckinResponse:
    def _wrap(self, payload: dict) -> str:
        return f"Some agent output.\n<status_report>\n{json.dumps(payload)}\n</status_report>\nMore text."

    def test_progressing(self):
        response = self._wrap({"status": "progressing", "summary": "Made good progress."})
        result = parse_checkin_response("task-1", response)
        assert result.parse_ok
        assert result.status == "progressing"
        assert result.summary == "Made good progress."
        assert result.user_message is None

    def test_completed_with_user_message(self):
        response = self._wrap({
            "status": "completed",
            "summary": "All done.",
            "user_message": "Task finished — please review output.json.",
        })
        result = parse_checkin_response("task-2", response)
        assert result.parse_ok
        assert result.status == "completed"
        assert result.user_message == "Task finished — please review output.json."

    def test_blocked(self):
        response = self._wrap({"status": "blocked", "summary": "Need credentials for the API."})
        result = parse_checkin_response("task-3", response)
        assert result.parse_ok
        assert result.status == "blocked"

    def test_no_status_report_tag(self):
        result = parse_checkin_response("task-4", "Agent output with no status tag.")
        assert not result.parse_ok
        assert "No <status_report>" in result.error

    def test_invalid_status_value(self):
        response = self._wrap({"status": "confused", "summary": "Not sure."})
        result = parse_checkin_response("task-5", response)
        assert not result.parse_ok
        assert "confused" in result.error

    def test_json_in_markdown_fence(self):
        """Model sometimes wraps JSON in ```json ... ``` fences."""
        payload = json.dumps({"status": "progressing", "summary": "On track."})
        response = f"<status_report>\n```json\n{payload}\n```\n</status_report>"
        result = parse_checkin_response("task-6", response)
        assert result.parse_ok
        assert result.status == "progressing"

    def test_malformed_json(self):
        response = "<status_report>not-json</status_report>"
        result = parse_checkin_response("task-7", response)
        assert not result.parse_ok
        assert "JSON parse error" in result.error

    def test_empty_user_message_omitted(self):
        """user_message should be None when empty string or missing."""
        response = self._wrap({"status": "progressing", "summary": "Fine.", "user_message": ""})
        result = parse_checkin_response("task-8", response)
        assert result.parse_ok
        assert result.user_message is None

    def test_task_id_preserved(self):
        response = self._wrap({"status": "progressing", "summary": "OK."})
        result = parse_checkin_response("my-task-id", response)
        assert result.task_id == "my-task-id"


# ---------------------------------------------------------------------------
# Stale task detection
# ---------------------------------------------------------------------------

class TestFindStaleTasks:
    def _make_conn(self, tmp_path):
        """Create an in-memory SQLite DB with the minimal schema."""
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT,
                assignee TEXT,
                status TEXT,
                updated_at INTEGER,
                last_heartbeat_at INTEGER
            );
        """)
        return conn

    def test_returns_stale_running_tasks(self, tmp_path):
        conn = self._make_conn(tmp_path)
        stale_time = int(time.time()) - 3600       # 1 hour ago
        fresh_time = int(time.time()) - 60          # 1 minute ago
        conn.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?)",
            ("stale-task", "Old Task", "alice", "running", stale_time, None),
        )
        conn.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?)",
            ("fresh-task", "New Task", "bob", "running", fresh_time, None),
        )
        result = find_stale_tasks(conn, stale_minutes=30)
        ids = [r["id"] for r in result]
        assert "stale-task" in ids
        assert "fresh-task" not in ids

    def test_ignores_non_running_tasks(self, tmp_path):
        conn = self._make_conn(tmp_path)
        stale_time = int(time.time()) - 3600
        for status in ("done", "blocked", "ready", "triage"):
            conn.execute(
                "INSERT INTO tasks VALUES (?,?,?,?,?,?)",
                (f"task-{status}", "T", "alice", status, stale_time, None),
            )
        result = find_stale_tasks(conn, stale_minutes=30)
        assert result == []

    def test_uses_last_heartbeat_over_updated_at(self, tmp_path):
        conn = self._make_conn(tmp_path)
        # updated_at is stale but last_heartbeat_at is fresh
        stale_time = int(time.time()) - 3600
        fresh_time = int(time.time()) - 60
        conn.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?)",
            ("task-hb", "Task", "alice", "running", stale_time, fresh_time),
        )
        result = find_stale_tasks(conn, stale_minutes=30)
        assert result == []
