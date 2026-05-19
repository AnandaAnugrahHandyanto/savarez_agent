"""Tests for CLI /selectioncopy command."""

from unittest.mock import MagicMock, patch

from cli import HermesCLI


def _make_cli() -> HermesCLI:
    cli_obj = HermesCLI.__new__(HermesCLI)
    cli_obj.config = {}
    cli_obj.console = MagicMock()
    cli_obj.agent = None
    cli_obj.conversation_history = []
    cli_obj.session_id = "sess-selectioncopy-test"
    cli_obj._pending_input = MagicMock()
    cli_obj._app = None
    return cli_obj


def test_selectioncopy_toggle_without_arg():
    """Bare /selectioncopy should toggle the current value."""
    cli_obj = _make_cli()
    test_cfg = {"display": {"selectioncopy": True}}

    with patch("hermes_cli.config.load_config", return_value=test_cfg), \
         patch("cli.save_config_value", return_value=True) as mock_save, \
         patch("cli._cprint") as mock_print:
        result = cli_obj.process_command("/selectioncopy")

    assert result is True
    mock_save.assert_called_once_with("display.selectioncopy", False)
    assert any("OFF" in str(call) for call in mock_print.call_args_list)


def test_selectioncopy_on():
    cli_obj = _make_cli()
    test_cfg = {"display": {"selectioncopy": False}}

    with patch("hermes_cli.config.load_config", return_value=test_cfg), \
         patch("cli.save_config_value", return_value=True) as mock_save:
        cli_obj.process_command("/selectioncopy on")

    mock_save.assert_called_once_with("display.selectioncopy", True)


def test_selectioncopy_off():
    cli_obj = _make_cli()
    test_cfg = {"display": {"selectioncopy": True}}

    with patch("hermes_cli.config.load_config", return_value=test_cfg), \
         patch("cli.save_config_value", return_value=True) as mock_save:
        cli_obj.process_command("/selectioncopy off")

    mock_save.assert_called_once_with("display.selectioncopy", False)


def test_selectioncopy_status():
    cli_obj = _make_cli()
    test_cfg = {"display": {"selectioncopy": True}}

    with patch("hermes_cli.config.load_config", return_value=test_cfg), \
         patch("cli._cprint") as mock_print:
        cli_obj.process_command("/selectioncopy status")

    assert any("ON" in str(call) for call in mock_print.call_args_list)


def test_selectioncopy_rejects_invalid_arg():
    cli_obj = _make_cli()
    test_cfg = {"display": {"selectioncopy": True}}

    with patch("hermes_cli.config.load_config", return_value=test_cfg), \
         patch("cli._cprint") as mock_print:
        result = cli_obj.process_command("/selectioncopy maybe")

    assert result is True
    assert any("usage" in str(call).lower() for call in mock_print.call_args_list)
