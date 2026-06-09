"""Behavioral tests for Windows-specific compatibility fixes.

Complements ``tests/tools/test_windows_compat.py`` (which does source-level
pattern linting) with cross-platform-mocked tests that exercise the actual
code paths Hermes takes on native Windows.

Runs on Linux CI — every test mocks ``sys.platform``, ``subprocess.run``,
and ``os.kill`` as needed to simulate Windows behavior without requiring a
Windows runner.
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# configure_windows_stdio
# ---------------------------------------------------------------------------


class TestConfigureWindowsStdio:
    """``hermes_cli.stdio.configure_windows_stdio`` wiring.

    The function must:
    - be a no-op on non-Windows
    - only configure once per process (idempotent)
    - set PYTHONIOENCODING / PYTHONUTF8 without overriding explicit user settings
    - reconfigure sys.stdout/stderr/stdin to UTF-8 on Windows
    - flip the console code page to CP_UTF8 (65001) via ctypes
    - respect HERMES_DISABLE_WINDOWS_UTF8 opt-out
    """

    @pytest.fixture(autouse=True)
    def _reset_configured(self, monkeypatch):
        """Reload the module before each test so the _CONFIGURED flag resets."""
        # Remove from sys.modules so import triggers a fresh load
        sys.modules.pop("hermes_cli.stdio", None)
        # Fresh import now; tests import from hermes_cli.stdio themselves,
        # but this guarantees the module they get is a brand-new copy.
        import hermes_cli.stdio as _s
        _s._CONFIGURED = False
        yield
        sys.modules.pop("hermes_cli.stdio", None)

    def test_no_op_on_posix(self):
        from hermes_cli import stdio

        assert stdio.is_windows() is False
        result = stdio.configure_windows_stdio()
        assert result is False

    def test_idempotent(self):
        from hermes_cli import stdio

        stdio.configure_windows_stdio()
        # Second call returns False because _CONFIGURED is set
        assert stdio.configure_windows_stdio() is False

    def test_windows_path_sets_env_and_reconfigures_streams(self, monkeypatch):
        from hermes_cli import stdio

        monkeypatch.setattr(stdio, "is_windows", lambda: True)
        # Pretend the user has no prior setting
        monkeypatch.delenv("PYTHONIOENCODING", raising=False)
        monkeypatch.delenv("PYTHONUTF8", raising=False)
        monkeypatch.delenv("HERMES_DISABLE_WINDOWS_UTF8", raising=False)
        monkeypatch.delenv("EDITOR", raising=False)
        monkeypatch.delenv("VISUAL", raising=False)

        reconfigure_calls = []

        def fake_reconfigure(stream, *, encoding="utf-8", errors="replace"):
            reconfigure_calls.append((stream, encoding, errors))

        cp_calls = []

        def fake_flip():
            cp_calls.append(True)

        monkeypatch.setattr(stdio, "_reconfigure_stream", fake_reconfigure)
        monkeypatch.setattr(stdio, "_flip_console_code_page_to_utf8", fake_flip)
        # Pretend notepad.exe is on PATH (it always is on real Windows hosts,
        # but not on the Linux CI runner — mock it so the editor default
        # survives).
        monkeypatch.setattr(stdio, "_default_windows_editor", lambda: "notepad")

        result = stdio.configure_windows_stdio()
        assert result is True
        assert os.environ.get("PYTHONIOENCODING") == "utf-8"
        assert os.environ.get("PYTHONUTF8") == "1"
        # EDITOR must be set so prompt_toolkit's open_in_editor finds
        # a working program on Windows (it defaults to /usr/bin/nano).
        assert os.environ.get("EDITOR") == "notepad"
        assert len(cp_calls) == 1  # SetConsoleOutputCP path hit
        assert len(reconfigure_calls) == 3  # stdout, stderr, stdin

    def test_respects_existing_editor_var(self, monkeypatch):
        """User's explicit EDITOR wins over our default."""
        from hermes_cli import stdio

        monkeypatch.setattr(stdio, "is_windows", lambda: True)
        monkeypatch.setenv("EDITOR", "code --wait")
        monkeypatch.setattr(stdio, "_reconfigure_stream", lambda *a, **kw: None)
        monkeypatch.setattr(stdio, "_flip_console_code_page_to_utf8", lambda: None)
        monkeypatch.setattr(stdio, "_default_windows_editor", lambda: "notepad")

        stdio.configure_windows_stdio()
        assert os.environ["EDITOR"] == "code --wait"

    def test_respects_existing_visual_var(self, monkeypatch):
        """VISUAL takes precedence over our EDITOR default too."""
        from hermes_cli import stdio

        monkeypatch.setattr(stdio, "is_windows", lambda: True)
        monkeypatch.delenv("EDITOR", raising=False)
        monkeypatch.setenv("VISUAL", "nvim")
        monkeypatch.setattr(stdio, "_reconfigure_stream", lambda *a, **kw: None)
        monkeypatch.setattr(stdio, "_flip_console_code_page_to_utf8", lambda: None)
        monkeypatch.setattr(stdio, "_default_windows_editor", lambda: "notepad")

        stdio.configure_windows_stdio()
        # EDITOR should NOT be set when VISUAL already is (prompt_toolkit
        # checks VISUAL first anyway, but we also shouldn't override it).
        assert os.environ.get("EDITOR", "") != "notepad"
        assert os.environ["VISUAL"] == "nvim"

    def test_respects_existing_env_var(self, monkeypatch):
        """User's explicit PYTHONIOENCODING wins over our default."""
        from hermes_cli import stdio

        monkeypatch.setattr(stdio, "is_windows", lambda: True)
        monkeypatch.setenv("PYTHONIOENCODING", "latin-1")
        monkeypatch.setattr(stdio, "_reconfigure_stream", lambda *a, **kw: None)
        monkeypatch.setattr(stdio, "_flip_console_code_page_to_utf8", lambda: None)

        stdio.configure_windows_stdio()
        assert os.environ["PYTHONIOENCODING"] == "latin-1"

    @pytest.mark.parametrize("optout", ["1", "true", "True", "yes"])
    def test_disable_flag_short_circuits(self, monkeypatch, optout):
        from hermes_cli import stdio

        monkeypatch.setattr(stdio, "is_windows", lambda: True)
        monkeypatch.setenv("HERMES_DISABLE_WINDOWS_UTF8", optout)

        reconfigure_hit = []
        monkeypatch.setattr(
            stdio,
            "_reconfigure_stream",
            lambda *a, **kw: reconfigure_hit.append(True),
        )

        result = stdio.configure_windows_stdio()
        assert result is False
        assert reconfigure_hit == [], "opt-out must skip stream reconfiguration"

    def test_reconfigure_stream_handles_missing_method(self, monkeypatch):
        """StringIO-like objects without .reconfigure() must not blow up."""
        from hermes_cli import stdio
        import io

        buf = io.StringIO()
        # Must not raise
        stdio._reconfigure_stream(buf)


# ---------------------------------------------------------------------------
# terminate_pid — the centralized kill primitive
# ---------------------------------------------------------------------------


class TestTerminatePidRoutingOnWindows:
    """``gateway.status.terminate_pid`` must use taskkill /T /F on Windows.

    On Linux we can't reload gateway/status with sys.platform=win32 because
    the module unconditionally imports ``msvcrt`` in that branch.  Instead
    we patch the module-level ``_IS_WINDOWS`` flag and ``subprocess.run``
    on the already-loaded module, which exercises the same branching code.
    """

    def test_force_uses_taskkill_on_windows(self, monkeypatch):
        from gateway import status

        captured = {}

        def fake_run(args, **kwargs):
            captured["args"] = args
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            result.stdout = ""
            return result

        monkeypatch.setattr(status, "_IS_WINDOWS", True)
        monkeypatch.setattr(status.subprocess, "run", fake_run)
        status.terminate_pid(12345, force=True)

        assert captured["args"][0] == "taskkill"
        assert "/PID" in captured["args"]
        assert "12345" in captured["args"]
        assert "/T" in captured["args"]
        assert "/F" in captured["args"]

    def test_force_taskkill_failure_raises_oserror(self, monkeypatch):
        from gateway import status

        def fake_run(args, **kwargs):
            result = MagicMock()
            result.returncode = 128
            result.stderr = "ERROR: The process cannot be terminated."
            result.stdout = ""
            return result

        monkeypatch.setattr(status, "_IS_WINDOWS", True)
        monkeypatch.setattr(status.subprocess, "run", fake_run)
        with pytest.raises(OSError, match="cannot be terminated"):
            status.terminate_pid(12345, force=True)

    def test_graceful_on_windows_uses_os_kill_sigterm(self, monkeypatch):
        """Non-force path calls os.kill with SIGTERM (Windows has no SIGKILL).

        ``terminate_pid(pid)`` with force=False bypasses the taskkill branch
        and uses ``os.kill`` directly — so platform doesn't actually matter
        for the signal choice.  Verifies the getattr fallback works.
        """
        from gateway import status

        captured = {}

        def fake_kill(pid, sig):
            captured["pid"] = pid
            captured["sig"] = sig

        monkeypatch.setattr(status.os, "kill", fake_kill)
        status.terminate_pid(99, force=False)

        assert captured["pid"] == 99
        assert captured["sig"] == signal.SIGTERM

    def test_taskkill_not_found_falls_back_to_os_kill(self, monkeypatch):
        """On Windows without taskkill (WinPE, containers), fall back gracefully."""
        from gateway import status

        captured = {}

        def fake_run(args, **kwargs):
            raise FileNotFoundError(2, "taskkill not found")

        def fake_kill(pid, sig):
            captured["pid"] = pid
            captured["sig"] = sig

        monkeypatch.setattr(status, "_IS_WINDOWS", True)
        monkeypatch.setattr(status.subprocess, "run", fake_run)
        monkeypatch.setattr(status.os, "kill", fake_kill)
        status.terminate_pid(42, force=True)

        assert captured["pid"] == 42
        assert captured["sig"] == signal.SIGTERM


# ---------------------------------------------------------------------------
# SIGKILL fallback pattern
# ---------------------------------------------------------------------------


class TestSigkillFallback:
    """Modules that want SIGKILL must fall back to SIGTERM when absent."""

    def test_getattr_fallback_works_when_sigkill_missing(self, monkeypatch):
        """The `getattr(signal, "SIGKILL", signal.SIGTERM)` pattern."""
        # Build a stand-in signal module with no SIGKILL attribute
        fake_signal = MagicMock()
        del fake_signal.SIGKILL  # ensure it's absent
        fake_signal.SIGTERM = 15

        result = getattr(fake_signal, "SIGKILL", fake_signal.SIGTERM)
        assert result == 15

    def test_getattr_fallback_prefers_sigkill_when_present(self):
        """On POSIX the fallback is a no-op: real SIGKILL wins."""
        result = getattr(signal, "SIGKILL", signal.SIGTERM)
        assert result == signal.SIGKILL

    @pytest.mark.parametrize(
        "module_path, line_pattern",
        [
            ("hermes_cli.kanban_db", 'getattr(signal, "SIGKILL", signal.SIGTERM)'),
        ],
    )
    def test_module_uses_getattr_fallback(self, module_path, line_pattern):
        """Source-level check that our modules use the safe fallback."""
        rel = module_path.replace(".", "/") + ".py"
        root = Path(__file__).resolve().parents[2]
        source = (root / rel).read_text(encoding="utf-8")
        assert line_pattern in source, (
            f"{rel} must use the getattr fallback pattern on its SIGKILL site"
        )


# ---------------------------------------------------------------------------
# OSError widening on liveness probes
#
# Post-#21561, ``ProcessRegistry._is_host_pid_alive`` delegates to
# ``gateway.status._pid_exists``, which is the cross-platform liveness
# primitive (psutil-first, ctypes/os.kill fallback). The tests below assert
# (a) the delegation is correct and (b) ``_pid_exists`` correctly widens
# Windows' ``OSError(WinError 87)`` / ``PermissionError`` behavior on the
# POSIX fallback branch.
# ---------------------------------------------------------------------------


class TestProcessRegistryOSErrorWidening:
    """_is_host_pid_alive delegates to gateway.status._pid_exists."""

    def test_oserror_treated_as_not_alive(self, monkeypatch):
        """_pid_exists → False propagates as _is_host_pid_alive → False."""
        from tools.process_registry import ProcessRegistry

        monkeypatch.setattr("gateway.status._pid_exists", lambda pid: False)
        assert ProcessRegistry._is_host_pid_alive(12345) is False

    def test_permission_error_treated_as_alive(self, monkeypatch):
        """PermissionError is encoded by _pid_exists as alive=True; propagates as-is.

        This is a meaningful semantic change from the pre-#21561 version of
        this test (which asserted PermissionError → not-alive). The old
        ``os.kill(pid, 0)``-based probe couldn't distinguish "gone" from
        "owned by another user" on some platforms, so it conservatively
        returned False. The new psutil-based probe CAN distinguish them via
        ``OpenProcess + ERROR_ACCESS_DENIED`` on Windows / ``except
        PermissionError`` on POSIX, so alive=True is correct.
        """
        from tools.process_registry import ProcessRegistry

        monkeypatch.setattr("gateway.status._pid_exists", lambda pid: True)
        assert ProcessRegistry._is_host_pid_alive(12345) is True

    def test_zero_or_none_pid_returns_false_without_probing(self, monkeypatch):
        """No wasted syscall on falsy pids."""
        from tools.process_registry import ProcessRegistry

        probes = []
        monkeypatch.setattr(
            "gateway.status._pid_exists",
            lambda pid: probes.append(pid) or True,
        )
        assert ProcessRegistry._is_host_pid_alive(None) is False
        assert ProcessRegistry._is_host_pid_alive(0) is False
        assert probes == []

    def test_alive_pid_returns_true(self, monkeypatch):
        from tools.process_registry import ProcessRegistry

        monkeypatch.setattr("gateway.status._pid_exists", lambda pid: True)
        assert ProcessRegistry._is_host_pid_alive(os.getpid()) is True


class TestPidExistsOSErrorWidening:
    """gateway.status._pid_exists itself must widen Windows errors correctly.

    The POSIX fallback branch (reached when psutil isn't importable) is the
    only path where Python raises ``OSError(WinError 87)`` on Windows for a
    gone PID instead of ``ProcessLookupError``. The function must catch the
    wider ``OSError`` to match POSIX semantics.
    """

    def test_oserror_gone_pid_returns_false(self, monkeypatch):
        """Simulate Windows' OSError(WinError 87) for a gone PID via the POSIX fallback."""
        from gateway import status

        # Force the psutil-first branch to miss so we exercise the fallback.
        monkeypatch.setitem(
            __import__("sys").modules, "psutil",
            type("P", (), {"pid_exists": staticmethod(lambda pid: (_ for _ in ()).throw(ImportError()))})()
        )
        monkeypatch.setattr(status, "_IS_WINDOWS", False)

        def fake_kill(pid, sig):
            raise OSError(22, "Invalid argument")

        monkeypatch.setattr(status.os, "kill", fake_kill)
        assert status._pid_exists(12345) is False

    def test_permission_error_returns_true(self, monkeypatch):
        """POSIX fallback: PermissionError means alive (owned by another user)."""
        from gateway import status

        monkeypatch.setitem(
            __import__("sys").modules, "psutil",
            type("P", (), {"pid_exists": staticmethod(lambda pid: (_ for _ in ()).throw(ImportError()))})()
        )
        monkeypatch.setattr(status, "_IS_WINDOWS", False)

        def fake_kill(pid, sig):
            raise PermissionError(1, "Operation not permitted")

        monkeypatch.setattr(status.os, "kill", fake_kill)
        assert status._pid_exists(12345) is True


# ---------------------------------------------------------------------------
# tzdata dependency
# ---------------------------------------------------------------------------


class TestTzdataDependencyDeclared:
    """Windows installs must pull tzdata for zoneinfo to work."""

    def test_pyproject_declares_tzdata_for_win32(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "pyproject.toml").read_text(encoding="utf-8")
        # The dependency line should be conditional on sys_platform == 'win32'
        # and should NOT be in the core dependencies for Linux/macOS. We do
        # not care about the exact pinned version (which is bumped over time)
        # — only that tzdata is declared with a win32 marker. This is an
        # invariant check, not a snapshot test.
        import re
        # Match `"tzdata` … `; sys_platform == 'win32'"` allowing any version
        # specifier in between (==X.Y.Z, >=X.Y.Z,<W, etc.) and either quote
        # style on the marker.
        pattern = re.compile(
            r'"tzdata[^"]*;\s*sys_platform\s*==\s*[\'"]win32[\'"]\s*"'
        )
        assert pattern.search(source), (
            "tzdata must be a Windows-only dep in pyproject.toml dependencies "
            "(declared with a `; sys_platform == 'win32'` marker)"
        )


# ---------------------------------------------------------------------------
# README / docs consistency
# ---------------------------------------------------------------------------


class TestReadmeNoLongerSaysWindowsUnsupported:
    """The README shouldn't claim native Windows isn't supported."""

    def test_readme_does_not_say_not_supported(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "README.md").read_text(encoding="utf-8")
        # Previous string (removed in this PR): "Native Windows is not supported"
        assert "Native Windows is not supported" not in source, (
            "README.md still says native Windows is not supported — update the "
            "install copy to reflect the PowerShell installer."
        )

    def test_readme_mentions_powershell_installer(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "README.md").read_text(encoding="utf-8")
        assert "install.ps1" in source, (
            "README.md must point at scripts/install.ps1 for Windows users"
        )


# ---------------------------------------------------------------------------
# pty_bridge graceful import on Windows
# ---------------------------------------------------------------------------


class TestWebServerPtyBridgeGuard:
    """The web server must not crash if pty_bridge can't import (Windows)."""

    def test_import_guard_present_in_source(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "hermes_cli" / "web_server.py").read_text(encoding="utf-8")
        assert "_PTY_BRIDGE_AVAILABLE" in source
        assert "except ImportError" in source, (
            "web_server.py must wrap the pty_bridge import in try/except ImportError"
        )

    def test_pty_handler_checks_availability_flag(self):
        """The /api/pty handler must short-circuit when the bridge is unavailable."""
        root = Path(__file__).resolve().parents[2]
        source = (root / "hermes_cli" / "web_server.py").read_text(encoding="utf-8")
        assert "if not _PTY_BRIDGE_AVAILABLE" in source, (
            "/api/pty handler must return a friendly error when PTY is unavailable"
        )


# ---------------------------------------------------------------------------
# Entry points wire configure_windows_stdio
# ---------------------------------------------------------------------------


class TestEntryPointsConfigureStdio:
    """cli.py, hermes_cli/main.py, gateway/run.py must call configure_windows_stdio."""

    @pytest.mark.parametrize(
        "relpath",
        ["cli.py", "hermes_cli/main.py", "gateway/run.py"],
    )
    def test_entry_point_calls_configure_stdio(self, relpath):
        root = Path(__file__).resolve().parents[2]
        source = (root / relpath).read_text(encoding="utf-8")
        assert "configure_windows_stdio" in source, (
            f"{relpath} must call hermes_cli.stdio.configure_windows_stdio() "
            "early in startup so Windows consoles render Unicode without crashing"
        )


# ---------------------------------------------------------------------------
# _subprocess_compat shared helpers
# ---------------------------------------------------------------------------


class TestSubprocessCompatHelpers:
    """hermes_cli/_subprocess_compat.py POSIX + Windows behaviour."""

    def test_is_windows_matches_sys_platform(self):
        from hermes_cli import _subprocess_compat as sc
        assert sc.IS_WINDOWS == (sys.platform == "win32")

    def test_resolve_node_command_returns_absolute_on_posix(self):
        """On Linux, resolve_node_command('sh', ['-c','echo hi']) picks up /bin/sh."""
        from hermes_cli._subprocess_compat import resolve_node_command
        # We can't assert "npm is on PATH" portably; use `sh` which is
        # guaranteed on POSIX.  On Windows the test only confirms the
        # no-crash fallback path.
        argv = resolve_node_command("sh", ["-c", "echo hi"])
        assert argv[1:] == ["-c", "echo hi"]
        # First element is either an absolute path (sh found) or the bare
        # name (fallback) — both are acceptable behaviours.

    def test_resolve_node_command_fallback_when_absent(self):
        from hermes_cli._subprocess_compat import resolve_node_command
        argv = resolve_node_command(
            "zzz-definitely-not-on-path-xyzzy", ["--help"]
        )
        # Must fall back to the bare name — NOT return None, NOT crash.
        assert argv[0] == "zzz-definitely-not-on-path-xyzzy"
        assert argv[1:] == ["--help"]

    def test_windows_flags_zero_on_posix(self):
        from hermes_cli._subprocess_compat import (
            windows_detach_flags,
            windows_detach_flags_without_breakaway,
            windows_hide_flags,
        )
        if sys.platform != "win32":
            assert windows_detach_flags() == 0
            assert windows_detach_flags_without_breakaway() == 0
            assert windows_hide_flags() == 0

    def test_windows_detach_popen_kwargs_is_posix_equivalent_on_posix(self):
        from hermes_cli._subprocess_compat import windows_detach_popen_kwargs
        kwargs = windows_detach_popen_kwargs()
        if sys.platform != "win32":
            # POSIX path MUST produce start_new_session=True, which maps to
            # os.setsid() in the child — identical to the unchanged main
            # branch behaviour.  Do NOT break Linux/macOS here.
            assert kwargs == {"start_new_session": True}
        else:
            # Windows path must include creationflags with all 4 bits set
            # (including CREATE_BREAKAWAY_FROM_JOB — see the dedicated
            # breakaway test below for the rationale).
            assert "creationflags" in kwargs
            assert kwargs["creationflags"] != 0
            # No start_new_session on Windows (silently no-op there).
            assert "start_new_session" not in kwargs

    def test_windows_detach_flags_has_expected_win32_bits(self, monkeypatch):
        """Simulate Windows to verify flag bundle."""
        from hermes_cli import _subprocess_compat as sc
        monkeypatch.setattr(sc, "IS_WINDOWS", True)
        flags = sc.windows_detach_flags()
        # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_NO_WINDOW |
        # CREATE_BREAKAWAY_FROM_JOB
        assert flags & 0x00000200, "missing CREATE_NEW_PROCESS_GROUP"
        assert flags & 0x00000008, "missing DETACHED_PROCESS"
        assert flags & 0x08000000, "missing CREATE_NO_WINDOW"
        assert flags & 0x01000000, "missing CREATE_BREAKAWAY_FROM_JOB"

    def test_windows_detach_flags_includes_breakaway_from_job(self, monkeypatch):
        """CREATE_BREAKAWAY_FROM_JOB is load-bearing for the GUI-driven update path.

        Without it, the gateway-respawn watcher spawned by ``hermes update``
        (which runs under hermes-setup.exe, itself a grandchild of the
        Electron Desktop app) gets reaped when Electron exits and its
        Win32 job object is torn down by the OS.  Result: gateway dies
        during update and never comes back.

        Regression guard against accidentally dropping the breakaway bit
        from the default detach bundle.  This was fixed in
        ``fix/windows-gateway-reliability`` (PR #40909) and the bit must
        stay in the default bundle going forward.
        """
        from hermes_cli import _subprocess_compat as sc
        monkeypatch.setattr(sc, "IS_WINDOWS", True)
        assert sc.windows_detach_flags() & 0x01000000, (
            "CREATE_BREAKAWAY_FROM_JOB (0x01000000) must remain in the "
            "default detach flag bundle so the Desktop GUI update flow "
            "can respawn the gateway after Electron exits."
        )

    def test_windows_detach_flags_without_breakaway_drops_only_that_bit(
        self, monkeypatch
    ):
        """Fallback retry payload for restrictive job objects.

        Some Windows Terminal / container / kiosk configurations refuse
        CREATE_BREAKAWAY_FROM_JOB with ERROR_ACCESS_DENIED.  Callers
        catch ``OSError`` and retry with this payload (see
        ``gateway_windows._spawn_detached`` for the canonical pattern).
        It must drop ONLY the breakaway bit — DETACHED_PROCESS et al.
        are still required for the child to survive the parent's exit.
        """
        from hermes_cli import _subprocess_compat as sc
        monkeypatch.setattr(sc, "IS_WINDOWS", True)
        full = sc.windows_detach_flags()
        fallback = sc.windows_detach_flags_without_breakaway()
        # Fallback equals full minus the breakaway bit, nothing else changed.
        assert fallback == full & ~0x01000000
        # And the three "detach" bits we still need are present.
        assert fallback & 0x00000200, "fallback missing CREATE_NEW_PROCESS_GROUP"
        assert fallback & 0x00000008, "fallback missing DETACHED_PROCESS"
        assert fallback & 0x08000000, "fallback missing CREATE_NO_WINDOW"


# ---------------------------------------------------------------------------
# tui_gateway/entry.py signal installation survives absent POSIX signals
# ---------------------------------------------------------------------------


class TestTuiGatewayEntrySignalGuards:
    """Importing tui_gateway.entry must not crash when SIGPIPE/SIGHUP absent.

    Linux has both signals, so this is mostly a source-level invariant check
    (no bare ``signal.SIGPIPE`` at module level without a ``hasattr`` guard).
    On Windows the import would have raised AttributeError before this fix.
    """

    def test_source_guards_each_signal_installation(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "tui_gateway" / "entry.py").read_text(encoding="utf-8")
        # Every signal.signal(...) at module scope must be preceded by a
        # hasattr check.  We look at the text: no bare "signal.signal("
        # call should appear outside a function body without a guard.
        # Simpler heuristic: all SIGPIPE / SIGHUP references outside the
        # dict-building loop must be wrapped in hasattr.
        assert 'hasattr(signal, "SIGPIPE")' in source
        assert 'hasattr(signal, "SIGHUP")' in source
        assert 'hasattr(signal, "SIGTERM")' in source
        assert 'hasattr(signal, "SIGINT")' in source

    def test_module_imports_cleanly(self):
        """Importing the module must not raise — verifies the guards work."""
        # Drop any cached import so the module re-initialises
        for mod in list(sys.modules):
            if mod.startswith("tui_gateway"):
                del sys.modules[mod]
        import tui_gateway.entry  # noqa: F401  # must not raise


# ---------------------------------------------------------------------------
# hermes_cli/kanban_db.py waitpid guard
# ---------------------------------------------------------------------------


class TestKanbanWaitpidWindowsGuard:
    """os.WNOHANG doesn't exist on Windows — the dispatcher tick reap loop
    must be gated behind ``os.name != "nt"``."""

    def test_source_gates_waitpid_loop(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "hermes_cli" / "kanban_db.py").read_text(encoding="utf-8")
        # Find the waitpid call and confirm it's inside a POSIX gate.
        idx = source.find("os.waitpid(-1, os.WNOHANG)")
        assert idx > 0, "waitpid call must exist"
        # Look backwards up to 400 chars for the gate. Accept either form:
        #   `if os.name != "nt":` (run iff POSIX), or
        #   `if os.name == "nt": return []` (early-return guard).
        # Both correctly keep the waitpid loop off Windows; the early-return
        # form is stronger because the rest of the function never runs.
        preamble = source[max(0, idx - 400):idx]
        guard_patterns = (
            'os.name != "nt"',
            "os.name != 'nt'",
            'os.name == "nt"',  # early-return guard
            "os.name == 'nt'",
        )
        assert any(p in preamble for p in guard_patterns), (
            "os.waitpid(-1, os.WNOHANG) must sit behind an os.name guard "
            f"(checked patterns: {guard_patterns})"
        )


# ---------------------------------------------------------------------------
# code_execution_tool TCP loopback on Windows
# ---------------------------------------------------------------------------


class TestCodeExecutionTransportTcpFallback:
    """The RPC transport must fall back to TCP on Windows.

    We can't easily execute the sandbox on Linux CI in Windows mode, but we
    CAN assert that the generated client module supports both AF_UNIX and
    AF_INET endpoints based on the HERMES_RPC_SOCKET format.
    """

    def test_generated_client_handles_tcp_endpoint(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "tools" / "code_execution_tool.py").read_text(encoding="utf-8")
        # _UDS_TRANSPORT_HEADER body must parse both transports.
        assert 'endpoint.startswith("tcp://")' in source, (
            "generated sandbox client must accept tcp:// endpoints for Windows"
        )
        assert "socket.AF_INET" in source, (
            "generated sandbox client must be able to open AF_INET sockets"
        )

    def test_server_side_branches_on_use_tcp_rpc(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "tools" / "code_execution_tool.py").read_text(encoding="utf-8")
        assert "_use_tcp_rpc = _IS_WINDOWS" in source
        assert 'rpc_endpoint = f"tcp://{_host}:{_port}"' in source


# ---------------------------------------------------------------------------
# cron/scheduler.py /bin/bash dynamic resolution
# ---------------------------------------------------------------------------


class TestCronSchedulerBashResolution:
    """cron.scheduler must NOT hardcode /bin/bash — .sh scripts need a
    dynamically-resolved bash so Windows (Git Bash) works."""

    def test_source_uses_shutil_which_for_bash(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "cron" / "scheduler.py").read_text(encoding="utf-8")
        # The old hardcoded path should be gone as the sole bash source.
        # It may still appear as a POSIX fallback after shutil.which(), so
        # we check for the shutil.which call near the .sh/.bash branch.
        assert 'shutil.which("bash")' in source, (
            "cron.scheduler must resolve bash dynamically via shutil.which"
        )

    def test_error_message_when_bash_missing(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "cron" / "scheduler.py").read_text(encoding="utf-8")
        # The graceful-failure message must mention "bash not found" so
        # Windows users without Git Bash see an actionable error instead
        # of a WinError 2 traceback.
        assert "bash not found" in source.lower()


# ---------------------------------------------------------------------------
# Node-ecosystem launcher resolution (npm / npx / node)
# ---------------------------------------------------------------------------


class TestNpmBareSpawnsResolved:
    """Every spawn site that launches ``npm``/``npx`` must resolve via
    shutil.which / hermes_cli._subprocess_compat.resolve_node_command
    so Windows can execute the .cmd batch shims."""

    @pytest.mark.parametrize(
        "relpath",
        [
            "hermes_cli/tools_config.py",
            "hermes_cli/doctor.py",
            "gateway/platforms/whatsapp.py",
            "tools/browser_tool.py",
        ],
    )
    def test_no_bare_npm_or_npx_in_popen_argv(self, relpath):
        """Reject ``subprocess.run(["npm", ...])`` / ``["npx", ...]`` patterns.

        Those fail on Windows with WinError 193.  Callers must resolve
        via shutil.which(...) and pass the absolute path (or fall back
        to the bare name only as a last resort behind a variable).
        """
        root = Path(__file__).resolve().parents[2]
        source = (root / relpath).read_text(encoding="utf-8")
        # The forbidden literal: a subprocess invocation that names npm
        # or npx as a bare string inside an argv list.
        forbidden_patterns = [
            '["npm",',
            '["npx",',
            "['npm',",
            "['npx',",
        ]
        for pat in forbidden_patterns:
            # Exception: strings inside error-message text or comments are fine.
            # We only fail if the literal appears in an argv position, which
            # we approximate by checking it isn't inside a print/log/comment.
            # Find all occurrences and verify they're behind shutil.which.
            idx = 0
            while True:
                idx = source.find(pat, idx)
                if idx < 0:
                    break
                # Look at the preceding 120 chars — if "shutil.which" appears
                # there, or the pattern is inside a comment/string, it's fine.
                context = source[max(0, idx - 120):idx]
                if "#" in context.split("\n")[-1]:
                    idx += len(pat)
                    continue
                # Argv forms that START with a bare npm/npx are the bug.
                raise AssertionError(
                    f"{relpath}: bare {pat!r} still present at offset {idx} — "
                    f"resolve via shutil.which(...) so Windows can execute .cmd shims"
                )


# ---------------------------------------------------------------------------
# tools/environments/local.py Windows temp dir & PATH injection
# ---------------------------------------------------------------------------


class TestLocalEnvironmentWindowsTempDir:
    """LocalEnvironment.get_temp_dir must return a native Windows path on
    Windows, NOT the POSIX ``/tmp`` literal (which Python can't open)."""

    def test_posix_path_preserved_on_linux(self):
        """Linux/macOS behaviour MUST be unchanged — return / tmp or
        tempfile.gettempdir()-derived POSIX path.  This is the 'do no harm'
        test — regressions here break every Unix user's terminal tool."""
        from tools.environments.local import LocalEnvironment

        env = LocalEnvironment(cwd="/tmp", timeout=10, env={})
        tmp_dir = env.get_temp_dir()
        if sys.platform != "win32":
            assert tmp_dir.startswith("/"), (
                f"POSIX temp dir must start with '/'; got {tmp_dir!r}"
            )

    def test_source_has_windows_branch_using_hermes_home(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "tools" / "environments" / "local.py").read_text(encoding="utf-8")
        assert "if _IS_WINDOWS:" in source
        assert "get_hermes_home" in source
        assert 'cache_dir = get_hermes_home() / "cache" / "terminal"' in source


class TestLocalEnvironmentPathInjectionGated:
    """Sane PATH completion must stay POSIX-only."""

    def test_windows_path_is_left_unchanged(self, monkeypatch):
        from tools.environments import local as local_mod
        from tools.environments.local import _append_missing_sane_path_entries

        monkeypatch.setattr(local_mod, "_IS_WINDOWS", True)
        path = r"C:\Windows\System32;C:\Program Files\Git\bin"
        assert _append_missing_sane_path_entries(path) == path


# ---------------------------------------------------------------------------
# cli.py git path normalization
# ---------------------------------------------------------------------------


class TestGitBashPathNormalization:
    """_normalize_git_bash_path should turn /c/Users/... into C:\\Users\\...
    on Windows and leave paths unchanged on POSIX."""

    def test_posix_noop(self):
        """Must NOT mutate paths on Linux/macOS."""
        from cli import _normalize_git_bash_path
        if sys.platform != "win32":
            assert _normalize_git_bash_path("/home/teknium/foo") == "/home/teknium/foo"
            assert _normalize_git_bash_path("/c/Users/foo") == "/c/Users/foo"
            assert _normalize_git_bash_path("C:/Users/foo") == "C:/Users/foo"
            assert _normalize_git_bash_path(None) is None

    def test_empty_string_preserved(self):
        from cli import _normalize_git_bash_path
        assert _normalize_git_bash_path("") == ""

    def test_windows_translation(self, monkeypatch):
        """Simulate Windows and verify /c/Users/... becomes C:\\Users\\..."""
        import cli as cli_mod
        monkeypatch.setattr(cli_mod.sys, "platform", "win32")
        assert cli_mod._normalize_git_bash_path("/c/Users/foo") == r"C:\Users\foo"
        assert cli_mod._normalize_git_bash_path("/C/Users/foo") == r"C:\Users\foo"
        assert cli_mod._normalize_git_bash_path("/cygdrive/d/data") == r"D:\data"
        assert cli_mod._normalize_git_bash_path("/mnt/c/Users") == r"C:\Users"
        # Already-native path is preserved
        assert cli_mod._normalize_git_bash_path(r"C:\Users\foo") == r"C:\Users\foo"
        # Forward-slash Windows path is preserved (git on Windows often
        # returns this form; it's valid for both bash and Python, so we
        # don't need to translate).
        assert cli_mod._normalize_git_bash_path("C:/Users/foo") == "C:/Users/foo"


class TestWorktreeSymlinkFallback:
    """.worktreeinclude directory symlinks must fall back to copytree on
    Windows (where symlink creation requires admin / Dev Mode)."""

    def test_source_has_symlink_fallback(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "cli.py").read_text(encoding="utf-8")
        # Look for the try/except that handles OSError around os.symlink
        # with a shutil.copytree fallback.
        assert "os.symlink(str(src_resolved), str(dst))" in source
        assert "except (OSError, NotImplementedError)" in source
        assert "shutil.copytree" in source
        assert 'sys.platform == "win32"' in source


# ---------------------------------------------------------------------------
# Gateway detached watcher — Windows creationflags
# ---------------------------------------------------------------------------


class TestGatewayDetachedWatcherWindowsFlags:
    """launch_detached_profile_gateway_restart and the in-gateway update
    launcher must use CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS on
    Windows, not silent start_new_session=True."""

    def test_hermes_cli_gateway_uses_compat_kwargs(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "hermes_cli" / "gateway.py").read_text(encoding="utf-8")
        assert "windows_detach_popen_kwargs" in source, (
            "hermes_cli/gateway.py must use the platform-aware detach helper"
        )
        # The legacy start_new_session=True on the outer Popen should be
        # replaced by **windows_detach_popen_kwargs(). Inside the watcher
        # STRING the old pattern is replaced by explicit creationflags.
        assert "**windows_detach_popen_kwargs()" in source

    def test_gateway_run_update_has_windows_branch(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "gateway" / "run.py").read_text(encoding="utf-8")
        # Both the /restart and /update paths must have sys.platform=='win32' branches.
        assert 'if sys.platform == "win32":' in source
        # Windows branch uses windows_detach_popen_kwargs
        assert "windows_detach_popen_kwargs" in source

    def test_launch_detached_profile_gateway_restart_inlined_watcher_uses_breakaway(self):
        """The inlined respawn script (stringified Python passed to ``python -c``)
        must include CREATE_BREAKAWAY_FROM_JOB so the *respawned gateway* also
        breaks away from any job-object the watcher itself inherits.

        Static check — the watcher source is built at import time and embedded
        verbatim in the module text.  Parsing it for an exact AST node would be
        brittle; the textual presence of the hex flag plus the symbolic name is
        a sufficient regression guard.

        The bit was added to the inlined payload by PR #40909.  This test
        ensures a future refactor of the dedent block doesn't silently drop it.
        """
        root = Path(__file__).resolve().parents[2]
        text = (root / "hermes_cli" / "gateway.py").read_text(encoding="utf-8")
        marker = "watcher = textwrap.dedent("
        idx = text.find(marker)
        assert idx != -1, "watcher block not found in gateway.py"
        end = text.find(").strip()", idx)
        assert end != -1, "watcher block end not found"
        block = text[idx:end]
        assert "0x01000000" in block, (
            "Inlined respawn watcher must set CREATE_BREAKAWAY_FROM_JOB "
            "(0x01000000) on the respawned gateway — without it, the new "
            "gateway is reaped when the parent job is torn down."
        )
        assert "_CREATE_BREAKAWAY_FROM_JOB" in block, (
            "Inlined respawn watcher must name CREATE_BREAKAWAY_FROM_JOB "
            "symbolically so the intent is greppable."
        )

    def test_launch_detached_profile_gateway_restart_outer_popen_has_access_denied_fallback(
        self,
    ):
        """When the outer watcher Popen raises OSError (breakaway denied by
        the parent job object), the watcher launch must retry without the
        breakaway bit instead of giving up.

        This mirrors the canonical pattern in
        ``gateway_windows._spawn_detached`` and brings the post-update
        watcher path into parity with the gateway-start path: a
        breakaway-denied job object on the parent process (rare but
        possible on Windows Terminal with restrictive job settings,
        containers, kiosk-mode shells) shouldn't take out the entire
        gateway-respawn chain.

        Static check — without standing up a real Windows job object
        with breakaway forbidden, we can't trigger the OSError in a unit
        test.  The textual presence of the fallback helper import +
        ``windows_detach_flags_without_breakaway`` in the fallback path
        is the regression guard.
        """
        root = Path(__file__).resolve().parents[2]
        text = (root / "hermes_cli" / "gateway.py").read_text(encoding="utf-8")
        assert "windows_detach_flags_without_breakaway" in text, (
            "launch_detached_profile_gateway_restart must import "
            "windows_detach_flags_without_breakaway so it can retry a "
            "breakaway-denied Popen without giving up on the watcher."
        )
        # And the inlined watcher's respawn must also handle the denial —
        # check the symbol is referenced INSIDE the watcher block (not
        # just at module scope).
        marker = "watcher = textwrap.dedent("
        idx = text.find(marker)
        end = text.find(").strip()", idx)
        block = text[idx:end]
        # The inlined script catches OSError on the respawn and retries
        # with breakaway cleared via ``& ~_CREATE_BREAKAWAY_FROM_JOB``.
        assert "~_CREATE_BREAKAWAY_FROM_JOB" in block, (
            "Inlined respawn must catch OSError on the breakaway-denied "
            "CreateProcess and retry without the breakaway bit, matching "
            "gateway_windows._spawn_detached's fallback pattern."
        )

    def test_gateway_run_restart_watcher_inlined_respawn_uses_breakaway(self):
        """Behavioral regression guard for the inlined respawn watcher in
        ``GatewayRunner._launch_detached_restart_command``.

        Uses AST parsing + runtime exec with a mocked ``subprocess.Popen``
        to verify the inlined watcher's breakaway bit is set AND the
        OSError fallback retries without the bit.  Catches 12+ stealth
        attack patterns that pure static-text substring checks miss —
        including const-after-use NameError, const-in-comment, const=0
        with bit in comment, name typo, missing except handler, tuple
        spread in `**`, removed bit-clear, wrong constant value, primary
        wrapped in `if False:`, no-op Popen (docstring-only), lambda
        wrapper around `_flags_full`, and Popen moved outside try.

        Strategy:
        1. Parse gateway/run.py with ast, find the inlined watcher
           string via `textwrap.dedent(<str>)` structural match.
        2. textwrap.dedent the extracted string so it compiles.
        3. compile() it to catch syntax errors / TypeErrors.
        4. Walk the AST to verify:
           - Popen calls are NOT inside `if False:`, while, or for blocks
           - PRIMARY Popen uses `creationflags=_flags_full`
           - FALLBACK Popen uses `creationflags=_flags_fallback`
           - PRIMARY Popen is inside a try/except OSError (parent-map walk)
           - The except handler catches OSError
           - `_CREATE_BREAKAWAY_FROM_JOB = 0x01000000` is defined
           - `_flags_full` is a BinOp (not a Lambda/Call/Name wrapper)
           - `_flags_full` BitOr chain includes the breakaway Name
           - `_flags_fallback = _flags_full & ~_CREATE_BREAKAWAY_FROM_JOB`
             (Invert op, not USub)
        5. exec the inlined script with `subprocess.Popen` mocked to
           raise OSError(5) on the FIRST call and with
           `ctypes.windll.kernel32.OpenProcess` mocked to return NULL
           (so the test is platform-portable — on real Windows, PID
           1234 may or may not exist; the ctypes mock makes the
           wait-loop exit deterministically). Verify the SECOND
           Popen call's creationflags differs from the FIRST and that
           the SECOND does NOT have the breakaway bit set (the actual
           bit-cleared semantics at runtime, not just at the AST
           level).
        """
        import ast as _ast
        import textwrap as _textwrap
        root = Path(__file__).resolve().parents[2]
        text = (root / "gateway" / "run.py").read_text(encoding="utf-8")
        tree = _ast.parse(text)
        # Find textwrap.dedent(<str>) inside _launch_detached_restart_command
        # (handles both sync FunctionDef and async AsyncFunctionDef).
        candidate_blocks = []

        def _walk(node):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and node.name == "_launch_detached_restart_command":
                for child in _ast.walk(node):
                    if isinstance(child, _ast.Call) and child.args and isinstance(child.args[0], _ast.Constant) and isinstance(child.args[0].value, str):
                        func = child.func
                        if (
                            isinstance(func, _ast.Attribute)
                            and func.attr == "dedent"
                            and isinstance(func.value, _ast.Name)
                            and func.value.id == "textwrap"
                        ):
                            candidate_blocks.append(child.args[0].value)
            for child in _ast.iter_child_nodes(node):
                _walk(child)

        _walk(tree)
        assert candidate_blocks, (
            "Could not find `textwrap.dedent(<str>)` call inside "
            "_launch_detached_restart_command. The function may have "
            "been refactored to no longer use an inlined string-literal "
            "watcher; if so, this test needs updating."
        )
        # The inlined watcher is the largest string literal in the function.
        watcher_script = max(candidate_blocks, key=len)
        # textwrap.dedent the string so it compiles to valid Python.
        watcher_script = _textwrap.dedent(watcher_script)
        # compile-check: catches syntax errors and gross structural bugs.
        try:
            compile(watcher_script, "<inlined-watcher>", "exec")
        except SyntaxError as e:
            raise AssertionError(
                f"Inlined watcher script has a syntax error: {e}. "
                f"It must be a valid Python program exec'd by `python -c`."
            ) from e
        watcher_tree = _ast.parse(watcher_script)
        # Locate primary and fallback Popen calls by their creationflags
        # name (NOT by position — positions vary by edits).
        popen_calls = [
            n for n in _ast.walk(watcher_tree)
            if isinstance(n, _ast.Call)
            and isinstance(n.func, _ast.Attribute)
            and n.func.attr == "Popen"
        ]
        assert popen_calls, "Inlined watcher has no subprocess.Popen call"
        primary_cf, fallback_cf = None, None
        for pc in popen_calls:
            kw = {k.arg: k.value for k in pc.keywords if k.arg}
            cf = kw.get("creationflags")
            if isinstance(cf, _ast.Name):
                if cf.id == "_flags_full":
                    primary_cf = pc
                elif cf.id == "_flags_fallback":
                    fallback_cf = pc
        assert primary_cf is not None, (
            "Inlined watcher's PRIMARY Popen must use `creationflags=_flags_full`. "
            f"Found {len(popen_calls)} Popen call(s) but none reference `_flags_full`."
        )
        assert fallback_cf is not None, (
            "Inlined watcher's FALLBACK Popen must use `creationflags=_flags_fallback`. "
            f"Found {len(popen_calls)} Popen call(s) but none reference `_flags_fallback`."
        )
        # Both Popens must be at module scope (not inside `if False:`, while, for).
        for label, pc in [("primary", primary_cf), ("fallback", fallback_cf)]:
            for stmt in watcher_tree.body:
                if isinstance(stmt, _ast.If):
                    for sub in _ast.walk(stmt):
                        if sub is pc:
                            if isinstance(stmt.test, _ast.Constant) and stmt.test.value is False:
                                raise AssertionError(
                                    f"Inlined watcher's {label} Popen is wrapped in `if False:` — "
                                    f"it never runs."
                                )
                if isinstance(stmt, (_ast.While, _ast.For)):
                    for sub in _ast.walk(stmt):
                        if sub is pc:
                            raise AssertionError(
                                f"Inlined watcher's {label} Popen is inside a "
                                f"{type(stmt).__name__.lower()} block at line {stmt.lineno}."
                            )
        # PRIMARY Popen must be inside a try/except OSError. The
        # fallback path catches the OSError and retries without
        # breakaway. A Popen that raises OSError unhandled would
        # crash the watcher at runtime.
        # Build a parent map for the inlined watcher_tree.
        inline_parent_map = {}
        for parent in _ast.walk(watcher_tree):
            for child in _ast.iter_child_nodes(parent):
                inline_parent_map[id(child)] = parent
        primary_in_try = False
        primary_handler_catches_oserror = False
        node = primary_cf
        while id(node) in inline_parent_map:
            parent = inline_parent_map[id(node)]
            if isinstance(parent, _ast.Try) and any(n is primary_cf for n in _ast.walk(parent)):
                primary_in_try = True
                for h in parent.handlers:
                    if h.type is None:
                        primary_handler_catches_oserror = True  # bare except catches OSError
                        break
                    if isinstance(h.type, _ast.Name) and h.type.id == "OSError":
                        primary_handler_catches_oserror = True
                        break
                    if isinstance(h.type, _ast.Tuple):
                        for elt in h.type.elts:
                            if isinstance(elt, _ast.Name) and elt.id == "OSError":
                                primary_handler_catches_oserror = True
                                break
                break
            node = parent
        assert primary_in_try, (
            "Inlined watcher's PRIMARY Popen is NOT inside a try/except. "
            "If the parent job object refuses CREATE_BREAKAWAY_FROM_JOB, "
            "CreateProcess raises OSError — without a try/except wrapper, "
            "the watcher crashes and the respawn never happens."
        )
        assert primary_handler_catches_oserror, (
            "Inlined watcher's PRIMARY Popen's try/except handler does NOT "
            "catch OSError. CreateProcess can raise OSError on breakaway "
            "denial; the handler must catch it."
        )
        # _CREATE_BREAKAWAY_FROM_JOB must be defined as 0x01000000.
        breakaway_const_defs = [
            n for n in watcher_tree.body
            if isinstance(n, _ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], _ast.Name)
            and n.targets[0].id == "_CREATE_BREAKAWAY_FROM_JOB"
            and isinstance(n.value, _ast.Constant)
            and n.value.value == 0x01000000
        ]
        assert breakaway_const_defs, (
            "Inlined watcher must define `_CREATE_BREAKAWAY_FROM_JOB = 0x01000000` "
            "as a symbolic constant (greppable intent)."
        )
        # Verify _flags_full must be a BitOr expression that includes
        # _CREATE_BREAKAWAY_FROM_JOB. The right-hand side of the
        # assignment must be a BitOp(BitOr, ...) — NOT a lambda, a
        # function call, a Name, or a constant (which would all
        # bypass the bitwise-OR check at runtime).
        flags_full_defs = [
            n for n in watcher_tree.body
            if isinstance(n, _ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], _ast.Name)
            and n.targets[0].id == "_flags_full"
        ]
        assert flags_full_defs, "Inlined watcher must define `_flags_full`"
        for fa in flags_full_defs:
            # Reject Lambda/Call wrappers — the value must be a
            # bitwise expression. Lambdas would pass the Name-walk
            # check but fail at runtime (the variable would be a
            # function, not an int).
            if not isinstance(fa.value, _ast.BinOp):
                raise AssertionError(
                    f"Inlined watcher's `_flags_full` assignment value is "
                    f"{type(fa.value).__name__} — must be a bitwise "
                    f"expression (BinOp with BitOr). Lambdas/calls/Names "
                    f"would produce a non-int at runtime and break the "
                    f"`creationflags=` call."
                )
            if any(
                isinstance(sub, _ast.Name) and sub.id == "_CREATE_BREAKAWAY_FROM_JOB"
                for sub in _ast.walk(fa)
            ):
                break
        else:
            raise AssertionError(
                "Inlined watcher's `_flags_full` BitOr chain does NOT include "
                "`_CREATE_BREAKAWAY_FROM_JOB` (or its bit was set to 0)."
            )
        # _flags_fallback must be `_flags_full & ~_CREATE_BREAKAWAY_FROM_JOB`.
        flags_fb_defs = [
            n for n in watcher_tree.body
            if isinstance(n, _ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], _ast.Name)
            and n.targets[0].id == "_flags_fallback"
        ]
        assert flags_fb_defs, "Inlined watcher must define `_flags_fallback`"
        for fa in flags_fb_defs:
            v = fa.value
            if (
                isinstance(v, _ast.BinOp)
                and isinstance(v.op, _ast.BitAnd)
                and isinstance(v.left, _ast.Name)
                and v.left.id == "_flags_full"
                and isinstance(v.right, _ast.UnaryOp)
                and isinstance(v.right.op, _ast.Invert)
                and isinstance(v.right.operand, _ast.Name)
                and v.right.operand.id == "_CREATE_BREAKAWAY_FROM_JOB"
            ):
                break
        else:
            raise AssertionError(
                "Inlined watcher's `_flags_fallback` is NOT `_flags_full & ~_CREATE_BREAKAWAY_FROM_JOB`."
            )
        # RUNTIME: exec the inlined script with subprocess.Popen mocked
        # to raise OSError(5) on the first call (simulating breakaway
        # denied by the parent job object).  Verify the SECOND call
        # uses a different creationflags that EXCLUDES the breakaway bit.
        from unittest.mock import patch as _patch
        popen_calls_log = []
        call_count = [0]

        class _MockPopen:
            def __init__(self, *args, **kwargs):
                popen_calls_log.append((args, kwargs))
                call_count[0] += 1
                if call_count[0] == 1:
                    raise OSError(5, "Access is denied (simulated breakaway denial)")
                self.pid = 99999
                self.returncode = None

        def _mock_sleep(seconds):
            pass

        # time.monotonic must return a value past the 120s deadline so
        # the wait loop exits on first iteration.
        def _mock_monotonic():
            return 100000.0

        # Mock the ctypes kernel32 path on Windows. The inlined
        # watcher's `_alive(pid)` calls ctypes.windll.kernel32.OpenProcess
        # to check if the parent process is still alive. Without this
        # mock, the test would hit the real Win32 API, which on a real
        # Windows host could either (a) return NULL with GetLastError=87
        # for a non-existent PID (test passes by accident), or (b)
        # return a valid handle for PID 1234 if that PID happens to
        # be a long-lived system process, causing the test to hang
        # forever (because the while loop is `while time.monotonic() <
        # deadline` and our mock makes time.monotonic a constant).
        # Mocking ctypes.windll.kernel32.OpenProcess to return 0 (NULL)
        # deterministically exits the while loop on the first iteration,
        # making the test platform-portable.
        # Use a custom class whose methods support `.restype` attribute
        # assignment (the inlined watcher's `_alive` does
        # `k32.OpenProcess.restype = ctypes.c_void_p` and similar).
        class _K32Method:
            def __init__(self, fn, default_restype=0):
                self._fn = fn
                self.restype = default_restype
            def __call__(self, *args, **kwargs):
                return self._fn(*args, **kwargs)

        _k32_open_process = _K32Method(lambda access, inherit, pid: 0, default_restype=0)  # NULL handle
        _k32_wait_for_single_object = _K32Method(lambda h, ms: 0x102, default_restype=0)  # WAIT_TIMEOUT
        _k32_get_last_error = _K32Method(lambda: 87, default_restype=0)  # ERROR_INVALID_PARAMETER
        _k32_close_handle = _K32Method(lambda h: True, default_restype=0)

        class _FakeK32:
            def __init__(self):
                self.OpenProcess = _k32_open_process
                self.WaitForSingleObject = _k32_wait_for_single_object
                self.GetLastError = _k32_get_last_error
                self.CloseHandle = _k32_close_handle

        real_argv = sys.argv
        try:
            sys.argv = ["python", "1234", "hermes", "gateway", "restart"]
            with _patch("subprocess.Popen", _MockPopen), \
                 _patch("subprocess.DEVNULL", -3), \
                 _patch("time.sleep", _mock_sleep), \
                 _patch("time.monotonic", _mock_monotonic), \
                 _patch("ctypes.windll.kernel32", _FakeK32()):
                exec(watcher_script, {"__name__": "__main__"})
        finally:
            sys.argv = real_argv
        # Verify the call sequence: 1st call raises OSError, 2nd call
        # succeeds with different creationflags.
        assert len(popen_calls_log) == 2, (
            f"Inlined watcher should call subprocess.Popen exactly twice "
            f"(primary + fallback on OSError). Got {len(popen_calls_log)} call(s). "
            f"If the watcher doesn't retry on OSError, the fallback pattern is broken."
        )
        first_args, first_kwargs = popen_calls_log[0]
        second_args, second_kwargs = popen_calls_log[1]
        assert "creationflags" in first_kwargs, (
            f"Primary Popen has no creationflags kwarg. "
            f"Args: {first_args}, kwargs: {list(first_kwargs.keys())}"
        )
        assert "creationflags" in second_kwargs, (
            f"Fallback Popen has no creationflags kwarg. "
            f"Args: {second_args}, kwargs: {list(second_kwargs.keys())}"
        )
        # The two creationflags values must DIFFER — the fallback must
        # clear at least one bit (the breakaway bit).
        first_cf = first_kwargs["creationflags"]
        second_cf = second_kwargs["creationflags"]
        assert first_cf != second_cf, (
            f"Primary and fallback creationflags are equal ({first_cf}). "
            f"The fallback must clear at least the breakaway bit; if both calls "
            f"use the same value, the breakaway-denied case would just raise "
            f"OSError again."
        )
        # Primary MUST have the breakaway bit set; fallback MUST NOT.
        assert first_cf & 0x01000000, (
            f"Primary creationflags ({first_cf:#010x}) does NOT have "
            f"CREATE_BREAKAWAY_FROM_JOB (0x01000000). Respawned gateway "
            f"would be reaped with the parent."
        )
        assert not (second_cf & 0x01000000), (
            f"Fallback creationflags ({second_cf:#010x}) still has "
            f"CREATE_BREAKAWAY_FROM_JOB (0x01000000) — would raise OSError "
            f"again. No actual recovery."
        )
        # The cmd list (first positional arg) must be identical between
        # the two calls. If the fallback passes [] or a different list,
        # the gateway won't actually restart.
        assert first_args[0] == second_args[0], (
            f"Fallback cmd list differs from primary: "
            f"primary={list(first_args[0])!r}, fallback={list(second_args[0])!r}. "
            f"The fallback would launch a different command."
        )

    def test_gateway_run_restart_watcher_outer_popen_has_access_denied_fallback(self):
        """Behavioral regression guard for the outer watcher Popen in
        ``GatewayRunner._launch_detached_restart_command``.

        Uses AST parsing to verify the outer Popen's structure: must
        be wrapped in try/except OSError, must use `**`-spread kwargs
        (not a tuple), and the argv list must include `*cmd_argv` so
        the watcher gets the restart command.

        Catches the D1/D2/D3 attack patterns the static-text check
        misses: missing `*cmd_argv`, `**(call(),)` tuple spread (in
        EITHER the primary or fallback outer Popen), missing
        try/except on the outer Popen, and `popens[-1]` vs `popens[-2]`
        positional misses when the function has BOTH a primary and a
        fallback outer Popen.
        """
        import ast as _ast
        root = Path(__file__).resolve().parents[2]
        text = (root / "gateway" / "run.py").read_text(encoding="utf-8")
        tree = _ast.parse(text)

        def _find_function(tree, name):
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and node.name == name:
                    return node
            return None

        fn = _find_function(tree, "_launch_detached_restart_command")
        assert fn is not None, "_launch_detached_restart_command not found"
        # Find all Popen calls in the function (both inlined-string's
        # primary/fallback AND the outer watcher Popen).
        popens = [
            n for n in _ast.walk(fn)
            if isinstance(n, _ast.Call)
            and isinstance(n.func, _ast.Attribute)
            and n.func.attr == "Popen"
        ]
        assert len(popens) >= 3, (
            f"Expected at least 3 Popen calls in _launch_detached_restart_command "
            f"(inlined primary + inlined fallback + outer watcher). "
            f"Found {len(popens)}."
        )
        # The OUTER watcher Popen is the LAST one in the function body
        # (after the inlined string's Popens). It takes
        # `[sys.executable, "-c", watcher, str(current_pid), *cmd_argv]`
        # — note the `*cmd_argv` Starred element.
        # NOTE: there are TWO outer Popens (primary + fallback in the
        # try/except OSError wrapper). `popens[-1]` is the fallback,
        # `popens[-2]` is the primary. We verify BOTH because each
        # must independently pass the structural checks.
        outer_primary_popen = popens[-2] if len(popens) >= 2 else None
        outer_fallback_popen = popens[-1]
        assert outer_primary_popen is not None, (
            "Expected at least 2 outer Popen calls (primary + fallback) "
            "in _launch_detached_restart_command. Found fewer."
        )
        for label, outer_popen in [
            ("outer-primary", outer_primary_popen),
            ("outer-fallback", outer_fallback_popen),
        ]:
            # Verify the outer Popen's argv is a List with a Starred element
            # wrapping a Name "cmd_argv" (NOT the inlined-string's `cmd`).
            assert outer_popen.args, f"{label} Popen has no positional args"
            first_arg = outer_popen.args[0]
            assert isinstance(first_arg, _ast.List), (
                f"{label} Popen's first arg is {type(first_arg).__name__}, not a List. "
                f"Should be `[sys.executable, '-c', watcher, str(current_pid), *cmd_argv]`."
            )
            has_cmd_argv_star = any(
                isinstance(el, _ast.Starred)
                and isinstance(el.value, _ast.Name)
                and el.value.id == "cmd_argv"
                for el in first_arg.elts
            )
            assert has_cmd_argv_star, (
                f"{label} Popen's argv list has no `*cmd_argv` Starred element. "
                f"The watcher would be spawned without the 'gateway restart' "
                f"command — it would wait for the parent to die, then exit "
                f"without restarting the gateway."
            )
            # Verify the outer Popen uses `**`-spread kwargs (not a tuple
            # `**(call(),)`). The `**`-spread has `kw.arg is None` in AST.
            spread_kws = [kw for kw in outer_popen.keywords if kw.arg is None]
            assert spread_kws, (
                f"{label} Popen has no `**` kwargs spread. Found "
                f"{len(outer_popen.keywords)} kwarg(s): "
                f"{[kw.arg for kw in outer_popen.keywords]}. "
                f"Without a `**` spread, the creationflags dict is passed as "
                f"a single positional kwarg (Popen will raise TypeError). "
                f"The correct pattern is `subprocess.Popen(..., "
                f"stdout=..., stderr=..., **windows_detach_popen_kwargs())`."
            )
            for spread_kw in spread_kws:
                v = spread_kw.value
                if isinstance(v, (_ast.Call, _ast.Name)):
                    continue  # acceptable
                # Tuple spread `**(expr,)` would also raise TypeError at call
                raise AssertionError(
                    f"{label} Popen's `**` kwargs spread value is "
                    f"{type(v).__name__} — expected Call or Name. "
                    f"Pattern `**(expr,)` is a tuple spread and would raise TypeError."
                )
        # Verify the outer Popen is wrapped in a try/except OSError.
        # Build a parent map.
        parent_map = {}
        for parent in _ast.walk(tree):
            for child in _ast.iter_child_nodes(parent):
                parent_map[id(child)] = parent
        enclosing_try = None
        node = outer_popen
        while id(node) in parent_map:
            parent = parent_map[id(node)]
            if isinstance(parent, _ast.Try) and any(n is outer_popen for n in _ast.walk(parent)):
                enclosing_try = parent
                break
            node = parent
        assert enclosing_try is not None, (
            "Outer watcher Popen is NOT wrapped in a try/except. On Windows, "
            "the parent's job may refuse CREATE_BREAKAWAY_FROM_JOB, raising "
            "OSError — the user gets an unhandled exception."
        )
        # Verify the except handler catches OSError (or a subclass).
        assert enclosing_try.handlers, "Outer Popen's try/except has no except handler"
        oserror_caught = False
        for handler in enclosing_try.handlers:
            if handler.type is None:
                continue
            if isinstance(handler.type, _ast.Name) and handler.type.id == "OSError":
                oserror_caught = True
                break
            if isinstance(handler.type, _ast.Tuple):
                for elt in handler.type.elts:
                    if isinstance(elt, _ast.Name) and elt.id == "OSError":
                        oserror_caught = True
                        break
        assert oserror_caught, (
            "Outer Popen's except handler does NOT catch OSError. "
            "CreateProcess can raise OSError/PermissionError on breakaway "
            "denial; the handler must catch them."
        )
