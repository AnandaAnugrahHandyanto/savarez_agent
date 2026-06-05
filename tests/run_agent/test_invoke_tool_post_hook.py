"""Tests for invoke_tool — verify post-tool-call hook fires for every inline tool.

Why: invoke_tool is the concurrent execution path.  Each inline-dispatched tool
(todo, session_search, memory, clarify, delegate_task, model_switch) must call
_finish_agent_tool so that _emit_post_tool_call_hook fires exactly once.  A
missing _finish_agent_tool call silently drops post-tool telemetry/hook firing
for that tool.

The model_switch branch had a real gap where it returned the raw result instead
of wrapping it with _finish_agent_tool; this was fixed alongside the BUG-8
guard improvements.

What: Patches _emit_post_tool_call_hook and each tool's implementation to verify
the hook is called with the correct function_name for every inline branch.

Test: For each tested branch, assert that _emit_post_tool_call_hook is called
exactly once with the correct function_name after invoke_tool returns.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _make_stub_agent(**extra):
    """Build a minimal agent stub sufficient for invoke_tool's inline branches."""
    store = MagicMock()
    stub = SimpleNamespace(
        session_id="test-session",
        _current_turn_id="turn-1",
        _current_api_request_id="req-1",
        valid_tool_names=frozenset({"todo", "session_search", "memory", "clarify", "model_switch", "delegate_task"}),
        _todo_store=store,
        _memory_store=store,
        _memory_manager=None,
        clarify_callback=None,
        _context_engine_tool_names=None,
        **extra,
    )
    return stub


class TestInvokeToolPostHook:
    """Each inline branch in invoke_tool must fire _emit_post_tool_call_hook."""

    def _call_invoke_tool(self, agent, function_name, function_args):
        from agent.agent_runtime_helpers import invoke_tool
        return invoke_tool(
            agent,
            function_name=function_name,
            function_args=function_args,
            effective_task_id="task-1",
            tool_call_id="tc-1",
        )

    def test_model_switch_fires_post_hook(self):
        """Why: model_switch previously returned without calling _finish_agent_tool.
        What: Patches model_switch_tool and _emit_post_tool_call_hook; asserts hook fires.
        Test: hook call count == 1 with function_name == 'model_switch'.
        """
        agent = _make_stub_agent()
        switch_result = json.dumps({"success": True, "model": "test-model"})

        with patch("tools.model_switch_tool.model_switch_tool", return_value=switch_result) as mock_switch, \
             patch("model_tools._emit_post_tool_call_hook") as mock_hook:
            result = self._call_invoke_tool(agent, "model_switch", {"slug": "test-model", "reason": "test"})

        assert result == switch_result
        mock_hook.assert_called_once()
        call_kwargs = mock_hook.call_args
        assert call_kwargs.kwargs.get("function_name") == "model_switch" or \
               (call_kwargs.args and call_kwargs.args[0] == "model_switch"), \
            f"Expected function_name='model_switch', got: {call_kwargs}"

    def test_todo_fires_post_hook(self):
        """Why: Control case — todo correctly wraps with _finish_agent_tool.
        What: Verifies the hook fires once for the todo branch.
        Test: hook call count == 1 with function_name == 'todo'.
        """
        agent = _make_stub_agent()
        todo_result = json.dumps({"todos": []})

        with patch("tools.todo_tool.todo_tool", return_value=todo_result), \
             patch("model_tools._emit_post_tool_call_hook") as mock_hook:
            result = self._call_invoke_tool(agent, "todo", {"todos": [], "merge": False})

        assert result == todo_result
        mock_hook.assert_called_once()
        call_kwargs = mock_hook.call_args
        assert call_kwargs.kwargs.get("function_name") == "todo" or \
               (call_kwargs.args and call_kwargs.args[0] == "todo"), \
            f"Expected function_name='todo', got: {call_kwargs}"

    def test_clarify_fires_post_hook(self):
        """Why: Control case — clarify correctly wraps with _finish_agent_tool.
        What: Verifies the hook fires once for the clarify branch.
        Test: hook call count == 1 with function_name == 'clarify'.
        """
        agent = _make_stub_agent()
        clarify_result = json.dumps({"answer": "yes"})

        with patch("tools.clarify_tool.clarify_tool", return_value=clarify_result), \
             patch("model_tools._emit_post_tool_call_hook") as mock_hook:
            result = self._call_invoke_tool(agent, "clarify", {"question": "proceed?"})

        assert result == clarify_result
        mock_hook.assert_called_once()
        call_kwargs = mock_hook.call_args
        assert call_kwargs.kwargs.get("function_name") == "clarify" or \
               (call_kwargs.args and call_kwargs.args[0] == "clarify"), \
            f"Expected function_name='clarify', got: {call_kwargs}"
