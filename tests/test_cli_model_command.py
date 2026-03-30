"""Regression tests for the interactive CLI /model slash command."""

from unittest.mock import MagicMock, patch

from cli import HermesCLI


def _make_cli():
    cli_obj = HermesCLI.__new__(HermesCLI)
    cli_obj.config = {}
    cli_obj.console = MagicMock()
    cli_obj.agent = object()
    cli_obj.conversation_history = []
    cli_obj.session_id = "session-test"
    cli_obj._pending_input = MagicMock()
    cli_obj.model = "anthropic/claude-opus-4.6"
    cli_obj.provider = "openrouter"
    cli_obj.requested_provider = "auto"
    cli_obj.api_key = "test-key"
    cli_obj.base_url = "https://openrouter.ai/api/v1"
    cli_obj.api_mode = "chat_completions"
    cli_obj._active_agent_route_signature = ("anthropic/claude-opus-4.6", "openrouter")
    cli_obj._model_is_default = True
    return cli_obj


def test_process_command_dispatches_model_handler():
    cli_obj = _make_cli()

    with patch.object(cli_obj, "_handle_model_command") as handler:
        cli_obj.process_command("/model openai/gpt-5.4")

    handler.assert_called_once_with("/model openai/gpt-5.4")


def test_handle_model_command_shows_status_and_usage(capsys):
    cli_obj = _make_cli()

    cli_obj._handle_model_command("/model")

    output = capsys.readouterr().out
    assert "Current model: anthropic/claude-opus-4.6" in output
    assert "Provider: OpenRouter" in output
    assert "Usage: /model list" in output
    assert "Run `hermes model` for the full interactive picker." in output


def test_handle_model_command_list_shows_provider_listing():
    cli_obj = _make_cli()

    with patch.object(cli_obj, "_show_model_and_providers") as show_listing:
        cli_obj._handle_model_command("/model list")

    show_listing.assert_called_once()


def test_handle_model_command_switches_model_and_persists():
    cli_obj = _make_cli()

    class _Result:
        success = True
        new_model = "gpt-5.4"
        target_provider = "openai-codex"
        provider_label = "OpenAI Codex"
        base_url = "https://chatgpt.com/backend-api/codex"
        api_key = "codex-key"
        warning_message = ""

    with patch("hermes_cli.model_switch.switch_model", return_value=_Result()) as switch_mock, \
         patch("hermes_cli.auth._update_config_for_provider") as update_provider, \
         patch("hermes_cli.auth._save_model_choice") as save_model, \
         patch("hermes_cli.auth.deactivate_provider") as deactivate_provider, \
         patch.object(cli_obj, "_ensure_runtime_credentials", return_value=True) as ensure_runtime:
        cli_obj._handle_model_command("/model openai-codex:gpt-5.4")

    switch_mock.assert_called_once_with(
        "openai-codex:gpt-5.4",
        current_provider="openrouter",
        current_base_url="https://openrouter.ai/api/v1",
        current_api_key="test-key",
    )
    update_provider.assert_called_once_with("openai-codex", "https://chatgpt.com/backend-api/codex")
    save_model.assert_called_once_with("gpt-5.4")
    deactivate_provider.assert_not_called()
    ensure_runtime.assert_called_once()
    assert cli_obj.model == "gpt-5.4"
    assert cli_obj.requested_provider == "openai-codex"
    assert cli_obj.provider == "openai-codex"
    assert cli_obj.api_key == "codex-key"
    assert cli_obj.base_url == "https://chatgpt.com/backend-api/codex"
    assert cli_obj.agent is None
    assert cli_obj._active_agent_route_signature is None
    assert cli_obj._model_is_default is False
