"""Tests for HERMES_READ_SAFE_ROOT sandboxing.

Mirrors test_file_write_safety.py for the read side. Used by the
meta-harness diagnosis agent (Phase B) to confine a proposer agent
to a specific archive directory.
"""

import json
import os
from pathlib import Path

import pytest

from tools.file_operations import _get_safe_read_root, _is_read_denied


# ── Default-off behavior ───────────────────────────────────────────────


class TestDefaultOff:
    """With HERMES_READ_SAFE_ROOT unset, reads are never denied by this check."""

    def test_unset_env_returns_none_root(self, monkeypatch):
        monkeypatch.delenv("HERMES_READ_SAFE_ROOT", raising=False)
        assert _get_safe_read_root() is None

    def test_unset_env_allows_any_path(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("HERMES_READ_SAFE_ROOT", raising=False)
        denied, reason = _is_read_denied(str(tmp_path / "anything"))
        assert denied is False
        assert reason is None

    def test_empty_env_is_treated_as_unset(self, monkeypatch):
        monkeypatch.setenv("HERMES_READ_SAFE_ROOT", "")
        assert _get_safe_read_root() is None
        denied, _ = _is_read_denied("/etc/passwd")
        assert denied is False


# ── Sandbox enforcement ────────────────────────────────────────────────


class TestSafeReadRoot:
    """HERMES_READ_SAFE_ROOT should sandbox reads to a specific subtree."""

    def test_read_inside_safe_root_allowed(self, tmp_path: Path, monkeypatch):
        safe_root = tmp_path / "archive"
        target = safe_root / "traces" / "task_001.json"
        target.parent.mkdir(parents=True)
        target.write_text("{}")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOT", str(safe_root))
        denied, reason = _is_read_denied(str(target))
        assert denied is False
        assert reason is None

    def test_read_at_safe_root_itself_allowed(self, tmp_path: Path, monkeypatch):
        safe_root = tmp_path / "archive"
        safe_root.mkdir()
        monkeypatch.setenv("HERMES_READ_SAFE_ROOT", str(safe_root))
        denied, _ = _is_read_denied(str(safe_root))
        assert denied is False

    def test_read_outside_safe_root_denied(self, tmp_path: Path, monkeypatch):
        safe_root = tmp_path / "archive"
        outside = tmp_path / "other" / "secret.txt"
        safe_root.mkdir()
        outside.parent.mkdir()
        outside.write_text("secret")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOT", str(safe_root))
        denied, reason = _is_read_denied(str(outside))
        assert denied is True
        assert reason is not None
        assert "outside" in reason

    def test_parent_directory_escape_denied(self, tmp_path: Path, monkeypatch):
        """../../etc/passwd attempt."""
        safe_root = tmp_path / "archive"
        safe_root.mkdir()
        escape = safe_root / ".." / ".." / "etc" / "passwd"

        monkeypatch.setenv("HERMES_READ_SAFE_ROOT", str(safe_root))
        denied, _ = _is_read_denied(str(escape))
        assert denied is True

    def test_symlink_escape_denied(self, tmp_path: Path, monkeypatch):
        """A symlink INSIDE the safe root that points OUTSIDE must be rejected."""
        safe_root = tmp_path / "archive"
        outside_file = tmp_path / "secret.txt"
        safe_root.mkdir()
        outside_file.write_text("secret")

        # Create a symlink inside safe_root that points to the outside file
        escape_link = safe_root / "escape.txt"
        escape_link.symlink_to(outside_file)

        monkeypatch.setenv("HERMES_READ_SAFE_ROOT", str(safe_root))
        denied, reason = _is_read_denied(str(escape_link))
        assert denied is True
        assert reason is not None

    def test_absolute_path_inside_allowed(self, tmp_path: Path, monkeypatch):
        safe_root = tmp_path / "archive"
        target = safe_root / "deep" / "nested" / "file.json"
        target.parent.mkdir(parents=True)
        target.write_text("{}")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOT", str(safe_root))
        denied, _ = _is_read_denied(str(target.absolute()))
        assert denied is False

    def test_absolute_path_outside_denied(self, monkeypatch, tmp_path: Path):
        safe_root = tmp_path / "archive"
        safe_root.mkdir()
        monkeypatch.setenv("HERMES_READ_SAFE_ROOT", str(safe_root))
        denied, _ = _is_read_denied("/etc/passwd")
        assert denied is True

    def test_tilde_in_env_is_expanded(self, tmp_path: Path, monkeypatch):
        """~ in HERMES_READ_SAFE_ROOT should be expanded."""
        safe_root = tmp_path / "archive"
        safe_root.mkdir()
        monkeypatch.setenv("HERMES_READ_SAFE_ROOT", str(safe_root))
        root = _get_safe_read_root()
        assert root == str(safe_root.resolve())

    def test_sibling_directory_prefix_not_matched(self, tmp_path: Path, monkeypatch):
        """'/tmp/archive' must NOT match '/tmp/archive_other' by string prefix."""
        safe_root = tmp_path / "archive"
        sibling = tmp_path / "archive_other" / "file.txt"
        safe_root.mkdir()
        sibling.parent.mkdir()
        sibling.write_text("not inside")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOT", str(safe_root))
        denied, _ = _is_read_denied(str(sibling))
        assert denied is True, "sibling directory with shared prefix must be denied"


# ── Integration with the actual read_file_tool ─────────────────────────


class TestReadFileToolIntegration:
    """The top-level read_file_tool must honor the safe-root guard."""

    def test_read_file_tool_denies_outside_root(self, tmp_path: Path, monkeypatch):
        from tools.file_tools import read_file_tool

        safe_root = tmp_path / "archive"
        outside = tmp_path / "outside.txt"
        safe_root.mkdir()
        outside.write_text("secret payload")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOT", str(safe_root))
        result = read_file_tool(str(outside))
        data = json.loads(result)
        assert "error" in data
        assert "outside" in data["error"].lower() or "sandbox" in data["error"].lower()

    def test_read_file_tool_allows_inside_root(self, tmp_path: Path, monkeypatch):
        from tools.file_tools import read_file_tool

        safe_root = tmp_path / "archive"
        inside = safe_root / "note.txt"
        safe_root.mkdir()
        inside.write_text("hello meta-harness")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOT", str(safe_root))
        result = read_file_tool(str(inside))
        data = json.loads(result)
        # Should NOT be an error result
        assert "error" not in data or "outside" not in data.get("error", "").lower()

    def test_search_tool_denies_outside_root(self, tmp_path: Path, monkeypatch):
        from tools.file_tools import search_tool

        safe_root = tmp_path / "archive"
        outside = tmp_path / "other"
        safe_root.mkdir()
        outside.mkdir()
        (outside / "secret.txt").write_text("password=hunter2")

        monkeypatch.setenv("HERMES_READ_SAFE_ROOT", str(safe_root))
        result = search_tool(pattern="password", path=str(outside))
        data = json.loads(result)
        assert "error" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
