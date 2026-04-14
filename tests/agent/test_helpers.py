"""Tests for agent/helpers.py — standalone helper utilities."""

import pytest
import io
import sys
from pathlib import Path

from agent.helpers import (
    SafeWriter,
    install_safe_stdio,
    IterationBudget,
    is_destructive_command,
    should_parallelize_tool_batch,
    extract_parallel_scope_path,
    paths_overlap,
    qwen_portal_headers,
    NEVER_PARALLEL_TOOLS,
    PARALLEL_SAFE_TOOLS,
    PATH_SCOPED_TOOLS,
    MAX_TOOL_WORKERS,
)


# --- SafeWriter ---

class TestSafeWriter:
    def test_write_passes_through(self):
        buf = io.StringIO()
        writer = SafeWriter(buf)
        writer.write("hello")
        assert buf.getvalue() == "hello"

    def test_write_catches_oserror(self):
        class BrokenStream:
            def write(self, data):
                raise OSError("broken pipe")
        writer = SafeWriter(BrokenStream())
        # Should not raise, returns length
        assert writer.write("hello") == 5

    def test_write_catches_valueerror(self):
        class ClosedStream:
            def write(self, data):
                raise ValueError("closed file")
        writer = SafeWriter(ClosedStream())
        assert writer.write("hello") == 5

    def test_flush_catches_oserror(self):
        class BrokenStream:
            def flush(self):
                raise OSError("flush fail")
        writer = SafeWriter(BrokenStream())
        # Should not raise
        writer.flush()

    def test_isatty_catches_error(self):
        class BrokenStream:
            def isatty(self):
                raise OSError("no tty")
        writer = SafeWriter(BrokenStream())
        assert writer.isatty() is False

    def test_fileno_delegates(self):
        buf = io.BytesIO()
        writer = SafeWriter(sys.stdout)  # Use a real stream with fileno
        # Just verify it doesn't crash
        try:
            writer.fileno()
        except (io.UnsupportedOperation, AttributeError):
            pass  # StringIO doesn't have fileno, that's fine


# --- install_safe_stdio ---

class TestInstallSafeStdio:
    def test_wraps_streams(self):
        original_out = sys.stdout
        original_err = sys.stderr
        try:
            install_safe_stdio()
            assert isinstance(sys.stdout, SafeWriter)
            assert isinstance(sys.stderr, SafeWriter)
        finally:
            sys.stdout = original_out
            sys.stderr = original_err

    def test_idempotent(self):
        original_out = sys.stdout
        original_err = sys.stderr
        try:
            install_safe_stdio()
            install_safe_stdio()  # Second call should be no-op
            assert isinstance(sys.stdout, SafeWriter)
        finally:
            sys.stdout = original_out
            sys.stderr = original_err


# --- IterationBudget ---

class TestIterationBudget:
    def test_consume_within_budget(self):
        budget = IterationBudget(max_total=5)
        assert budget.consume() is True
        assert budget.used == 1
        assert budget.remaining == 4

    def test_consume_exhausts_budget(self):
        budget = IterationBudget(max_total=2)
        assert budget.consume() is True
        assert budget.consume() is True
        assert budget.consume() is False
        assert budget.remaining == 0

    def test_refund(self):
        budget = IterationBudget(max_total=3)
        budget.consume()
        budget.consume()
        budget.refund()
        assert budget.used == 1

    def test_refund_below_zero_clamped(self):
        budget = IterationBudget(max_total=2)
        budget.refund()  # Should not go below 0
        assert budget.used == 0

    def test_remaining_never_negative(self):
        budget = IterationBudget(max_total=0)
        assert budget.remaining == 0


# --- is_destructive_command ---

class TestIsDestructiveCommand:
    def test_rm_is_destructive(self):
        assert is_destructive_command("rm -rf /") is True

    def test_rm_file(self):
        assert is_destructive_command("rm file.txt") is True

    def test_echo_not_destructive(self):
        assert is_destructive_command("echo hello") is False

    def test_ls_not_destructive(self):
        assert is_destructive_command("ls -la") is False

    def test_empty_not_destructive(self):
        assert is_destructive_command("") is False

    def test_git_reset_destructive(self):
        assert is_destructive_command("git reset --hard") is True

    def test_redirect_overwrite(self):
        assert is_destructive_command("echo hi > file.txt") is True

    def test_redirect_append_safe(self):
        assert is_destructive_command("echo hi >> file.txt") is False

    def test_mv_destructive(self):
        assert is_destructive_command("mv a.txt b.txt") is True

    def test_sed_inplace(self):
        assert is_destructive_command("sed -i 's/old/new/' file.txt") is True

    def test_dd_destructive(self):
        assert is_destructive_command("dd if=/dev/zero of=disk.img") is True


# --- paths_overlap ---

class TestPathsOverlap:
    def test_same_path(self):
        assert paths_overlap(Path("/a/b"), Path("/a/b")) is True

    def test_parent_child(self):
        assert paths_overlap(Path("/a"), Path("/a/b")) is True

    def test_different_roots(self):
        assert paths_overlap(Path("/a/b"), Path("/c/d")) is False

    def test_siblings(self):
        assert paths_overlap(Path("/a/b"), Path("/a/c")) is False

    def test_empty_paths(self):
        assert paths_overlap(Path(""), Path("")) is False


# --- extract_parallel_scope_path ---

class TestExtractParallelScopePath:
    def test_non_scoped_tool_returns_none(self):
        assert extract_parallel_scope_path("web_search", {}) is None

    def test_read_file_returns_path(self, tmp_path):
        result = extract_parallel_scope_path("read_file", {"path": str(tmp_path / "test.txt")})
        assert result is not None

    def test_empty_path_returns_none(self):
        assert extract_parallel_scope_path("read_file", {"path": ""}) is None

    def test_missing_path_returns_none(self):
        assert extract_parallel_scope_path("read_file", {}) is None


# --- should_parallelize_tool_batch ---

class TestShouldParallelizeToolBatch:
    def _make_call(self, name, arguments=None):
        """Create a mock tool call object."""
        import json
        class MockFunction:
            def __init__(self, name, arguments):
                self.name = name
                self.arguments = json.dumps(arguments or {})
        class MockToolCall:
            def __init__(self, name, arguments=None):
                self.function = MockFunction(name, arguments)
        return MockToolCall(name, arguments)

    def test_single_call_returns_false(self):
        calls = [self._make_call("web_search", {"query": "test"})]
        assert should_parallelize_tool_batch(calls) is False

    def test_never_parallel_tools_returns_false(self):
        calls = [
            self._make_call("clarify", {"question": "a"}),
            self._make_call("web_search", {"query": "b"}),
        ]
        assert should_parallelize_tool_batch(calls) is False

    def test_two_safe_tools_returns_true(self):
        calls = [
            self._make_call("web_search", {"query": "a"}),
            self._make_call("web_search", {"query": "b"}),
        ]
        assert should_parallelize_tool_batch(calls) is True


# --- qwen_portal_headers ---

class TestQwenPortalHeaders:
    def test_returns_dict(self):
        headers = qwen_portal_headers()
        assert isinstance(headers, dict)

    def test_contains_user_agent(self):
        headers = qwen_portal_headers()
        assert "User-Agent" in headers
        assert "QwenCode/" in headers["User-Agent"]

    def test_contains_cache_control(self):
        headers = qwen_portal_headers()
        assert headers["X-DashScope-CacheControl"] == "enable"

    def test_contains_auth_type(self):
        headers = qwen_portal_headers()
        assert headers["X-DashScope-AuthType"] == "qwen-oauth"


# --- Constants ---

class TestConstants:
    def test_max_tool_workers_reasonable(self):
        assert 1 <= MAX_TOOL_WORKERS <= 32

    def test_parallel_safe_tools_not_empty(self):
        assert len(PARALLEL_SAFE_TOOLS) > 0

    def test_path_scoped_tools_subset(self):
        # Path-scoped tools should not overlap with never-parallel
        assert not PATH_SCOPED_TOOLS & NEVER_PARALLEL_TOOLS
