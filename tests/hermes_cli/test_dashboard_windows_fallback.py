"""Tests for _find_stale_dashboard_pids Windows wmic fallback (#44567).

Verifies that when wmic is missing or fails on modern Windows 11,
the function falls back to PowerShell's Get-CimInstance to discover
running hermes dashboard processes.
"""
from __future__ import annotations

import subprocess
import sys
from unittest.mock import patch, MagicMock

import pytest


class TestFindStaleDashboardPidsWindowsFallback:
    """Windows-specific: wmic → PowerShell Get-CimInstance fallback."""

    @staticmethod
    def _wmic_output(pid: int = 1234, cmd: str = "hermes dashboard") -> str:
        return f"CommandLine={cmd}\nProcessId={pid}\n\n"

    @staticmethod
    def _powershell_output(pid: int = 1234, cmd: str = "hermes dashboard") -> str:
        return f"CommandLine={cmd}\nProcessId={pid}\n\n"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_wmic_missing_falls_back_to_powershell(self):
        """When wmic is not found, must use PowerShell Get-CimInstance."""
        from hermes_cli.main import _find_stale_dashboard_pids

        ps_output = self._powershell_output(5678, "python hermes dashboard")

        with (
            patch("shutil.which", side_effect=lambda cmd: {
                "wmic": None,
                "powershell": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            }.get(cmd)),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(
                returncode=0, stdout=ps_output
            )
            pids = _find_stale_dashboard_pids()

        assert 5678 in pids
        # Verify PowerShell was called, not wmic
        call_args = mock_run.call_args[0][0]
        assert "powershell" in call_args[0].lower() or "pwsh" in call_args[0].lower()

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_wmic_failure_falls_back_to_powershell(self):
        """When wmic returns non-zero exit, must fall back to PowerShell."""
        from hermes_cli.main import _find_stale_dashboard_pids

        ps_output = self._powershell_output(9999, "hermes_cli.main dashboard")

        with (
            patch("shutil.which", return_value="C:\\Windows\\System32\\wbem\\WMIC.exe"),
            patch("subprocess.run") as mock_run,
        ):
            # First call (wmic) fails, second call (PowerShell) succeeds
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout=""),  # wmic fails
                MagicMock(returncode=0, stdout=ps_output),  # PowerShell succeeds
            ]
            pids = _find_stale_dashboard_pids()

        assert 9999 in pids
        assert mock_run.call_count == 2

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_both_wmic_and_powershell_missing_returns_empty(self):
        """When neither wmic nor PowerShell is available, return empty."""
        from hermes_cli.main import _find_stale_dashboard_pids

        with patch("shutil.which", return_value=None):
            pids = _find_stale_dashboard_pids()

        assert pids == []

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_wmic_oserror_falls_back_to_powershell(self):
        """When wmic raises OSError, must fall back to PowerShell."""
        from hermes_cli.main import _find_stale_dashboard_pids

        ps_output = self._powershell_output(4321, "hermes dashboard --profile work")

        with (
            patch("shutil.which", side_effect=lambda cmd: {
                "wmic": "C:\\Windows\\System32\\wbem\\WMIC.exe",
                "powershell": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            }.get(cmd)),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = [
                OSError("The system cannot find the file specified"),
                MagicMock(returncode=0, stdout=ps_output),
            ]
            pids = _find_stale_dashboard_pids()

        assert 4321 in pids
