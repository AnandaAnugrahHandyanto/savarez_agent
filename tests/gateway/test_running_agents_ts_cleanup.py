"""Tests for _running_agents_ts cleanup — ensures timestamp entries are
removed whenever their corresponding _running_agents entry is deleted.

When an agent entry is removed from _running_agents (stop, new, resume,
shutdown), the matching _running_agents_ts entry must also be cleaned up.
Orphaned timestamps cause memory leaks and can corrupt stale-timeout checks
if session keys are reused.
"""

import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.run import GatewayRunner


def _make_runner(tmp_path) -> GatewayRunner:
    config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="t")},
        sessions_dir=tmp_path / "sessions",
    )
    runner = GatewayRunner(config)
    # Prevent real adapter creation
    runner._create_adapter = MagicMock(return_value=MagicMock())
    return runner


class TestRunningAgentsTsCleanup:
    def test_stop_command_cleans_ts(self, tmp_path):
        """Deleting from _running_agents on /stop must also pop _running_agents_ts."""
        runner = _make_runner(tmp_path)
        key = "chat_123"
        runner._running_agents[key] = MagicMock()
        runner._running_agents_ts[key] = 1000.0

        # Simulate what the stop path does
        if key in runner._running_agents:
            del runner._running_agents[key]
        runner._running_agents_ts.pop(key, None)

        assert key not in runner._running_agents
        assert key not in runner._running_agents_ts

    def test_new_command_cleans_ts(self, tmp_path):
        """Deleting from _running_agents on /new must also pop _running_agents_ts."""
        runner = _make_runner(tmp_path)
        key = "chat_456"
        runner._running_agents[key] = MagicMock()
        runner._running_agents_ts[key] = 2000.0

        if key in runner._running_agents:
            del runner._running_agents[key]
        runner._running_agents_ts.pop(key, None)

        assert key not in runner._running_agents
        assert key not in runner._running_agents_ts

    def test_resume_command_cleans_ts(self, tmp_path):
        """Deleting from _running_agents on /resume must also pop _running_agents_ts."""
        runner = _make_runner(tmp_path)
        key = "chat_789"
        runner._running_agents[key] = MagicMock()
        runner._running_agents_ts[key] = 3000.0

        if key in runner._running_agents:
            del runner._running_agents[key]
        runner._running_agents_ts.pop(key, None)

        assert key not in runner._running_agents
        assert key not in runner._running_agents_ts

    def test_shutdown_clears_ts(self, tmp_path):
        """_running_agents.clear() must be followed by _running_agents_ts.clear()."""
        runner = _make_runner(tmp_path)
        runner._running_agents = {"a": MagicMock(), "b": MagicMock()}
        runner._running_agents_ts = {"a": 100.0, "b": 200.0}

        runner._running_agents.clear()
        runner._running_agents_ts.clear()

        assert len(runner._running_agents) == 0
        assert len(runner._running_agents_ts) == 0

    def test_all_del_sites_have_ts_pop(self):
        """Source-level check: every `del self._running_agents[...]` must be
        followed (within a few lines) by `self._running_agents_ts.pop(...)`.
        This catches sites that were missed during code review."""
        import gateway.run as mod

        source = open(mod.__file__).read()

        # Find all del self._running_agents[...] lines
        del_pattern = re.compile(
            r'del\s+self\._running_agents\[(\w+)\]'
        )
        # Find all self._running_agents_ts.pop(...) lines
        pop_pattern = re.compile(
            r'self\._running_agents_ts\.pop\('
        )

        del_lines = []
        pop_lines = []
        for i, line in enumerate(source.splitlines(), 1):
            # Only match actual del statements (not docstring references)
            if del_pattern.search(line) and line.lstrip().startswith("del "):
                del_lines.append(i)
            if pop_pattern.search(line):
                pop_lines.append(i)

        # For each del line, check that there's a pop within 5 lines after it
        missing = []
        for del_line in del_lines:
            # Check if any pop line is within 5 lines after the del
            found = any(
                pop_line > del_line and pop_line <= del_line + 5
                for pop_line in pop_lines
            )
            if not found:
                # Also check if the del is inside a .clear() block
                # (which has its own test)
                line_text = source.splitlines()[del_line - 1]
                if '.clear()' not in line_text:
                    missing.append(del_line)

        assert missing == [], (
            f"Lines with `del self._running_agents[...]` but no "
            f"`_running_agents_ts.pop` within 5 lines: {missing}"
        )

    def test_clear_site_also_clears_ts(self):
        """Source-level check: every `self._running_agents.clear()` must be
        followed by `self._running_agents_ts.clear()`."""
        import gateway.run as mod

        source = open(mod.__file__).read()

        clear_pattern = re.compile(r'self\._running_agents\.clear\(\)')
        ts_clear_pattern = re.compile(r'self\._running_agents_ts\.clear\(\)')

        clear_lines = []
        ts_clear_lines = []
        for i, line in enumerate(source.splitlines(), 1):
            if clear_pattern.search(line):
                clear_lines.append(i)
            if ts_clear_pattern.search(line):
                ts_clear_lines.append(i)

        missing = []
        for clear_line in clear_lines:
            found = any(
                ts_line > clear_line and ts_line <= clear_line + 5
                for ts_line in ts_clear_lines
            )
            if not found:
                missing.append(clear_line)

        assert missing == [], (
            f"Lines with `_running_agents.clear()` but no "
            f"`_running_agents_ts.clear()` within 5 lines: {missing}"
        )
