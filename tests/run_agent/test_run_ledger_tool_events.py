import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent.tool_guardrails import ToolCallGuardrailController
from run_agent import AIAgent


def _tool_call(call_id: str, name: str, args: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


def _make_agent(tmp_path, run_id: str = "run-tools") -> AIAgent:
    from agent.run_ledger import RunLedger

    agent = object.__new__(AIAgent)
    agent.session_id = "session-tools"
    agent._run_ledger = RunLedger(
        run_id=run_id,
        session_id=agent.session_id,
        config={"preview_chars": 128, "blob_threshold_chars": 256, "fsync": False},
    )
    agent._interrupt_requested = False
    agent._vprint = MagicMock()
    agent.log_prefix = ""
    agent.quiet_mode = True
    agent.verbose_logging = False
    agent.log_prefix_chars = 200
    agent.platform = "test"
    agent.tool_progress_callback = None
    agent.tool_start_callback = None
    agent.tool_complete_callback = None
    agent._checkpoint_mgr = SimpleNamespace(enabled=False)
    agent._tool_guardrails = ToolCallGuardrailController()
    agent._tool_guardrail_halt_decision = None
    agent._current_tool = None
    agent._touch_activity = MagicMock()
    agent._context_engine_tool_names = set()
    agent._memory_manager = None
    agent._todo_store = MagicMock()
    agent.clarify_callback = None
    agent._should_emit_quiet_tool_messages = MagicMock(return_value=False)
    agent._should_start_quiet_spinner = MagicMock(return_value=False)
    agent._apply_pending_steer_to_tool_results = MagicMock()
    agent._subdirectory_hints = SimpleNamespace(check_tool_call=MagicMock(return_value=""))
    agent.valid_tool_names = {"synthetic_tool", "terminal", "read_file"}
    agent.tool_delay = 0
    agent._print_fn = None
    agent._tool_worker_threads = set()
    agent._tool_worker_threads_lock = __import__("threading").Lock()
    agent._safe_print = MagicMock()
    return agent


def _events(agent: AIAgent) -> list[dict]:
    return agent._run_ledger.read_events().events


def test_sequential_tool_call_records_start_and_terminal_event(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    agent = _make_agent(tmp_path)
    messages = []
    assistant = SimpleNamespace(
        tool_calls=[_tool_call("call-ok", "synthetic_tool", {"path": "a.txt"})],
    )

    with patch("run_agent.handle_function_call", return_value=json.dumps({"ok": True, "token": "sk-testsecret1234567890"})):
        agent._execute_tool_calls_sequential(assistant, messages, "task-a")

    events = _events(agent)
    assert [event["type"] for event in events] == ["tool.started", "tool.finished"]
    assert [event["tool_call_id"] for event in events] == ["call-ok", "call-ok"]
    assert events[1]["status"] == "ok"
    assert events[1]["metadata"]["ok"] is True
    assert "sha256" in events[1]["output"]
    assert "sk-testsecret" not in json.dumps(events)


def test_error_tool_result_records_error_and_recovers_no_in_flight(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    agent = _make_agent(tmp_path, run_id="run-error")
    messages = []
    assistant = SimpleNamespace(
        tool_calls=[_tool_call("call-error", "synthetic_tool", {"query": "bad"})],
    )

    with patch("run_agent.handle_function_call", return_value=json.dumps({"success": False, "error": "failed"})):
        agent._execute_tool_calls_sequential(assistant, messages, "task-a")

    events = _events(agent)
    assert events[-1]["type"] == "tool.failed"
    assert events[-1]["status"] == "error"
    assert events[-1]["metadata"]["ok"] is False
    assert agent._run_ledger.recover_state()["in_flight"] == {}


def test_sequential_tool_exception_records_failed_event_and_recovers_no_in_flight(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    agent = _make_agent(tmp_path, run_id="run-seq-exception")
    messages = []
    assistant = SimpleNamespace(
        tool_calls=[_tool_call("call-raises", "synthetic_tool", {"query": "explode"})],
    )

    with patch("run_agent.handle_function_call", side_effect=RuntimeError("boom")):
        agent._execute_tool_calls_sequential(assistant, messages, "task-a")

    events = _events(agent)
    assert [event["type"] for event in events] == ["tool.started", "tool.failed"]
    assert events[-1]["tool_call_id"] == "call-raises"
    assert "boom" in events[-1]["output"]["preview"]
    assert agent._run_ledger.recover_state()["in_flight"] == {}
    assert messages[-1]["tool_call_id"] == "call-raises"


def test_concurrent_tool_calls_record_start_and_terminal_per_call(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    agent = _make_agent(tmp_path, run_id="run-concurrent")
    messages = []
    assistant = SimpleNamespace(
        tool_calls=[
            _tool_call("call-a", "read_file", {"path": "a.txt"}),
            _tool_call("call-b", "read_file", {"path": "b.txt"}),
        ],
    )

    def fake_invoke(function_name, function_args, *_args, **_kwargs):
        return json.dumps({"success": True, "path": function_args["path"]})

    agent._invoke_tool = MagicMock(side_effect=fake_invoke)

    agent._execute_tool_calls_concurrent(assistant, messages, "task-a")

    events = _events(agent)
    by_call = {}
    for event in events:
        by_call.setdefault(event["tool_call_id"], []).append(event["type"])

    assert by_call == {
        "call-a": ["tool.started", "tool.finished"],
        "call-b": ["tool.started", "tool.finished"],
    }
    assert {message["tool_call_id"] for message in messages} == {"call-a", "call-b"}


def test_concurrent_tool_exception_records_failed_event(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    agent = _make_agent(tmp_path, run_id="run-concurrent-exception")
    messages = []
    assistant = SimpleNamespace(
        tool_calls=[_tool_call("call-raises", "read_file", {"path": "boom.txt"})],
    )
    agent._invoke_tool = MagicMock(side_effect=RuntimeError("boom"))

    agent._execute_tool_calls_concurrent(assistant, messages, "task-a")

    events = _events(agent)
    assert [event["type"] for event in events] == ["tool.started", "tool.failed"]
    assert events[-1]["tool_call_id"] == "call-raises"
    assert "boom" in events[-1]["output"]["preview"]
    assert agent._run_ledger.recover_state()["in_flight"] == {}
    assert messages[-1]["tool_call_id"] == "call-raises"
