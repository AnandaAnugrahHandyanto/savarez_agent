import subprocess

from tools.env_passthrough import clear_env_passthrough, register_env_passthrough
from tools.environments import ssh as ssh_env
from tools.environments.ssh import SSHEnvironment


def _make_ssh_env(monkeypatch):
    monkeypatch.setattr(ssh_env.shutil, "which", lambda _name: "/usr/bin/ssh")
    monkeypatch.setattr(ssh_env.SSHEnvironment, "_establish_connection", lambda self: None)
    monkeypatch.setattr(ssh_env.SSHEnvironment, "_detect_remote_home", lambda self: "/home/testuser")
    monkeypatch.setattr(ssh_env.SSHEnvironment, "_ensure_remote_dirs", lambda self: None)
    monkeypatch.setattr(ssh_env.SSHEnvironment, "init_session", lambda self: None)
    monkeypatch.setattr(
        ssh_env,
        "FileSyncManager",
        lambda **kw: type(
            "M",
            (),
            {"sync": lambda self, **k: None, "sync_back": lambda self: None},
        )(),
    )
    return SSHEnvironment(host="example.com", user="testuser")


def test_login_shell_forwards_registered_passthrough_env_vars(monkeypatch):
    clear_env_passthrough()
    monkeypatch.setenv("NEXTCLOUD_URL", "https://next.example.com")
    monkeypatch.setenv("NEXTCLOUD_USER", "alice")
    register_env_passthrough(["NEXTCLOUD_URL", "NEXTCLOUD_USER"])
    env = _make_ssh_env(monkeypatch)

    captured = {}

    def fake_popen(cmd, stdin_data=None, **kwargs):
        captured["cmd"] = cmd
        return object()

    monkeypatch.setattr(ssh_env, "_popen_bash", fake_popen)

    env._run_bash("printf test", login=True)

    assert captured["cmd"][:3] == ["ssh", "-o", f"ControlPath={env.control_socket}"]
    assert "-o" in captured["cmd"]
    assert "SendEnv=NEXTCLOUD_URL" in captured["cmd"]
    assert "SendEnv=NEXTCLOUD_USER" in captured["cmd"]

    clear_env_passthrough()


def test_login_shell_omits_unregistered_env_vars(monkeypatch):
    clear_env_passthrough()
    monkeypatch.setenv("NEXTCLOUD_URL", "https://next.example.com")
    env = _make_ssh_env(monkeypatch)

    captured = {}

    def fake_popen(cmd, stdin_data=None, **kwargs):
        captured["cmd"] = cmd
        return object()

    monkeypatch.setattr(ssh_env, "_popen_bash", fake_popen)

    env._run_bash("printf test", login=True)

    assert "SendEnv=NEXTCLOUD_URL" not in captured["cmd"]

    clear_env_passthrough()
