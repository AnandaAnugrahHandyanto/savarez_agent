"""Tests for _resolve_path() — TERMINAL_CWD-aware path resolution in file_tools."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest


class TestResolvePath:
    """Verify _resolve_path respects TERMINAL_CWD for worktree isolation."""

    def test_relative_path_uses_terminal_cwd(self, monkeypatch, tmp_path):
        """Relative paths resolve against TERMINAL_CWD, not process CWD."""
        monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
        from tools.file_tools import _resolve_path

        result = _resolve_path("foo/bar.py")
        assert result == (tmp_path / "foo" / "bar.py")

    def test_absolute_path_ignores_terminal_cwd(self, monkeypatch, tmp_path):
        """Absolute paths are unaffected by TERMINAL_CWD."""
        monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
        from tools.file_tools import _resolve_path

        absolute = (tmp_path / "already-absolute.txt").resolve()
        result = _resolve_path(str(absolute))
        assert result == absolute

    def test_falls_back_to_cwd_without_terminal_cwd(self, monkeypatch):
        """Without TERMINAL_CWD, falls back to os.getcwd()."""
        monkeypatch.delenv("TERMINAL_CWD", raising=False)
        from tools.file_tools import _resolve_path

        result = _resolve_path("some_file.txt")
        assert result == Path(os.getcwd()) / "some_file.txt"

    def test_tilde_expansion(self, monkeypatch, tmp_path):
        """~ is expanded before TERMINAL_CWD join (already absolute)."""
        monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
        from tools.file_tools import _resolve_path

        result = _resolve_path("~/notes.txt")
        # After expanduser, ~/notes.txt becomes absolute → TERMINAL_CWD ignored
        assert result == Path.home() / "notes.txt"

    def test_result_is_resolved(self, monkeypatch, tmp_path):
        """Output path has no '..' components."""
        monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
        from tools.file_tools import _resolve_path

        result = _resolve_path("a/../b/file.txt")
        assert ".." not in str(result)
        assert result == (tmp_path / "b" / "file.txt")

    def test_relative_path_prefers_live_file_ops_cwd(self, monkeypatch, tmp_path):
        """Live env.cwd must win after the terminal session changes directory."""
        start_dir = tmp_path / "start"
        live_dir = tmp_path / "worktree"
        start_dir.mkdir()
        live_dir.mkdir()
        monkeypatch.setenv("TERMINAL_CWD", str(start_dir))

        from tools import file_tools

        task_id = "live-cwd"
        fake_ops = SimpleNamespace(
            env=SimpleNamespace(cwd=str(live_dir)),
            cwd=str(start_dir),
        )

        with file_tools._file_ops_lock:
            previous = file_tools._file_ops_cache.get(task_id)
            file_tools._file_ops_cache[task_id] = fake_ops

        try:
            result = file_tools._resolve_path("nested/file.txt", task_id=task_id)
        finally:
            with file_tools._file_ops_lock:
                if previous is None:
                    file_tools._file_ops_cache.pop(task_id, None)
                else:
                    file_tools._file_ops_cache[task_id] = previous

        assert result == live_dir / "nested" / "file.txt"


class TestTildeRealHome:
    """Regression: ~ must resolve to the real user home, not $HOME (#28456).

    Hermes profile sandboxing sets $HOME to the profile sandbox dir.
    ``Path.expanduser()`` would honor that and silently fail to find files
    at the user's real home.
    """

    def test_tilde_ignores_sandbox_home_env(self, monkeypatch, tmp_path):
        import pwd
        sandbox = tmp_path / "profiles" / "threepio" / "home"
        sandbox.mkdir(parents=True)
        monkeypatch.setenv("HOME", str(sandbox))

        from tools.file_tools import _expanduser_real, _resolve_path

        real_home = pwd.getpwuid(os.getuid()).pw_dir
        assert _expanduser_real("~/foo.txt") == os.path.join(real_home, "foo.txt")
        assert _expanduser_real("~") == real_home

        # _resolve_path output must be under real home, not sandbox
        result = str(_resolve_path("~/.hermes/shared/x.md"))
        assert result.startswith(real_home), result
        assert str(sandbox) not in result

    def test_tilde_other_user_delegates_to_stdlib(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        from tools.file_tools import _expanduser_real

        assert _expanduser_real("~nosuch_user_xyz123/f") == os.path.expanduser(
            "~nosuch_user_xyz123/f"
        )
