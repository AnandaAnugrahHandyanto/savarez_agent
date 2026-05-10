"""Regression tests for task/session cwd propagation in terminal_tool."""

import json

import tools.file_tools as file_tools
import tools.terminal_tool as terminal_tool


def _minimal_terminal_config(env_type="local", cwd="/default", **overrides):
    config = {
        "env_type": env_type,
        "cwd": cwd,
        "timeout": 60,
        "host_cwd": None,
        "docker_image": "docker:test",
        "singularity_image": "docker://docker:test",
        "modal_image": "modal:test",
        "daytona_image": "daytona:test",
        "vercel_runtime": "",
        "container_cpu": 1,
        "container_memory": 5120,
        "container_disk": 51200,
        "container_persistent": True,
        "docker_volumes": [],
        "docker_mount_cwd_to_workspace": False,
        "docker_forward_env": [],
        "docker_env": {},
        "docker_run_as_host_user": False,
        "modal_mode": "auto",
        "ssh_host": "",
        "ssh_user": "",
        "ssh_port": 22,
        "ssh_key": "",
        "ssh_persistent": False,
        "local_persistent": False,
    }
    config.update(overrides)
    return config


def test_foreground_command_uses_registered_task_cwd_for_existing_environment(monkeypatch):
    """ACP can update task cwd after the local env exists; foreground must honor it."""
    calls = []

    class FakeEnv:
        env = {}

        def execute(self, command, **kwargs):
            calls.append((command, kwargs))
            return {"output": "ok", "returncode": 0}

    task_id = "acp-session-1"
    monkeypatch.setattr(terminal_tool, "_active_environments", {task_id: FakeEnv()})
    monkeypatch.setattr(terminal_tool, "_last_activity", {})
    monkeypatch.setattr(terminal_tool, "_task_env_overrides", {task_id: {"cwd": "/workspace/acp"}})
    monkeypatch.setattr(terminal_tool, "_get_env_config", lambda: _minimal_terminal_config())
    monkeypatch.setattr(
        terminal_tool,
        "_check_all_guards",
        lambda command, env_type: {"approved": True},
    )

    result = json.loads(terminal_tool.terminal_tool(command="pwd", task_id=task_id))

    assert result["exit_code"] == 0
    assert calls == [("pwd", {"timeout": 60, "cwd": "/workspace/acp"})]


def test_explicit_workdir_still_wins_over_registered_task_cwd(monkeypatch):
    calls = []

    class FakeEnv:
        env = {}

        def execute(self, command, **kwargs):
            calls.append(kwargs)
            return {"output": "ok", "returncode": 0}

    task_id = "acp-session-1"
    monkeypatch.setattr(terminal_tool, "_active_environments", {task_id: FakeEnv()})
    monkeypatch.setattr(terminal_tool, "_last_activity", {})
    monkeypatch.setattr(terminal_tool, "_task_env_overrides", {task_id: {"cwd": "/workspace/acp"}})
    monkeypatch.setattr(terminal_tool, "_get_env_config", lambda: _minimal_terminal_config())
    monkeypatch.setattr(
        terminal_tool,
        "_check_all_guards",
        lambda command, env_type: {"approved": True},
    )

    result = json.loads(
        terminal_tool.terminal_tool(
            command="pwd",
            task_id=task_id,
            workdir="/explicit/workdir",
        )
    )

    assert result["exit_code"] == 0
    assert calls == [{"timeout": 60, "cwd": "/explicit/workdir"}]


def test_terminal_recreates_environment_when_backend_changes(monkeypatch):
    created = []
    cleaned = []
    configs = iter(
        [
            _minimal_terminal_config(env_type="local", cwd="/workspace/local"),
            _minimal_terminal_config(env_type="docker", cwd="/workspace/docker"),
        ]
    )

    class FakeEnv:
        def __init__(self, name):
            self.name = name
            self.env = {}

        def execute(self, command, **kwargs):
            return {"output": self.name, "returncode": 0}

        def cleanup(self):
            cleaned.append(self.name)

    monkeypatch.setattr(terminal_tool, "_active_environments", {})
    monkeypatch.setattr(terminal_tool, "_last_activity", {})
    monkeypatch.setattr(terminal_tool, "_environment_signatures", {})
    monkeypatch.setattr(terminal_tool, "_creation_locks", {})
    monkeypatch.setattr(terminal_tool, "_task_env_overrides", {})
    monkeypatch.setattr(terminal_tool, "_get_env_config", lambda: next(configs))
    monkeypatch.setattr(terminal_tool, "_start_cleanup_thread", lambda: None)
    monkeypatch.setattr(terminal_tool, "_foreground_background_guidance", lambda command: None)
    monkeypatch.setattr(
        terminal_tool,
        "_check_all_guards",
        lambda command, env_type: {"approved": True},
    )
    monkeypatch.setattr(
        terminal_tool,
        "_create_environment",
        lambda **kwargs: created.append(kwargs["env_type"]) or FakeEnv(kwargs["env_type"]),
    )

    first = json.loads(terminal_tool.terminal_tool(command="pwd", task_id="task-1"))
    second = json.loads(terminal_tool.terminal_tool(command="pwd", task_id="task-1"))

    assert first["output"] == "local"
    assert second["output"] == "docker"
    assert created == ["local", "docker"]
    assert cleaned == ["local"]


def test_file_ops_recreates_environment_when_backend_changes(monkeypatch):
    created = []
    cleaned = []
    configs = iter(
        [
            _minimal_terminal_config(env_type="local", cwd="/workspace/local"),
            _minimal_terminal_config(env_type="docker", cwd="/workspace/docker"),
        ]
    )

    class FakeEnv:
        def __init__(self, name):
            self.name = name
            self.cwd = f"/workspace/{name}"

        def cleanup(self):
            cleaned.append(self.name)

    class FakeShellFileOperations:
        def __init__(self, env):
            self.env = env
            self.cwd = env.cwd

    monkeypatch.setattr(terminal_tool, "_active_environments", {})
    monkeypatch.setattr(terminal_tool, "_last_activity", {})
    monkeypatch.setattr(terminal_tool, "_environment_signatures", {})
    monkeypatch.setattr(terminal_tool, "_creation_locks", {})
    monkeypatch.setattr(terminal_tool, "_task_env_overrides", {})
    monkeypatch.setattr(terminal_tool, "_get_env_config", lambda: next(configs))
    monkeypatch.setattr(terminal_tool, "_start_cleanup_thread", lambda: None)
    monkeypatch.setattr(
        terminal_tool,
        "_create_environment",
        lambda **kwargs: created.append(kwargs["env_type"]) or FakeEnv(kwargs["env_type"]),
    )
    monkeypatch.setattr(file_tools, "_file_ops_cache", {})
    monkeypatch.setattr(file_tools, "ShellFileOperations", FakeShellFileOperations)

    first = file_tools._get_file_ops("task-1")
    second = file_tools._get_file_ops("task-1")

    assert first.env.name == "local"
    assert second.env.name == "docker"
    assert created == ["local", "docker"]
    assert cleaned == ["local"]
