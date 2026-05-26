import json
from types import SimpleNamespace

import pytest

from orchestration_telemetry import append_event, read_events, telemetry_path
from tools.delegate_tool import _append_delegate_route_telemetry
from tools.kanban_tools import _append_kanban_route_telemetry


def _event_text(event):
    return json.dumps(event, sort_keys=True)


@pytest.fixture(autouse=True)
def _enable_isolated_telemetry(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_ORCHESTRATION_TELEMETRY", "1")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))


def test_orchestration_telemetry_writes_metadata_only_and_sanitizes(tmp_path):
    path = tmp_path / "routing.jsonl"

    written = append_event(
        "route.selected",
        surface="delegate_task",
        path=path,
        status="selected",
        goal="summarize a confidential customer thread",
        context="the raw user context must not be persisted",
        route={
            "provider": "nous",
            "model": "deepseek/deepseek-v4-flash",
            "api_key": "sk-should-not-appear-in-log",
        },
        metrics={"duration_seconds": 1.25},
    )

    assert written == path
    events = read_events(path=path)
    assert len(events) == 1
    event = events[0]
    text = _event_text(event)

    assert event["schema_version"] == 1
    assert event["surface"] == "delegate_task"
    assert event["event_type"] == "route.selected"
    assert event["route"]["provider"] == "nous"
    assert event["classification"] == {"domain": "unknown", "sensitivity": "unknown", "risk": "unknown"}
    assert event["context_sources"] == []
    assert event["retries_escalations"] == {"retry_count": 0, "escalated": False}
    assert event["quality"] == {"user_correction_signal": "not_captured"}
    assert event["route"]["api_key"] == "[REDACTED]"
    assert "goal" not in event
    assert "context" not in event
    assert "confidential customer" not in text
    assert "raw user context" not in text
    assert "sk-should-not" not in text
    assert "goal" in event["privacy"]["content_fields_excluded"]
    assert "context" in event["privacy"]["content_fields_excluded"]
    assert "api_key" in event["privacy"]["secret_fields_redacted"]


def test_profile_config_can_enable_telemetry_without_env(monkeypatch, tmp_path):
    monkeypatch.delenv("HERMES_ORCHESTRATION_TELEMETRY", raising=False)
    home = tmp_path / "hermes-home"
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(
        "logging:\n  orchestration_telemetry:\n    enabled: true\n",
        encoding="utf-8",
    )
    path = home / "logs" / "routing.jsonl"

    written = append_event(
        "route.selected",
        surface="kanban_create",
        path=path,
        status="selected",
        body="task body must not persist",
        route={"chosen_route": "kanban_create", "assignee_profile": "researcher"},
    )

    assert written == path
    event = read_events(path=path)[0]
    assert event["surface"] == "kanban_create"
    assert "body" not in event
    assert "body" in event["privacy"]["content_fields_excluded"]


def test_delegate_route_telemetry_helper_records_completion_without_summary():
    child = SimpleNamespace(
        _orchestration_route_telemetry={
            "action_type": "spawn_subagent",
            "route": {
                "chosen_route": "delegate_task",
                "provider": "openrouter",
                "model": "anthropic/claude-sonnet-4",
                "reasoning_effort": "xhigh",
                "role": "leaf",
                "execution_mode": "delegate_task",
                "route_reason": "delegate_task default route",
            },
            "tree": {"subagent_id": "sa-test", "depth": 0, "task_index": 0, "task_count": 1},
            "tooling": {"toolsets": ["terminal"], "tool_count": 1},
        }
    )

    _append_delegate_route_telemetry(
        "route.completed",
        child=child,
        status="completed",
        extra={
            "summary": "do not persist this child summary",
            "metrics": {"duration_seconds": 2.0, "api_calls": 1},
            "outcome": {"success": True, "exit_reason": "completed"},
        },
    )

    events = read_events(path=telemetry_path())
    assert len(events) == 1
    event = events[0]
    text = _event_text(event)

    assert event["surface"] == "delegate_task"
    assert event["status"] == "completed"
    assert event["route"]["model"] == "anthropic/claude-sonnet-4"
    assert event["metrics"]["api_calls"] == 1
    assert "summary" not in event
    assert "do not persist" not in text
    assert "summary" in event["privacy"]["content_fields_excluded"]


def test_kanban_route_telemetry_helper_records_route_without_title():
    _append_kanban_route_telemetry(
        "route.selected",
        status="ready",
        action_type="create_kanban_task",
        title="secret task title should not persist",
        route={
            "chosen_route": "kanban_create",
            "assignee_profile": "researcher",
            "workspace_kind": "scratch",
        },
        tree={"task_id": "t_example", "parent_task_ids": ["t_parent"], "parent_count": 1},
        input_shape={"title_chars": 36, "body_chars": 0, "body_supplied": False},
    )

    events = read_events(path=telemetry_path())
    assert len(events) == 1
    event = events[0]
    text = _event_text(event)

    assert event["surface"] == "kanban_create"
    assert event["status"] == "ready"
    assert event["route"]["assignee_profile"] == "researcher"
    assert event["tree"]["task_id"] == "t_example"
    assert "title" not in event
    assert "secret task title" not in text
    assert "title" in event["privacy"]["content_fields_excluded"]
