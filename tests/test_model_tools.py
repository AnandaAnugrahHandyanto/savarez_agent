"""Tests for model_tools.py — function call dispatch, agent-loop interception, legacy toolsets."""

import json
import pytest

from model_tools import (
    handle_function_call,
    get_all_tool_names,
    get_toolset_for_tool,
    _AGENT_LOOP_TOOLS,
    _LEGACY_TOOLSET_MAP,
    TOOL_TO_TOOLSET_MAP,
)


# =========================================================================
# handle_function_call
# =========================================================================

class TestHandleFunctionCall:
    def test_agent_loop_tool_returns_error(self):
        for tool_name in _AGENT_LOOP_TOOLS:
            result = json.loads(handle_function_call(tool_name, {}))
            assert "error" in result
            assert "agent loop" in result["error"].lower()

    def test_unknown_tool_returns_error(self):
        result = json.loads(handle_function_call("totally_fake_tool_xyz", {}))
        assert "error" in result
        assert "totally_fake_tool_xyz" in result["error"]

    def test_exception_returns_json_error(self):
        # Even if something goes wrong, should return valid JSON
        result = handle_function_call("web_search", None)  # None args may cause issues
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert "error" in parsed
        assert len(parsed["error"]) > 0
        assert "error" in parsed["error"].lower() or "failed" in parsed["error"].lower()

    def test_pre_tool_call_block_directive_returns_json_error_and_skips_dispatch(self, monkeypatch):
        hook_calls = []
        dispatch_called = False

        def fake_invoke_hook(hook_name, **kwargs):
            hook_calls.append(hook_name)
            if hook_name == "pre_tool_call":
                return [{"action": "block", "message": "Tool call blocked by plugin"}]
            return []

        def fake_dispatch(*args, **kwargs):
            nonlocal dispatch_called
            dispatch_called = True
            raise AssertionError("dispatch should not run when pre_tool_call blocks")

        monkeypatch.setattr("hermes_cli.plugins.invoke_hook", fake_invoke_hook)
        monkeypatch.setattr("model_tools.registry.dispatch", fake_dispatch)

        result = json.loads(handle_function_call("read_file", {"path": "notes.txt"}, task_id="t1"))

        assert result == {"error": "Tool call blocked by plugin"}
        assert dispatch_called is False
        assert hook_calls == ["pre_tool_call"]

    def test_blocked_tool_does_not_notify_other_tool_call(self, monkeypatch):
        notifications = []

        def fake_invoke_hook(hook_name, **kwargs):
            if hook_name == "pre_tool_call":
                return [{"action": "block", "message": "Tool call blocked by plugin"}]
            return []

        def fake_dispatch(*args, **kwargs):
            raise AssertionError("dispatch should not run when pre_tool_call blocks")

        monkeypatch.setattr("hermes_cli.plugins.invoke_hook", fake_invoke_hook)
        monkeypatch.setattr(
            "tools.file_tools.notify_other_tool_call",
            lambda task_id: notifications.append(task_id),
        )
        monkeypatch.setattr("model_tools.registry.dispatch", fake_dispatch)

        result = json.loads(handle_function_call("web_search", {"q": "test"}, task_id="t1"))

        assert result == {"error": "Tool call blocked by plugin"}
        assert notifications == []

    def test_invalid_pre_tool_call_hook_returns_are_ignored(self, monkeypatch):
        hook_calls = []

        def fake_invoke_hook(hook_name, **kwargs):
            hook_calls.append(hook_name)
            if hook_name == "pre_tool_call":
                return [
                    "block",
                    123,
                    {"action": "block"},
                    {"action": "deny", "message": "nope"},
                    {"message": "missing action"},
                    {"action": "block", "message": 123},
                ]
            return []

        def fake_dispatch(tool_name, tool_args, **kwargs):
            assert tool_name == "read_file"
            assert tool_args == {"path": "notes.txt"}
            return json.dumps({"ok": True})

        monkeypatch.setattr("hermes_cli.plugins.invoke_hook", fake_invoke_hook)
        monkeypatch.setattr("model_tools.registry.dispatch", fake_dispatch)

        result = json.loads(handle_function_call("read_file", {"path": "notes.txt"}, task_id="t1"))

        assert result == {"ok": True}
        assert hook_calls == ["pre_tool_call", "post_tool_call"]


# =========================================================================
# Agent loop tools
# =========================================================================

class TestAgentLoopTools:
    def test_expected_tools_in_set(self):
        assert "todo" in _AGENT_LOOP_TOOLS
        assert "memory" in _AGENT_LOOP_TOOLS
        assert "session_search" in _AGENT_LOOP_TOOLS
        assert "delegate_task" in _AGENT_LOOP_TOOLS

    def test_no_regular_tools_in_set(self):
        assert "web_search" not in _AGENT_LOOP_TOOLS
        assert "terminal" not in _AGENT_LOOP_TOOLS


# =========================================================================
# Legacy toolset map
# =========================================================================

class TestLegacyToolsetMap:
    def test_expected_legacy_names(self):
        expected = [
            "web_tools", "terminal_tools", "vision_tools", "moa_tools",
            "image_tools", "skills_tools", "browser_tools", "cronjob_tools",
            "rl_tools", "file_tools", "tts_tools",
        ]
        for name in expected:
            assert name in _LEGACY_TOOLSET_MAP, f"Missing legacy toolset: {name}"

    def test_values_are_lists_of_strings(self):
        for name, tools in _LEGACY_TOOLSET_MAP.items():
            assert isinstance(tools, list), f"{name} is not a list"
            for tool in tools:
                assert isinstance(tool, str), f"{name} contains non-string: {tool}"


# =========================================================================
# Backward-compat wrappers
# =========================================================================

class TestBackwardCompat:
    def test_get_all_tool_names_returns_list(self):
        names = get_all_tool_names()
        assert isinstance(names, list)
        assert len(names) > 0
        # Should contain well-known tools
        assert "web_search" in names
        assert "terminal" in names

    def test_get_toolset_for_tool(self):
        result = get_toolset_for_tool("web_search")
        assert result is not None
        assert isinstance(result, str)

    def test_get_toolset_for_unknown_tool(self):
        result = get_toolset_for_tool("totally_nonexistent_tool")
        assert result is None

    def test_tool_to_toolset_map(self):
        assert isinstance(TOOL_TO_TOOLSET_MAP, dict)
        assert len(TOOL_TO_TOOLSET_MAP) > 0
