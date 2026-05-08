"""Tests for _resolve_system_service_hermes_home and _system_service_hermes_home_override.

Regression tests for issue #22035: ``sudo hermes gateway restart --system`` reads
gateway_state.json from root's HERMES_HOME instead of the service user's.
"""

import os
from unittest.mock import patch, MagicMock

import hermes_cli.gateway as gateway


class TestResolveSystemHermesHome:
    """_resolve_system_service_hermes_home parses HERMES_HOME from unit Environment."""

    def test_parses_hermes_home_from_environment(self):
        """Standard unit file Environment line is parsed correctly."""
        mock_props = {
            "Environment": '"HERMES_HOME=/home/alice/.hermes" "PATH=/usr/bin" '
            '"LOGNAME=alice"'
        }
        with patch.object(
            gateway, "_read_systemd_unit_properties", return_value=mock_props
        ):
            result = gateway._resolve_system_service_hermes_home(system=True)
        assert result == "/home/alice/.hermes"

    def test_returns_none_when_no_hermes_home(self):
        """Returns None when Environment has no HERMES_HOME entry."""
        mock_props = {"Environment": '"PATH=/usr/bin" "LOGNAME=alice"'}
        with patch.object(
            gateway, "_read_systemd_unit_properties", return_value=mock_props
        ):
            result = gateway._resolve_system_service_hermes_home(system=True)
        assert result is None

    def test_returns_none_when_environment_missing(self):
        """Returns None when Environment property is absent."""
        mock_props: dict[str, str] = {}
        with patch.object(
            gateway, "_read_systemd_unit_properties", return_value=mock_props
        ):
            result = gateway._resolve_system_service_hermes_home(system=True)
        assert result is None

    def test_handles_unquoted_values(self):
        """Handles systemctl output without quotes."""
        mock_props = {"Environment": "HERMES_HOME=/opt/hermes/.hermes PATH=/usr/bin"}
        with patch.object(
            gateway, "_read_systemd_unit_properties", return_value=mock_props
        ):
            result = gateway._resolve_system_service_hermes_home(system=True)
        assert result == "/opt/hermes/.hermes"

    def test_handles_hermes_home_at_end(self):
        """Handles HERMES_HOME as the last environment variable."""
        mock_props = {
            "Environment": '"PATH=/usr/bin" "LOGNAME=alice" '
            '"HERMES_HOME=/srv/hermes/.hermes"'
        }
        with patch.object(
            gateway, "_read_systemd_unit_properties", return_value=mock_props
        ):
            result = gateway._resolve_system_service_hermes_home(system=True)
        assert result == "/srv/hermes/.hermes"


class TestSystemServiceHermesHomeOverride:
    """_system_service_hermes_home_override context manager."""

    def test_sets_hermes_home_for_system_scope(self, monkeypatch):
        """Sets HERMES_HOME from unit file when system=True."""
        monkeypatch.delenv("HERMES_HOME", raising=False)
        mock_props = {
            "Environment": '"HERMES_HOME=/home/alice/.hermes" "PATH=/usr/bin"'
        }
        with patch.object(
            gateway, "_read_systemd_unit_properties", return_value=mock_props
        ):
            with gateway._system_service_hermes_home_override(system=True):
                assert os.environ["HERMES_HOME"] == "/home/alice/.hermes"
        # Restored after exit
        assert "HERMES_HOME" not in os.environ

    def test_restores_original_hermes_home(self, monkeypatch):
        """Restores the original HERMES_HOME value after exit."""
        monkeypatch.setenv("HERMES_HOME", "/original/path")
        mock_props = {
            "Environment": '"HERMES_HOME=/home/alice/.hermes" "PATH=/usr/bin"'
        }
        with patch.object(
            gateway, "_read_systemd_unit_properties", return_value=mock_props
        ):
            with gateway._system_service_hermes_home_override(system=True):
                assert os.environ["HERMES_HOME"] == "/home/alice/.hermes"
        assert os.environ["HERMES_HOME"] == "/original/path"

    def test_noop_for_user_scope(self, monkeypatch):
        """Does nothing when system=False."""
        monkeypatch.setenv("HERMES_HOME", "/original/path")
        with gateway._system_service_hermes_home_override(system=False):
            assert os.environ["HERMES_HOME"] == "/original/path"
        assert os.environ["HERMES_HOME"] == "/original/path"

    def test_noop_when_no_hermes_home_in_unit(self, monkeypatch):
        """Does nothing when unit file has no HERMES_HOME."""
        monkeypatch.setenv("HERMES_HOME", "/original/path")
        mock_props = {"Environment": '"PATH=/usr/bin"'}
        with patch.object(
            gateway, "_read_systemd_unit_properties", return_value=mock_props
        ):
            with gateway._system_service_hermes_home_override(system=True):
                assert os.environ["HERMES_HOME"] == "/original/path"
        assert os.environ["HERMES_HOME"] == "/original/path"

    def test_restores_on_exception(self, monkeypatch):
        """Restores HERMES_HOME even when exception occurs inside the block."""
        monkeypatch.setenv("HERMES_HOME", "/original/path")
        mock_props = {
            "Environment": '"HERMES_HOME=/home/alice/.hermes" "PATH=/usr/bin"'
        }
        with patch.object(
            gateway, "_read_systemd_unit_properties", return_value=mock_props
        ):
            try:
                with gateway._system_service_hermes_home_override(system=True):
                    assert os.environ["HERMES_HOME"] == "/home/alice/.hermes"
                    raise RuntimeError("test error")
            except RuntimeError:
                pass
        assert os.environ["HERMES_HOME"] == "/original/path"
