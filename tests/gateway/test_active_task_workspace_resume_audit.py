"""Regression specs for active-task/workspace restart recovery.

These tests are intentionally xfail during the audit phase. They capture the
expected durable model before production behavior is changed.
"""

import json
import time
from datetime import datetime
from unittest.mock import patch

import pytest

from gateway.config import Platform
from gateway.run import GatewayRunner
from gateway.session import SessionEntry, SessionSource
from tools.process_registry import ProcessRegistry, ProcessSession


@pytest.mark.xfail(
    reason="No durable active task/workspace record exists on SessionEntry yet.",
    strict=True,
)
def test_session_entry_persists_active_task_workspace_snapshot():
    now = datetime(2026, 5, 31, 12, 0, 0)
    source = SessionSource(
        platform=Platform.DISCORD,
        chat_id="thread-parent",
        chat_type="thread",
        thread_id="thread-1",
        user_id="u1",
    )
    entry = SessionEntry(
        session_key="agent:main:discord:thread:thread-parent:thread-1",
        session_id="sid",
        created_at=now,
        updated_at=now,
        origin=source,
    )

    data = entry.to_dict()

    assert data["active_task"] == {
        "repo_path": "/tmp/project",
        "branch": "main",
        "command": "python tools/refill.py",
        "status": "running",
        "latest_log_path": "/tmp/project/runtime/refill.json",
    }


@pytest.mark.xfail(
    reason="Gateway cwd selection has no active-task workspace resolver yet.",
    strict=True,
)
def test_gateway_exposes_workspace_resolver_that_prefers_active_task_cwd():
    assert hasattr(GatewayRunner, "_resolve_agent_working_directory")


@pytest.mark.xfail(
    reason=(
        "Process checkpoint is written at spawn time; later notification "
        "metadata mutations are not automatically flushed."
    ),
    strict=True,
)
def test_process_checkpoint_flushes_after_notification_metadata_changes(tmp_path):
    registry = ProcessRegistry()
    session = ProcessSession(
        id="proc_active",
        command="python tools/refill.py",
        task_id="agent:main:discord:thread:thread-parent:thread-1",
        session_key="agent:main:discord:thread:thread-parent:thread-1",
        pid=12345,
        pid_scope="host",
        cwd="/tmp/project",
        started_at=time.time(),
    )
    registry._running[session.id] = session
    checkpoint = tmp_path / "processes.json"

    with patch("tools.process_registry.CHECKPOINT_PATH", checkpoint):
        registry._write_checkpoint()
        session.notify_on_complete = True
        session.watcher_platform = "discord"
        session.watcher_chat_id = "thread-parent"
        session.watcher_thread_id = "thread-1"
        session.watcher_interval = 5

        data = json.loads(checkpoint.read_text())

    assert data[0]["notify_on_complete"] is True
    assert data[0]["watcher_platform"] == "discord"
    assert data[0]["watcher_interval"] == 5
