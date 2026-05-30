"""Guard against orphaning a second gateway dispatcher on a supervised host.

Regression coverage for issue #35240: running ``hermes gateway run [--replace]``
or a manual ``gateway restart`` fallback from an interactive shell while a
systemd/launchd-managed gateway for the same profile is alive used to spawn a
long-lived orphan that escaped the service cgroup and became a silent
concurrent writer on the shared ``kanban.db`` — corrupting it.

The guard lives in one place — ``_guard_against_supervised_gateway()``, called
from ``run_gateway()`` — so every code path that reaches a foreground start
(``run``, the manual ``restart`` fallback, ``start`` fallback) is covered.
"""

import subprocess

import pytest


class _FakeRun:
    """Minimal stand-in for ``subprocess.run`` returning canned stdout."""

    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode

    def __call__(self, *args, **kwargs):
        return self


class TestGuardAgainstSupervisedGateway:
    def _patch_no_supervisor_env(self, monkeypatch):
        monkeypatch.delenv("INVOCATION_ID", raising=False)

    def test_refuses_when_supervised_and_not_self(self, monkeypatch, capsys):
        import hermes_cli.gateway as gateway_mod

        self._patch_no_supervisor_env(monkeypatch)
        monkeypatch.setattr(gateway_mod, "is_macos", lambda: False)
        monkeypatch.setattr(gateway_mod, "get_service_name", lambda: "hermes-gateway-argus")
        monkeypatch.setattr(
            gateway_mod, "_supervised_gateway_main_pid", lambda: 999_999
        )

        with pytest.raises(SystemExit) as exc:
            gateway_mod._guard_against_supervised_gateway(force=False)
        assert exc.value.code == 1

        out = capsys.readouterr().out
        assert "already running (PID 999999)" in out
        assert "systemctl restart hermes-gateway-argus.service" in out

    def test_force_overrides_refusal(self, monkeypatch, capsys):
        import hermes_cli.gateway as gateway_mod

        self._patch_no_supervisor_env(monkeypatch)
        monkeypatch.setattr(gateway_mod, "is_macos", lambda: False)
        monkeypatch.setattr(gateway_mod, "get_service_name", lambda: "hermes-gateway")
        monkeypatch.setattr(
            gateway_mod, "_supervised_gateway_main_pid", lambda: 999_999
        )

        # Must not raise SystemExit.
        gateway_mod._guard_against_supervised_gateway(force=True)
        out = capsys.readouterr().out
        assert "--force" in out

    def test_skips_when_running_under_systemd(self, monkeypatch):
        import hermes_cli.gateway as gateway_mod

        monkeypatch.setenv("INVOCATION_ID", "deadbeefcafe")
        # Even if a MainPID is reported, INVOCATION_ID means *we* are the unit.
        monkeypatch.setattr(
            gateway_mod, "_supervised_gateway_main_pid", lambda: 999_999
        )
        gateway_mod._guard_against_supervised_gateway(force=False)  # no raise

    def test_skips_when_detected_pid_is_self(self, monkeypatch):
        import os

        import hermes_cli.gateway as gateway_mod

        self._patch_no_supervisor_env(monkeypatch)
        monkeypatch.setattr(
            gateway_mod, "_supervised_gateway_main_pid", lambda: os.getpid()
        )
        gateway_mod._guard_against_supervised_gateway(force=False)  # no raise

    def test_no_op_when_no_supervisor(self, monkeypatch):
        import hermes_cli.gateway as gateway_mod

        self._patch_no_supervisor_env(monkeypatch)
        monkeypatch.setattr(gateway_mod, "_supervised_gateway_main_pid", lambda: None)
        gateway_mod._guard_against_supervised_gateway(force=False)  # no raise

    def test_macos_hint_mentions_launchd(self, monkeypatch, capsys):
        import hermes_cli.gateway as gateway_mod

        self._patch_no_supervisor_env(monkeypatch)
        monkeypatch.setattr(gateway_mod, "is_macos", lambda: True)
        monkeypatch.setattr(gateway_mod, "get_launchd_label", lambda: "com.hermes.gateway")
        monkeypatch.setattr(
            gateway_mod, "_supervised_gateway_main_pid", lambda: 999_999
        )

        with pytest.raises(SystemExit):
            gateway_mod._guard_against_supervised_gateway(force=False)
        out = capsys.readouterr().out
        assert "hermes gateway restart" in out
        assert "com.hermes.gateway" in out


class TestSupervisedGatewayMainPid:
    def test_systemd_main_pid_parsed(self, monkeypatch):
        import hermes_cli.gateway as gateway_mod

        monkeypatch.setattr(gateway_mod, "supports_systemd_services", lambda: True)
        monkeypatch.setattr(gateway_mod, "is_macos", lambda: False)
        monkeypatch.setattr(gateway_mod, "get_service_name", lambda: "hermes-gateway")
        monkeypatch.setattr(subprocess, "run", _FakeRun(stdout="4154204\n"))

        assert gateway_mod._supervised_gateway_main_pid() == 4154204

    def test_systemd_zero_main_pid_means_not_running(self, monkeypatch):
        import hermes_cli.gateway as gateway_mod

        monkeypatch.setattr(gateway_mod, "supports_systemd_services", lambda: True)
        monkeypatch.setattr(gateway_mod, "is_macos", lambda: False)
        monkeypatch.setattr(gateway_mod, "get_service_name", lambda: "hermes-gateway")
        # systemctl reports MainPID=0 for an inactive unit.
        monkeypatch.setattr(subprocess, "run", _FakeRun(stdout="0\n"))

        assert gateway_mod._supervised_gateway_main_pid() is None

    def test_launchd_main_pid_parsed(self, monkeypatch):
        import hermes_cli.gateway as gateway_mod

        monkeypatch.setattr(gateway_mod, "supports_systemd_services", lambda: False)
        monkeypatch.setattr(gateway_mod, "is_macos", lambda: True)
        monkeypatch.setattr(gateway_mod, "get_launchd_label", lambda: "com.hermes.gateway")
        plist = (
            "{\n"
            '\t"PID" = 4242;\n'
            '\t"Label" = "com.hermes.gateway";\n'
            "};\n"
        )
        monkeypatch.setattr(subprocess, "run", _FakeRun(stdout=plist, returncode=0))

        assert gateway_mod._supervised_gateway_main_pid() == 4242

    def test_launchd_not_loaded_returns_none(self, monkeypatch):
        import hermes_cli.gateway as gateway_mod

        monkeypatch.setattr(gateway_mod, "supports_systemd_services", lambda: False)
        monkeypatch.setattr(gateway_mod, "is_macos", lambda: True)
        monkeypatch.setattr(gateway_mod, "get_launchd_label", lambda: "com.hermes.gateway")
        # Non-zero return code: job not loaded.
        monkeypatch.setattr(subprocess, "run", _FakeRun(stdout="", returncode=1))

        assert gateway_mod._supervised_gateway_main_pid() is None
