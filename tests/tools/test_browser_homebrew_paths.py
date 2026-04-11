"""Tests for macOS Homebrew PATH discovery in browser_tool.py."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

from tools.browser_tool import (
    _build_browser_cmd_prefix,
    _discover_homebrew_node_dirs,
    _find_agent_browser,
    _run_browser_command,
    _SANE_PATH,
    check_browser_requirements,
)


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
        expected_dirs = {
            os.path.join("/opt/homebrew/opt", "node@20", "bin"),
            os.path.join("/opt/homebrew/opt", "node@24", "bin"),
        }

        def mock_isdir(p):
            if p == "/opt/homebrew/opt":
                return True
            # node@20/bin and node@24/bin exist
            if p in expected_dirs:
                return True
            return False

        with patch("os.path.isdir", side_effect=mock_isdir), \
             patch("os.listdir", return_value=entries):
            result = _discover_homebrew_node_dirs()

        assert len(result) == 2
        assert os.path.join("/opt/homebrew/opt", "node@20", "bin") in result
        assert os.path.join("/opt/homebrew/opt", "node@24", "bin") in result

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
            assert _find_agent_browser() == "/usr/local/bin/agent-browser"

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
            assert result == "/opt/homebrew/bin/agent-browser"

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
            assert result == "npx agent-browser"

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

    def test_windows_prefers_native_exe_before_npm_shims(self, monkeypatch):
        """Windows should prefer the packaged native exe over .cmd/.ps1 shims."""
        original_path_exists = Path.exists

        def mock_path_exists(self):
            path_str = str(self)
            if path_str.endswith("agent-browser-win32-x64.exe"):
                return True
            if path_str.endswith("agent-browser.cmd") or path_str.endswith("agent-browser.ps1"):
                return True
            if "node_modules" in path_str and "agent-browser" in path_str:
                return False
            return original_path_exists(self)

        monkeypatch.setattr("tools.browser_tool.os.name", "nt")

        with patch("shutil.which", return_value=None), \
             patch("os.path.isdir", return_value=False), \
             patch.object(Path, "exists", mock_path_exists), \
             patch(
                 "tools.browser_tool._discover_homebrew_node_dirs",
                 return_value=[],
             ):
            result = _find_agent_browser()
            assert result.endswith("node_modules\\agent-browser\\bin\\agent-browser-win32-x64.exe")


class TestBrowserRequirements:
    def test_termux_requires_real_agent_browser_install_not_npx_fallback(self, monkeypatch):
        monkeypatch.setenv("TERMUX_VERSION", "0.118.3")
        monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
        monkeypatch.setattr("tools.browser_tool._is_camofox_mode", lambda: False)
        monkeypatch.setattr("tools.browser_tool._get_cloud_provider", lambda: None)
        monkeypatch.setattr("tools.browser_tool._find_agent_browser", lambda: "npx agent-browser")

        assert check_browser_requirements() is False


class TestRunBrowserCommandTermuxFallback:
    def test_termux_local_mode_rejects_bare_npx_fallback(self, monkeypatch):
        monkeypatch.setenv("TERMUX_VERSION", "0.118.3")
        monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
        monkeypatch.setattr("tools.browser_tool._find_agent_browser", lambda: "npx agent-browser")
        monkeypatch.setattr("tools.browser_tool._get_cloud_provider", lambda: None)

        result = _run_browser_command("task-1", "navigate", ["https://example.com"])

        assert result["success"] is False
        assert "bare npx fallback" in result["error"]
        assert "agent-browser install" in result["error"]


class TestRunBrowserCommandPathConstruction:
    """Verify _run_browser_command() includes Homebrew node dirs in subprocess PATH."""

    def test_build_browser_cmd_prefix_keeps_npx_fallback_split(self):
        assert _build_browser_cmd_prefix("npx agent-browser") == ["npx", "agent-browser"]

    def test_build_browser_cmd_prefix_wraps_windows_cmd(self, monkeypatch):
        monkeypatch.setattr("tools.browser_tool.os.name", "nt")
        result = _build_browser_cmd_prefix(r"C:\\repo\\node_modules\\.bin\\agent-browser.cmd")
        assert result == [
            "cmd.exe",
            "/d",
            "/s",
            "/c",
            r"C:\\repo\\node_modules\\.bin\\agent-browser.cmd",
        ]

    def test_build_browser_cmd_prefix_wraps_windows_powershell_script(self, monkeypatch):
        monkeypatch.setattr("tools.browser_tool.os.name", "nt")
        result = _build_browser_cmd_prefix(r"C:\\repo\\node_modules\\.bin\\agent-browser.ps1")
        assert result == [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            r"C:\\repo\\node_modules\\.bin\\agent-browser.ps1",
        ]

    def test_build_browser_cmd_prefix_keeps_executable_path_with_spaces(self):
        browser_path = "/Users/test/Library/Application Support/hermes/node_modules/.bin/agent-browser"
        assert _build_browser_cmd_prefix(browser_path) == [browser_path]

    def test_subprocess_preserves_executable_path_with_spaces(self, tmp_path):
        """A local agent-browser path containing spaces must stay one argv entry."""
        captured_cmd = None

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        def capture_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return mock_proc

        fake_session = {
            "session_name": "test-session",
            "session_id": "test-id",
            "cdp_url": None,
        }
        fake_json = json.dumps({"success": True})
        browser_path = "/Users/test/Library/Application Support/hermes/node_modules/.bin/agent-browser"
        hermes_home = str(tmp_path / "hermes-home")

        with patch("tools.browser_tool._find_agent_browser", return_value=browser_path), \
             patch("tools.browser_tool._get_session_info", return_value=fake_session), \
             patch("tools.browser_tool._socket_safe_tmpdir", return_value=str(tmp_path)), \
             patch("tools.browser_tool._discover_homebrew_node_dirs", return_value=[]), \
             patch("hermes_constants.Path.home", return_value=tmp_path), \
             patch("subprocess.Popen", side_effect=capture_popen), \
             patch("os.open", return_value=99), \
             patch("os.close"), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch.dict(
                 os.environ,
                 {
                     "PATH": "/usr/bin:/bin",
                     "HOME": "/home/test",
                     "HERMES_HOME": hermes_home,
                 },
                 clear=True,
             ):
            with patch("builtins.open", mock_open(read_data=fake_json)):
                _run_browser_command("test-task", "navigate", ["https://example.com"])

        assert captured_cmd is not None
        assert captured_cmd[0] == browser_path
        assert captured_cmd[1:5] == [
            "--session",
            "test-session",
            "--json",
            "navigate",
        ]

    def test_subprocess_wraps_windows_cmd_launcher(self, tmp_path, monkeypatch):
        captured_cmd = None

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        def capture_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return mock_proc

        fake_session = {
            "session_name": "test-session",
            "session_id": "test-id",
            "cdp_url": None,
        }
        fake_json = json.dumps({"success": True})
        hermes_home = str(tmp_path / "hermes-home")
        browser_path = r"C:\\repo\\node_modules\\.bin\\agent-browser.cmd"

        monkeypatch.setattr("tools.browser_tool.os.name", "nt")

        with patch("tools.browser_tool._find_agent_browser", return_value=browser_path), \
             patch("tools.browser_tool._get_session_info", return_value=fake_session), \
             patch("tools.browser_tool._socket_safe_tmpdir", return_value=str(tmp_path)), \
             patch("tools.browser_tool._discover_homebrew_node_dirs", return_value=[]), \
             patch("hermes_constants.Path.home", return_value=tmp_path), \
             patch("subprocess.Popen", side_effect=capture_popen), \
             patch("os.open", return_value=99), \
             patch("os.close"), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch.dict(
                 os.environ,
                 {
                     "PATH": r"C:\\Windows\\System32;C:\\Program Files\\nodejs",
                     "HOME": r"C:\\Users\\test",
                     "HERMES_HOME": hermes_home,
                 },
                 clear=True,
             ):
            with patch("builtins.open", mock_open(read_data=fake_json)):
                _run_browser_command("test-task", "navigate", ["https://example.com"])

        assert captured_cmd is not None
        assert captured_cmd[:5] == [
            "cmd.exe",
            "/d",
            "/s",
            "/c",
            browser_path,
        ]
        assert captured_cmd[5:9] == [
            "--session",
            "test-session",
            "--json",
            "navigate",
        ]

    def test_subprocess_wraps_windows_powershell_launcher(self, tmp_path, monkeypatch):
        captured_cmd = None

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        def capture_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return mock_proc

        fake_session = {
            "session_name": "test-session",
            "session_id": "test-id",
            "cdp_url": None,
        }
        fake_json = json.dumps({"success": True})
        hermes_home = str(tmp_path / "hermes-home")
        browser_path = r"C:\\repo\\node_modules\\.bin\\agent-browser.ps1"

        monkeypatch.setattr("tools.browser_tool.os.name", "nt")

        with patch("tools.browser_tool._find_agent_browser", return_value=browser_path), \
             patch("tools.browser_tool._get_session_info", return_value=fake_session), \
             patch("tools.browser_tool._socket_safe_tmpdir", return_value=str(tmp_path)), \
             patch("tools.browser_tool._discover_homebrew_node_dirs", return_value=[]), \
             patch("hermes_constants.Path.home", return_value=tmp_path), \
             patch("subprocess.Popen", side_effect=capture_popen), \
             patch("os.open", return_value=99), \
             patch("os.close"), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch.dict(
                 os.environ,
                 {
                     "PATH": r"C:\\Windows\\System32;C:\\Program Files\\nodejs",
                     "HOME": r"C:\\Users\\test",
                     "HERMES_HOME": hermes_home,
                 },
                 clear=True,
             ):
            with patch("builtins.open", mock_open(read_data=fake_json)):
                _run_browser_command("test-task", "navigate", ["https://example.com"])

        assert captured_cmd is not None
        assert captured_cmd[:6] == [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            browser_path,
        ]
        assert captured_cmd[6:10] == [
            "--session",
            "test-session",
            "--json",
            "navigate",
        ]

    def test_subprocess_splits_npx_fallback_into_command_and_package(self, tmp_path):
        """The synthetic npx fallback should still expand into separate argv items."""
        captured_cmd = None

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        def capture_popen(cmd, **kwargs):
            nonlocal captured_cmd
            captured_cmd = cmd
            return mock_proc

        fake_session = {
            "session_name": "test-session",
            "session_id": "test-id",
            "cdp_url": None,
        }
        fake_json = json.dumps({"success": True})
        hermes_home = str(tmp_path / "hermes-home")

        with patch("tools.browser_tool._find_agent_browser", return_value="npx agent-browser"), \
             patch("tools.browser_tool._get_session_info", return_value=fake_session), \
             patch("tools.browser_tool._socket_safe_tmpdir", return_value=str(tmp_path)), \
             patch("tools.browser_tool._discover_homebrew_node_dirs", return_value=[]), \
             patch("hermes_constants.Path.home", return_value=tmp_path), \
             patch("subprocess.Popen", side_effect=capture_popen), \
             patch("os.open", return_value=99), \
             patch("os.close"), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch.dict(
                 os.environ,
                 {
                     "PATH": "/usr/bin:/bin",
                     "HOME": "/home/test",
                     "HERMES_HOME": hermes_home,
                 },
                 clear=True,
             ):
            with patch("builtins.open", mock_open(read_data=fake_json)):
                _run_browser_command("test-task", "navigate", ["https://example.com"])

        assert captured_cmd is not None
        assert captured_cmd[:2] == ["npx", "agent-browser"]
        assert captured_cmd[2:6] == [
            "--session",
            "test-session",
            "--json",
            "navigate",
        ]

    def test_subprocess_path_includes_homebrew_node_dirs(self, tmp_path):
        """When _discover_homebrew_node_dirs returns dirs, they should appear
        in the subprocess env PATH passed to Popen."""
        captured_env = {}

        # Create a mock Popen that captures the env dict
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        def capture_popen(cmd, **kwargs):
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
        sane_dirs = ["/opt/homebrew/bin", "/opt/homebrew/sbin"]
        hermes_home = str(tmp_path / ".hermes")

        # We need os.path.isdir to return True for our fake dirs
        # but we also need real isdir for tmp_path operations
        real_isdir = os.path.isdir

        def selective_isdir(p):
            if p in fake_homebrew_dirs or p in sane_dirs or p.startswith(str(tmp_path)):
                return True
            return real_isdir(p)

        with patch("tools.browser_tool._find_agent_browser", return_value="/usr/local/bin/agent-browser"), \
             patch("tools.browser_tool._get_session_info", return_value=fake_session), \
             patch("tools.browser_tool._socket_safe_tmpdir", return_value=str(tmp_path)), \
             patch("tools.browser_tool._discover_homebrew_node_dirs", return_value=fake_homebrew_dirs), \
             patch("tools.browser_tool._iter_sane_path_dirs", return_value=sane_dirs), \
             patch("os.path.isdir", side_effect=selective_isdir), \
             patch("subprocess.Popen", side_effect=capture_popen), \
             patch("os.open", return_value=99), \
             patch("os.close"), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch.dict(
                 os.environ,
                 {
                     "PATH": "/usr/bin:/bin",
                     "HOME": "/home/test",
                     "HERMES_HOME": hermes_home,
                 },
                 clear=True,
             ):
            # The function reads from temp files for stdout/stderr
            with patch("builtins.open", mock_open(read_data=fake_json)):
                _run_browser_command("test-task", "navigate", ["https://example.com"])

        # Verify Homebrew node dirs made it into the subprocess PATH
        result_path = captured_env.get("PATH", "")
        assert "/opt/homebrew/opt/node@24/bin" in result_path
        assert "/opt/homebrew/opt/node@20/bin" in result_path
        assert "/opt/homebrew/bin" in result_path  # from _SANE_PATH

    def test_subprocess_path_includes_sane_path_homebrew(self, tmp_path):
        """_SANE_PATH Homebrew entries should appear even without versioned node dirs."""
        captured_env = {}

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        def capture_popen(cmd, **kwargs):
            captured_env.update(kwargs.get("env", {}))
            return mock_proc

        fake_session = {
            "session_name": "test-session",
            "session_id": "test-id",
            "cdp_url": None,
        }

        fake_json = json.dumps({"success": True})
        real_isdir = os.path.isdir
        sane_dirs = ["/opt/homebrew/bin", "/opt/homebrew/sbin"]
        hermes_home = str(tmp_path / ".hermes")

        def selective_isdir(p):
            if p in sane_dirs or p.startswith(str(tmp_path)):
                return True
            return real_isdir(p)

        with patch("tools.browser_tool._find_agent_browser", return_value="/usr/local/bin/agent-browser"), \
             patch("tools.browser_tool._get_session_info", return_value=fake_session), \
             patch("tools.browser_tool._socket_safe_tmpdir", return_value=str(tmp_path)), \
             patch("tools.browser_tool._discover_homebrew_node_dirs", return_value=[]), \
             patch("tools.browser_tool._iter_sane_path_dirs", return_value=sane_dirs), \
             patch("os.path.isdir", side_effect=selective_isdir), \
             patch("subprocess.Popen", side_effect=capture_popen), \
             patch("os.open", return_value=99), \
             patch("os.close"), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch.dict(
                 os.environ,
                 {
                     "PATH": "/usr/bin:/bin",
                     "HOME": "/home/test",
                     "HERMES_HOME": hermes_home,
                 },
                 clear=True,
             ):
            with patch("builtins.open", mock_open(read_data=fake_json)):
                _run_browser_command("test-task", "navigate", ["https://example.com"])

        result_path = captured_env.get("PATH", "")
        assert "/opt/homebrew/bin" in result_path
        assert "/opt/homebrew/sbin" in result_path
