"""Focused tests for browser_batch tool and wiring."""

import json
from unittest.mock import patch


def test_browser_batch_schema_and_wiring():
    from model_tools import _LEGACY_TOOLSET_MAP
    from toolsets import TOOLSETS, _HERMES_CORE_TOOLS, resolve_toolset
    from tools.browser_tool import BROWSER_TOOL_SCHEMAS
    from tools.registry import registry
    from tools import browser_tool  # noqa: F401

    schema = next(s for s in BROWSER_TOOL_SCHEMAS if s["name"] == "browser_batch")
    props = schema["parameters"]["properties"]

    assert "actions" in props
    assert props["actions"]["type"] == "array"
    assert "stop_on_error" in props
    assert props["stop_on_error"]["type"] == "boolean"

    assert "browser_batch" in TOOLSETS["browser"]["tools"]
    assert "browser_batch" in _HERMES_CORE_TOOLS
    assert "browser_batch" in _LEGACY_TOOLSET_MAP["browser_tools"]
    assert "browser_batch" in resolve_toolset("hermes-api-server")
    assert "browser_batch" in registry._tools


def test_browser_batch_runs_wrapped_tools_in_order():
    from tools.browser_tool import browser_batch

    with (
        patch("tools.browser_tool.browser_navigate", return_value=json.dumps({"success": True, "url": "https://example.com"})) as mock_navigate,
        patch("tools.browser_tool.browser_click", return_value=json.dumps({"success": True, "clicked": "@e1"})) as mock_click,
        patch("tools.browser_tool._run_browser_command", side_effect=AssertionError("must use high-level wrappers")),
    ):
        result = json.loads(
            browser_batch(
                actions=[
                    {"action": "navigate", "url": "https://example.com"},
                    {"action": "click", "ref": "@e1"},
                ],
                task_id="task-123",
            )
        )

    assert result["success"] is True
    assert result["total_actions"] == 2
    assert result["completed_actions"] == 2
    assert result["stopped_on_error"] is False
    assert [step["action"] for step in result["results"]] == ["navigate", "click"]
    assert result["results"][0]["result"]["url"] == "https://example.com"
    assert result["results"][1]["result"]["clicked"] == "@e1"
    mock_navigate.assert_called_once_with(url="https://example.com", task_id="task-123")
    mock_click.assert_called_once_with(ref="@e1", task_id="task-123")


def test_browser_batch_stops_on_first_error_by_default():
    from tools.browser_tool import browser_batch

    with (
        patch("tools.browser_tool.browser_navigate", return_value=json.dumps({"success": True, "url": "https://example.com"})) as mock_navigate,
        patch("tools.browser_tool.browser_click", return_value=json.dumps({"success": False, "error": "element not found"})) as mock_click,
        patch("tools.browser_tool.browser_snapshot", return_value=json.dumps({"success": True, "snapshot": "unused"})) as mock_snapshot,
    ):
        result = json.loads(
            browser_batch(
                actions=[
                    {"action": "navigate", "url": "https://example.com"},
                    {"action": "click", "ref": "@missing"},
                    {"action": "snapshot"},
                ],
                task_id="task-err",
            )
        )

    assert result["success"] is False
    assert result["stop_on_error"] is True
    assert result["stopped_on_error"] is True
    assert result["failed_action_index"] == 1
    assert result["completed_actions"] == 1
    assert len(result["results"]) == 2
    assert result["results"][1]["success"] is False
    assert result["results"][1]["result"]["error"] == "element not found"
    mock_navigate.assert_called_once()
    mock_click.assert_called_once()
    mock_snapshot.assert_not_called()


def test_browser_batch_can_continue_after_errors():
    from tools.browser_tool import browser_batch

    with (
        patch("tools.browser_tool.browser_navigate", return_value=json.dumps({"success": True, "url": "https://example.com"})),
        patch("tools.browser_tool.browser_click", return_value=json.dumps({"success": False, "error": "element not found"})),
        patch("tools.browser_tool.browser_snapshot", return_value=json.dumps({"success": True, "snapshot": "page state"})) as mock_snapshot,
    ):
        result = json.loads(
            browser_batch(
                actions=[
                    {"action": "navigate", "url": "https://example.com"},
                    {"action": "click", "ref": "@missing"},
                    {"action": "snapshot", "full": True},
                ],
                stop_on_error=False,
                task_id="task-continue",
            )
        )

    assert result["success"] is False
    assert result["stop_on_error"] is False
    assert result["stopped_on_error"] is False
    assert result["completed_actions"] == 2
    assert len(result["results"]) == 3
    assert result["results"][2]["success"] is True
    assert result["results"][2]["result"]["snapshot"] == "page state"
    mock_snapshot.assert_called_once_with(full=True, task_id="task-continue", user_task=None)


def test_browser_batch_validates_input_shape_and_required_fields():
    from tools.browser_tool import browser_batch

    empty = json.loads(browser_batch(actions=[]))
    assert empty["success"] is False
    assert "non-empty" in empty["error"]

    too_many = json.loads(browser_batch(actions=[{"action": "back"}] * 26))
    assert too_many["success"] is False
    assert "25" in too_many["error"]

    missing_ref = json.loads(browser_batch(actions=[{"action": "click"}]))
    assert missing_ref["success"] is False
    assert "ref" in missing_ref["error"]

    unknown = json.loads(browser_batch(actions=[{"action": "teleport"}]))
    assert unknown["success"] is False
    assert "teleport" in unknown["error"]
