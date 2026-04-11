"""Tests for MCP environment variable interpolation warnings."""
import os
from unittest.mock import patch

import pytest


class TestMcpEnvVarWarning:
    """_interpolate_value should warn when env vars resolve to empty strings."""

    def test_warns_on_missing_env_var(self, capsys):
        """Interpolating a missing env var should print a warning to stderr."""
        from hermes_cli.mcp_config import _interpolate_value

        # Ensure the variable is not set
        os.environ.pop("_HERMES_TEST_MISSING_VAR", None)

        result = _interpolate_value("Bearer ${_HERMES_TEST_MISSING_VAR}")

        # Should still return empty for the var (backward compatible)
        assert result == "Bearer "
        # But should warn the user on stderr
        captured = capsys.readouterr()
        assert "_HERMES_TEST_MISSING_VAR" in captured.err

    def test_no_warning_when_var_exists(self, capsys):
        """No warning should be emitted when the env var is set."""
        from hermes_cli.mcp_config import _interpolate_value

        os.environ["_HERMES_TEST_SET_VAR"] = "my-key-123"
        try:
            result = _interpolate_value("Bearer ${_HERMES_TEST_SET_VAR}")

            assert result == "Bearer my-key-123"
            captured = capsys.readouterr()
            assert "_HERMES_TEST_SET_VAR" not in captured.err
        finally:
            del os.environ["_HERMES_TEST_SET_VAR"]
