"""Tests for tools.task_tools."""

import json

import pytest

from agent.task_manager import TaskManager
from tools import task_tools
from tools.registry import registry


@pytest.fixture
def isolated_task_manager(monkeypatch, tmp_path):
    manager = TaskManager(storage_path=tmp_path / "state" / "tasks.json")
    monkeypatch.setattr(task_tools, "TASK_MANAGER", manager)
    return manager


def test_task_create_tool(isolated_task_manager):
    payload = json.loads(registry.dispatch("task_create", {"title": "Create task tool"}))

    assert payload["title"] == "Create task tool"
    assert payload["status"] == "pending"
    assert isolated_task_manager.get(payload["task_id"]) is not None


def test_task_update_tool(isolated_task_manager):
    created = json.loads(registry.dispatch("task_create", {"title": "Update task tool"}))

    payload = json.loads(
        registry.dispatch(
            "task_update",
            {
                "task_id": created["task_id"],
                "status": "running",
                "result_summary": "started",
                "metadata": {"step": 1},
            },
        )
    )

    assert payload["status"] == "running"
    assert payload["result_summary"] == "started"
    assert payload["metadata"] == {"step": 1}


def test_task_list_tool(isolated_task_manager):
    first = json.loads(registry.dispatch("task_create", {"title": "List local"}))
    second = json.loads(
        registry.dispatch(
            "task_create",
            {"title": "List delegated", "kind": "delegated"},
        )
    )
    json.loads(registry.dispatch("task_update", {"task_id": second["task_id"], "status": "running"}))

    payload = json.loads(registry.dispatch("task_list", {"status": "running"}))

    assert [task["task_id"] for task in payload["tasks"]] == [second["task_id"]]
    assert first["task_id"] not in {task["task_id"] for task in payload["tasks"]}


def test_task_get_tool(isolated_task_manager):
    created = json.loads(registry.dispatch("task_create", {"title": "Get task tool"}))

    payload = json.loads(registry.dispatch("task_get", {"task_id": created["task_id"]}))

    assert payload["task"]["task_id"] == created["task_id"]
    assert payload["task"]["title"] == "Get task tool"


def test_task_cancel_tool(isolated_task_manager):
    created = json.loads(registry.dispatch("task_create", {"title": "Cancel task tool"}))

    payload = json.loads(registry.dispatch("task_cancel", {"task_id": created["task_id"]}))

    assert payload["status"] == "cancelled"
    assert isolated_task_manager.get(created["task_id"])["status"] == "cancelled"
