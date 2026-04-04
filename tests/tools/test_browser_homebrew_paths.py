"""Tests for macOS Homebrew PATH discovery in browser_tool.py."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

from tools.browser_tool import (
    _discover_homebrew_node_dirs,
    _find_agent_browser,
    _run_browser_command,
    _SANE_PATH,
)


def _norm_path_str(path) -> str:
    return os.fspath(path).replace("\\", "/")


class TestSanePath:
    """Verify _SANE_PATH includes Homebrew directories."""

    def test_includes_homebrew_bin(self):
        assert "/opt/homebrew/bin" in _SANE_PATH

    def test_includes_homebrew_sbin(self):
        assert "/opt/homebrew/sbin" in _SANE_PATH

    def test_includes_standard_dirs(self):
        assert "/usr/local/bin" in _SANE_PATH
        assert "/usr/bin" in _SANE_PATH
        assert "/bin" in _SANE_PATH


class TestDiscoverHomebrewNodeDirs:
    """Tests for _discover_homebrew_node_dirs()."""

    def test_returns_empty_when_no_homebrew(self):
        """Non-macOS systems without /opt/homebrew/opt should return empty."""
        with patch("os.path.isdir", return_value=False):
            assert _discover_homebrew_node_dirs() == []

    def test_finds_versioned_node_dirs(self):
        """Should discover node@20/bin, node@24/bin etc."""
        entries = ["node@20", "node@24", "openssl", "node", "python@3.12"]

        def mock_isdir(p):
            normalized = _norm_path_str(p)
            if normalized == "/opt/homebrew/opt":
                return True
            # node@20/bin and node@24/bin exist
            if normalized in (
                "/opt/homebrew/opt/node@20/bin",
                "/opt/homebrew/opt/node@24/bin",
            ):
                return True
            return False

        with patch("os.path.isdir", side_effect=mock_isdir), \
             patch("os.listdir", return_value=entries):
            result = _discover_homebrew_node_dirs()

        assert len(result) == 2
        normalized_result = [_norm_path_str(p) for p in result]
        assert "/opt/homebrew/opt/node@20/bin" in normalized_result
        assert "/opt/homebrew/opt/node@24/bin" in normalized_result

    def test_excludes_plain_node(self):
        """'node' (unversioned) should be excluded — covered by /opt/homebrew/bin."""
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["node"]):
            result = _discover_homebrew_node_dirs()
        assert result == []

    def test_handles_oserror_gracefully(self):
        """Should return empty list if listdir raises OSError."""
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", side_effect=OSError("Permission denied")):
            assert _discover_homebrew_node_dirs() == []


class TestFindAgentBrowser:
    """Tests for _find_agent_browser() Homebrew path search."""

    def test_finds_in_current_path(self):
        """Should return result from shutil.which if available on current PATH."""
        with patch("shutil.which", return_value="/usr/local/bin/agent-browser"):
            assert _find_agent_browser() == ["/usr/local/bin/agent-browser"]

    def test_finds_in_homebrew_bin(self):
        """Should search Homebrew dirs when not found on current PATH."""
        def mock_which(cmd, path=None):
            if path and "/opt/homebrew/bin" in path and cmd == "agent-browser":
                return "/opt/homebrew/bin/agent-browser"
            return None

        with patch("shutil.which", side_effect=mock_which), \
             patch("os.path.isdir", return_value=True), \
             patch(
                 "tools.browser_tool._discover_homebrew_node_dirs",
                 return_value=[],
             ):
            result = _find_agent_browser()
            assert result == ["/opt/homebrew/bin/agent-browser"]

    def test_finds_npx_in_homebrew(self):
        """Should find npx in Homebrew paths as a fallback."""
        def mock_which(cmd, path=None):
            if cmd == "agent-browser":
                return None
            if cmd == "npx":
                if path and "/opt/homebrew/bin" in path:
                    return "/opt/homebrew/bin/npx"
                return None
            return None

        # Mock Path.exists() to prevent the local node_modules check from matching
        original_path_exists = Path.exists

        def mock_path_exists(self):
            if "node_modules" in str(self) and "agent-browser" in str(self):
                return False
            return original_path_exists(self)

        with patch("shutil.which", side_effect=mock_which), \
             patch("os.path.isdir", return_value=True), \
             patch.object(Path, "exists", mock_path_exists), \
             patch(
                 "tools.browser_tool._discover_homebrew_node_dirs",
                 return_value=[],
             ):
            result = _find_agent_browser()
            assert result == ["/opt/homebrew/bin/npx", "agent-browser"]

    def test_preserves_spaced_windows_executable_path(self):
        """Executable paths with spaces must stay a single argv element."""
        spaced_path = r"C:\Program Files\nodejs\agent-browser.cmd"

        with patch("shutil.which", return_value=spaced_path):
            assert _find_agent_browser() == [spaced_path]

    def test_raises_when_not_found(self):
        """Should raise FileNotFoundError when nothing works."""
        original_path_exists = Path.exists

        def mock_path_exists(self):
            if "node_modules" in str(self) and "agent-browser" in str(self):
                return False
            return original_path_exists(self)

        with patch("shutil.which", return_value=None), \
             patch("os.path.isdir", return_value=False), \
             patch.object(Path, "exists", mock_path_exists), \
             patch(
                 "tools.browser_tool._discover_homebrew_node_dirs",
                 return_value=[],
             ):
            with pytest.raises(FileNotFoundError, match="agent-browser CLI not found"):
                _find_agent_browser()


class TestRunBrowserCommandPathConstruction:
    """Verify _run_browser_command() includes Homebrew node dirs in subprocess PATH."""

    def test_subprocess_path_includes_homebrew_node_dirs(self, tmp_path):
        """When _discover_homebrew_node_dirs returns dirs, they should appear
        in the subprocess env PATH passed to Popen."""
        captured_env = {}

        # Create a mock Popen that captures the env dict
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        captured_cmd = []

        def capture_popen(cmd, **kwargs):
            captured_cmd[:] = cmd
            captured_env.update(kwargs.get("env", {}))
            return mock_proc

        fake_session = {
            "session_name": "test-session",
            "session_id": "test-id",
            "cdp_url": None,
        }

        # Write fake JSON output to the stdout temp file
        fake_json = json.dumps({"success": True})
        stdout_file = tmp_path / "stdout"
        stdout_file.write_text(fake_json)

        fake_homebrew_dirs = [
            "/opt/homebrew/opt/node@24/bin",
            "/opt/homebrew/opt/node@20/bin",
        ]

        # We need os.path.isdir to return True for our fake dirs
        # but we also need real isdir for tmp_path operations
        real_isdir = os.path.isdir

        def selective_isdir(p):
            normalized = _norm_path_str(p)
            if normalized in fake_homebrew_dirs or normalized.startswith(_norm_path_str(tmp_path)):
                return True
            if "/opt/homebrew/" in normalized:
                return True  # _SANE_PATH dirs
            return real_isdir(p)

        with patch("tools.browser_tool._find_agent_browser", return_value=["/usr/local/bin/agent-browser"]), \
             patch("tools.browser_tool._get_session_info", return_value=fake_session), \
             patch("tools.browser_tool._socket_safe_tmpdir", return_value=str(tmp_path)), \
             patch("tools.browser_tool._discover_homebrew_node_dirs", return_value=fake_homebrew_dirs), \
             patch("pathlib.Path.home", return_value=Path("/home/test")), \
             patch("os.path.isdir", side_effect=selective_isdir), \
             patch("subprocess.Popen", side_effect=capture_popen), \
             patch("os.open", return_value=99), \
             patch("os.close"), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch.dict(os.environ, {"PATH": "/usr/bin:/bin", "HOME": "/home/test", "HERMES_HOME": "/home/test/.hermes"}, clear=True):
            # The function reads from temp files for stdout/stderr
            with patch("builtins.open", mock_open(read_data=fake_json)):
                _run_browser_command("test-task", "navigate", ["https://example.com"])

        # Verify Homebrew node dirs made it into the subprocess PATH
        result_path = _norm_path_str(captured_env.get("PATH", ""))
        assert "/opt/homebrew/opt/node@24/bin" in result_path
        assert "/opt/homebrew/opt/node@20/bin" in result_path
        assert "/opt/homebrew/bin" in result_path  # from _SANE_PATH
        assert captured_cmd[:4] == [
            "/usr/local/bin/agent-browser",
            "--session",
            "test-session",
            "--json",
        ]

    def test_subprocess_path_includes_sane_path_homebrew(self, tmp_path):
        """_SANE_PATH Homebrew entries should appear even without versioned node dirs."""
        captured_env = {}

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        captured_cmd = []

        def capture_popen(cmd, **kwargs):
            captured_cmd[:] = cmd
            captured_env.update(kwargs.get("env", {}))
            return mock_proc

        fake_session = {
            "session_name": "test-session",
            "session_id": "test-id",
            "cdp_url": None,
        }

        fake_json = json.dumps({"success": True})
        real_isdir = os.path.isdir

        def selective_isdir(p):
            normalized = _norm_path_str(p)
            if "/opt/homebrew/" in normalized:
                return True
            if normalized.startswith(_norm_path_str(tmp_path)):
                return True
            return real_isdir(p)

        with patch("tools.browser_tool._find_agent_browser", return_value=["/usr/local/bin/agent-browser"]), \
             patch("tools.browser_tool._get_session_info", return_value=fake_session), \
             patch("tools.browser_tool._socket_safe_tmpdir", return_value=str(tmp_path)), \
             patch("tools.browser_tool._discover_homebrew_node_dirs", return_value=[]), \
             patch("pathlib.Path.home", return_value=Path("/home/test")), \
             patch("os.path.isdir", side_effect=selective_isdir), \
             patch("subprocess.Popen", side_effect=capture_popen), \
             patch("os.open", return_value=99), \
             patch("os.close"), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch.dict(os.environ, {"PATH": "/usr/bin:/bin", "HOME": "/home/test", "HERMES_HOME": "/home/test/.hermes"}, clear=True):
            with patch("builtins.open", mock_open(read_data=fake_json)):
                _run_browser_command("test-task", "navigate", ["https://example.com"])

        result_path = _norm_path_str(captured_env.get("PATH", ""))
        assert "/opt/homebrew/bin" in result_path
        assert "/opt/homebrew/sbin" in result_path
        assert captured_cmd[:4] == [
            "/usr/local/bin/agent-browser",
            "--session",
            "test-session",
            "--json",
        ]

    def test_run_browser_command_preserves_spaced_windows_executable_path(self, tmp_path):
        """_run_browser_command must not split executable paths that contain spaces."""
        captured_cmd = []

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        def capture_popen(cmd, **kwargs):
            captured_cmd[:] = cmd
            return mock_proc

        fake_session = {
            "session_name": "test-session",
            "session_id": "test-id",
            "cdp_url": None,
        }

        fake_json = json.dumps({"success": True})
        spaced_path = r"C:\Program Files\nodejs\agent-browser.cmd"

        real_isdir = os.path.isdir

        def selective_isdir(p):
            if _norm_path_str(p).startswith(_norm_path_str(tmp_path)):
                return True
            return real_isdir(p)

        with patch("tools.browser_tool._find_agent_browser", return_value=[spaced_path]), \
             patch("tools.browser_tool._get_session_info", return_value=fake_session), \
             patch("tools.browser_tool._socket_safe_tmpdir", return_value=str(tmp_path)), \
             patch("tools.browser_tool._discover_homebrew_node_dirs", return_value=[]), \
             patch("pathlib.Path.home", return_value=Path("/home/test")), \
             patch("os.path.isdir", side_effect=selective_isdir), \
             patch("subprocess.Popen", side_effect=capture_popen), \
             patch("os.open", return_value=99), \
             patch("os.close"), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch.dict(os.environ, {"PATH": r"C:\Program Files\nodejs", "HOME": "/home/test", "HERMES_HOME": "/home/test/.hermes"}, clear=True):
            with patch("builtins.open", mock_open(read_data=fake_json)):
                _run_browser_command("test-task", "navigate", ["https://example.com"])

        assert captured_cmd[0] == spaced_path
        assert captured_cmd[1:] == [
            "--session",
            "test-session",
            "--json",
            "navigate",
            "https://example.com",
        ]
