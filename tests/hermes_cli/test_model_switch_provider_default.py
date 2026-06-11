"""Regression tests for provider-only /model switches."""

from hermes_cli.model_switch import switch_model


_MOCK_VALIDATION = {
    "accepted": True,
    "persist": True,
    "recognized": True,
    "message": None,
}


def test_explicit_openai_codex_provider_without_model_uses_provider_default(monkeypatch):
    """`/model --provider openai-codex` should choose a Codex model.

    This path previously tried local endpoint model autodetection against
    chatgpt.com and failed with "No model detected" before consulting the
    provider's curated/default model list.
    """
    monkeypatch.setattr(
        "hermes_cli.models.get_default_model_for_provider",
        lambda provider: "gpt-5.4" if provider == "openai-codex" else "",
    )
    monkeypatch.setattr(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        lambda **kwargs: {
            "api_key": "codex-token",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_mode": "codex_app_server",
        },
    )
    monkeypatch.setattr(
        "hermes_cli.models.validate_requested_model",
        lambda *args, **kwargs: _MOCK_VALIDATION,
    )
    monkeypatch.setattr("hermes_cli.model_switch.get_model_info", lambda *args, **kwargs: None)
    monkeypatch.setattr("hermes_cli.model_switch.get_model_capabilities", lambda *args, **kwargs: None)

    result = switch_model(
        raw_input="",
        current_provider="openrouter",
        current_model="anthropic/claude-sonnet-4.6",
        explicit_provider="openai-codex",
    )

    assert result.success is True
    assert result.new_model == "gpt-5.4"
    assert result.target_provider == "openai-codex"
    assert result.api_mode == "codex_app_server"
