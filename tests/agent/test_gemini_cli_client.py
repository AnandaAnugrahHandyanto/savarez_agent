import json
from types import SimpleNamespace
from unittest.mock import patch

from agent.gemini_cli_client import GeminiCLIClient


def test_gemini_cli_client_builds_openai_style_response_from_json_output():
    client = GeminiCLIClient(command="gemini", args=["--sandbox"])

    completed = SimpleNamespace(
        returncode=0,
        stdout=json.dumps(
            {
                "response": 'Done. <tool_call>{"id":"call_1","type":"function","function":{"name":"read_file","arguments":"{\\"path\\":\\"README.md\\"}"}}</tool_call>',
                "stats": {},
            }
        ),
        stderr="",
    )

    with patch("agent.gemini_cli_client.subprocess.run", return_value=completed) as mock_run:
        result = client.chat.completions.create(
            model="gemini-2.5-pro",
            messages=[{"role": "user", "content": "inspect the readme"}],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "description": "Read a file",
                        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
                    },
                }
            ],
        )

    assert result.model == "gemini-2.5-pro"
    assert result.choices[0].finish_reason == "tool_calls"
    assert result.choices[0].message.content == "Done."
    assert result.choices[0].message.tool_calls[0].function.name == "read_file"
    assert result.choices[0].message.tool_calls[0].function.arguments == '{"path":"README.md"}'
    command = mock_run.call_args.args[0]
    assert command[0] == "gemini"
    assert "--output-format" in command
    assert "json" in command
    assert "--model" in command
    prompt = mock_run.call_args.kwargs["input"]
    assert "Hermes requested model hint: gemini-2.5-pro" in prompt
    assert "User:\ninspect the readme" in prompt
    assert "read_file" in prompt


def test_gemini_cli_client_raises_when_process_fails():
    client = GeminiCLIClient(command="gemini")
    completed = SimpleNamespace(returncode=1, stdout="", stderr="oauth expired")

    with patch("agent.gemini_cli_client.subprocess.run", return_value=completed):
        try:
            client.chat.completions.create(
                model="gemini-2.5-pro",
                messages=[{"role": "user", "content": "hello"}],
            )
        except RuntimeError as exc:
            assert "oauth expired" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")


def test_resolve_provider_client_supports_gemini_cli(monkeypatch):
    from agent.auxiliary_client import resolve_provider_client

    monkeypatch.setattr(
        "hermes_cli.auth.resolve_external_process_provider_credentials",
        lambda provider_id: {
            "provider": provider_id,
            "api_key": "gemini-cli",
            "base_url": "cli://gemini",
            "command": "/usr/local/bin/gemini",
            "args": ["--sandbox"],
        },
    )

    client, model = resolve_provider_client("gemini-cli", model="gemini-2.5-pro", async_mode=False)

    assert isinstance(client, GeminiCLIClient)
    assert model == "gemini-2.5-pro"
    assert client._command == "/usr/local/bin/gemini"
    assert client._args == ["--sandbox"]
