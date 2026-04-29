"""Regression tests for the Windows-specific fixes in tools/environments/local.py.

The drive-mount regex and WSL-launcher detection are pure functions and run
on any platform.  The cygpath fallback and the end-to-end
LocalEnvironment.execute() smoke test only run on Windows.
"""

import os
import sys

import pytest

from tools.environments.local import (
    LocalEnvironment,
    _is_wsl_bash_launcher,
    _posix_to_win_path,
)


class TestPosixToWinPath:
    """Drive-mount regex — fast path, runs everywhere.

    On non-Windows hosts, cygpath is unreachable so the slow path is a
    no-op.  Cases here exercise either the regex (drive mounts) or the
    early-return guards (empty, already-Windows paths).
    """

    @pytest.mark.parametrize("path,expected", [
        # MSYS / Git Bash style
        ("/c/Users/me", "C:\\Users\\me"),
        ("/c/Users/me/proj", "C:\\Users\\me\\proj"),
        ("/d/data", "D:\\data"),
        ("/c", "C:\\"),
        ("/c/", "C:\\"),
        # WSL style
        ("/mnt/c/Users/me", "C:\\Users\\me"),
        ("/mnt/d/code", "D:\\code"),
        # Already a Windows path — leave alone (doesn't start with "/")
        ("C:\\Users\\me", "C:\\Users\\me"),
        ("D:\\data\\proj", "D:\\data\\proj"),
        # Edge cases
        ("", ""),
    ])
    def test_drive_mount_conversions(self, path, expected):
        assert _posix_to_win_path(path) == expected


@pytest.mark.skipif(sys.platform != "win32", reason="cygpath only exists on Windows")
class TestPosixToWinPathCygpathFallback:
    """MSYS virtual mounts (/tmp, /home, /usr) — cygpath slow path.

    Git Bash maps ``%LOCALAPPDATA%\\Temp`` to ``/tmp`` via fstab, so any
    cwd under the user's temp dir comes back as ``/tmp/...`` from
    ``pwd -P``.  Without cygpath fallback, subprocess.Popen rejects it
    with WinError 267.
    """

    def test_tmp_resolves_to_localappdata(self):
        result = _posix_to_win_path("/tmp")
        assert os.path.isdir(result), f"/tmp -> {result!r} should be a real dir"
        assert ":" in result, f"/tmp -> {result!r} should be Windows-form"

    def test_tmp_subpath(self):
        result = _posix_to_win_path("/tmp/some-subdir")
        assert ":" in result
        # cygpath preserves subpath even if it doesn't exist on disk
        assert result.lower().endswith("some-subdir")

    def test_unrecognized_posix_path_returns_input(self):
        # cygpath happily maps any path; verify it returns *something*
        # Windows-form rather than the original POSIX-form.
        result = _posix_to_win_path("/totally/made/up")
        assert result != "/totally/made/up"


class TestIsWslBashLauncher:
    """``_is_wsl_bash_launcher`` is only ever called on Windows (guarded by
    ``_IS_WINDOWS`` in ``_find_bash``).  These tests run everywhere because
    the function itself is pure; the case-insensitive case is skipped off
    Windows because ``os.path.normcase`` is a no-op outside Windows so the
    upper-case variant doesn't normalise to the canonical form.
    """

    def test_system32_bash_is_wsl(self):
        sysroot = os.environ.get("SystemRoot", r"C:\Windows")
        assert _is_wsl_bash_launcher(os.path.join(sysroot, "System32", "bash.exe"))

    def test_git_bash_is_not_wsl(self):
        assert not _is_wsl_bash_launcher(r"C:\Program Files\Git\bin\bash.exe")
        assert not _is_wsl_bash_launcher(r"C:\Program Files\Git\usr\bin\bash.exe")

    def test_empty_path(self):
        assert not _is_wsl_bash_launcher("")
        assert not _is_wsl_bash_launcher(None)  # type: ignore[arg-type]

    @pytest.mark.skipif(sys.platform != "win32",
                        reason="os.path.normcase is a no-op outside Windows")
    def test_case_insensitive(self):
        sysroot = os.environ.get("SystemRoot", r"C:\Windows")
        upper = os.path.join(sysroot.upper(), "SYSTEM32", "BASH.EXE")
        assert _is_wsl_bash_launcher(upper)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only smoke test")
class TestLocalEnvironmentWindows:
    """End-to-end check that LocalEnvironment captures output on Windows.

    Before the fixes in this PR, every command on Windows returned either
    empty output (select.select OSError 10038 swallowed) or
    NotADirectoryError (Popen rejected POSIX-form cwd).

    Uses a known Windows directory (SystemRoot) rather than tmp_path because
    pytest's tmp_path can resolve to a POSIX-only path under MSYS-flavoured
    environments, which would mask the behaviour we're trying to verify.
    """

    @pytest.fixture
    def env(self):
        return LocalEnvironment(
            cwd=os.environ.get("SystemRoot", r"C:\Windows"),
            timeout=30,
        )

    def test_echo_captures_output(self, env):
        result = env.execute("echo HERMES_WINDOWS_OK", timeout=10)
        assert result["returncode"] == 0
        assert "HERMES_WINDOWS_OK" in result["output"]

    def test_cwd_is_windows_form_after_init(self, env):
        # _update_cwd reads `pwd -P` from Git Bash (POSIX) and must convert
        # it back to a native Windows path so subprocess.Popen accepts it.
        assert os.path.isdir(env.cwd), (
            f"env.cwd={env.cwd!r} should be a real Windows directory; "
            "if it starts with '/c/' or '/mnt/c/' the POSIX→Windows "
            "conversion in _update_cwd is broken."
        )

    def test_pipeline_captures_output(self, env):
        result = env.execute("printf 'a\\nb\\nc\\n' | wc -l", timeout=10)
        assert result["returncode"] == 0
        assert result["output"].strip() == "3"
