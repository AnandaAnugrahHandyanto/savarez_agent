"""Tests for SSH bulk upload via tar pipe."""

import os
import shutil
import subprocess
import tarfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from tools.environments import ssh as ssh_env
from tools.environments.ssh import SSHEnvironment


@pytest.fixture
def mock_ssh_env(monkeypatch, tmp_path):
    """Create an SSHEnvironment with mocked SSH/subprocess calls."""
    monkeypatch.setattr(ssh_env.shutil, "which", lambda _: "/usr/bin/ssh")
    monkeypatch.setattr(ssh_env.SSHEnvironment, "_establish_connection", lambda self: None)
    monkeypatch.setattr(ssh_env.SSHEnvironment, "_detect_remote_home", lambda self: "/home/testuser")
    monkeypatch.setattr(ssh_env.SSHEnvironment, "_ensure_remote_dirs", lambda self: None)
    monkeypatch.setattr(ssh_env.SSHEnvironment, "init_session", lambda self: None)
    monkeypatch.setattr(
        ssh_env, "FileSyncManager",
        lambda **kw: type("M", (), {"sync": lambda self, **k: None})(),
    )
    env = SSHEnvironment(host="testhost", user="testuser")
    return env


class TestSSHBulkUpload:
    """Test _ssh_bulk_upload method."""

    def test_empty_files_is_noop(self, mock_ssh_env):
        """Empty file list should not spawn any subprocess."""
        with patch.object(subprocess, "run") as mock_run, \
             patch.object(subprocess, "Popen") as mock_popen:
            mock_ssh_env._ssh_bulk_upload([])
            mock_run.assert_not_called()
            mock_popen.assert_not_called()

    def test_staging_directory_mirrors_remote_paths(self, mock_ssh_env, tmp_path):
        """Files are staged in a temp dir matching their remote path layout."""
        # Create source files
        src_a = tmp_path / "a.txt"
        src_b = tmp_path / "b.txt"
        src_a.write_text("content_a")
        src_b.write_text("content_b")

        files = [
            (str(src_a), "/home/testuser/.hermes/credentials/a.txt"),
            (str(src_b), "/home/testuser/.hermes/skills/b.txt"),
        ]

        staged_files = {}

        original_popen = subprocess.Popen

        def capture_tar_popen(cmd, **kwargs):
            # Intercept the tar create command to inspect staging dir
            if cmd[0] == "tar" and "cf" in cmd:
                staging_dir = cmd[cmd.index("-C") + 1]
                for root, _dirs, fnames in os.walk(staging_dir):
                    for f in fnames:
                        full = os.path.join(root, f)
                        rel = os.path.relpath(full, staging_dir)
                        staged_files[rel] = Path(full).read_text()
            mock = MagicMock()
            mock.stdout = MagicMock()
            mock.stderr = MagicMock()
            mock.communicate.return_value = (b"", b"")
            mock.returncode = 0
            mock.wait.return_value = 0
            return mock

        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
            with patch.object(subprocess, "Popen", side_effect=capture_tar_popen):
                mock_ssh_env._ssh_bulk_upload(files)

        assert "home/testuser/.hermes/credentials/a.txt" in staged_files
        assert "home/testuser/.hermes/skills/b.txt" in staged_files
        assert staged_files["home/testuser/.hermes/credentials/a.txt"] == "content_a"
        assert staged_files["home/testuser/.hermes/skills/b.txt"] == "content_b"

    def test_mkdir_called_before_tar(self, mock_ssh_env, tmp_path):
        """Remote parent dirs are pre-created via SSH before tar transfer."""
        src = tmp_path / "f.txt"
        src.write_text("data")

        files = [
            (str(src), "/home/testuser/.hermes/credentials/f.txt"),
            (str(src), "/home/testuser/.hermes/skills/deep/nested/f.txt"),
        ]

        run_calls = []

        def mock_run(cmd, **kwargs):
            run_calls.append(cmd)
            return subprocess.CompletedProcess([], 0)

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        with patch.object(subprocess, "run", side_effect=mock_run):
            with patch.object(subprocess, "Popen", return_value=mock_proc):
                mock_ssh_env._ssh_bulk_upload(files)

        # First subprocess.run call should be the mkdir
        assert len(run_calls) == 1
        mkdir_cmd = " ".join(run_calls[0])
        assert "mkdir -p" in mkdir_cmd
        assert "/home/testuser/.hermes/credentials" in mkdir_cmd
        assert "/home/testuser/.hermes/skills/deep/nested" in mkdir_cmd

    def test_tar_pipe_structure(self, mock_ssh_env, tmp_path):
        """Verify tar create pipes into ssh tar extract."""
        src = tmp_path / "x.txt"
        src.write_text("hello")

        files = [(str(src), "/home/testuser/.hermes/x.txt")]

        popen_calls = []

        def mock_popen(cmd, **kwargs):
            popen_calls.append((cmd, kwargs))
            mock = MagicMock()
            mock.stdout = MagicMock()
            mock.communicate.return_value = (b"", b"")
            mock.returncode = 0
            mock.wait.return_value = 0
            return mock

        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
            with patch.object(subprocess, "Popen", side_effect=mock_popen):
                mock_ssh_env._ssh_bulk_upload(files)

        assert len(popen_calls) == 2

        # First: tar create
        tar_cmd = popen_calls[0][0]
        assert tar_cmd[0] == "tar"
        assert "cf" in tar_cmd
        assert "-C" in tar_cmd
        assert "stdout" in popen_calls[0][1] and popen_calls[0][1]["stdout"] == subprocess.PIPE

        # Second: ssh tar extract
        ssh_cmd = popen_calls[1][0]
        assert "ssh" in ssh_cmd[0]
        assert "tar" in ssh_cmd
        assert "xf" in ssh_cmd
        assert "-C" in ssh_cmd
        assert "/" in ssh_cmd

    def test_ssh_extract_failure_raises(self, mock_ssh_env, tmp_path):
        """Non-zero exit from remote tar should raise RuntimeError."""
        src = tmp_path / "f.txt"
        src.write_text("data")

        files = [(str(src), "/home/testuser/.hermes/f.txt")]

        def mock_popen(cmd, **kwargs):
            mock = MagicMock()
            mock.stdout = MagicMock()
            mock.communicate.return_value = (b"", b"tar: error writing output")
            mock.returncode = 1
            mock.wait.return_value = 0
            return mock

        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
            with patch.object(subprocess, "Popen", side_effect=mock_popen):
                with pytest.raises(RuntimeError, match="SSH bulk upload failed"):
                    mock_ssh_env._ssh_bulk_upload(files)

    def test_bulk_upload_wired_in_filesyncmanager(self, monkeypatch, tmp_path):
        """Verify SSHEnvironment passes bulk_upload_fn to FileSyncManager."""
        monkeypatch.setattr(ssh_env.shutil, "which", lambda _: "/usr/bin/ssh")
        monkeypatch.setattr(ssh_env.SSHEnvironment, "_establish_connection", lambda self: None)
        monkeypatch.setattr(ssh_env.SSHEnvironment, "_detect_remote_home", lambda self: "/home/u")
        monkeypatch.setattr(ssh_env.SSHEnvironment, "_ensure_remote_dirs", lambda self: None)
        monkeypatch.setattr(ssh_env.SSHEnvironment, "init_session", lambda self: None)

        captured_kwargs = {}

        def capture_fsm(**kwargs):
            captured_kwargs.update(kwargs)
            return type("M", (), {"sync": lambda self, **k: None})()

        monkeypatch.setattr(ssh_env, "FileSyncManager", capture_fsm)

        env = SSHEnvironment(host="h", user="u")
        assert "bulk_upload_fn" in captured_kwargs
        assert captured_kwargs["bulk_upload_fn"] is not None
        assert callable(captured_kwargs["bulk_upload_fn"])

    def test_control_socket_in_ssh_command(self, mock_ssh_env, tmp_path):
        """SSH commands in bulk upload use the ControlMaster socket."""
        src = tmp_path / "f.txt"
        src.write_text("data")
        files = [(str(src), "/home/testuser/.hermes/f.txt")]

        popen_cmds = []

        def mock_popen(cmd, **kwargs):
            popen_cmds.append(cmd)
            mock = MagicMock()
            mock.stdout = MagicMock()
            mock.communicate.return_value = (b"", b"")
            mock.returncode = 0
            mock.wait.return_value = 0
            return mock

        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
            with patch.object(subprocess, "Popen", side_effect=mock_popen):
                mock_ssh_env._ssh_bulk_upload(files)

        # The SSH extract command should include ControlPath
        ssh_cmd = " ".join(popen_cmds[1])
        assert "ControlPath=" in ssh_cmd
        assert "testuser@testhost" in ssh_cmd

    def test_mkdir_failure_raises(self, mock_ssh_env, tmp_path):
        """Non-zero exit from remote mkdir should raise RuntimeError."""
        src = tmp_path / "f.txt"
        src.write_text("data")
        files = [(str(src), "/home/testuser/.hermes/f.txt")]

        def mock_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                cmd, returncode=1, stderr="Permission denied"
            )

        with patch.object(subprocess, "run", side_effect=mock_run):
            with pytest.raises(RuntimeError, match="SSH mkdir failed"):
                mock_ssh_env._ssh_bulk_upload(files)
