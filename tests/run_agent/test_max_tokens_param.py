from unittest.mock import patch

from run_agent import AIAgent


def _make_agent(*, provider: str, base_url: str, model: str) -> AIAgent:
    with patch("run_agent.OpenAI"), patch(
        "hermes_cli.config.load_config",
        return_value={"agent": {}},
    ):
        return AIAgent(
            api_key="test-key",
            provider=provider,
            base_url=base_url,
            model=model,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            enabled_toolsets=[],
            disabled_toolsets=[],
        )


def test_custom_gpt5_chat_completions_uses_max_completion_tokens():
    agent = _make_agent(
        provider="custom",
        base_url="http://127.0.0.1:2455/v1",
        model="gpt-5.5",
    )

    assert agent._max_tokens_param(65536) == {"max_completion_tokens": 65536}


def test_custom_gpt5_vendor_prefix_uses_max_completion_tokens():
    agent = _make_agent(
        provider="custom",
        base_url="http://127.0.0.1:2455/v1",
        model="openai/gpt-5.5",
    )

    assert agent._max_tokens_param(65536) == {"max_completion_tokens": 65536}


def test_custom_non_gpt5_keeps_max_tokens():
    agent = _make_agent(
        provider="custom",
        base_url="http://127.0.0.1:2455/v1",
        model="local/llama-3.3",
    )

    assert agent._max_tokens_param(8192) == {"max_tokens": 8192}
