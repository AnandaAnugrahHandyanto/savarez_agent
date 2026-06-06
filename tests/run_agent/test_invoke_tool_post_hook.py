"""Test that _invoke_tool fires the post-tool-call hook exactly once for model_switch.

Why: The concurrent invoke_tool path had a gap where model_switch returned the raw
_model_switch_tool() result without wrapping it in _finish_agent_tool(), so the
_emit_post_tool_call_hook was never called. Every other agent-level tool branch
(todo, session_search, memory, clarify, delegate_task) correctly wraps its return
with _finish_agent_tool(). This test pins the fix so the regression cannot recur.

What: Asserts _emit_post_tool_call_hook fires exactly once when _invoke_tool routes
to model_switch, matching the behavior of the todo branch (validated by the
mirror test also included here for reference).

Test: monkeypatch invoke_hook / has_hook to capture hook calls, patch
model_switch_tool to return a known string, call agent._invoke_tool("model_switch",
...) and assert exactly one "post_tool_call" hook event with the right fields.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers copied from test_run_agent.py to keep this file self-contained
# ---------------------------------------------------------------------------

def _make_tool_defs(*names: str) -> list:
    """Build minimal tool definition list accepted by AIAgent.__init__."""
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"{n} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for n in names
    ]


@pytest.fixture()
def agent():
    """Minimal AIAgent with mocked OpenAI client and tool loading."""
    from run_agent import AIAgent

    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInvokeToolPostHookModelSwitch:
    """The post-tool-call hook must fire exactly once for model_switch on the concurrent path."""

    def test_model_switch_emits_post_tool_call_hook_exactly_once(self, agent, monkeypatch):
        """_invoke_tool model_switch branch must call _emit_post_tool_call_hook.

        Why: Before the fix model_switch returned the raw _model_switch_tool() result
        directly, bypassing _finish_agent_tool() and therefore never emitting the
        post-tool-call hook. Telemetry and plugin observers were silently dropped.

        What: Patches invoke_hook/has_hook to capture events; asserts exactly one
        post_tool_call event with correct tool_name, tool_call_id, and result.

        Test: Run _invoke_tool("model_switch", ...) with the model_switch_tool patched
        to return a known string. Verify the captured hook events include exactly one
        post_tool_call entry containing the expected fields.
        """
        hook_calls: list = []

        monkeypatch.setattr(
            "hermes_cli.plugins.get_pre_tool_call_block_message",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "hermes_cli.plugins.invoke_hook",
            lambda hook_name, **kwargs: hook_calls.append((hook_name, kwargs)) or [],
        )
        monkeypatch.setattr("hermes_cli.plugins.has_hook", lambda name: True)

        model_switch_result = json.dumps({"switched": True, "model": "test-model"})

        with patch(
            "tools.model_switch_tool.model_switch_tool",
            return_value=model_switch_result,
        ) as mock_ms:
            result = agent._invoke_tool(
                "model_switch",
                {"slug": "test-model", "reason": "complexity", "scope": "session"},
                "task-1",
                tool_call_id="ms-call-1",
            )

        # The underlying tool was called
        mock_ms.assert_called_once()

        # The result is passed through unchanged
        assert result == model_switch_result

        # Exactly one post_tool_call hook event
        post_calls = [c for c in hook_calls if c[0] == "post_tool_call"]
        assert len(post_calls) == 1, (
            f"Expected exactly 1 post_tool_call hook event, got {len(post_calls)}. "
            "Likely cause: model_switch branch missing _finish_agent_tool() wrapper."
        )

        event_kwargs = post_calls[0][1]
        assert event_kwargs["tool_name"] == "model_switch"
        assert event_kwargs["tool_call_id"] == "ms-call-1"
        assert event_kwargs["result"] == model_switch_result
        assert event_kwargs["status"] == "ok"
        assert event_kwargs["error_type"] is None
        assert isinstance(event_kwargs["duration_ms"], int)

    def test_model_switch_hook_fires_once_not_zero_times(self, agent, monkeypatch):
        """Regression guard: hook count must be >= 1, catching the original zero-fires bug.

        Why: A bare return _model_switch_tool(...) means _emit_post_tool_call_hook is
        never reached — this test captures the pre-fix failure mode explicitly.

        What: Verifies post_tool_call hook count is not zero after a model_switch call.

        Test: Same setup as the main test; asserts post_calls is non-empty.
        """
        hook_calls: list = []

        monkeypatch.setattr(
            "hermes_cli.plugins.get_pre_tool_call_block_message",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "hermes_cli.plugins.invoke_hook",
            lambda hook_name, **kwargs: hook_calls.append((hook_name, kwargs)) or [],
        )
        monkeypatch.setattr("hermes_cli.plugins.has_hook", lambda name: True)

        with patch(
            "tools.model_switch_tool.model_switch_tool",
            return_value='{"switched": true}',
        ):
            agent._invoke_tool(
                "model_switch",
                {"slug": "fast-model", "reason": "cheap", "scope": "turn"},
                "task-2",
                tool_call_id="ms-call-2",
            )

        post_calls = [c for c in hook_calls if c[0] == "post_tool_call"]
        assert post_calls, "post_tool_call hook never fired — model_switch missing _finish_agent_tool wrapper"

    def test_todo_emits_post_tool_call_hook_exactly_once(self, agent, monkeypatch):
        """Mirror test: confirm the existing todo branch behaviour that model_switch must match.

        Why: Documents the canonical peer-branch contract so reviewers can verify
        model_switch and todo are handled identically.

        What: Asserts that _invoke_tool("todo", ...) also emits exactly one post_tool_call
        hook, proving both branches share the same behaviour after the fix.

        Test: Same monkeypatch setup; patch todo_tool; call _invoke_tool("todo"); assert
        exactly one post_tool_call event with correct fields.
        """
        hook_calls: list = []

        monkeypatch.setattr(
            "hermes_cli.plugins.get_pre_tool_call_block_message",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "hermes_cli.plugins.invoke_hook",
            lambda hook_name, **kwargs: hook_calls.append((hook_name, kwargs)) or [],
        )
        monkeypatch.setattr("hermes_cli.plugins.has_hook", lambda name: True)

        todo_result = '{"ok": true}'

        with patch("tools.todo_tool.todo_tool", return_value=todo_result) as mock_todo:
            result = agent._invoke_tool(
                "todo",
                {"todos": []},
                "task-3",
                tool_call_id="todo-call-1",
            )

        mock_todo.assert_called_once()
        assert result == todo_result

        post_calls = [c for c in hook_calls if c[0] == "post_tool_call"]
        assert len(post_calls) == 1
        assert post_calls[0][1]["tool_name"] == "todo"
        assert post_calls[0][1]["tool_call_id"] == "todo-call-1"
        assert post_calls[0][1]["status"] == "ok"

    def test_model_switch_in_agent_runtime_post_hook_tool_names(self):
        """model_switch must be in AGENT_RUNTIME_POST_HOOK_TOOL_NAMES.

        Why: The predicate agent_runtime_owns_post_tool_hook() gates which tools get
        their post-hook emitted by the agent runtime vs the registry dispatcher.
        If model_switch is missing, the outer dispatcher may double-emit or skip.

        What: Imports the frozenset and asserts model_switch is present.

        Test: Direct import check — fails immediately if someone removes the entry.
        """
        from agent.agent_runtime_helpers import AGENT_RUNTIME_POST_HOOK_TOOL_NAMES
        assert "model_switch" in AGENT_RUNTIME_POST_HOOK_TOOL_NAMES

    def test_agent_runtime_owns_post_tool_hook_returns_true_for_model_switch(self, agent):
        """agent_runtime_owns_post_tool_hook must return True for model_switch.

        Why: Ensures the ownership predicate correctly identifies model_switch as an
        agent-level tool, preventing the outer dispatcher from double-emitting hooks.

        What: Calls agent_runtime_owns_post_tool_hook(agent, "model_switch") and
        asserts the return value is True.

        Test: Direct function call — simple boolean assertion.
        """
        from agent.agent_runtime_helpers import agent_runtime_owns_post_tool_hook
        assert agent_runtime_owns_post_tool_hook(agent, "model_switch") is True
