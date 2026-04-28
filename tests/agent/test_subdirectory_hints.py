"""Tests for progressive subdirectory hint discovery."""

import os
import stat
from pathlib import Path

import pytest

from agent.subdirectory_hints import SubdirectoryHintTracker


@pytest.fixture
def project(tmp_path):
    """Create a mock project tree with hint files in subdirectories."""
    # Root — already loaded at startup
    (tmp_path / "AGENTS.md").write_text("Root project instructions")

    # backend/ — has its own AGENTS.md
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "AGENTS.md").write_text("Backend-specific instructions:\n- Use FastAPI\n- Always add type hints")

    # backend/src/ — no hints
    (backend / "src").mkdir()
    (backend / "src" / "main.py").write_text("print('hello')")

    # frontend/ — has CLAUDE.md
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "CLAUDE.md").write_text("Frontend rules:\n- Use TypeScript\n- No any types")

    # docs/ — no hints
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("Documentation")

    # deep/nested/path/ — has .cursorrules
    deep = tmp_path / "deep" / "nested" / "path"
    deep.mkdir(parents=True)
    (deep / ".cursorrules").write_text("Cursor rules for nested path")

    return tmp_path


class TestSubdirectoryHintTracker:
    """Unit tests for SubdirectoryHintTracker."""

    def test_working_dir_not_loaded(self, project):
        """Working dir is pre-marked as loaded (startup handles it)."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        # Reading a file in the root should NOT trigger hints
        result = tracker.check_tool_call("read_file", {"path": str(project / "AGENTS.md")})
        assert result is None

    def test_discovers_agents_md_via_ancestor_walk(self, project):
        """Reading backend/src/main.py discovers backend/AGENTS.md via ancestor walk."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result = tracker.check_tool_call(
            "read_file", {"path": str(project / "backend" / "src" / "main.py")}
        )
        # backend/src/ has no hints, but ancestor walk finds backend/AGENTS.md
        assert result is not None
        assert "Backend-specific instructions" in result
        # Second read in same subtree should not re-trigger
        result2 = tracker.check_tool_call(
            "read_file", {"path": str(project / "backend" / "AGENTS.md")}
        )
        assert result2 is None  # backend/ already loaded

    def test_discovers_claude_md(self, project):
        """Frontend CLAUDE.md should be discovered."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result = tracker.check_tool_call(
            "read_file", {"path": str(project / "frontend" / "index.ts")}
        )
        assert result is not None
        assert "Frontend rules" in result

    def test_no_duplicate_loading(self, project):
        """Same directory should not be loaded twice."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result1 = tracker.check_tool_call(
            "read_file", {"path": str(project / "frontend" / "a.ts")}
        )
        assert result1 is not None

        result2 = tracker.check_tool_call(
            "read_file", {"path": str(project / "frontend" / "b.ts")}
        )
        assert result2 is None  # already loaded

    def test_no_hints_in_empty_directory(self, project):
        """Directories without hint files return None."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result = tracker.check_tool_call(
            "read_file", {"path": str(project / "docs" / "README.md")}
        )
        assert result is None

    def test_terminal_command_path_extraction(self, project):
        """Paths extracted from terminal commands."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result = tracker.check_tool_call(
            "terminal", {"command": f"cat {project / 'frontend' / 'index.ts'}"}
        )
        assert result is not None
        assert "Frontend rules" in result

    def test_terminal_cd_command(self, project):
        """cd into a directory with hints."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result = tracker.check_tool_call(
            "terminal", {"command": f"cd {project / 'backend'} && ls"}
        )
        assert result is not None
        assert "Backend-specific instructions" in result

    def test_relative_path(self, project):
        """Relative paths resolved against working_dir."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result = tracker.check_tool_call(
            "read_file", {"path": "frontend/index.ts"}
        )
        assert result is not None
        assert "Frontend rules" in result

    def test_outside_working_dir_still_checked(self, tmp_path, project):
        """Paths outside working_dir are still checked for hints."""
        other_project = tmp_path / "other"
        other_project.mkdir()
        (other_project / "AGENTS.md").write_text("Other project rules")
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result = tracker.check_tool_call(
            "read_file", {"path": str(other_project / "file.py")}
        )
        assert result is not None
        assert "Other project rules" in result

    def test_workdir_arg(self, project):
        """The workdir argument from terminal tool is checked."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result = tracker.check_tool_call(
            "terminal", {"command": "ls", "workdir": str(project / "frontend")}
        )
        assert result is not None
        assert "Frontend rules" in result

    def test_deeply_nested_cursorrules(self, project):
        """Deeply nested .cursorrules should be discovered."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result = tracker.check_tool_call(
            "read_file", {"path": str(project / "deep" / "nested" / "path" / "file.py")}
        )
        assert result is not None
        assert "Cursor rules for nested path" in result

    def test_hint_format_includes_path(self, project):
        """Discovered hints should indicate which file they came from."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result = tracker.check_tool_call(
            "read_file", {"path": str(project / "backend" / "file.py")}
        )
        assert result is not None
        assert "Subdirectory context discovered:" in result
        assert "AGENTS.md" in result

    def test_truncation_of_large_hints(self, tmp_path):
        """Hint files over the limit are truncated."""
        sub = tmp_path / "bigdir"
        sub.mkdir()
        (sub / "AGENTS.md").write_text("x" * 20_000)

        tracker = SubdirectoryHintTracker(working_dir=str(tmp_path))
        result = tracker.check_tool_call(
            "read_file", {"path": str(sub / "file.py")}
        )
        assert result is not None
        assert "truncated" in result.lower()
        # Should be capped
        assert len(result) < 20_000

    def test_empty_args(self, project):
        """Empty args should not crash."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        assert tracker.check_tool_call("read_file", {}) is None
        assert tracker.check_tool_call("terminal", {"command": ""}) is None

    def test_url_in_command_ignored(self, project):
        """URLs in shell commands should not be treated as paths."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result = tracker.check_tool_call(
            "terminal", {"command": "curl https://example.com/frontend/api"}
        )
        assert result is None

    def test_multiline_terminal_command_skips_path_extraction(self, project):
        """Multiline/heredoc commands should not trigger hint discovery."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result = tracker.check_tool_call(
            "terminal",
            {
                "command": f"python3 - <<'PY'\nprint('{project / 'frontend' / 'index.ts'}')\nPY"
            },
        )
        assert result is None

    def test_long_terminal_command_skips_path_extraction(self, project):
        """Very long inline commands should not trigger hint discovery."""
        tracker = SubdirectoryHintTracker(working_dir=str(project))
        long_path = str(project / "frontend" / "index.ts")
        command = "python3 -c \"" + (long_path + " ") * 300 + "\""
        result = tracker.check_tool_call("terminal", {"command": command})
        assert result is None

    def test_skips_dependency_directories(self, project):
        """Dependency/build trees should never be scanned for subdirectory hints."""
        dep_dir = project / "node_modules" / "pkg"
        dep_dir.mkdir(parents=True)
        (dep_dir / "CLAUDE.md").write_text("dependency hint")

        tracker = SubdirectoryHintTracker(working_dir=str(project))
        result = tracker.check_tool_call("read_file", {"path": str(dep_dir / "index.js")})
        assert result is None

    def test_skips_symlinked_hint_files(self, tmp_path):
        """Symlinked hint files should be ignored to avoid blocking/unsafe reads."""
        target = tmp_path / "real-claude.md"
        target.write_text("real target")
        sub = tmp_path / "symlinked"
        sub.mkdir()
        os.symlink(target, sub / "CLAUDE.md")

        tracker = SubdirectoryHintTracker(working_dir=str(tmp_path))
        result = tracker.check_tool_call("read_file", {"path": str(sub / "file.py")})
        assert result is None

    def test_read_hint_file_skips_non_regular_files(self, tmp_path, monkeypatch):
        """Non-regular hint files should be ignored before any blocking read attempt."""
        tracker = SubdirectoryHintTracker(working_dir=str(tmp_path))
        hint_path = tmp_path / "AGENTS.md"
        hint_path.write_text("placeholder")

        fake_mode = stat.S_IFIFO | 0o644
        monkeypatch.setattr(
            "agent.subdirectory_hints.os.lstat",
            lambda _path: type("Stat", (), {"st_mode": fake_mode})(),
        )

        result = tracker._read_hint_file(hint_path)
        assert result is None
