"""Tests for the Plan Mode hook plugin (Phase B2).

12 test cases covering plan mode activation, tool filtering, and deactivation.
"""

import importlib
import os

import pytest

# Load plan_mode_hook via importlib (hyphenated directory name)
_PLUGIN_DIR = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, "plugins", "hongxing-enhancements"
)
_spec = importlib.util.spec_from_file_location(
    "plan_mode_hook",
    os.path.join(_PLUGIN_DIR, "plan_mode_hook.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

enter_plan_mode = _mod.enter_plan_mode
exit_plan_mode = _mod.exit_plan_mode
is_active = _mod.is_active
pre_tool_call = _mod.pre_tool_call


@pytest.fixture(autouse=True)
def _reset_plan_mode():
    """Ensure plan mode is off before and after each test."""
    exit_plan_mode()
    yield
    exit_plan_mode()


# ── Inactive state ─────────────────────────────────────────────────────

class TestInactive:
    def test_inactive_allows_all(self):
        assert pre_tool_call("write_file", {"path": "/tmp/x"}) is None

    def test_inactive_allows_terminal(self):
        assert pre_tool_call("terminal", {"command": "rm -rf /"}) is None


# ── Activation / deactivation ─────────────────────────────────────────

class TestActivation:
    def test_enter_plan_mode(self):
        enter_plan_mode()
        assert is_active() is True

    def test_exit_plan_mode(self):
        enter_plan_mode()
        exit_plan_mode()
        assert is_active() is False


# ── Allowed tools in plan mode ─────────────────────────────────────────

class TestAllowedInPlanMode:
    def test_read_file_allowed(self):
        enter_plan_mode()
        assert pre_tool_call("read_file", {}) is None

    def test_search_files_allowed(self):
        enter_plan_mode()
        assert pre_tool_call("search_files", {"query": "foo"}) is None

    def test_session_search_allowed(self):
        enter_plan_mode()
        assert pre_tool_call("session_search", {"query": "bar"}) is None

    def test_plan_mode_tool_allowed(self):
        enter_plan_mode()
        assert pre_tool_call("plan_mode", {"action": "status"}) is None


# ── Denied tools in plan mode ──────────────────────────────────────────

class TestDeniedInPlanMode:
    def test_write_file_denied(self):
        enter_plan_mode()
        result = pre_tool_call("write_file", {"path": "/tmp/x"})
        assert result is not None
        assert result["action"] == "deny"

    def test_patch_denied(self):
        enter_plan_mode()
        result = pre_tool_call("patch", {"path": "/tmp/x"})
        assert result is not None
        assert result["action"] == "deny"

    def test_terminal_denied(self):
        enter_plan_mode()
        result = pre_tool_call("terminal", {"command": "ls"})
        assert result is not None
        assert result["action"] == "deny"

    def test_delegate_task_denied(self):
        enter_plan_mode()
        result = pre_tool_call("delegate_task", {"goal": "do stuff"})
        assert result is not None
        assert result["action"] == "deny"

    def test_todo_denied(self):
        enter_plan_mode()
        result = pre_tool_call("todo", {"todos": []})
        assert result is not None
        assert result["action"] == "deny"


# ── Memory action-aware filtering ─────────────────────────────────────

class TestMemoryInPlanMode:
    def test_memory_read_allowed(self):
        enter_plan_mode()
        assert pre_tool_call("memory", {"action": "read"}) is None

    def test_memory_add_denied(self):
        enter_plan_mode()
        result = pre_tool_call("memory", {"action": "add", "content": "x"})
        assert result is not None
        assert result["action"] == "deny"

    def test_memory_replace_denied(self):
        enter_plan_mode()
        result = pre_tool_call("memory", {"action": "replace"})
        assert result is not None
        assert result["action"] == "deny"


# ── Exit restores normal behavior ─────────────────────────────────────

class TestExitRestores:
    def test_exit_restores_write_file(self):
        enter_plan_mode()
        assert pre_tool_call("write_file", {})["action"] == "deny"
        exit_plan_mode()
        assert pre_tool_call("write_file", {}) is None

    def test_exit_restores_memory_add(self):
        enter_plan_mode()
        assert pre_tool_call("memory", {"action": "add"})["action"] == "deny"
        exit_plan_mode()
        assert pre_tool_call("memory", {"action": "add"}) is None
