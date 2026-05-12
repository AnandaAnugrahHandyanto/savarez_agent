"""Cross-platform stale-scoped-lock detection (issue #24067).

These tests pin down the psutil-backed root-cause fix for the long-standing
"macOS PID reused by a system process keeps the Telegram/Feishu/WeChat scoped
lock alive" bug.  They are deliberately hermetic — they mock psutil so they
run identically on Linux/macOS/Windows CI.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import pytest

from gateway import status


_LOCK_HASH = "2bb80d537b1da3e3"  # sha256("secret")[:16] — matches existing fixtures


def _write_lock(lock_dir, payload: dict[str, Any]):
    lock_path = lock_dir / f"telegram-bot-token-{_LOCK_HASH}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(payload))
    return lock_path


class _FakeProc:
    """Minimal stand-in for ``psutil.Process``.

    Each attribute is either a value (returned) or a callable raising an
    exception so individual accessors can be selectively denied.
    """

    def __init__(
        self,
        *,
        name: Any = "python",
        cmdline: Any = None,
        create_time: Any = 1_700_000.0,
    ) -> None:
        self._name = name
        self._cmdline = cmdline if cmdline is not None else []
        self._create_time = create_time

    def name(self) -> str:
        if isinstance(self._name, type) and issubclass(self._name, BaseException):
            raise self._name()
        return self._name

    def cmdline(self) -> list[str]:
        if isinstance(self._cmdline, type) and issubclass(self._cmdline, BaseException):
            raise self._cmdline()
        return list(self._cmdline)

    def create_time(self) -> float:
        if isinstance(self._create_time, type) and issubclass(self._create_time, BaseException):
            raise self._create_time()
        return float(self._create_time)


def _install_fake_psutil(monkeypatch, *, proc_factory, pid_exists: bool = True):
    """Replace cached ``psutil`` module with a fake exposing only what we use."""
    import psutil

    class _Module:
        NoSuchProcess = psutil.NoSuchProcess
        AccessDenied = psutil.AccessDenied
        ZombieProcess = psutil.ZombieProcess

        @staticmethod
        def Process(pid):  # noqa: N802 — psutil API name
            return proc_factory(pid)

        @staticmethod
        def pid_exists(pid):
            return pid_exists

    monkeypatch.setitem(sys.modules, "psutil", _Module)
    return _Module


class TestGetProcessStartTime:
    def test_returns_milliseconds_int(self, monkeypatch):
        _install_fake_psutil(
            monkeypatch,
            proc_factory=lambda pid: _FakeProc(create_time=1_700_000.123),
        )
        assert status._get_process_start_time(4242) == int(1_700_000.123 * 1000)

    def test_returns_none_when_process_missing(self, monkeypatch):
        import psutil

        def _missing(_pid):
            raise psutil.NoSuchProcess(_pid)

        _install_fake_psutil(monkeypatch, proc_factory=_missing)
        assert status._get_process_start_time(4242) is None

    def test_returns_none_on_access_denied(self, monkeypatch):
        import psutil

        def _denied(_pid):
            raise psutil.AccessDenied(_pid)

        _install_fake_psutil(monkeypatch, proc_factory=_denied)
        assert status._get_process_start_time(4242) is None

    def test_returns_none_on_zombie(self, monkeypatch):
        import psutil

        def _zombie(_pid):
            raise psutil.ZombieProcess(_pid)

        _install_fake_psutil(monkeypatch, proc_factory=_zombie)
        assert status._get_process_start_time(4242) is None

    def test_self_returns_positive_value(self):
        """End-to-end against the real psutil — works without /proc."""
        value = status._get_process_start_time(os.getpid())
        assert isinstance(value, int)
        assert value > 0


class TestReadProcessCmdline:
    def test_prefers_psutil_cmdline(self, monkeypatch):
        _install_fake_psutil(
            monkeypatch,
            proc_factory=lambda pid: _FakeProc(
                cmdline=["python", "-m", "hermes_cli.main", "gateway", "run"]
            ),
        )
        assert (
            status._read_process_cmdline(4242)
            == "python -m hermes_cli.main gateway run"
        )

    def test_falls_back_to_ps_when_psutil_denies(self, monkeypatch):
        import psutil

        def _denied(_pid):
            raise psutil.AccessDenied(_pid)

        _install_fake_psutil(monkeypatch, proc_factory=_denied)

        class _Result:
            returncode = 0
            stdout = "  /opt/hermes/bin/hermes gateway run --replace\n"

        monkeypatch.setattr(status.shutil, "which", lambda name: "/bin/ps")
        monkeypatch.setattr(status.subprocess, "run", lambda *a, **kw: _Result())
        assert (
            status._read_process_cmdline(4242)
            == "/opt/hermes/bin/hermes gateway run --replace"
        )

    def test_skips_ps_when_not_on_path(self, monkeypatch):
        import psutil

        def _denied(_pid):
            raise psutil.AccessDenied(_pid)

        _install_fake_psutil(monkeypatch, proc_factory=_denied)
        monkeypatch.setattr(status.shutil, "which", lambda name: None)

        def _explode(*_a, **_kw):
            raise AssertionError("subprocess.run must not be invoked when ps is absent")

        monkeypatch.setattr(status.subprocess, "run", _explode)
        assert status._read_process_cmdline(99_999_991) is None


class TestLooksLikeGatewayProcess:
    def test_rejects_non_python_name(self, monkeypatch):
        """macOS PID reuse: name='FileProvider' must short-circuit to False."""
        _install_fake_psutil(
            monkeypatch,
            proc_factory=lambda pid: _FakeProc(
                name="FileProvider",
                cmdline=["com.apple.CloudDocs.iCloudDriveFileProvider"],
            ),
        )
        assert status._looks_like_gateway_process(4242) is False

    def test_accepts_python_name_and_matching_cmdline(self, monkeypatch):
        _install_fake_psutil(
            monkeypatch,
            proc_factory=lambda pid: _FakeProc(
                name="python3.11",
                cmdline=[
                    "/opt/python/bin/python3.11",
                    "-m",
                    "hermes_cli.main",
                    "gateway",
                    "run",
                ],
            ),
        )
        assert status._looks_like_gateway_process(4242) is True

    def test_python_name_but_unrelated_cmdline(self, monkeypatch):
        _install_fake_psutil(
            monkeypatch,
            proc_factory=lambda pid: _FakeProc(
                name="python3.11",
                cmdline=["python3.11", "-m", "pip", "install", "something"],
            ),
        )
        assert status._looks_like_gateway_process(4242) is False

    def test_accepts_hermes_binary_name(self, monkeypatch):
        _install_fake_psutil(
            monkeypatch,
            proc_factory=lambda pid: _FakeProc(
                name="hermes-gateway",
                cmdline=["/usr/local/bin/hermes-gateway"],
            ),
        )
        assert status._looks_like_gateway_process(4242) is True

    def test_access_denied_falls_through_to_cmdline_check(self, monkeypatch):
        """If psutil cannot read name(), still trust cmdline."""
        import psutil

        class _PartialDenied(_FakeProc):
            def name(self) -> str:  # type: ignore[override]
                raise psutil.AccessDenied(0)

        _install_fake_psutil(
            monkeypatch,
            proc_factory=lambda pid: _PartialDenied(
                cmdline=["python", "-m", "hermes_cli.main", "gateway", "run"]
            ),
        )
        assert status._looks_like_gateway_process(4242) is True


class TestAcquireScopedLockStaleDetection:
    def _setup_lock_dir(self, tmp_path, monkeypatch):
        lock_dir = tmp_path / "locks"
        monkeypatch.setenv("HERMES_GATEWAY_LOCK_DIR", str(lock_dir))
        return lock_dir

    def test_pid_reuse_by_system_process_releases_lock(self, tmp_path, monkeypatch):
        """Issue #24067: macOS recycled PID, system daemon, no start_time."""
        lock_dir = self._setup_lock_dir(tmp_path, monkeypatch)
        lock_path = _write_lock(
            lock_dir,
            {
                "pid": 873,
                "start_time": None,
                "kind": "hermes-gateway",
                "argv": [
                    "/Users/u/.hermes/hermes-agent/hermes_cli/main.py",
                    "gateway",
                    "run",
                    "--replace",
                ],
            },
        )

        _install_fake_psutil(
            monkeypatch,
            proc_factory=lambda pid: _FakeProc(
                name="FileProvider",
                cmdline=["com.apple.CloudDocs.iCloudDriveFileProvider"],
                create_time=2_100_000.0,
            ),
        )
        monkeypatch.setattr(status, "_pid_exists", lambda pid: True)

        acquired, _existing = status.acquire_scoped_lock(
            "telegram-bot-token", "secret", metadata={"platform": "telegram"}
        )
        assert acquired is True
        payload = json.loads(lock_path.read_text())
        assert payload["pid"] == os.getpid()
        assert payload["metadata"]["platform"] == "telegram"

    def test_same_hermes_process_keeps_lock(self, tmp_path, monkeypatch):
        lock_dir = self._setup_lock_dir(tmp_path, monkeypatch)
        _write_lock(
            lock_dir,
            {
                "pid": 99999,
                "start_time": int(1_700_000.123 * 1000),
                "kind": "hermes-gateway",
                "argv": ["python", "-m", "hermes_cli.main", "gateway", "run"],
            },
        )

        _install_fake_psutil(
            monkeypatch,
            proc_factory=lambda pid: _FakeProc(
                name="python3.11",
                cmdline=["python", "-m", "hermes_cli.main", "gateway", "run"],
                create_time=1_700_000.123,
            ),
        )
        monkeypatch.setattr(status, "_pid_exists", lambda pid: True)

        acquired, existing = status.acquire_scoped_lock(
            "telegram-bot-token", "secret", metadata={"platform": "telegram"}
        )
        assert acquired is False
        assert existing["pid"] == 99999

    def test_pid_alive_but_start_time_mismatch_is_stale(self, tmp_path, monkeypatch):
        lock_dir = self._setup_lock_dir(tmp_path, monkeypatch)
        lock_path = _write_lock(
            lock_dir,
            {
                "pid": 99999,
                "start_time": 1_000_000_000,
                "kind": "hermes-gateway",
                "argv": ["python", "-m", "hermes_cli.main", "gateway", "run"],
            },
        )

        _install_fake_psutil(
            monkeypatch,
            proc_factory=lambda pid: _FakeProc(
                name="python3.11",
                cmdline=["python", "-m", "hermes_cli.main", "gateway", "run"],
                create_time=2_000_000.0,
            ),
        )
        monkeypatch.setattr(status, "_pid_exists", lambda pid: True)

        acquired, _existing = status.acquire_scoped_lock(
            "telegram-bot-token", "secret", metadata={"platform": "telegram"}
        )
        assert acquired is True
        payload = json.loads(lock_path.read_text())
        assert payload["pid"] == os.getpid()

    def test_legacy_jiffies_lock_is_replaced(self, tmp_path, monkeypatch):
        """Locks with old Linux jiffies values self-heal under the psutil ms world."""
        lock_dir = self._setup_lock_dir(tmp_path, monkeypatch)
        _write_lock(
            lock_dir,
            {
                "pid": 99999,
                "start_time": 4242,  # old Linux jiffies
                "kind": "hermes-gateway",
                "argv": ["python", "-m", "hermes_cli.main", "gateway", "run"],
            },
        )

        _install_fake_psutil(
            monkeypatch,
            proc_factory=lambda pid: _FakeProc(
                name="python3.11",
                cmdline=["python", "-m", "hermes_cli.main", "gateway", "run"],
                create_time=1_700_000.0,
            ),
        )
        monkeypatch.setattr(status, "_pid_exists", lambda pid: True)

        acquired, _existing = status.acquire_scoped_lock(
            "telegram-bot-token", "secret", metadata={"platform": "telegram"}
        )
        assert acquired is True

    def test_cross_platform_lockfile_one_sided_start_time_hermes(
        self, tmp_path, monkeypatch
    ):
        """Lock has start_time, live process has None — fall back to cmdline (matches)."""
        lock_dir = self._setup_lock_dir(tmp_path, monkeypatch)
        _write_lock(
            lock_dir,
            {
                "pid": 99999,
                "start_time": 1_700_000_000,
                "kind": "hermes-gateway",
                "argv": ["python", "-m", "hermes_cli.main", "gateway", "run"],
            },
        )

        import psutil

        class _CreateTimeDenied(_FakeProc):
            def create_time(self) -> float:  # type: ignore[override]
                raise psutil.AccessDenied(0)

        _install_fake_psutil(
            monkeypatch,
            proc_factory=lambda pid: _CreateTimeDenied(
                name="python3.11",
                cmdline=["python", "-m", "hermes_cli.main", "gateway", "run"],
            ),
        )
        monkeypatch.setattr(status, "_pid_exists", lambda pid: True)

        acquired, existing = status.acquire_scoped_lock(
            "telegram-bot-token", "secret", metadata={"platform": "telegram"}
        )
        assert acquired is False
        assert existing["pid"] == 99999

    def test_cross_platform_lockfile_one_sided_start_time_other_process(
        self, tmp_path, monkeypatch
    ):
        """Lock has start_time, live process has None, cmdline says NOT us → stale."""
        lock_dir = self._setup_lock_dir(tmp_path, monkeypatch)
        _write_lock(
            lock_dir,
            {
                "pid": 99999,
                "start_time": 1_700_000_000,
                "kind": "hermes-gateway",
                "argv": ["python", "-m", "hermes_cli.main", "gateway", "run"],
            },
        )

        import psutil

        class _CreateTimeDenied(_FakeProc):
            def create_time(self) -> float:  # type: ignore[override]
                raise psutil.AccessDenied(0)

        _install_fake_psutil(
            monkeypatch,
            proc_factory=lambda pid: _CreateTimeDenied(
                name="FileProvider",
                cmdline=["com.apple.CloudDocs.iCloudDriveFileProvider"],
            ),
        )
        monkeypatch.setattr(status, "_pid_exists", lambda pid: True)

        acquired, _existing = status.acquire_scoped_lock(
            "telegram-bot-token", "secret", metadata={"platform": "telegram"}
        )
        assert acquired is True

    def test_pid_gone_short_circuits_to_stale(self, tmp_path, monkeypatch):
        lock_dir = self._setup_lock_dir(tmp_path, monkeypatch)
        _write_lock(
            lock_dir,
            {"pid": 99999, "start_time": None, "kind": "hermes-gateway"},
        )

        monkeypatch.setattr(status, "_pid_exists", lambda pid: False)

        acquired, _existing = status.acquire_scoped_lock(
            "telegram-bot-token", "secret", metadata={"platform": "telegram"}
        )
        assert acquired is True


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="Smoke test inspects POSIX psutil behavior",
)
def test_real_process_start_time_is_stable_across_calls():
    a = status._get_process_start_time(os.getpid())
    b = status._get_process_start_time(os.getpid())
    assert a is not None
    assert a == b
