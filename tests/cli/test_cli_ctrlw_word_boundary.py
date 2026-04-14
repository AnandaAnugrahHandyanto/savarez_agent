"""Tests for configurable Ctrl+W word-boundary handling."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cli import HermesCLI


def _make_cli(mode: str):
    cli_obj = HermesCLI.__new__(HermesCLI)
    cli_obj.ctrlw_word_boundary = mode
    return cli_obj


class TestCtrlWWordBoundaryHelpers:
    def test_normalize_ctrlw_word_boundary_accepts_alphanumeric(self):
        assert HermesCLI._normalize_ctrlw_word_boundary("alphanumeric") == "alphanumeric"

    def test_normalize_ctrlw_word_boundary_defaults_to_whitespace(self):
        assert HermesCLI._normalize_ctrlw_word_boundary("bogus") == "whitespace"
        assert HermesCLI._normalize_ctrlw_word_boundary("") == "whitespace"
        assert HermesCLI._normalize_ctrlw_word_boundary(None) == "whitespace"

    def test_ctrlw_uses_whitespace_boundary_for_default_mode(self):
        cli_obj = _make_cli("whitespace")
        assert cli_obj._ctrlw_uses_whitespace_boundary() is True

    def test_ctrlw_uses_non_whitespace_boundary_for_alphanumeric_mode(self):
        cli_obj = _make_cli("alphanumeric")
        assert cli_obj._ctrlw_uses_whitespace_boundary() is False

    def test_handle_ctrl_w_dispatches_builtin_with_whitespace_mode(self):
        cli_obj = _make_cli("whitespace")
        fake_event = SimpleNamespace()
        handler = MagicMock()
        fake_binding = SimpleNamespace(handler=handler)

        with patch("prompt_toolkit.key_binding.bindings.named_commands.get_by_name", return_value=fake_binding) as mock_get:
            cli_obj._handle_ctrl_w(fake_event)

        mock_get.assert_called_once_with("unix-word-rubout")
        handler.assert_called_once_with(fake_event, WORD=True)

    def test_handle_ctrl_w_dispatches_builtin_with_alphanumeric_mode(self):
        cli_obj = _make_cli("alphanumeric")
        fake_event = SimpleNamespace()
        handler = MagicMock()
        fake_binding = SimpleNamespace(handler=handler)

        with patch("prompt_toolkit.key_binding.bindings.named_commands.get_by_name", return_value=fake_binding):
            cli_obj._handle_ctrl_w(fake_event)

        handler.assert_called_once_with(fake_event, WORD=False)
