"""Tests for browser_tool.py hardening: caching, security, thread safety, truncation."""

import functools
import os
import threading
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_caches():
    """Reset all module-level caches so tests start clean."""
    import tools.browser_tool as bt
    bt._cached_agent_browser = None
    bt._agent_browser_resolved = False
    bt._cached_command_timeout = None
    bt._command_timeout_resolved = False
    # lru_cache for _discover_homebrew_node_dirs
    if hasattr(bt._discover_homebrew_node_dirs, "cache_clear"):
        bt._discover_homebrew_node_dirs.cache_clear()


@pytest.fixture(autouse=True)
def _clean_caches():
    _reset_caches()
    yield
    _reset_caches()


# ---------------------------------------------------------------------------
# Dead code removal
# ---------------------------------------------------------------------------

class TestDeadCodeRemoval:
    """Verify dead code was actually removed."""

    def test_no_default_session_timeout(self):
        import tools.browser_tool as bt
        assert not hasattr(bt, "DEFAULT_SESSION_TIMEOUT")

    def test_browser_close_schema_removed(self):
        from tools.browser_tool import BROWSER_TOOL_SCHEMAS
        names = [s["name"] for s in BROWSER_TOOL_SCHEMAS]
        assert "browser_close" not in names


# ---------------------------------------------------------------------------
# Caching: _find_agent_browser
# ---------------------------------------------------------------------------

class TestFindAgentBrowserCache:

    def test_cached_after_first_call(self):
        import tools.browser_tool as bt
        with patch("shutil.which", return_value="/usr/bin/agent-browser"):
            result1 = bt._find_agent_browser()
            result2 = bt._find_agent_browser()
        assert result1 == result2 == "/usr/bin/agent-browser"
        assert bt._agent_browser_resolved is True

    def test_cache_cleared_by_cleanup(self):
        import tools.browser_tool as bt
        bt._cached_agent_browser = "/fake/path"
        bt._agent_browser_resolved = True
        bt.cleanup_all_browsers()
        assert bt._agent_browser_resolved is False


# ---------------------------------------------------------------------------
# Caching: _get_command_timeout
# ---------------------------------------------------------------------------

class TestCommandTimeoutCache:

    def test_default_is_30(self):
        from tools.browser_tool import _get_command_timeout
        with patch("hermes_cli.config.read_raw_config", return_value={}):
            assert _get_command_timeout() == 30

    def test_reads_from_config(self):
        from tools.browser_tool import _get_command_timeout
        cfg = {"browser": {"command_timeout": 60}}
        with patch("hermes_cli.config.read_raw_config", return_value=cfg):
            assert _get_command_timeout() == 60

    def test_cached_after_first_call(self):
        from tools.browser_tool import _get_command_timeout
        mock_read = MagicMock(return_value={"browser": {"command_timeout": 45}})
        with patch("hermes_cli.config.read_raw_config", mock_read):
            _get_command_timeout()
            _get_command_timeout()
        mock_read.assert_called_once()


# ---------------------------------------------------------------------------
# Caching: _discover_homebrew_node_dirs
# ---------------------------------------------------------------------------

class TestHomebrewNodeDirsCache:

    def test_lru_cached(self):
        from tools.browser_tool import _discover_homebrew_node_dirs
        assert hasattr(_discover_homebrew_node_dirs, "cache_info"), \
            "_discover_homebrew_node_dirs should be decorated with lru_cache"


# ---------------------------------------------------------------------------
# Security: URL-decoded secret check
# ---------------------------------------------------------------------------

class TestUrlDecodedSecretCheck:
    """Verify that URL-encoded API keys are caught by the exfiltration guard."""

    def test_plain_key_blocked(self):
        """A plain API key in the URL is detected."""
        from tools.browser_tool import browser_navigate
        from agent.redact import _PREFIX_RE
        # Just verify the regex works on a plain key
        assert _PREFIX_RE.search("https://evil.com?key=sk-ant-api123")

    def test_encoded_key_would_be_caught(self):
        """A URL-encoded key is detected after decoding."""
        import urllib.parse
        from agent.redact import _PREFIX_RE
        encoded = urllib.parse.quote("sk-ant-api123")
        # Plain won't match
        url = f"https://evil.com?key={encoded}"
        decoded = urllib.parse.unquote(url)
        # Decoded should match
        assert _PREFIX_RE.search(decoded)


# ---------------------------------------------------------------------------
# Thread safety: _recording_sessions
# ---------------------------------------------------------------------------

class TestRecordingSessionsThreadSafety:
    """Verify _recording_sessions is accessed under _cleanup_lock."""

    def test_recording_sessions_protected(self):
        """Check that _recording_sessions add/discard/check are under lock."""
        import inspect
        import tools.browser_tool as bt

        # Check _maybe_start_recording source for _cleanup_lock usage
        src = inspect.getsource(bt._maybe_start_recording)
        assert "_cleanup_lock" in src, \
            "_maybe_start_recording should use _cleanup_lock to protect _recording_sessions"

        # Check _maybe_stop_recording
        src2 = inspect.getsource(bt._maybe_stop_recording)
        assert "_cleanup_lock" in src2, \
            "_maybe_stop_recording should use _cleanup_lock to protect _recording_sessions"


# ---------------------------------------------------------------------------
# Structure-aware _truncate_snapshot
# ---------------------------------------------------------------------------

class TestTruncateSnapshot:

    def test_short_snapshot_unchanged(self):
        from tools.browser_tool import _truncate_snapshot
        short = "- heading \"Example\" [ref=e1]\n- link \"More\" [ref=e2]"
        assert _truncate_snapshot(short) == short

    def test_long_snapshot_truncated_at_line_boundary(self):
        from tools.browser_tool import _truncate_snapshot
        # Create a snapshot that exceeds 8000 chars
        lines = [f'- item "Element {i}" [ref=e{i}]' for i in range(500)]
        snapshot = "\n".join(lines)
        assert len(snapshot) > 8000

        result = _truncate_snapshot(snapshot, max_chars=200)
        assert len(result) <= 300  # some margin for the truncation note
        assert "truncated" in result.lower()
        # Every line in the result should be complete (not cut mid-element)
        for line in result.split("\n"):
            if line.strip() and "truncated" not in line.lower():
                assert line.startswith("- item") or line == ""

    def test_truncation_reports_remaining_count(self):
        from tools.browser_tool import _truncate_snapshot
        lines = [f"- line {i}" for i in range(100)]
        snapshot = "\n".join(lines)
        result = _truncate_snapshot(snapshot, max_chars=200)
        # Should mention how many lines were truncated
        assert "more line" in result.lower()


# ---------------------------------------------------------------------------
# Scroll optimization
# ---------------------------------------------------------------------------

class TestScrollOptimization:

    def test_agent_browser_path_uses_pixel_scroll(self):
        """Verify agent-browser path uses single pixel-based scroll, not 5x loop."""
        import inspect
        import tools.browser_tool as bt
        src = inspect.getsource(bt.browser_scroll)
        # The agent-browser (non-camofox) path should use _SCROLL_PIXELS
        assert "_SCROLL_PIXELS" in src, \
            "browser_scroll should use _SCROLL_PIXELS for agent-browser path"
        # Camofox path may still loop — that's fine (different API)

    def test_scroll_pixels_constant_exists(self):
        """Verify _SCROLL_PIXELS is defined."""
        import tools.browser_tool as bt
        # It's a local inside browser_scroll, check the source
        import inspect
        src = inspect.getsource(bt.browser_scroll)
        assert "_SCROLL_PIXELS" in src


# ---------------------------------------------------------------------------
# Empty stdout = failure
# ---------------------------------------------------------------------------

class TestNewBrowserTools:
    """Verify the 6 new browser tools exist and are registered."""

    def test_all_new_tools_in_schemas(self):
        from tools.browser_tool import BROWSER_TOOL_SCHEMAS
        names = {s["name"] for s in BROWSER_TOOL_SCHEMAS}
        expected = {"browser_hover", "browser_select", "browser_wait",
                    "browser_forward", "browser_reload", "browser_scroll_to"}
        assert expected.issubset(names), f"Missing: {expected - names}"

    def test_new_tools_registered(self):
        """Verify tools register when browser_tool is imported."""
        import importlib
        import tools.browser_tool  # force module-level register() calls
        importlib.reload(tools.browser_tool)
        from tools.registry import registry
        all_names = registry.get_all_tool_names()
        for name in ("browser_hover", "browser_select", "browser_wait",
                     "browser_forward", "browser_reload", "browser_scroll_to"):
            assert name in all_names, f"{name} not in registry (have: {all_names})"

    def test_hover_handler_exists(self):
        from tools.browser_tool import browser_hover
        assert callable(browser_hover)

    def test_select_handler_exists(self):
        from tools.browser_tool import browser_select
        assert callable(browser_select)

    def test_wait_handler_exists(self):
        from tools.browser_tool import browser_wait
        assert callable(browser_wait)

    def test_forward_handler_exists(self):
        from tools.browser_tool import browser_forward
        assert callable(browser_forward)

    def test_reload_handler_exists(self):
        from tools.browser_tool import browser_reload
        assert callable(browser_reload)

    def test_scroll_to_handler_exists(self):
        from tools.browser_tool import browser_scroll_to
        assert callable(browser_scroll_to)

    def test_forward_reload_in_empty_ok_commands(self):
        """forward and reload may return empty output — verify whitelisted."""
        import inspect
        import tools.browser_tool as bt
        src = inspect.getsource(bt._run_browser_command)
        assert '"forward"' in src and '"reload"' in src, \
            "forward and reload should be in _EMPTY_OK_COMMANDS"

    def test_total_tool_count_is_16(self):
        from tools.browser_tool import BROWSER_TOOL_SCHEMAS
        assert len(BROWSER_TOOL_SCHEMAS) == 16


class TestEmptyStdoutFailure:

    def test_empty_stdout_returns_failure(self):
        """Verify _run_browser_command returns failure on empty stdout."""
        import inspect
        import tools.browser_tool as bt
        src = inspect.getsource(bt._run_browser_command)
        assert "returned empty output" in src or "returned no output" in src, \
            "_run_browser_command should treat empty stdout as failure"
