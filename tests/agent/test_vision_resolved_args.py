"""Test that call_llm vision path passes resolved provider args, not raw ones."""

from unittest.mock import patch, MagicMock


def test_vision_call_uses_resolved_provider_args():
    """Resolved provider/model/key/url from config must reach resolve_vision_provider_client."""
    from agent.auxiliary_client import call_llm

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="description"))],
        usage=MagicMock(prompt_tokens=10, completion_tokens=5),
    )

    with patch(
        "agent.auxiliary_client._resolve_task_provider_model",
        return_value=("my-resolved-provider", "my-resolved-model", "http://resolved", "resolved-key", "chat_completions"),
    ), patch(
        "agent.auxiliary_client.resolve_vision_provider_client",
        return_value=("my-resolved-provider", fake_client, "my-resolved-model"),
    ) as mock_vision:
        call_llm(
            "vision",
            provider="raw-provider",
            model="raw-model",
            base_url="http://raw",
            api_key="raw-key",
            messages=[{"role": "user", "content": "describe this"}],
        )

    # The resolved values must be passed, not the raw call_llm arguments
    call_args = mock_vision.call_args
    assert call_args.kwargs["provider"] == "my-resolved-provider"
    assert call_args.kwargs["model"] == "my-resolved-model"
    assert call_args.kwargs["base_url"] == "http://resolved"
    assert call_args.kwargs["api_key"] == "resolved-key"


def test_vision_base_url_override_keeps_explicit_provider():
    """Explicit provider should still drive credential resolution with custom base_url."""
    from agent.auxiliary_client import resolve_vision_provider_client

    fake_client = MagicMock()
    with patch(
        "agent.auxiliary_client._resolve_task_provider_model",
        return_value=(
            "zai",
            "glm-4v",
            "https://open.bigmodel.cn/api/paas/v4",
            None,
            "chat_completions",
        ),
    ), patch(
        "agent.auxiliary_client.resolve_provider_client",
        return_value=(fake_client, "glm-4v"),
    ) as mock_resolve:
        provider, client, model = resolve_vision_provider_client()

    assert provider == "zai"
    assert client is fake_client
    assert model == "glm-4v"
    assert mock_resolve.call_args.args[0] == "zai"
    assert mock_resolve.call_args.kwargs["explicit_base_url"] == "https://open.bigmodel.cn/api/paas/v4"


def test_resolve_task_provider_preserves_named_provider_with_base_url():
    """_resolve_task_provider_model must not replace a named provider with 'custom'
    when base_url is passed as an argument.  Otherwise downstream
    resolve_provider_client('custom', ...) only checks OPENAI_API_KEY and
    falls back to 'no-key-required', causing 401 for non-OpenAI providers.

    Regression test for: auxiliary vision with provider=xiaomi + base_url
    returning api_key='no-key-required' instead of resolving XIAOMI_API_KEY.
    """
    from agent.auxiliary_client import _resolve_task_provider_model

    provider, model, base_url, api_key, api_mode = _resolve_task_provider_model(
        task=None,
        provider="xiaomi",
        model="mimo-v2-omni",
        base_url="https://token-plan-ams.xiaomimimo.com/v1",
        api_key=None,
    )

    # Provider must be preserved as "xiaomi", NOT rewritten to "custom"
    assert provider == "xiaomi"
    assert model == "mimo-v2-omni"
    assert base_url == "https://token-plan-ams.xiaomimimo.com/v1"
    # api_key is None here — resolve_provider_client will look up XIAOMI_API_KEY


def test_resolve_task_provider_base_url_without_named_provider_defaults_to_custom():
    """When base_url is passed without a named provider, 'custom' is correct."""
    from agent.auxiliary_client import _resolve_task_provider_model

    provider, model, base_url, api_key, api_mode = _resolve_task_provider_model(
        task=None,
        provider=None,
        model="gpt-4o",
        base_url="http://localhost:8080/v1",
        api_key=None,
    )

    assert provider == "custom"
    assert base_url == "http://localhost:8080/v1"
