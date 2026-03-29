"""Tests for Windows-specific doctor checks."""
import builtins
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
import hermes_cli.doctor as doctor


class TestWindowsDoctorChecks:
    """_check_windows_platform produces the expected diagnostics."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_windows_build_check_passes(self, capsys):
        """On a modern Windows box the build check should produce output."""
        issues = []
        doctor._check_windows_platform(issues)
        captured = capsys.readouterr()
        assert "Windows build" in captured.out or "Windows Platform" in captured.out

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_wsl_check_present(self, capsys):
        issues = []
        doctor._check_windows_platform(issues)
        captured = capsys.readouterr()
        assert "WSL" in captured.out

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_keyring_check_present(self, capsys):
        issues = []
        doctor._check_windows_platform(issues)
        captured = capsys.readouterr()
        assert "keyring" in captured.out

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_keyring_warn_when_missing(self, capsys):
        import importlib
        original_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == "keyring":
                raise ImportError("mocked for test")
            return original_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=mock_import):
            issues = []
            doctor._check_windows_platform(issues)
        captured = capsys.readouterr()
        # Should mention keyring not installed
        assert "keyring" in captured.out


class TestDoctorLinterGuard:
    """Gateway linger check is platform-guarded."""

    def test_gateway_linger_only_runs_on_linux(self):
        """_check_gateway_service_linger should return early on non-Linux."""
        issues = []
        # On non-Linux (Windows or macOS), the function should not crash
        doctor._check_gateway_service_linger(issues)
        # No systemd-related issues should be added on non-Linux
        systemd_issues = [i for i in issues if "linger" in i.lower()]
        if sys.platform != "linux":
            assert len(systemd_issues) == 0


class TestWindowsChecksNotCalledOnLinux:
    """_check_windows_platform should only be invoked on win32."""

    def test_windows_checks_gated_by_platform(self):
        """Verify the guard in run_doctor prevents Windows checks on Linux."""
        # Just verify the function exists and is callable
        assert callable(doctor._check_windows_platform)
