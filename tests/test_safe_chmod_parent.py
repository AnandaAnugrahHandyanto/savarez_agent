"""Tests for safe_chmod_parent() in agent/file_safety.py (issue #25821).

Prevents os.chmod("/", 0o700) from bricking the host by blocking chmod on
root and well-known system directories.
"""
import os
import stat
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

from agent.file_safety import safe_chmod_parent, _UNSAFE_PARENT_DIRS


class TestSafeChmodParent:

    def test_normal_directory_gets_chmod(self):
        """A normal directory should be chmod'd to 0o700."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "sub" / "file.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()

            os.chmod(target.parent, 0o755)
            safe_chmod_parent(target)

            mode = stat.S_IMODE(os.stat(target.parent).st_mode)
            assert mode == 0o700

    def test_root_directory_is_skipped(self):
        """chmod on '/' must be skipped."""
        target = Path("/.hermes_tokens")
        original_mode = stat.S_IMODE(os.stat("/").st_mode)
        safe_chmod_parent(target)
        new_mode = stat.S_IMODE(os.stat("/").st_mode)
        assert new_mode == original_mode

    @pytest.mark.parametrize("sys_dir", sorted(_UNSAFE_PARENT_DIRS - {"/"}))
    def test_system_directories_are_skipped(self, sys_dir):
        """Well-known system directories must be skipped."""
        if not os.path.isdir(sys_dir):
            pytest.skip(f"{sys_dir} not available on this system")
        target = Path(sys_dir) / ".hermes_test_file"
        original_mode = stat.S_IMODE(os.stat(sys_dir).st_mode)
        safe_chmod_parent(target)
        new_mode = stat.S_IMODE(os.stat(sys_dir).st_mode)
        assert new_mode == original_mode

    def test_nonexistent_parent_skipped(self):
        """If parent doesn't exist, skip chmod gracefully."""
        target = Path("/tmp/nonexistent_dir_xyz987/file.json")
        safe_chmod_parent(target)  # Should not raise

    def test_oserror_silently_ignored(self):
        """OSError from chmod (e.g. Windows mounts) should be silently ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "file.json"
            target.touch()
            with patch("os.chmod", side_effect=OSError("Permission denied")):
                safe_chmod_parent(target)  # Should not raise

    def test_unsafe_parent_dirs_constant(self):
        """The blocklist should include all critical system directories."""
        expected = {"/", "/etc", "/usr", "/var", "/sys", "/proc", "/boot",
                    "/dev", "/bin", "/sbin", "/lib", "/lib64", "/opt", "/root"}
        assert expected.issubset(_UNSAFE_PARENT_DIRS)

    def test_nested_directory_works(self):
        """Deeply nested directories should still be chmod'd."""
        with tempfile.TemporaryDirectory() as tmpdir:
            deep = Path(tmpdir) / "a" / "b" / "c"
            deep.mkdir(parents=True, exist_ok=True)
            target = deep / "file.json"
            target.touch()

            safe_chmod_parent(target)

            mode = stat.S_IMODE(os.stat(deep).st_mode)
            assert mode == 0o700
