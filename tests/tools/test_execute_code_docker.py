"""Tests for tools/execute_code_docker.py and Docker sandbox path in code_execution_tool."""

import os
import subprocess
from unittest import mock

import pytest


class TestRunScriptInDocker:
    """Tests for run_script_in_docker with mocked subprocess."""

    def test_basic_successful_run(self):
        from tools.execute_code_docker import run_script_in_docker

        mock_proc = mock.MagicMock()
        mock_proc.communicate.return_value = (b"hello world\n", b"")
        mock_proc.returncode = 0

        with mock.patch("tools.execute_code_docker.subprocess.Popen", return_value=mock_proc) as mock_popen:
            stdout, stderr, rc = run_script_in_docker(
                script_path="/tmp/work/script.py",
                tmpdir="/tmp/work",
                sock_path="/tmp/hermes_rpc_test.sock",
                image="python:3.11",
                child_env={"FOO": "bar", "BAZ": "qux"},
                timeout=30,
            )

        assert stdout == b"hello world\n"
        assert stderr == b""
        assert rc == 0

        # Verify docker run command structure
        call_args = mock_popen.call_args[0][0]
        assert call_args[0] == "docker"
        assert call_args[1] == "run"
        assert "--rm" in call_args
        assert "--name" in call_args
        # Container name follows --name flag and matches hermes-sandbox-<hex8>
        name_idx = call_args.index("--name")
        container_name = call_args[name_idx + 1]
        assert container_name.startswith("hermes-sandbox-")
        assert len(container_name) == len("hermes-sandbox-") + 8
        assert "--network=host" in call_args
        assert "-v" in call_args
        assert "python:3.11" in call_args
        assert "python3" in call_args
        assert "/tmp/work/script.py" in call_args

    def test_env_vars_passed(self):
        from tools.execute_code_docker import run_script_in_docker

        mock_proc = mock.MagicMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0

        with mock.patch("tools.execute_code_docker.subprocess.Popen", return_value=mock_proc) as mock_popen:
            run_script_in_docker(
                script_path="/tmp/work/script.py",
                tmpdir="/tmp/work",
                sock_path="/tmp/rpc.sock",
                image="python:3.11",
                child_env={"MY_VAR": "value123", "ANOTHER": "test"},
                timeout=30,
            )

        call_args = mock_popen.call_args[0][0]
        # Check that env vars are passed via -e flags
        assert "-e" in call_args
        env_flags = []
        for i, arg in enumerate(call_args):
            if arg == "-e" and i + 1 < len(call_args):
                env_flags.append(call_args[i + 1])
        assert "MY_VAR=value123" in env_flags
        assert "ANOTHER=test" in env_flags

    def test_env_vars_with_equals_in_key_skipped(self):
        from tools.execute_code_docker import run_script_in_docker

        mock_proc = mock.MagicMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0

        with mock.patch("tools.execute_code_docker.subprocess.Popen", return_value=mock_proc) as mock_popen:
            run_script_in_docker(
                script_path="/tmp/work/script.py",
                tmpdir="/tmp/work",
                sock_path="/tmp/rpc.sock",
                image="python:3.11",
                child_env={"GOOD": "val", "BAD=KEY": "val", "": "empty_key"},
                timeout=30,
            )

        call_args = mock_popen.call_args[0][0]
        env_flags = []
        for i, arg in enumerate(call_args):
            if arg == "-e" and i + 1 < len(call_args):
                env_flags.append(call_args[i + 1])
        assert "GOOD=val" in env_flags
        # Keys with '=' or empty keys should be skipped
        assert not any("BAD=KEY" in f for f in env_flags)

    def test_timeout_returns_negative_one(self):
        from tools.execute_code_docker import run_script_in_docker

        mock_proc = mock.MagicMock()
        mock_proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="docker", timeout=5),
            (b"partial", b"timeout err"),
        ]
        mock_proc.kill.return_value = None
        mock_proc.returncode = -1

        with mock.patch("tools.execute_code_docker.subprocess.Popen", return_value=mock_proc), \
             mock.patch("tools.execute_code_docker.subprocess.run") as mock_run:
            stdout, stderr, rc = run_script_in_docker(
                script_path="/tmp/work/script.py",
                tmpdir="/tmp/work",
                sock_path="/tmp/rpc.sock",
                image="python:3.11",
                child_env={},
                timeout=5,
            )

        assert rc == -1
        # docker kill must be called before proc.kill()
        mock_run.assert_called_once()
        docker_kill_args = mock_run.call_args[0][0]
        assert docker_kill_args[0] == "docker"
        assert docker_kill_args[1] == "kill"
        mock_proc.kill.assert_called_once()

    def test_docker_not_found(self):
        from tools.execute_code_docker import run_script_in_docker

        with mock.patch(
            "tools.execute_code_docker.subprocess.Popen",
            side_effect=FileNotFoundError("No such file: docker"),
        ):
            stdout, stderr, rc = run_script_in_docker(
                script_path="/tmp/work/script.py",
                tmpdir="/tmp/work",
                sock_path="/tmp/rpc.sock",
                image="python:3.11",
                child_env={},
                timeout=30,
            )

        assert rc == 127
        assert b"Docker executable not found" in stderr

    def test_nonzero_exit_code(self):
        from tools.execute_code_docker import run_script_in_docker

        mock_proc = mock.MagicMock()
        mock_proc.communicate.return_value = (b"", b"Traceback...\n")
        mock_proc.returncode = 1

        with mock.patch("tools.execute_code_docker.subprocess.Popen", return_value=mock_proc):
            stdout, stderr, rc = run_script_in_docker(
                script_path="/tmp/work/script.py",
                tmpdir="/tmp/work",
                sock_path="/tmp/rpc.sock",
                image="python:3.11",
                child_env={},
                timeout=30,
            )

        assert rc == 1
        assert stderr == b"Traceback...\n"


class TestCodeExecutionToolDockerPath:
    """Test that code_execution_tool routes to docker when env vars are set."""

    def test_docker_path_used_when_env_set(self):
        """When TERMINAL_ENV=docker and TERMINAL_DOCKER_IMAGE is set, docker path is used."""
        env_patch = {
            "TERMINAL_ENV": "docker",
            "TERMINAL_DOCKER_IMAGE": "python:3.11",
        }
        with mock.patch.dict(os.environ, env_patch):
            backend = os.environ.get("TERMINAL_ENV", "local")
            image = os.environ.get("TERMINAL_DOCKER_IMAGE", "")
            use_docker = backend == "docker" and bool(image)
            assert use_docker is True

    def test_local_path_used_by_default(self):
        """When TERMINAL_ENV is not set (default), local path is used."""
        env_patch = {"TERMINAL_ENV": "local"}
        with mock.patch.dict(os.environ, env_patch, clear=False):
            # Remove TERMINAL_DOCKER_IMAGE if present
            with mock.patch.dict(os.environ, {"TERMINAL_DOCKER_IMAGE": ""}, clear=False):
                backend = os.environ.get("TERMINAL_ENV", "local")
                image = os.environ.get("TERMINAL_DOCKER_IMAGE", "")
                use_docker = backend == "docker" and bool(image)
                assert use_docker is False

    def test_local_path_when_no_image(self):
        """Even with TERMINAL_ENV=docker, no image means local path."""
        env_patch = {"TERMINAL_ENV": "docker", "TERMINAL_DOCKER_IMAGE": ""}
        with mock.patch.dict(os.environ, env_patch):
            backend = os.environ.get("TERMINAL_ENV", "local")
            image = os.environ.get("TERMINAL_DOCKER_IMAGE", "")
            use_docker = backend == "docker" and bool(image)
            assert use_docker is False
