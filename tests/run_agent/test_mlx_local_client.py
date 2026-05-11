from types import SimpleNamespace
from unittest.mock import Mock


def _minimal_agent(provider="custom"):
    from run_agent import AIAgent

    agent = object.__new__(AIAgent)
    agent.provider = provider
    agent.model = "/tmp/qwen-mlx"
    agent.base_url = "mlx://local"
    agent._client_log_context = lambda: "test-context"
    return agent


def test_create_openai_client_routes_mlx_local_before_url_validation():
    agent = _minimal_agent()
    client_kwargs = {
        "api_key": "no-key-required",
        "base_url": "mlx://local",
        "default_headers": {"x-test": "1"},
        "timeout": 123,
        "http_client": object(),  # OpenAI-specific; must not leak into local shim
    }

    client = agent._create_openai_client(
        client_kwargs,
        reason="unit-test",
        shared=False,
    )

    from agent.mlx_local_client import MLXLocalClient

    assert isinstance(client, MLXLocalClient)
    assert client.base_url == "mlx://local"
    assert client.api_key == "no-key-required"
    assert "http_client" not in client_kwargs or client_kwargs["http_client"] is not None


def test_provider_mlx_local_initializes_without_api_key_or_base_url():
    from agent.mlx_local_client import MLXLocalClient
    from run_agent import AIAgent

    agent = AIAgent(
        provider="mlx-local",
        model="/models/qwen",
        quiet_mode=True,
        skip_memory=True,
        enabled_toolsets=[],
    )

    assert agent.provider == "mlx-local"
    assert agent.base_url == "mlx://local"
    assert agent.api_key == "mlx-local"
    assert isinstance(agent.client, MLXLocalClient)


def test_mlx_local_client_non_streaming_invokes_mlx_generate(monkeypatch):
    from agent.mlx_local_client import MLXLocalClient

    completed = SimpleNamespace(stdout="local qwen ok\n", stderr="", returncode=0)
    run = Mock(return_value=completed)
    monkeypatch.setattr("agent.mlx_local_client.subprocess.run", run)

    client = MLXLocalClient(command="mlx_lm.generate")
    response = client.chat.completions.create(
        model="/models/qwen",
        messages=[
            {"role": "system", "content": "Be terse."},
            {"role": "user", "content": "Say ok"},
        ],
        max_tokens=20,
        temperature=0,
    )

    assert response.choices[0].message.content == "local qwen ok"
    assert response.choices[0].message.tool_calls is None
    assert response.choices[0].finish_reason == "stop"
    argv = run.call_args.args[0]
    assert argv[:2] == ["mlx_lm.generate", "--model"]
    assert "/models/qwen" in argv
    assert "--prompt" in argv
    assert argv[argv.index("--prompt") + 1] == "-"
    assert "Say ok" in run.call_args.kwargs["input"]
    assert "--max-tokens" in argv
    assert "--temp" in argv


def test_mlx_local_client_streaming_returns_openai_shaped_chunks(monkeypatch):
    from agent.mlx_local_client import MLXLocalClient

    monkeypatch.setattr(
        "agent.mlx_local_client.subprocess.run",
        Mock(return_value=SimpleNamespace(stdout="streamed ok", stderr="", returncode=0)),
    )

    client = MLXLocalClient(command="mlx_lm.generate")
    chunks = list(
        client.chat.completions.create(
            model="/models/qwen",
            messages=[{"role": "user", "content": "Say ok"}],
            stream=True,
            stream_options={"include_usage": True},
        )
    )

    assert chunks[0].choices[0].delta.content == "streamed ok"
    assert chunks[0].choices[0].finish_reason is None
    assert chunks[1].choices[0].finish_reason == "stop"
    assert chunks[2].choices == []
    assert chunks[2].usage.total_tokens == 0


def test_mlx_local_client_extracts_tool_call_blocks(monkeypatch):
    from agent.mlx_local_client import MLXLocalClient

    raw = '<tool_call>{"id":"call_1","type":"function","function":{"name":"read_file","arguments":"{\\"path\\":\\"/tmp/a\\"}"}}</tool_call>'
    monkeypatch.setattr(
        "agent.mlx_local_client.subprocess.run",
        Mock(return_value=SimpleNamespace(stdout=raw, stderr="", returncode=0)),
    )

    client = MLXLocalClient(command="mlx_lm.generate")
    response = client.chat.completions.create(
        model="/models/qwen",
        messages=[{"role": "user", "content": "Read file"}],
        tools=[{"type": "function", "function": {"name": "read_file", "parameters": {}}}],
    )

    tool_call = response.choices[0].message.tool_calls[0]
    assert response.choices[0].finish_reason == "tool_calls"
    assert response.choices[0].message.content is None
    assert tool_call.id == "call_1"
    assert tool_call.function.name == "read_file"
    assert tool_call.function.arguments == '{"path":"/tmp/a"}'


def test_mlx_local_client_preserves_tool_turn_context(monkeypatch):
    from agent.mlx_local_client import MLXLocalClient

    run = Mock(return_value=SimpleNamespace(stdout="done", stderr="", returncode=0))
    monkeypatch.setattr("agent.mlx_local_client.subprocess.run", run)

    client = MLXLocalClient(command="mlx_lm.generate")
    client.chat.completions.create(
        model="/models/qwen",
        messages=[
            {"role": "user", "content": "Read the file"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": '{"path":"/tmp/a"}'},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "name": "read_file",
                "content": "file contents",
            },
        ],
    )

    prompt = run.call_args.kwargs["input"]
    assert "<tool_call>" in prompt
    assert "read_file" in prompt
    assert "tool_call_id=call_1" in prompt
    assert "file contents" in prompt
