import json
from unittest.mock import patch

from tools.environments.local import LocalEnvironment, _make_run_env, _sanitize_subprocess_env


class TestLocalTempDir:
    def test_uses_os_tmpdir_for_session_artifacts(self, monkeypatch):
        monkeypatch.setenv("TMPDIR", "/data/data/com.termux/files/usr/tmp")
        monkeypatch.delenv("TMP", raising=False)
        monkeypatch.delenv("TEMP", raising=False)

        with patch.object(LocalEnvironment, "init_session", autospec=True, return_value=None):
            env = LocalEnvironment(cwd=".", timeout=10)

        assert env.get_temp_dir() == "/data/data/com.termux/files/usr/tmp"
        assert env._snapshot_path == f"/data/data/com.termux/files/usr/tmp/hermes-snap-{env._session_id}.sh"
        assert env._cwd_file == f"/data/data/com.termux/files/usr/tmp/hermes-cwd-{env._session_id}.txt"

    def test_prefers_backend_env_tmpdir_override(self, monkeypatch):
        monkeypatch.delenv("TMPDIR", raising=False)
        monkeypatch.delenv("TMP", raising=False)
        monkeypatch.delenv("TEMP", raising=False)

        with patch.object(LocalEnvironment, "init_session", autospec=True, return_value=None):
            env = LocalEnvironment(
                cwd=".",
                timeout=10,
                env={"TMPDIR": "/data/data/com.termux/files/home/.cache/hermes-tmp/"},
            )

        assert env.get_temp_dir() == "/data/data/com.termux/files/home/.cache/hermes-tmp"
        assert env._snapshot_path == (
            f"/data/data/com.termux/files/home/.cache/hermes-tmp/hermes-snap-{env._session_id}.sh"
        )
        assert env._cwd_file == (
            f"/data/data/com.termux/files/home/.cache/hermes-tmp/hermes-cwd-{env._session_id}.txt"
        )

    def test_falls_back_to_tempfile_when_tmp_missing(self, monkeypatch):
        monkeypatch.delenv("TMPDIR", raising=False)
        monkeypatch.delenv("TMP", raising=False)
        monkeypatch.delenv("TEMP", raising=False)

        with patch("tools.environments.local.os.path.isdir", return_value=False), \
             patch("tools.environments.local.os.access", return_value=False), \
             patch("tools.environments.local.tempfile.gettempdir", return_value="/cache/tmp"), \
             patch.object(LocalEnvironment, "init_session", autospec=True, return_value=None):
            env = LocalEnvironment(cwd=".", timeout=10)
            assert env.get_temp_dir() == "/cache/tmp"
            assert env._snapshot_path == f"/cache/tmp/hermes-snap-{env._session_id}.sh"
            assert env._cwd_file == f"/cache/tmp/hermes-cwd-{env._session_id}.txt"


class TestProfileGitHubAuthPassthrough:
    def _write_podman_connections(self, host_home, identity_path="/tmp/podman-machine-key"):
        connections_dir = host_home / ".config" / "containers"
        connections_dir.mkdir(parents=True)
        (connections_dir / "podman-connections.json").write_text(
            json.dumps({
                "Connection": {
                    "Default": "podman-machine-default",
                    "Connections": {
                        "podman-machine-default": {
                            "URI": "ssh://core@127.0.0.1:56260/run/user/501/podman/podman.sock",
                            "Identity": identity_path,
                            "IsMachine": True,
                        }
                    },
                },
                "Farm": {},
            }),
            encoding="utf-8",
        )

    def test_make_run_env_preserves_host_gh_and_git_config_before_profile_home(self, monkeypatch, tmp_path):
        host_home = tmp_path / "host"
        profile_root = tmp_path / "profile"
        (host_home / ".config" / "gh").mkdir(parents=True)
        (host_home / ".gitconfig").write_text("[credential]\n", encoding="utf-8")
        (profile_root / "home").mkdir(parents=True)

        monkeypatch.setenv("HOME", str(host_home))
        monkeypatch.setenv("HERMES_HOME", str(profile_root))
        monkeypatch.delenv("GH_CONFIG_DIR", raising=False)
        monkeypatch.delenv("GIT_CONFIG_GLOBAL", raising=False)

        run_env = _make_run_env({})

        assert run_env["HOME"] == str(profile_root / "home")
        assert run_env["GH_CONFIG_DIR"] == str(host_home / ".config" / "gh")
        assert run_env["GIT_CONFIG_GLOBAL"] == str(host_home / ".gitconfig")

    def test_make_run_env_preserves_host_podman_connection_before_profile_home(self, monkeypatch, tmp_path):
        host_home = tmp_path / "host"
        profile_root = tmp_path / "profile"
        (profile_root / "home").mkdir(parents=True)
        self._write_podman_connections(host_home, identity_path=str(host_home / ".local" / "machine"))

        monkeypatch.setenv("HOME", str(host_home))
        monkeypatch.setenv("HERMES_HOME", str(profile_root))
        monkeypatch.delenv("CONTAINER_HOST", raising=False)
        monkeypatch.delenv("CONTAINER_SSHKEY", raising=False)

        run_env = _make_run_env({})

        assert run_env["HOME"] == str(profile_root / "home")
        assert run_env["CONTAINER_HOST"] == "ssh://core@127.0.0.1:56260/run/user/501/podman/podman.sock"
        assert run_env["CONTAINER_SSHKEY"] == str(host_home / ".local" / "machine")

    def test_sanitize_subprocess_env_preserves_host_gh_and_git_config_for_background_processes(self, monkeypatch, tmp_path):
        host_home = tmp_path / "host"
        profile_root = tmp_path / "profile"
        (host_home / ".config" / "gh").mkdir(parents=True)
        (host_home / ".gitconfig").write_text("[credential]\n", encoding="utf-8")
        (profile_root / "home").mkdir(parents=True)

        monkeypatch.setenv("HERMES_HOME", str(profile_root))

        run_env = _sanitize_subprocess_env({"HOME": str(host_home)}, {})

        assert run_env["HOME"] == str(profile_root / "home")
        assert run_env["GH_CONFIG_DIR"] == str(host_home / ".config" / "gh")
        assert run_env["GIT_CONFIG_GLOBAL"] == str(host_home / ".gitconfig")

    def test_sanitize_subprocess_env_preserves_host_podman_connection_for_background_processes(self, monkeypatch, tmp_path):
        host_home = tmp_path / "host"
        profile_root = tmp_path / "profile"
        (profile_root / "home").mkdir(parents=True)
        self._write_podman_connections(host_home, identity_path=str(host_home / ".local" / "machine"))

        monkeypatch.setenv("HERMES_HOME", str(profile_root))

        run_env = _sanitize_subprocess_env({"HOME": str(host_home)}, {})

        assert run_env["HOME"] == str(profile_root / "home")
        assert run_env["CONTAINER_HOST"] == "ssh://core@127.0.0.1:56260/run/user/501/podman/podman.sock"
        assert run_env["CONTAINER_SSHKEY"] == str(host_home / ".local" / "machine")
