"""Tests for low-level model.request runtime trace events."""

import json

from run_agent import AIAgent


def _make_agent() -> AIAgent:
    return AIAgent(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1?secret=do-not-log",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        session_id="model-trace-session",
    )


def test_emit_model_request_trace_logs_safe_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    agent = _make_agent()

    agent._emit_model_request_trace(
        api_kwargs={
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": "secret prompt"}],
            "tools": [{"type": "function", "function": {"name": "read_file"}}],
            "api_key": "sk-secret",
            "base_url": "https://openrouter.ai/api/v1?secret=do-not-log",
        },
        effective_task_id="task-123",
        api_call_count=2,
    )

    from agent.runtime_trace import read_runtime_events

    [event] = read_runtime_events(session_id="model-trace-session")
    assert event["event"] == "model.request"
    assert event["task_id"] == "task-123"
    assert event["data"] == {
        "provider": "openrouter",
        "model": "openai/gpt-4o-mini",
        "api_mode": agent.api_mode,
        "base_url_host": "openrouter.ai",
        "tool_count": 1,
        "api_call_count": 2,
    }

    raw_trace = (tmp_path / ".hermes" / "logs" / "runtime-trace.jsonl").read_text(encoding="utf-8")
    assert "secret prompt" not in raw_trace
    assert "sk-secret" not in raw_trace
    assert "do-not-log" not in raw_trace
    assert "messages" not in raw_trace
    assert '"base_url"' not in raw_trace


def test_emit_model_request_trace_is_best_effort(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    logs_path = hermes_home / "logs"
    logs_path.parent.mkdir(parents=True)
    logs_path.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    agent = _make_agent()

    # Must not raise even when trace storage is unavailable.
    agent._emit_model_request_trace(
        api_kwargs={"messages": [{"role": "user", "content": "hello"}]},
        effective_task_id="task-123",
        api_call_count=0,
    )
