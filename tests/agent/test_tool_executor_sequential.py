"""Tests for the sequential tool execution path (execute_tool_calls_sequential).

Covers dispatch, error handling, callbacks, and post-processing
logic that the concurrent-path tests and guardrail-specific tests
do not exercise.
"""

import json
import logging
import time
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agent.tool_executor import execute_tool_calls_sequential
from agent.tool_guardrails import ToolGuardrailDecision
from run_agent import AIAgent


# ---------------------------------------------------------------------------
# Helpers (mirror patterns in tests/run_agent/)
# ---------------------------------------------------------------------------

def _make_tool_defs(*names: str) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"{name} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for name in names
    ]


def _mock_tool_call(name="web_search", arguments="{}", call_id=None):
    return SimpleNamespace(
        id=call_id or f"call_{uuid.uuid4().hex[:8]}",
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _make_agent(*tool_names: str, config: dict | None = None) -> AIAgent:
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs(*tool_names)),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("hermes_cli.config.load_config", return_value=config or {}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            max_iterations=10,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
    agent.client = MagicMock()
    agent._cached_system_prompt = "You are helpful."
    agent._use_prompt_caching = False
    agent.tool_delay = 0
    agent.compression_enabled = False
    agent.save_trajectories = False
    return agent


# ===========================================================================
# Interrupt handling
# ===========================================================================

class TestInterruptHandling:
    """Interrupt before / during sequential execution."""

    def test_interrupt_before_any_tool_skips_all(self):
        agent = _make_agent("web_search")
        agent._interrupt_requested = True
        tc = _mock_tool_call("web_search", '{"q":"test"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.handle_function_call") as mock_hfc:
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        mock_hfc.assert_not_called()
        assert len(messages) == 1
        assert messages[0]["role"] == "tool"
        assert "cancelled" in messages[0]["content"]
        assert messages[0]["tool_call_id"] == "c1"

    def test_interrupt_skips_multiple_remaining_tools(self):
        agent = _make_agent("web_search")
        agent._interrupt_requested = True
        calls = [
            _mock_tool_call("web_search", '{"q":"a"}', "c1"),
            _mock_tool_call("read_file", '{"path":"x.py"}', "c2"),
            _mock_tool_call("write_file", '{"path":"y.py","content":"z"}', "c3"),
        ]
        msg = SimpleNamespace(content="", tool_calls=calls)
        messages = []

        with patch("run_agent.handle_function_call") as mock_hfc:
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        mock_hfc.assert_not_called()
        assert len(messages) == 3
        assert all(m["role"] == "tool" for m in messages)
        assert all("cancelled" in m["content"] for m in messages)

    def test_interrupt_after_first_tool_skips_remaining(self):
        agent = _make_agent("web_search", "read_file", "write_file")
        calls = [
            _mock_tool_call("web_search", '{"q":"first"}', "c1"),
            _mock_tool_call("read_file", '{"path":"a.txt"}', "c2"),
            _mock_tool_call("write_file", '{"path":"b.txt","content":"data"}', "c3"),
        ]
        msg = SimpleNamespace(content="", tool_calls=calls)
        messages = []
        call_count = 0

        def fake_hfc(name, args, task_id, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                agent._interrupt_requested = True
            return json.dumps({"result": "ok"})

        with patch("run_agent.handle_function_call", side_effect=fake_hfc):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert call_count == 1
        assert len(messages) == 3
        assert messages[0]["role"] == "tool"
        assert messages[1]["role"] == "tool"
        assert "skipped" in messages[1]["content"]
        assert "not started" in messages[2]["content"]

    def test_no_interrupt_executes_all(self):
        agent = _make_agent("web_search")
        agent._interrupt_requested = False
        calls = [
            _mock_tool_call("web_search", '{"q":"a"}', "c1"),
            _mock_tool_call("web_search", '{"q":"b"}', "c2"),
        ]
        msg = SimpleNamespace(content="", tool_calls=calls)
        messages = []
        executed = []

        def fake_hfc(name, args, task_id, **kw):
            executed.append((name, args))
            return json.dumps({"result": "ok"})

        with patch("run_agent.handle_function_call", side_effect=fake_hfc):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert len(executed) == 2
        assert len(messages) == 2


# ===========================================================================
# Argument parsing edge cases
# ===========================================================================

class TestArgParsing:
    """Resilience to malformed tool-call arguments."""

    def test_invalid_json_falls_back_to_empty_dict(self):
        agent = _make_agent("web_search")
        agent._interrupt_requested = False
        tc = _mock_tool_call("web_search", "not valid json at all", "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []
        captured_args = []

        def fake_hfc(name, args, task_id, **kw):
            captured_args.append(args)
            return json.dumps({"result": "ok"})

        with patch("run_agent.handle_function_call", side_effect=fake_hfc):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert captured_args == [{}]

    def test_non_dict_json_falls_back_to_empty_dict(self):
        agent = _make_agent("web_search")
        agent._interrupt_requested = False
        tc = _mock_tool_call("web_search", '"string_value"', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []
        captured_args = []

        def fake_hfc(name, args, task_id, **kw):
            captured_args.append(args)
            return json.dumps({"result": "ok"})

        with patch("run_agent.handle_function_call", side_effect=fake_hfc):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert captured_args == [{}]


# ===========================================================================
# Plugin and guardrail blocking
# ===========================================================================

class TestBlocking:
    """Plugin pre-tool-call hooks and guardrail enforcement."""

    def test_plugin_block_returns_error_without_execution(self):
        agent = _make_agent("web_search")
        tc = _mock_tool_call("web_search", '{"q":"blocked"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with (
            patch("hermes_cli.plugins.get_pre_tool_call_block_message", return_value="blocked by policy"),
            patch("run_agent.handle_function_call") as mock_hfc,
        ):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        mock_hfc.assert_not_called()
        assert len(messages) == 1
        payload = json.loads(messages[0]["content"])
        assert "error" in payload
        assert "blocked by policy" in payload["error"]

    def test_guardrail_block_returns_result_without_execution(self):
        agent = _make_agent("web_search")
        tc = _mock_tool_call("web_search", '{"q":"blocked"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []
        blocking_decision = ToolGuardrailDecision(
            action="block", code="test_block", message="blocked by guardrail",
            tool_name="web_search",
        )

        with (
            patch("run_agent.handle_function_call") as mock_hfc,
            patch.object(agent._tool_guardrails, "before_call", return_value=blocking_decision),
        ):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        mock_hfc.assert_not_called()
        assert len(messages) == 1
        assert "tool_call_id" in messages[0]

    def test_plugin_block_prevents_nudge_counter_reset(self):
        agent = _make_agent("memory")
        agent._turns_since_memory = 5
        tc = _mock_tool_call("memory", '{"action":"add","target":"memory","content":"data"}', "c_mem")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("hermes_cli.plugins.get_pre_tool_call_block_message", return_value="policy"):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        # Counter should NOT have been reset since plugin blocked execution
        assert agent._turns_since_memory == 5


# ===========================================================================
# Built-in tool dispatch
# ===========================================================================

class TestBuiltinToolDispatch:
    """Dispatch of agent-level built-in tools."""

    def test_todo_dispatched(self):
        agent = _make_agent("todo")
        tc = _mock_tool_call("todo", '{"todos":[{"content":"test","status":"pending"}]}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert len(messages) == 1
        assert messages[0]["role"] == "tool"

    def test_session_search_dispatched(self):
        agent = _make_agent("session_search")
        agent._session_db = MagicMock()
        tc = _mock_tool_call("session_search", '{"query":"test query"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.AIAgent._get_session_db_for_recall", return_value=agent._session_db):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert len(messages) == 1
        assert messages[0]["role"] == "tool"

    def test_session_search_db_unavailable(self):
        agent = _make_agent("session_search")
        tc = _mock_tool_call("session_search", '{"query":"test"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.AIAgent._get_session_db_for_recall", return_value=None):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert len(messages) == 1
        payload = json.loads(messages[0]["content"])
        assert payload.get("success") is False

    def test_memory_dispatched_with_on_memory_write_bridge(self):
        agent = _make_agent("memory")
        agent._memory_manager = MagicMock()
        agent._memory_manager.has_tool.return_value = False
        tc = _mock_tool_call("memory", '{"action":"add","target":"memory","content":"note"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert len(messages) == 1
        agent._memory_manager.on_memory_write.assert_called_once()

    def test_clarify_dispatched(self):
        agent = _make_agent("clarify")
        agent.clarify_callback = MagicMock()
        tc = _mock_tool_call("clarify", '{"question":"continue?"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert len(messages) == 1
        assert messages[0]["role"] == "tool"
        assert messages[0]["name"] == "clarify"


# ===========================================================================
# Registry dispatch (handle_function_call)
# ===========================================================================

class TestRegistryDispatch:
    """Dispatch through handle_function_call (quiet_mode and normal)."""

    def test_quiet_mode_path_dispatches_to_handle_function_call(self):
        agent = _make_agent("web_search")
        agent.quiet_mode = True
        tc = _mock_tool_call("web_search", '{"query":"test"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.handle_function_call", return_value=json.dumps({"result": "ok"})) as mock_hfc:
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        mock_hfc.assert_called_once()
        assert len(messages) == 1

    def test_normal_path_dispatches_to_handle_function_call(self):
        agent = _make_agent("web_search")
        agent.quiet_mode = False
        tc = _mock_tool_call("web_search", '{"query":"test"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.handle_function_call", return_value=json.dumps({"result": "ok"})) as mock_hfc:
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        mock_hfc.assert_called_once()
        assert len(messages) == 1

    def test_handle_function_call_error_caught(self):
        agent = _make_agent("web_search")
        agent.quiet_mode = False
        tc = _mock_tool_call("web_search", '{"query":"test"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.handle_function_call", side_effect=RuntimeError("connection failed")):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert len(messages) == 1
        assert "Error executing tool" in messages[0]["content"]

    def test_quiet_mode_handle_function_call_error_caught(self):
        agent = _make_agent("web_search")
        agent.quiet_mode = True
        tc = _mock_tool_call("web_search", '{"query":"test"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.handle_function_call", side_effect=RuntimeError("timeout")):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert len(messages) == 1
        assert "Error executing tool" in messages[0]["content"]


# ===========================================================================
# Callback resilience
# ===========================================================================

class TestCallbackResilience:
    """Tool callbacks must not block execution when they raise."""

    def test_tool_progress_callback_error_does_not_block(self):
        agent = _make_agent("web_search")
        agent.tool_progress_callback = MagicMock(side_effect=ValueError("callback error"))

        tc = _mock_tool_call("web_search", '{"query":"test"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.handle_function_call", return_value=json.dumps({"ok": True})):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert len(messages) == 1
        assert messages[0]["role"] == "tool"

    def test_tool_start_callback_error_does_not_block(self):
        agent = _make_agent("web_search")
        agent.tool_start_callback = MagicMock(side_effect=ValueError("start error"))

        tc = _mock_tool_call("web_search", '{"query":"test"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.handle_function_call", return_value=json.dumps({"ok": True})):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert len(messages) == 1

    def test_tool_complete_callback_error_does_not_block(self):
        agent = _make_agent("web_search")
        agent.tool_complete_callback = MagicMock(side_effect=ValueError("complete error"))

        tc = _mock_tool_call("web_search", '{"query":"test"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.handle_function_call", return_value=json.dumps({"ok": True})):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert len(messages) == 1


# ===========================================================================
# Tool delay
# ===========================================================================

class TestToolDelay:
    """Tool delay between sequential calls."""

    def test_tool_delay_sleeps_between_calls(self):
        agent = _make_agent("web_search")
        agent.tool_delay = 0.05
        calls = [
            _mock_tool_call("web_search", '{"q":"a"}', "c1"),
            _mock_tool_call("web_search", '{"q":"b"}', "c2"),
        ]
        msg = SimpleNamespace(content="", tool_calls=calls)
        messages = []
        results = []

        def fake_hfc(name, args, task_id, **kw):
            results.append(name)
            return json.dumps({"ok": True})

        start = time.time()
        with patch("run_agent.handle_function_call", side_effect=fake_hfc):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")
        elapsed = time.time() - start

        assert len(results) == 2
        assert elapsed >= 0.05


# ===========================================================================
# Post-processing
# ===========================================================================

class TestPostProcessing:
    """Result post-processing: error detection, file mutation logging, steer."""

    def test_error_result_is_logged_as_warning(self, caplog):
        agent = _make_agent("web_search")
        tc = _mock_tool_call("web_search", '{"query":"test"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with (
            patch("run_agent.handle_function_call", return_value=json.dumps({"error": "boom"})),
            caplog.at_level(logging.WARNING),
        ):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert any("returned error" in rec.message for rec in caplog.records)

    def test_file_mutation_result_tracked_when_not_blocked(self):
        agent = _make_agent("write_file")
        agent.quiet_mode = False
        tc = _mock_tool_call("write_file", '{"path":"/tmp/test.txt","content":"data"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.AIAgent._record_file_mutation_result") as mock_record:
            with patch("run_agent.handle_function_call", return_value=json.dumps({"success": True})):
                agent._execute_tool_calls_sequential(msg, messages, "task-1")

        mock_record.assert_called_once()

    def test_steer_drained_between_tools(self):
        agent = _make_agent("web_search")
        agent._pending_steer = "interject here"
        calls = [
            _mock_tool_call("web_search", '{"q":"a"}', "c1"),
            _mock_tool_call("web_search", '{"q":"b"}', "c2"),
        ]
        msg = SimpleNamespace(content="", tool_calls=calls)
        messages = []

        with patch("run_agent.handle_function_call", return_value=json.dumps({"ok": True})):
            with patch.object(agent, "_apply_pending_steer_to_tool_results") as mock_steer:
                agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert mock_steer.call_count >= 2


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:
    """Boundary conditions."""

    def test_empty_tool_calls_list(self):
        agent = _make_agent("web_search")
        msg = SimpleNamespace(content="", tool_calls=[])
        messages = []

        agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert messages == []

    def test_single_tool_call_completes(self):
        agent = _make_agent("web_search")
        tc = _mock_tool_call("web_search", '{"query":"hello"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.handle_function_call", return_value=json.dumps({"result": "found"})):
            agent._execute_tool_calls_sequential(msg, messages, "task-1")

        assert len(messages) == 1
        assert messages[0]["name"] == "web_search"
        assert messages[0]["role"] == "tool"
        assert messages[0]["tool_call_id"] == "c1"

    def test_tool_delay_zero_does_not_sleep(self):
        agent = _make_agent("web_search")
        agent.tool_delay = 0
        tc = _mock_tool_call("web_search", '{"q":"test"}', "c1")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.handle_function_call", return_value=json.dumps({"ok": True})):
            with patch.object(time, "sleep") as mock_sleep:
                agent._execute_tool_calls_sequential(msg, messages, "task-1")

        mock_sleep.assert_not_called()


# ===========================================================================
# Integration with the module-level function directly
# ===========================================================================

class TestModuleLevelFunction:
    """Direct calls to the extracted module-level function."""

    def test_module_function_dispatches_correctly(self):
        agent = _make_agent("web_search")
        tc = _mock_tool_call("web_search", '{"query":"direct"}', "c_direct")
        msg = SimpleNamespace(content="", tool_calls=[tc])
        messages = []

        with patch("run_agent.handle_function_call", return_value=json.dumps({"ok": True})):
            execute_tool_calls_sequential(agent, msg, messages, "task-1")

        assert len(messages) == 1
        assert messages[0]["name"] == "web_search"
