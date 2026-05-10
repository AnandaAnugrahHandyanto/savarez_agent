from pathlib import Path
from unittest.mock import MagicMock

from run_agent import AIAgent


def _make_agent(tmp_path: Path, *, run_id: str = "parent-session") -> AIAgent:
    from agent.run_ledger import RunLedger

    agent = object.__new__(AIAgent)
    agent.session_id = "parent-session"
    agent._parent_session_id = None
    agent.model = "test/model"
    agent.platform = "cli"
    agent.tools = []
    agent.logs_dir = tmp_path
    agent.session_log_file = tmp_path / f"session_{agent.session_id}.json"
    agent._session_db = None
    agent._session_db_created = False
    agent._session_init_model_config = {"model": "test/model"}
    agent._last_flushed_db_idx = 0
    agent._memory_manager = None
    agent._cached_system_prompt = "old-system"
    agent._last_compression_summary_warning = None
    agent._last_aux_fallback_warning_key = None
    agent.quiet_mode = True
    agent.log_prefix = ""
    agent._todo_store = MagicMock()
    agent._todo_store.format_for_injection.return_value = ""
    agent.context_compressor = MagicMock()
    agent.context_compressor.compression_count = 1
    agent.context_compressor.last_prompt_tokens = 0
    agent.context_compressor.last_completion_tokens = 0
    agent.context_compressor._last_summary_validation_failed = False
    agent.context_compressor._last_summary_error = None
    agent.context_compressor._last_aux_model_failure_model = None
    agent.context_compressor._last_aux_model_failure_error = None
    agent._save_session_log = MagicMock()
    agent._emit_warning = MagicMock()
    agent._vprint = MagicMock()
    agent._invalidate_system_prompt = MagicMock()
    agent._build_system_prompt = MagicMock(return_value="new-system")
    agent._run_ledger = RunLedger(run_id=run_id, session_id=agent.session_id)
    return agent


def _source_messages() -> list[dict]:
    return [
        {"role": "user", "content": "Initial requirements"},
        {"role": "assistant", "content": "I will inspect."},
        {"role": "tool", "tool_call_id": "call-1", "content": "output"},
        {"role": "assistant", "content": "Found it."},
    ]


def _compressed_messages() -> list[dict]:
    return [
        {"role": "user", "content": "## Active State\nWorking summary"},
        {"role": "assistant", "content": "Ready to continue."},
    ]


def test_successful_compression_writes_capsule_and_appends_references(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    agent = _make_agent(tmp_path)
    agent._run_ledger.append_event("tool.started", tool_name="terminal", tool_call_id="call-1")
    agent._run_ledger.append_event("tool.finished", tool_name="terminal", tool_call_id="call-1", status="ok")
    compressed = _compressed_messages()
    agent.context_compressor.compress.return_value = compressed

    result, _prompt = agent._compress_context(_source_messages(), "system prompt", approx_tokens=10_000)

    capsule_dir = home / "runs" / "parent-session" / "capsules"
    capsules = list(capsule_dir.glob("*.json"))
    assert len(capsules) == 1

    summary = result[0]["content"]
    relative_capsule = "capsules/" + capsules[0].name
    assert "\n## Durable Context References\n" in summary
    assert "- Source event span: parent-session:evt_000000001..evt_000000002" in summary
    assert f"- State capsule: {relative_capsule}" in summary
    assert relative_capsule == "capsules/cap_000000002.json"


def test_capsule_regeneration_uses_deterministic_path(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    agent = _make_agent(tmp_path)
    agent._run_ledger.append_event("tool.started", tool_name="terminal", tool_call_id="call-1")
    agent._run_ledger.append_event("tool.finished", tool_name="terminal", tool_call_id="call-1", status="ok")

    first = agent._run_ledger.write_state_capsule(event_span=agent._run_ledger.current_event_span())
    second = agent._run_ledger.write_state_capsule(event_span={"start_seq": 1, "end_seq": 2})

    assert first["relative_path"] == "capsules/cap_000000002.json"
    assert second["relative_path"] == "capsules/cap_000000002.json"
    assert len(list((home / "runs" / "parent-session" / "capsules").glob("*.json"))) == 1


def test_validation_abort_writes_no_capsule_and_no_references(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    agent = _make_agent(tmp_path)
    original_messages = _source_messages()
    agent.context_compressor.compress.return_value = _compressed_messages()
    agent.context_compressor._last_summary_validation_failed = True
    agent.context_compressor._last_summary_error = "missing Active State"

    result, _prompt = agent._compress_context(original_messages, "system prompt", approx_tokens=10_000)

    assert result is original_messages
    assert not list((home / "runs" / "parent-session" / "capsules").glob("*.json"))
    assert "Durable Context References" not in "\n".join(str(msg.get("content", "")) for msg in result)
