import json
from types import SimpleNamespace

from agent.claude_code_cli_client import (
    ClaudeCodeCLIClient,
    _extract_progress_events,
    _format_messages_as_prompt,
)


def test_claude_code_cli_client_returns_chat_completion_shape(monkeypatch):
    client = ClaudeCodeCLIClient(command="claude")

    monkeypatch.setattr(
        client,
        "_iter_events",
        lambda prompt_text, *, model, timeout_seconds: iter(
            [
                {"type": "text", "text": "Claude says hi."},
                {
                    "type": "result",
                    "usage": SimpleNamespace(
                        prompt_tokens=12,
                        completion_tokens=5,
                        total_tokens=17,
                        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
                    ),
                    "output": None,
                },
            ]
        ),
    )

    response = client.chat.completions.create(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert response.model == "claude-sonnet-4-6"
    assert response.choices[0].message.content == "Claude says hi."
    assert response.choices[0].finish_reason == "stop"
    assert response.usage.total_tokens == 17


def test_claude_code_cli_client_stream_emits_text_then_usage(monkeypatch):
    client = ClaudeCodeCLIClient(command="claude")

    monkeypatch.setattr(
        client,
        "_iter_events",
        lambda prompt_text, *, model, timeout_seconds: iter(
            [
                {"type": "text", "text": "Hello"},
                {
                    "type": "result",
                    "usage": SimpleNamespace(
                        prompt_tokens=8,
                        completion_tokens=3,
                        total_tokens=11,
                        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
                    ),
                    "output": None,
                },
            ]
        ),
    )

    stream = client.chat.completions.create(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": "hello"}],
        stream=True,
    )
    chunks = list(stream)

    assert chunks[0].choices[0].delta.content == "Hello"
    assert chunks[1].choices[0].finish_reason == "stop"
    assert chunks[2].usage.total_tokens == 11


def test_claude_code_cli_client_uses_result_output_fallback(monkeypatch):
    client = ClaudeCodeCLIClient(command="claude")

    monkeypatch.setattr(
        client,
        "_iter_events",
        lambda prompt_text, *, model, timeout_seconds: iter(
            [
                {
                    "type": "result",
                    "usage": SimpleNamespace(
                        prompt_tokens=10,
                        completion_tokens=6,
                        total_tokens=16,
                        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
                    ),
                    "output": "Final answer after internal tool use.",
                },
            ]
        ),
    )

    response = client.chat.completions.create(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": "inspect the repo"}],
    )

    assert response.choices[0].message.content == "Final answer after internal tool use."
    assert response.usage.total_tokens == 16


def test_claude_code_cli_client_build_command_allows_multiple_turns(monkeypatch):
    monkeypatch.delenv("HERMES_CLAUDE_CODE_MAX_TURNS", raising=False)
    monkeypatch.delenv("HERMES_CLAUDE_CODE_ALLOWED_TOOLS", raising=False)
    monkeypatch.delenv("HERMES_CLAUDE_CODE_PERMISSION_MODE", raising=False)
    client = ClaudeCodeCLIClient(command="claude")

    command = client._build_command("hello", model="claude-sonnet-4-6")

    assert "--max-turns" in command
    assert command[command.index("--max-turns") + 1] == "10"
    assert "--allowedTools" in command
    assert command[command.index("--allowedTools") + 1] == "Read,Glob,Grep"
    assert "--permission-mode" in command
    assert command[command.index("--permission-mode") + 1] == "acceptEdits"


def test_claude_code_cli_client_derives_tools_from_enabled_toolsets(monkeypatch):
    monkeypatch.delenv("HERMES_CLAUDE_CODE_ALLOWED_TOOLS", raising=False)
    client = ClaudeCodeCLIClient(command="claude", enabled_toolsets=["file", "terminal"])

    command = client._build_command("hello", model="claude-sonnet-4-6")

    assert "--allowedTools" in command
    assert command[command.index("--allowedTools") + 1] == "Read,Glob,Grep,Edit,Write,Bash"


def test_claude_code_cli_client_build_command_respects_max_turns_env(monkeypatch):
    monkeypatch.setenv("HERMES_CLAUDE_CODE_MAX_TURNS", "12")
    client = ClaudeCodeCLIClient(command="claude")

    command = client._build_command("hello", model="claude-sonnet-4-6")

    assert "--max-turns" in command
    assert command[command.index("--max-turns") + 1] == "12"


def test_claude_code_cli_client_build_command_respects_tool_env(monkeypatch):
    monkeypatch.setenv("HERMES_CLAUDE_CODE_ALLOWED_TOOLS", "Read,Glob,Grep,Bash")
    monkeypatch.setenv("HERMES_CLAUDE_CODE_PERMISSION_MODE", "acceptEdits")
    client = ClaudeCodeCLIClient(command="claude")

    command = client._build_command("hello", model="claude-sonnet-4-6")

    assert "--allowedTools" in command
    assert command[command.index("--allowedTools") + 1] == "Read,Glob,Grep,Bash"
    assert "--permission-mode" in command
    assert command[command.index("--permission-mode") + 1] == "acceptEdits"


def test_claude_code_cli_client_raises_on_error_result(monkeypatch):
    client = ClaudeCodeCLIClient(command="claude")

    monkeypatch.setattr(
        client,
        "_iter_events",
        lambda prompt_text, *, model, timeout_seconds: iter(
            [
                {
                    "type": "result",
                    "usage": SimpleNamespace(
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
                    ),
                    "output": "Permission denied",
                    "is_error": True,
                },
            ]
        ),
    )

    try:
        client.chat.completions.create(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "inspect the repo"}],
        )
    except RuntimeError as exc:
        assert "Permission denied" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for Claude Code error result")


def test_extract_progress_events_reads_tool_and_thinking_blocks():
    events = _extract_progress_events(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "thinking", "thinking": "Need to inspect the repo."},
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "README.md"}},
                ]
            },
        }
    )

    assert events == [
        {
            "kind": "thinking",
            "tool_name": "_thinking",
            "preview": "Need to inspect the repo.",
            "message": "Need to inspect the repo.",
        },
        {
            "kind": "tool",
            "tool_name": "Read",
            "preview": "file_path",
            "message": "Claude Code used Read",
        },
    ]


def test_claude_code_cli_client_builds_hermes_mcp_bundle(monkeypatch):
    monkeypatch.delenv("HERMES_CLAUDE_CODE_HERMES_MCP_TOOLS", raising=False)
    monkeypatch.setattr(
        "agent.claude_code_cli_client._claude_mcp_bridge_available",
        lambda: True,
    )
    client = ClaudeCodeCLIClient(command="claude", session_id="sess_123")

    config_path, extra_tools, temp_dir = client._build_hermes_mcp_bundle(
        "search prior session context"
    )
    awareness = client._get_hermes_mcp_awareness()

    assert config_path is not None
    assert temp_dir is not None
    assert "mcp__hermes_native__session_search" in extra_tools
    assert "mcp__hermes_native__hermes_list_native_tools" in extra_tools
    assert "session_search" in awareness

    with open(config_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    server = payload["mcpServers"]["hermes_native"]
    assert server["env"]["HERMES_NATIVE_MCP_TOOLS"] == "session_search"
    assert server["env"]["HERMES_NATIVE_MCP_SESSION_ID"] == "sess_123"
    assert "HERMES_NATIVE_MCP_USER_TASK" in server["env"]


def test_claude_code_cli_client_build_command_merges_hermes_mcp_tools(monkeypatch):
    monkeypatch.delenv("HERMES_CLAUDE_CODE_ALLOWED_TOOLS", raising=False)
    client = ClaudeCodeCLIClient(command="claude")

    command = client._build_command(
        "hello",
        model="claude-sonnet-4-6",
        mcp_config_path="/tmp/.mcp.json",
        extra_allowed_tools=[
            "mcp__hermes_native__session_search",
            "mcp__hermes_native__hermes_list_native_tools",
        ],
    )

    assert "--allowedTools" in command
    assert command[command.index("--allowedTools") + 1] == (
        "Read,Glob,Grep,mcp__hermes_native__session_search,"
        "mcp__hermes_native__hermes_list_native_tools"
    )
    assert "--mcp-config" in command
    assert command[command.index("--mcp-config") + 1] == "/tmp/.mcp.json"


def test_format_messages_as_prompt_mentions_hermes_native_awareness():
    prompt = _format_messages_as_prompt(
        [{"role": "user", "content": "find my last session"}],
        model="claude-sonnet-4-6",
        hermes_tool_awareness=(
            "Hermes-native MCP tools are available in this run. "
            "Current bridged Hermes tools: hermes_list_native_tools, session_search."
        ),
    )

    assert "Hermes-native MCP tools are available in this run." in prompt
    assert "session_search" in prompt
