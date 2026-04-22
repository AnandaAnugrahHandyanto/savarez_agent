import json
from unittest.mock import patch

import pytest

from agent.claude_cli_client import ClaudeCLIClient, _extract_tool_calls_from_text


def test_extract_tool_calls_from_text_parses_blocks_and_preserves_visible_text():
    text = (
        "Checking repo state now.\n"
        "<tool_call>{\"id\":\"call_1\",\"type\":\"function\",\"function\":{\"name\":\"terminal\",\"arguments\":\"{\\\"command\\\":\\\"git status --short\\\"}\"}}</tool_call>\n"
        "I will summarize after that."
    )

    tool_calls, visible_text = _extract_tool_calls_from_text(text)

    assert len(tool_calls) == 1
    assert tool_calls[0].function.name == "terminal"
    assert json.loads(tool_calls[0].function.arguments) == {"command": "git status --short"}
    assert "<tool_call>" not in visible_text
    assert "Checking repo state now." in visible_text
    assert "I will summarize after that." in visible_text


def test_run_prompt_raises_helpful_error_when_claude_cli_missing():
    client = ClaudeCLIClient(command="definitely-missing-claude")

    with patch("agent.claude_cli_client.shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="Could not find Claude CLI command 'definitely-missing-claude'"):
            client._run_prompt(
                "Reply with OK.",
                system_prompt="",
                model="claude-opus-4-7",
                effort=None,
                timeout_seconds=5.0,
            )


def test_bootstrap_hydration_runs_once_per_session_and_prompt_hash():
    client = ClaudeCLIClient(command="claude", strip_runtime=True)
    calls = []

    def fake_run_prompt(prompt_text, *, system_prompt, model, effort, timeout_seconds):
        calls.append(
            {
                "prompt_text": prompt_text,
                "system_prompt": system_prompt,
                "model": model,
                "effort": effort,
                "timeout_seconds": timeout_seconds,
            }
        )
        if prompt_text == "Reply with exactly OK.":
            client._last_session_id = "sess-123"
        return {"result": "OK"}

    client._run_prompt = fake_run_prompt

    with patch("agent.claude_cli_client._chunk_hydration_text", return_value=["chunk one", "chunk two"]):
        client._ensure_bootstrap_hydrated(
            model="claude-opus-4-7",
            full_system_prompt="System block",
            timeout_seconds=90.0,
        )
        assert len(calls) == 3
        assert calls[0]["prompt_text"] == "Reply with exactly OK."
        assert client._hydrated_session_id == "sess-123"

        client._ensure_bootstrap_hydrated(
            model="claude-opus-4-7",
            full_system_prompt="System block",
            timeout_seconds=90.0,
        )
        assert len(calls) == 3

        client._ensure_bootstrap_hydrated(
            model="claude-opus-4-7",
            full_system_prompt="Different system block",
            timeout_seconds=90.0,
        )
        assert len(calls) == 5
        assert calls[-1]["prompt_text"].startswith("Internal Hermes context block 2/2")
