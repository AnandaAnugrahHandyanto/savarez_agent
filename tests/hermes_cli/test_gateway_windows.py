import pytest
from unittest.mock import MagicMock, patch

from hermes_cli.gateway import _gateway_command_inner

class DummyArgs:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

@pytest.fixture
def mock_windows_env():
    with patch("hermes_cli.gateway.is_windows", return_value=True), \
         patch("hermes_cli.gateway.is_managed", return_value=False), \
         patch("hermes_cli.gateway.is_termux", return_value=False), \
         patch("hermes_cli.gateway.is_container", return_value=False), \
         patch("hermes_cli.gateway.supports_systemd_services", return_value=False), \
         patch("hermes_cli.gateway.is_macos", return_value=False), \
         patch("hermes_cli.gateway.is_wsl", return_value=False):
        yield

class TestWindowsGatewayDispatch:
    """Ensure that the windows_ functions are called when running gateway commands on Windows."""

    @patch("hermes_cli.gateway.windows_install")
    def test_install_calls_windows_install(self, mock_install, mock_windows_env):
        args = DummyArgs(gateway_command="install", force=False, system=False, run_as_user=None)
        _gateway_command_inner(args)
        mock_install.assert_called_once_with(force=False)

    @patch("hermes_cli.gateway.windows_uninstall")
    def test_uninstall_calls_windows_uninstall(self, mock_uninstall, mock_windows_env):
        args = DummyArgs(gateway_command="uninstall", system=False)
        _gateway_command_inner(args)
        mock_uninstall.assert_called_once()

    @patch("hermes_cli.gateway.windows_start")
    def test_start_calls_windows_start(self, mock_start, mock_windows_env):
        args = DummyArgs(gateway_command="start", system=False, all=False)
        _gateway_command_inner(args)
        mock_start.assert_called_once()

    @patch("hermes_cli.gateway.windows_stop")
    def test_stop_calls_windows_stop_and_kill(self, mock_stop, mock_windows_env):
        args = DummyArgs(gateway_command="stop", system=False, all=False)
        _gateway_command_inner(args)
        mock_stop.assert_called_once()

    @patch("hermes_cli.gateway.windows_status")
    @patch("hermes_cli.gateway.get_gateway_runtime_snapshot")
    def test_status_calls_windows_status(self, mock_snapshot, mock_status, mock_windows_env):
        args = DummyArgs(gateway_command="status", system=False, deep=False, full=False)
        _gateway_command_inner(args)
        mock_status.assert_called_once_with(False, False)

    @patch("hermes_cli.gateway.windows_stop")
    @patch("hermes_cli.gateway.windows_start")
    def test_restart_calls_stop_and_start(self, mock_start, mock_stop, mock_windows_env):
        args = DummyArgs(gateway_command="restart", system=False, all=False)
        _gateway_command_inner(args)
        mock_stop.assert_called_once()
        mock_start.assert_called_once()
