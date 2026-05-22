"""Tests for HERMES_READ_SAFE_ROOTS / HERMES_READ_ALLOWED_FILES env-var allowlist.

Mirrors test_file_write_safety.py's pytest style and exercises the same
monkeypatch-driven env-var pattern used for HERMES_WRITE_SAFE_ROOT.

The four cases required by the PR:
  1. Allowed roots  → get_read_block_error returns None  (read permitted)
  2. Outside roots  → get_read_block_error returns error string  (read denied)
  3. Specific file allowlist (HERMES_READ_ALLOWED_FILES) bypasses root check
  4. Env var not set → all reads permitted (backwards compat)
"""

import os
from pathlib import Path

import pytest

from agent.file_safety import (
    get_read_block_error,
    get_read_safe_roots,
    get_read_allowed_files,
)


class TestGetReadSafeRoots:
    """Unit tests for the get_read_safe_roots() helper."""

    def test_returns_empty_list_when_unset(self, monkeypatch):
        monkeypatch.delenv("HERMES_READ_SAFE_ROOTS", raising=False)
        assert get_read_safe_roots() == []

    def test_returns_empty_list_when_blank(self, monkeypatch):
        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", "")
        assert get_read_safe_roots() == []

    def test_single_root_resolved(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", str(tmp_path))
        roots = get_read_safe_roots()
        assert len(roots) == 1
        assert roots[0] == str(tmp_path.resolve())

    def test_multiple_roots_colon_separated(self, tmp_path: Path, monkeypatch):
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        root_a.mkdir()
        root_b.mkdir()
        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", f"{root_a}:{root_b}")
        roots = get_read_safe_roots()
        assert len(roots) == 2
        assert str(root_a.resolve()) in roots
        assert str(root_b.resolve()) in roots

    def test_empty_segments_ignored(self, tmp_path: Path, monkeypatch):
        """Trailing colons or double-colons must not produce empty entries."""
        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", f"{tmp_path}::")
        roots = get_read_safe_roots()
        assert all(r for r in roots)


class TestGetReadAllowedFiles:
    """Unit tests for the get_read_allowed_files() helper."""

    def test_returns_empty_set_when_unset(self, monkeypatch):
        monkeypatch.delenv("HERMES_READ_ALLOWED_FILES", raising=False)
        assert get_read_allowed_files() == set()

    def test_single_file_resolved(self, tmp_path: Path, monkeypatch):
        f = tmp_path / "secret.md"
        f.write_text("hello")
        monkeypatch.setenv("HERMES_READ_ALLOWED_FILES", str(f))
        files = get_read_allowed_files()
        assert str(f.resolve()) in files

    def test_multiple_files_colon_separated(self, tmp_path: Path, monkeypatch):
        f1 = tmp_path / "a.md"
        f2 = tmp_path / "b.md"
        f1.write_text("a")
        f2.write_text("b")
        monkeypatch.setenv("HERMES_READ_ALLOWED_FILES", f"{f1}:{f2}")
        files = get_read_allowed_files()
        assert str(f1.resolve()) in files
        assert str(f2.resolve()) in files


class TestReadAllowlist:
    """
    End-to-end tests for get_read_block_error() with the allowlist active.

    Four mandatory PR cases:
      1. Allowed root   → returns None
      2. Outside roots  → returns error string
      3. File allowlist → specific file outside root returns None
      4. Env var unset  → all reads return None (backwards compat)
    """

    # ── Case 1: allowed roots ────────────────────────────────────────────────

    def test_path_inside_root_allowed(self, tmp_path: Path, monkeypatch):
        """A path inside a configured safe root is permitted (returns None)."""
        safe_root = tmp_path / "workspace"
        safe_root.mkdir()
        target = safe_root / "notes.txt"
        target.write_text("hello")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", str(safe_root))
        monkeypatch.delenv("HERMES_READ_ALLOWED_FILES", raising=False)

        assert get_read_block_error(str(target)) is None

    def test_root_itself_is_allowed(self, tmp_path: Path, monkeypatch):
        """Reading the root directory itself is permitted."""
        safe_root = tmp_path / "workspace"
        safe_root.mkdir()

        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", str(safe_root))
        monkeypatch.delenv("HERMES_READ_ALLOWED_FILES", raising=False)

        assert get_read_block_error(str(safe_root)) is None

    def test_nested_path_inside_root_allowed(self, tmp_path: Path, monkeypatch):
        """Deep nesting inside a root is permitted."""
        safe_root = tmp_path / "workspace"
        deep = safe_root / "a" / "b" / "c"
        deep.mkdir(parents=True)
        target = deep / "file.py"
        target.write_text("x = 1")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", str(safe_root))
        monkeypatch.delenv("HERMES_READ_ALLOWED_FILES", raising=False)

        assert get_read_block_error(str(target)) is None

    def test_multi_root_second_root_allowed(self, tmp_path: Path, monkeypatch):
        """A path that lives in the *second* configured root is permitted."""
        root_a = tmp_path / "wiki"
        root_b = tmp_path / "workspace"
        root_a.mkdir()
        root_b.mkdir()
        target = root_b / "doc.md"
        target.write_text("content")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", f"{root_a}:{root_b}")
        monkeypatch.delenv("HERMES_READ_ALLOWED_FILES", raising=False)

        assert get_read_block_error(str(target)) is None

    # ── Case 2: outside roots ────────────────────────────────────────────────

    def test_path_outside_root_denied(self, tmp_path: Path, monkeypatch):
        """A path outside the configured roots is denied (returns error string)."""
        safe_root = tmp_path / "workspace"
        safe_root.mkdir()
        outside = tmp_path / "secrets" / "key.pem"
        outside.parent.mkdir()
        outside.write_text("PRIVATE")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", str(safe_root))
        monkeypatch.delenv("HERMES_READ_ALLOWED_FILES", raising=False)

        error = get_read_block_error(str(outside))
        assert error is not None
        assert "outside" in error.lower() or "denied" in error.lower()

    def test_error_message_names_the_roots(self, tmp_path: Path, monkeypatch):
        """The denial message should include the configured roots for usability."""
        safe_root = tmp_path / "workspace"
        safe_root.mkdir()

        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", str(safe_root))
        monkeypatch.delenv("HERMES_READ_ALLOWED_FILES", raising=False)

        error = get_read_block_error("/etc/passwd")
        assert error is not None
        assert str(safe_root.resolve()) in error

    def test_path_prefix_match_not_tricked_by_sibling(self, tmp_path: Path, monkeypatch):
        """A path whose prefix matches but isn't under the root is denied.

        E.g. safe_root=/tmp/workspace must not allow /tmp/workspace-evil/.
        """
        safe_root = tmp_path / "workspace"
        safe_root.mkdir()
        sibling = tmp_path / "workspace-evil"
        sibling.mkdir()
        target = sibling / "steal.txt"
        target.write_text("no")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", str(safe_root))
        monkeypatch.delenv("HERMES_READ_ALLOWED_FILES", raising=False)

        error = get_read_block_error(str(target))
        assert error is not None, "Sibling directory must not pass the prefix check"

    # ── Case 3: per-file allowlist ───────────────────────────────────────────

    def test_allowed_file_bypasses_roots(self, tmp_path: Path, monkeypatch):
        """A file listed in HERMES_READ_ALLOWED_FILES is readable even if
        it lives outside every configured safe root."""
        safe_root = tmp_path / "workspace"
        safe_root.mkdir()
        soul_file = tmp_path / "SOUL.md"
        soul_file.write_text("soul content")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", str(safe_root))
        monkeypatch.setenv("HERMES_READ_ALLOWED_FILES", str(soul_file))

        assert get_read_block_error(str(soul_file)) is None

    def test_allowed_file_does_not_unlock_other_files(self, tmp_path: Path, monkeypatch):
        """Allowlisting one file must not open up other files beside it."""
        safe_root = tmp_path / "workspace"
        safe_root.mkdir()
        soul_file = tmp_path / "SOUL.md"
        soul_file.write_text("soul content")
        secret = tmp_path / "secret.env"
        secret.write_text("TOKEN=abc")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", str(safe_root))
        monkeypatch.setenv("HERMES_READ_ALLOWED_FILES", str(soul_file))

        error = get_read_block_error(str(secret))
        assert error is not None

    # ── Case 4: backwards compatibility ─────────────────────────────────────

    def test_no_env_var_allows_all_reads(self, monkeypatch):
        """When HERMES_READ_SAFE_ROOTS is unset, all reads are permitted."""
        monkeypatch.delenv("HERMES_READ_SAFE_ROOTS", raising=False)
        monkeypatch.delenv("HERMES_READ_ALLOWED_FILES", raising=False)

        # Paths that would be denied when the allowlist is active
        assert get_read_block_error("/etc/passwd") is None
        assert get_read_block_error(os.path.expanduser("~/.ssh/id_rsa")) is None

    def test_empty_env_var_allows_all_reads(self, monkeypatch):
        """Blank HERMES_READ_SAFE_ROOTS (not just unset) also allows all reads."""
        monkeypatch.setenv("HERMES_READ_SAFE_ROOTS", "")
        monkeypatch.delenv("HERMES_READ_ALLOWED_FILES", raising=False)

        assert get_read_block_error("/etc/passwd") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
