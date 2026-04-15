"""Tests for the interactive CLI /model picker (provider → model drill-down)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class _FakeBuffer:
    def __init__(self, text="draft text"):
        self.text = text
        self.cursor_position = len(text)
        self.reset_calls = []

    def reset(self, append_to_history=False):
        self.reset_calls.append(append_to_history)
        self.text = ""
        self.cursor_position = 0


def _make_providers():
    return [
        {
            "slug": "openrouter",
            "name": "OpenRouter",
            "is_current": True,
            "is_user_defined": False,
            "models": ["anthropic/claude-opus-4.6", "openai/gpt-5.4"],
            "total_models": 2,
            "source": "built-in",
        },
        {
            "slug": "anthropic",
            "name": "Anthropic",
            "is_current": False,
            "is_user_defined": False,
            "models": ["claude-opus-4.6", "claude-sonnet-4.6"],
            "total_models": 2,
            "source": "built-in",
        },
        {
            "slug": "custom:my-ollama",
            "name": "My Ollama",
            "is_current": False,
            "is_user_defined": True,
            "models": ["llama3", "mistral"],
            "total_models": 2,
            "source": "user-config",
            "api_url": "http://localhost:11434/v1",
        },
    ]


def _make_picker_cli(picker_return_value):
    cli = MagicMock()
    cli._run_curses_picker = MagicMock(return_value=picker_return_value)
    cli._app = MagicMock()
    cli._status_bar_visible = True
    return cli


def _make_modal_cli():
    from cli import HermesCLI

    cli = HermesCLI.__new__(HermesCLI)
    cli.model = "gpt-5.4"
    cli.provider = "openrouter"
    cli.requested_provider = "openrouter"
    cli.base_url = ""
    cli.api_key = ""
    cli.api_mode = ""
    cli._explicit_api_key = ""
    cli._explicit_base_url = ""
    cli._pending_model_switch_note = None
    cli._model_picker_state = None
    cli._modal_input_snapshot = None
    cli._status_bar_visible = True
    cli._invalidate = MagicMock()
    cli._agent_running = False
    cli.agent = None
    cli.config = {}
    cli.console = MagicMock()
    cli._app = SimpleNamespace(
        current_buffer=_FakeBuffer(),
        invalidate=MagicMock(),
        _is_running=True,
    )
    return cli


def test_prompt_text_input_uses_run_in_terminal_when_app_active():
    from cli import HermesCLI

    cli = _make_modal_cli()

    with (
        patch("prompt_toolkit.application.run_in_terminal", side_effect=lambda fn: fn()) as run_mock,
        patch("builtins.input", return_value="manual-value"),
    ):
        result = HermesCLI._prompt_text_input(cli, "Enter value: ")

    assert result == "manual-value"
    run_mock.assert_called_once()
    assert cli._status_bar_visible is True


def test_resume_command_uses_run_in_terminal_for_interactive_picker_flow():
    from cli import HermesCLI

    cli = _make_modal_cli()
    cli.session_id = "current"
    cli._session_db = MagicMock()
    cli._session_db.list_sessions_rich.return_value = [
        {"id": "current", "title": "Current", "preview": "Current preview", "last_active": 0, "parent_session_id": None},
        {"id": "root", "title": "Checking Running Hermes Agent", "preview": "check running gateways", "last_active": 0, "parent_session_id": None},
        {"id": "child", "title": None, "preview": "compressed tail", "last_active": 0, "parent_session_id": "root"},
    ]
    cli._session_db.get_compression_continuation_chain.return_value = [
        {"id": "root", "title": "Checking Running Hermes Agent", "preview": "check running gateways", "last_active": 0, "parent_session_id": None},
        {"id": "child", "title": None, "preview": "compressed tail", "last_active": 0, "parent_session_id": "root"},
    ]
    cli._session_db.get_session.side_effect = lambda sid: {
        "root": {"id": "root", "title": "Checking Running Hermes Agent"},
        "child": {"id": "child", "title": None},
    }.get(sid)
    cli._session_db.get_messages_as_conversation.return_value = []
    cli._run_session_browse_picker = MagicMock(side_effect=["root", "child"])

    task = MagicMock()
    task.add_done_callback.side_effect = lambda cb: cb(task)

    with patch("prompt_toolkit.application.run_in_terminal", side_effect=lambda fn: (fn(), task)[1]) as run_mock:
        HermesCLI._handle_resume_command(cli, "/resume")

    assert cli.session_id == "child"
    run_mock.assert_called_once()
    assert cli._run_session_browse_picker.call_count == 2
    assert cli._status_bar_visible is True


def test_should_handle_model_command_inline_uses_command_name_resolution():
    from cli import HermesCLI

    cli = _make_modal_cli()

    with patch("hermes_cli.commands.resolve_command", return_value=SimpleNamespace(name="model")):
        assert HermesCLI._should_handle_model_command_inline(cli, "/model") is True

    with patch("hermes_cli.commands.resolve_command", return_value=SimpleNamespace(name="help")):
        assert HermesCLI._should_handle_model_command_inline(cli, "/model") is False

    assert HermesCLI._should_handle_model_command_inline(cli, "/model", has_images=True) is False


def test_should_handle_resume_command_inline_uses_command_name_resolution():
    from cli import HermesCLI

    cli = _make_modal_cli()

    with patch("hermes_cli.commands.resolve_command", return_value=SimpleNamespace(name="resume")):
        assert HermesCLI._should_handle_resume_command_inline(cli, "/resume") is True
        assert HermesCLI._should_handle_resume_command_inline(cli, "/r my-session --list") is True
        assert HermesCLI._should_handle_resume_command_inline(cli, "/resume my-session") is False
        assert HermesCLI._should_handle_resume_command_inline(cli, "/resume my-session --last") is False

    with patch("hermes_cli.commands.resolve_command", return_value=SimpleNamespace(name="help")):
        assert HermesCLI._should_handle_resume_command_inline(cli, "/resume") is False

    with patch("cli._cprint") as cprint_mock, patch(
        "hermes_cli.commands.resolve_command", return_value=SimpleNamespace(name="resume")
    ):
        assert HermesCLI._should_handle_resume_command_inline(cli, "/resume --last") is False
    cprint_mock.assert_not_called()

    assert HermesCLI._should_handle_resume_command_inline(cli, "/resume", has_images=True) is False


def test_process_command_model_without_args_opens_modal_picker_and_captures_draft():
    from cli import HermesCLI

    cli = _make_modal_cli()
    providers = _make_providers()

    with (
        patch("hermes_cli.model_switch.list_authenticated_providers", return_value=providers),
        patch("cli._cprint"),
    ):
        result = cli.process_command("/model")

    assert result is True
    assert cli._model_picker_state is not None
    assert cli._model_picker_state["stage"] == "provider"
    assert cli._model_picker_state["selected"] == 0
    assert cli._modal_input_snapshot == {"text": "draft text", "cursor_position": len("draft text")}
    assert cli._app.current_buffer.text == ""


def test_model_picker_provider_then_model_selection_applies_switch_result_and_restores_draft():
    from cli import HermesCLI

    cli = _make_modal_cli()
    providers = _make_providers()

    with (
        patch("hermes_cli.model_switch.list_authenticated_providers", return_value=providers),
        patch("cli._cprint"),
    ):
        assert cli.process_command("/model") is True

    cli._model_picker_state["selected"] = 1
    with patch("hermes_cli.models.provider_model_ids", return_value=["claude-opus-4.6", "claude-sonnet-4.6"]):
        HermesCLI._handle_model_picker_selection(cli)

    assert cli._model_picker_state["stage"] == "model"
    assert cli._model_picker_state["provider_data"]["slug"] == "anthropic"
    assert cli._model_picker_state["model_list"] == ["claude-opus-4.6", "claude-sonnet-4.6"]

    cli._model_picker_state["selected"] = 0
    switch_result = SimpleNamespace(
        success=True,
        error_message=None,
        new_model="claude-opus-4.6",
        target_provider="anthropic",
        api_key="",
        base_url="",
        api_mode="anthropic_messages",
        provider_label="Anthropic",
        model_info=None,
        warning_message=None,
        provider_changed=True,
    )

    with (
        patch("hermes_cli.model_switch.switch_model", return_value=switch_result) as switch_mock,
        patch("cli._cprint"),
    ):
        HermesCLI._handle_model_picker_selection(cli)

    assert cli._model_picker_state is None
    assert cli.model == "claude-opus-4.6"
    assert cli.provider == "anthropic"
    assert cli.requested_provider == "anthropic"
    assert cli._app.current_buffer.text == "draft text"
    switch_mock.assert_called_once()
    assert switch_mock.call_args.kwargs["explicit_provider"] == "anthropic"
