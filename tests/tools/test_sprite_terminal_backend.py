"""Tests for the Sprite terminal backend."""

from __future__ import annotations

import subprocess

import pytest

from tools import terminal_tool
from tools.environments import sprite as sprite_env


class _FakePopen:
    def __init__(self, args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.stdout = None
        self.returncode = None

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9


class _FakeRunResult:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_sprite_env_config_reads_sprite_settings(monkeypatch):
    monkeypatch.setenv("TERMINAL_ENV", "sprite")
    monkeypatch.setenv("TERMINAL_CWD", "/Users/bkearns/project")
    monkeypatch.setenv("TERMINAL_SPRITE_ORG", "ferrosa")
    monkeypatch.setenv("TERMINAL_SPRITE", "agent-dev")
    monkeypatch.setenv("TERMINAL_SPRITE_HTTP_POST", "true")

    config = terminal_tool._get_env_config()

    assert config["env_type"] == "sprite"
    assert config["cwd"] == "/root"
    assert config["sprite_org"] == "ferrosa"
    assert config["sprite"] == "agent-dev"
    assert config["sprite_http_post"] is True


def test_create_environment_constructs_sprite_backend(monkeypatch):
    monkeypatch.setattr(
        sprite_env, "ensure_sprite_available", lambda: "/usr/local/bin/sprite"
    )
    monkeypatch.setattr(sprite_env.SpriteEnvironment, "init_session", lambda self: None)

    env = terminal_tool._create_environment(
        "sprite",
        image="ignored",
        cwd="/workspace",
        timeout=77,
        container_config={
            "sprite_org": "ferrosa",
            "sprite": "agent-dev",
            "sprite_http_post": True,
        },
    )

    assert isinstance(env, sprite_env.SpriteEnvironment)
    assert env.cwd == "/workspace"
    assert env.timeout == 77
    assert env.org == "ferrosa"
    assert env.sprite == "agent-dev"
    assert env.http_post is True


def test_sprite_run_bash_uses_sprite_exec_context_flags(monkeypatch):
    monkeypatch.setattr(
        sprite_env, "ensure_sprite_available", lambda: "/opt/bin/sprite"
    )
    monkeypatch.setattr(sprite_env.SpriteEnvironment, "init_session", lambda self: None)
    popen_calls = []

    def fake_popen(args, **kwargs):
        popen_calls.append((args, kwargs))
        return _FakePopen(args, **kwargs)

    monkeypatch.setattr(sprite_env.subprocess, "Popen", fake_popen)

    env = sprite_env.SpriteEnvironment(
        cwd="/app",
        timeout=30,
        org="ferrosa",
        sprite="agent-dev",
        http_post=True,
    )
    proc = env._run_bash("printf hi", login=False, timeout=30)

    assert proc.args == [
        "/opt/bin/sprite",
        "exec",
        "-o",
        "ferrosa",
        "-s",
        "agent-dev",
        "--dir",
        "/app",
        "--http-post",
        "bash",
        "-c",
        "printf hi",
    ]
    assert popen_calls[0][1]["stdout"] == subprocess.PIPE
    assert popen_calls[0][1]["stderr"] == subprocess.STDOUT


def test_check_terminal_requirements_for_sprite(monkeypatch):
    monkeypatch.setattr(
        terminal_tool, "_get_env_config", lambda: {"env_type": "sprite"}
    )
    monkeypatch.setattr(
        sprite_env, "ensure_sprite_available", lambda: "/usr/local/bin/sprite"
    )
    monkeypatch.setattr(
        terminal_tool.subprocess,
        "run",
        lambda *args, **kwargs: _FakeRunResult(returncode=0, stdout="personal\n"),
    )

    assert terminal_tool.check_terminal_requirements() is True


def test_check_terminal_requirements_for_sprite_reports_auth_failure(monkeypatch):
    monkeypatch.setattr(
        terminal_tool, "_get_env_config", lambda: {"env_type": "sprite"}
    )
    monkeypatch.setattr(
        sprite_env, "ensure_sprite_available", lambda: "/usr/local/bin/sprite"
    )
    monkeypatch.setattr(
        terminal_tool.subprocess,
        "run",
        lambda *args, **kwargs: _FakeRunResult(
            returncode=1, stderr="not authenticated"
        ),
    )

    assert terminal_tool.check_terminal_requirements() is False


def test_ensure_sprite_available_fails_loud_when_missing(monkeypatch):
    monkeypatch.setattr(sprite_env.shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError, match="Sprite CLI is not installed"):
        sprite_env.ensure_sprite_available()
