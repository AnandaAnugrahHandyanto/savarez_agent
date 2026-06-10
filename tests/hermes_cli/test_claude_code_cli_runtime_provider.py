from hermes_cli.runtime_provider import resolve_runtime_provider
from run_agent import AIAgent


def test_claude_code_cli_runtime_provider_is_local_bridge():
    runtime = resolve_runtime_provider(requested="claude-code-cli")

    assert runtime["provider"] == "claude-code-cli"
    assert runtime["api_mode"] == "claude_code_cli"
    assert runtime["base_url"] == "local://claude-code-cli"
    assert runtime["api_key"] == "no-key-required"


def test_claude_code_cli_agent_init_does_not_create_http_client():
    agent = AIAgent(
        model="claude-code",
        provider="claude-code-cli",
        api_mode="claude_code_cli",
        base_url="local://claude-code-cli",
        api_key="no-key-required",
        quiet_mode=True,
        enabled_toolsets=["safe"],
        skip_memory=True,
    )

    assert agent.api_mode == "claude_code_cli"
    assert agent.provider == "claude-code-cli"
    assert agent.client is None
    assert agent._client_kwargs == {}
