from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import run_agent
from run_agent import AIAgent
from hermes_cli import kanban_db as kb


@pytest.fixture()
def agent():
    with (
        patch(
            "run_agent.get_tool_definitions",
            return_value=[
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "web_search tool",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        ),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        a = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        a.client = MagicMock()
        return a


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def test_worker_startup_guard_exits_on_invalid_run_id(agent, kanban_home, monkeypatch):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_demo")
    monkeypatch.setenv("HERMES_KANBAN_RUN_ID", "not-an-int")
    monkeypatch.setenv("HERMES_KANBAN_DB", str(kb.kanban_db_path()))

    result = agent.run_conversation("hello")

    assert result["completed"] is False
    assert result["api_calls"] == 0
    assert result["turn_exit_reason"] == "kanban_startup_guard:invalid_run_id"
    assert "invalid" in result["final_response"].lower()


def test_worker_startup_guard_exits_on_superseded_claim(agent, kanban_home, monkeypatch):
    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="startup-guard", assignee="worker")
        first = kb.claim_task(conn, tid)
        assert first is not None
        run1 = first.current_run_id
        lock1 = first.claim_lock
        assert run1 is not None and lock1 is not None

        assert kb.reclaim_task(conn, tid, reason="retry")
        second = kb.claim_task(conn, tid)
        assert second is not None
        assert second.current_run_id is not None and second.current_run_id != run1
    finally:
        conn.close()

    monkeypatch.setenv("HERMES_KANBAN_TASK", tid)
    monkeypatch.setenv("HERMES_KANBAN_RUN_ID", str(run1))
    monkeypatch.setenv("HERMES_KANBAN_CLAIM_LOCK", lock1)
    monkeypatch.setenv("HERMES_KANBAN_DB", str(kb.kanban_db_path()))

    result = agent.run_conversation("hello")

    assert result["completed"] is False
    assert result["api_calls"] == 0
    assert result["turn_exit_reason"] == "kanban_startup_guard:run_mismatch"
    assert "no longer belongs to this worker" in result["final_response"]


def test_worker_startup_guard_allows_current_owner_to_continue(agent, kanban_home, monkeypatch):
    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="startup-guard", assignee="worker")
        claimed = kb.claim_task(conn, tid)
        assert claimed is not None
        run_id = claimed.current_run_id
        claim_lock = claimed.claim_lock
        assert run_id is not None and claim_lock is not None
    finally:
        conn.close()

    monkeypatch.setenv("HERMES_KANBAN_TASK", tid)
    monkeypatch.setenv("HERMES_KANBAN_RUN_ID", str(run_id))
    monkeypatch.setenv("HERMES_KANBAN_CLAIM_LOCK", claim_lock)
    monkeypatch.setenv("HERMES_KANBAN_DB", str(kb.kanban_db_path()))

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="OK", tool_calls=None),
                finish_reason="stop",
            )
        ],
        model="test/model",
        usage=None,
    )
    agent.client.chat.completions.create.return_value = response

    with (
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
    ):
        result = agent.run_conversation("hello")

    assert result["completed"] is True
    assert result["api_calls"] == 1
    assert result["final_response"] == "OK"
