import json
from pathlib import Path


def test_write_turn_snapshot_creates_session_filterable_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    from agent.companion_audit import iter_session_audit_events, write_turn_snapshot

    event = write_turn_snapshot(
        session_id="session-123",
        profile="builderwrx-eddie",
        platform="telegram",
        user_message="Can Eddie ask Codex to look at Kestrel?",
        assistant_response=None,
        system_prompt="SYSTEM PROMPT TEXT",
        request_messages=[
            {"role": "system", "content": "SYSTEM PROMPT TEXT"},
            {"role": "user", "content": "hello\n\n<memory-context>known fact</memory-context>"},
        ],
        tools=[{"function": {"name": "clarify"}}, {"function": {"name": "memory"}}],
        enabled_toolsets=["safe", "memory"],
        memory_context="known fact",
        plugin_context="plugin fact",
        api_call_count=1,
        approx_input_tokens=42,
        request_char_count=100,
        model="gpt-test",
        provider="openai",
    )

    assert event["session_id"] == "session-123"
    assert event["profile"] == "builderwrx-eddie"
    assert event["context"]["system_prompt_sha256"]
    assert event["context"]["system_prompt_preview"] == "SYSTEM PROMPT TEXT"
    assert event["context"]["memory_context_present"] is True
    assert event["context"]["plugin_context_present"] is True
    assert event["tools"]["available"] == ["clarify", "memory"]
    assert event["tool_attempts"] == []

    audit_files = list((tmp_path / "audit").glob("*.jsonl"))
    assert len(audit_files) == 1
    line = audit_files[0].read_text(encoding="utf-8").strip()
    assert json.loads(line)["session_id"] == "session-123"

    events = list(iter_session_audit_events("session-123"))
    assert len(events) == 1
    assert events[0]["request"]["message_count"] == 2


def test_turn_snapshot_extracts_tool_attempts_from_conversation_history(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    from agent.companion_audit import write_turn_snapshot

    event = write_turn_snapshot(
        session_id="session-tools",
        profile="default",
        platform="telegram",
        user_message="do thing",
        assistant_response=None,
        system_prompt="system",
        request_messages=[
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {"name": "send_message", "arguments": '{"target":"telegram"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call-1", "name": "send_message", "content": '{"ok": false}'},
        ],
        tools=[],
        enabled_toolsets=[],
    )

    assert event["tool_attempts"] == [
        {
            "id": "call-1",
            "name": "send_message",
            "arguments": {"target": "telegram"},
            "result_preview": '{"ok": false}',
        }
    ]
