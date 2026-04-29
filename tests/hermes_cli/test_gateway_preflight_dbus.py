"""Tests for systemd preflight D-Bus / private-socket fallback (issue #17243)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import hermes_cli.gateway as gateway


# ---------------------------------------------------------------------------
# _systemd_private_socket_path
# ---------------------------------------------------------------------------

class TestSystemdPrivateSocketPath:
    def test_uses_xdg_runtime_dir(self, monkeypatch):
        monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1234")
        assert gateway._systemd_private_socket_path() == Path("/run/user/1234/systemd/private")

    def test_falls_back_to_uid(self, monkeypatch):
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
        monkeypatch.setattr("os.getuid", lambda: 5678)
        assert gateway._systemd_private_socket_path() == Path("/run/user/5678/systemd/private")


# ---------------------------------------------------------------------------
# _probe_systemctl_user
# ---------------------------------------------------------------------------

class TestProbeSystemctlUser:
    def test_returns_true_for_running(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/systemctl")
        monkeypatch.setattr(
            gateway.subprocess, "run",
            lambda *a, **kw: SimpleNamespace(stdout="running\n", stderr="", returncode=0),
        )
        assert gateway._probe_systemctl_user() is True

    def test_returns_true_for_degraded(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/systemctl")
        monkeypatch.setattr(
            gateway.subprocess, "run",
            lambda *a, **kw: SimpleNamespace(stdout="degraded\n", stderr="", returncode=1),
        )
        assert gateway._probe_systemctl_user() is True

    def test_returns_true_for_starting(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/systemctl")
        monkeypatch.setattr(
            gateway.subprocess, "run",
            lambda *a, **kw: SimpleNamespace(stdout="starting\n", stderr="", returncode=1),
        )
        assert gateway._probe_systemctl_user() is True

    def test_returns_false_when_systemctl_missing(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: None)
        assert gateway._probe_systemctl_user() is False

    def test_returns_false_on_connection_error(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/systemctl")
        monkeypatch.setattr(
            gateway.subprocess, "run",
            lambda *a, **kw: SimpleNamespace(
                stdout="", stderr="Failed to connect to bus\n", returncode=1,
            ),
        )
        assert gateway._probe_systemctl_user() is False

    def test_returns_false_on_timeout(self, monkeypatch):
        import subprocess as sp
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/systemctl")

        def _timeout(*a, **kw):
            raise sp.TimeoutExpired(cmd="systemctl", timeout=3)

        monkeypatch.setattr(gateway.subprocess, "run", _timeout)
        assert gateway._probe_systemctl_user() is False

    def test_returns_false_on_oserror(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/systemctl")

        def _oserror(*a, **kw):
            raise OSError("exec failed")

        monkeypatch.setattr(gateway.subprocess, "run", _oserror)
        assert gateway._probe_systemctl_user() is False


# ---------------------------------------------------------------------------
# _wait_for_user_dbus_socket — private socket fallback
# ---------------------------------------------------------------------------

class TestWaitForUserDbusSocket:
    def test_returns_true_when_private_socket_exists(self, monkeypatch):
        monkeypatch.setattr(gateway, "_user_dbus_socket_path", lambda: Path("/nonexistent/bus"))
        monkeypatch.setattr(
            gateway, "_systemd_private_socket_path",
            lambda: SimpleNamespace(exists=lambda: True),
        )
        assert gateway._wait_for_user_dbus_socket(timeout=0.1) is True

    def test_returns_false_when_neither_exists(self, monkeypatch):
        monkeypatch.setattr(
            gateway, "_user_dbus_socket_path",
            lambda: SimpleNamespace(exists=lambda: False),
        )
        monkeypatch.setattr(
            gateway, "_systemd_private_socket_path",
            lambda: SimpleNamespace(exists=lambda: False),
        )
        assert gateway._wait_for_user_dbus_socket(timeout=0.3) is False


# ---------------------------------------------------------------------------
# _preflight_user_systemd — Debian 13 scenario
# ---------------------------------------------------------------------------

class TestPreflightUserSystemd:
    def _patch_common(self, monkeypatch):
        """Disable real filesystem / subprocess calls used by the preflight."""
        monkeypatch.setattr(
            gateway, "_user_dbus_socket_path",
            lambda: SimpleNamespace(exists=lambda: False),
        )
        monkeypatch.setattr(gateway, "_ensure_user_systemd_env", lambda: None)
        monkeypatch.setattr("getpass.getuser", lambda: "testuser")
        monkeypatch.setattr("os.getuid", lambda: 1000)

    def test_passes_when_dbus_socket_exists(self, monkeypatch):
        monkeypatch.setattr(
            gateway, "_user_dbus_socket_path",
            lambda: SimpleNamespace(exists=lambda: True),
        )
        monkeypatch.setattr(gateway, "_ensure_user_systemd_env", lambda: None)
        gateway._preflight_user_systemd()

    def test_passes_when_private_socket_exists_no_dbus(self, monkeypatch):
        """Debian 13 scenario: no bus socket but systemd private socket present."""
        self._patch_common(monkeypatch)
        monkeypatch.setattr(
            gateway, "_systemd_private_socket_path",
            lambda: SimpleNamespace(exists=lambda: True),
        )
        gateway._preflight_user_systemd()

    def test_passes_when_probe_succeeds_no_sockets(self, monkeypatch):
        """systemctl --user works even without either socket file visible."""
        self._patch_common(monkeypatch)
        monkeypatch.setattr(
            gateway, "_systemd_private_socket_path",
            lambda: SimpleNamespace(exists=lambda: False),
        )
        monkeypatch.setattr(gateway, "_probe_systemctl_user", lambda **kw: True)
        gateway._preflight_user_systemd()

    def test_raises_when_all_checks_fail(self, monkeypatch):
        self._patch_common(monkeypatch)
        monkeypatch.setattr(
            gateway, "_systemd_private_socket_path",
            lambda: SimpleNamespace(exists=lambda: False),
        )
        monkeypatch.setattr(gateway, "_probe_systemctl_user", lambda **kw: False)
        monkeypatch.setattr(gateway, "get_systemd_linger_status", lambda: (False, "disabled"))
        monkeypatch.setattr("shutil.which", lambda _: None)

        with pytest.raises(gateway.UserSystemdUnavailableError):
            gateway._preflight_user_systemd(auto_enable_linger=False)

    def test_probe_rescues_after_linger_enabled_no_socket(self, monkeypatch):
        """Linger is on, bus socket never appears, but probe confirms reachability."""
        self._patch_common(monkeypatch)
        monkeypatch.setattr(
            gateway, "_systemd_private_socket_path",
            lambda: SimpleNamespace(exists=lambda: False),
        )
        probe_calls = []

        def _probe(**kw):
            probe_calls.append(1)
            return len(probe_calls) >= 2  # fail on early check, succeed in linger path

        monkeypatch.setattr(gateway, "_probe_systemctl_user", _probe)
        monkeypatch.setattr(gateway, "get_systemd_linger_status", lambda: (True, ""))
        monkeypatch.setattr(gateway, "_wait_for_user_dbus_socket", lambda timeout=3.0: False)

        gateway._preflight_user_systemd()

    def test_probe_rescues_after_enable_linger_succeeds(self, monkeypatch, capsys):
        """enable-linger succeeds, bus socket doesn't appear, but probe passes."""
        self._patch_common(monkeypatch)
        monkeypatch.setattr(
            gateway, "_systemd_private_socket_path",
            lambda: SimpleNamespace(exists=lambda: False),
        )
        probe_calls = []

        def _probe(**kw):
            probe_calls.append(1)
            return len(probe_calls) >= 2

        monkeypatch.setattr(gateway, "_probe_systemctl_user", _probe)
        monkeypatch.setattr(gateway, "get_systemd_linger_status", lambda: (False, ""))
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/loginctl")
        monkeypatch.setattr(
            gateway.subprocess, "run",
            lambda *a, **kw: SimpleNamespace(returncode=0, stdout="", stderr=""),
        )
        monkeypatch.setattr(gateway, "_wait_for_user_dbus_socket", lambda timeout=5.0: False)

        gateway._preflight_user_systemd()

        out = capsys.readouterr().out
        assert "user systemd now reachable" in out
