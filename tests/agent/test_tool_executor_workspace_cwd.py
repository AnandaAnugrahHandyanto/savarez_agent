"""Tests for workspace-aware tool execution bookkeeping."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import agent.tool_executor as tool_executor
from agent.tool_executor import execute_tool_calls_sequential


def test_destructive_terminal_checkpoint_uses_session_cwd(tmp_path, monkeypatch):
    session_dir = tmp_path / "session"
    global_dir = tmp_path / "global"
    session_dir.mkdir()
    global_dir.mkdir()
    monkeypatch.setenv("TERMINAL_CWD", str(global_dir))

    from gateway.session_context import clear_session_vars, set_session_vars

    tokens = set_session_vars(session_cwd=str(session_dir))
    try:
        monkeypatch.setattr(
            tool_executor,
            "_ra",
            lambda: SimpleNamespace(
                handle_function_call=lambda *_args, **_kwargs: '{"ok": true}',
                logger=MagicMock(),
            ),
        )

        checkpoint_mgr = MagicMock()
        checkpoint_mgr.enabled = True

        agent = MagicMock()
        agent._interrupt_requested = False
        agent._tool_guardrails.before_call.return_value = SimpleNamespace(allows_execution=True)
        agent._checkpoint_mgr = checkpoint_mgr
        agent.quiet_mode = True
        agent.tool_progress_callback = None
        agent.tool_start_callback = None
        agent.tool_delay = 0
        agent.session_id = "session-1"
        agent.valid_tool_names = set()
        agent.enabled_toolsets = None
        agent.disabled_toolsets = None
        agent._current_tool = None
        agent._touch_activity = MagicMock()
        agent._should_emit_quiet_tool_messages.return_value = False

        tool_call = SimpleNamespace(
            id="tool-1",
            function=SimpleNamespace(
                name="terminal",
                arguments='{"command": "rm -rf build"}',
            ),
        )
        assistant = SimpleNamespace(tool_calls=[tool_call])

        execute_tool_calls_sequential(agent, assistant, [], "session-1")

        checkpoint_mgr.ensure_checkpoint.assert_called()
        assert checkpoint_mgr.ensure_checkpoint.call_args.args[0] == str(session_dir)
    finally:
        clear_session_vars(tokens)
