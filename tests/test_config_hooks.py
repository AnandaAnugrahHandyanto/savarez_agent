"""Tests for config-driven hooks system."""

import asyncio
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from hermes_agent.config_hooks import (
    HookConfig,
    ConfigHookManager,
    get_config_hook_manager,
    invalidate_hook_cache,
)


class TestHookConfig:
    """Test HookConfig matcher logic."""

    def test_star_matches_all(self):
        """Wildcard matcher should match any tool."""
        hook = HookConfig(command="echo test", matcher="*")
        assert hook.matches("Bash")
        assert hook.matches("Read")
        assert hook.matches("Write")

    def test_single_tool_match(self):
        """Single tool matcher should match only that tool."""
        hook = HookConfig(command="echo test", matcher="Bash")
        assert hook.matches("Bash")
        assert not hook.matches("Read")
        assert not hook.matches("Write")

    def test_multiple_tools_match(self):
        """Pipe-separated matcher should match any listed tool."""
        hook = HookConfig(command="echo test", matcher="Bash|Read|Write")
        assert hook.matches("Bash")
        assert hook.matches("Read")
        assert hook.matches("Write")
        assert not hook.matches("Search")

    def test_empty_matcher_defaults_to_star(self):
        """Empty matcher should behave like star."""
        hook = HookConfig(command="echo test")
        assert hook.matches("Bash")
        assert hook.matches("Read")


class TestConfigHookManager:
    """Test ConfigHookManager lifecycle."""

    def test_load_hooks_from_config(self):
        """Manager should load hooks from config dict."""
        config = {
            "hooks": {
                "pre_tool_call": [
                    {
                        "command": "echo test",
                        "matcher": "Bash",
                        "timeout": 5,
                        "description": "Test hook",
                    }
                ]
            }
        }
        manager = ConfigHookManager(config)

        assert manager.has_hooks("pre_tool_call")
        assert not manager.has_hooks("post_tool_call")
        assert manager.has_hooks("pre_tool_call", "Bash")
        assert not manager.has_hooks("pre_tool_call", "Read")

    def test_invalid_hook_type_ignored(self):
        """Unknown hook types should be ignored with warning."""
        config = {
            "hooks": {
                "invalid_hook_type": [{"command": "echo test"}]
            }
        }
        manager = ConfigHookManager(config)
        assert not manager.has_hooks("invalid_hook_type")

    def test_hook_requires_command(self):
        """Hooks without command should be skipped."""
        config = {
            "hooks": {
                "pre_tool_call": [{"matcher": "Bash"}]  # Missing command
            }
        }
        manager = ConfigHookManager(config)
        assert not manager.has_hooks("pre_tool_call")


class TestHookExecution:
    """Test hook execution flow."""

    @pytest.mark.asyncio
    async def test_sync_hook_execution(self):
        """Sync hooks should execute and capture output."""
        manager = ConfigHookManager({
            "hooks": {
                "pre_tool_call": [
                    {
                        "command": "echo '{\"args\": {\"modified\": true}}'",
                        "matcher": "*",
                    }
                ]
            }
        })

        context = {"tool": "Bash", "args": {"original": True}}
        result = await manager.execute("pre_tool_call", context, "Bash")

        assert result["args"]["modified"] is True

    @pytest.mark.asyncio
    async def test_async_hook_non_blocking(self):
        """Async hooks should not block or modify context."""
        manager = ConfigHookManager({
            "hooks": {
                "pre_tool_call": [
                    {
                        "command": "sleep 10",  # Would timeout if blocking
                        "matcher": "*",
                        "async": True,
                        "timeout": 1,
                    }
                ]
            }
        })

        context = {"tool": "Bash", "args": {}}
        # Should complete quickly without waiting for sleep
        result = await manager.execute("pre_tool_call", context, "Bash")

        # Async hooks don't modify context
        assert result == context

    @pytest.mark.asyncio
    async def test_hook_timeout(self):
        """Hooks should respect timeout."""
        manager = ConfigHookManager({
            "hooks": {
                "pre_tool_call": [
                    {
                        "command": "sleep 10",
                        "matcher": "*",
                        "timeout": 1,
                    }
                ]
            }
        })

        context = {"tool": "Bash"}
        # Should raise timeout but be caught
        result = await manager.execute("pre_tool_call", context, "Bash")
        # Context unchanged after timeout
        assert result == context

    @pytest.mark.asyncio
    async def test_hook_filtering_by_tool(self):
        """Only matching hooks should execute."""
        manager = ConfigHookManager({
            "hooks": {
                "pre_tool_call": [
                    {
                        "command": "echo '{\"args\": {\"bash\": true}}'",
                        "matcher": "Bash",
                    },
                    {
                        "command": "echo '{\"args\": {\"read\": true}}'",
                        "matcher": "Read",
                    },
                ]
            }
        })

        # Execute for Bash - only Bash hook should run
        context = {"tool": "Bash", "args": {}}
        result = await manager.execute("pre_tool_call", context, "Bash")
        assert result["args"]["bash"] is True
        assert "read" not in result["args"]


class TestContextMerging:
    """Test context modification by hooks."""

    @pytest.mark.asyncio
    async def test_args_modification(self):
        """Hooks should be able to modify args."""
        manager = ConfigHookManager({
            "hooks": {
                "pre_tool_call": [
                    {
                        "command": "echo '{\"args\": {\"command\": \"modified\"}}'",
                        "matcher": "*",
                    }
                ]
            }
        })

        context = {"tool": "Bash", "args": {"command": "original"}}
        result = await manager.execute("pre_tool_call", context, "Bash")

        assert result["args"]["command"] == "modified"

    @pytest.mark.asyncio
    async def test_result_modification(self):
        """Hooks should be able to modify result."""
        manager = ConfigHookManager({
            "hooks": {
                "post_tool_call": [
                    {
                        "command": "echo '{\"result\": \"modified result\"}'",
                        "matcher": "*",
                    }
                ]
            }
        })

        context = {"tool": "Bash", "args": {}, "result": "original"}
        result = await manager.execute("post_tool_call", context, "Bash")

        assert result["result"] == "modified result"

    @pytest.mark.asyncio
    async def test_non_json_output_ignored(self):
        """Non-JSON output should not break context."""
        manager = ConfigHookManager({
            "hooks": {
                "pre_tool_call": [
                    {
                        "command": "echo 'plain text output'",
                        "matcher": "*",
                    }
                ]
            }
        })

        context = {"tool": "Bash", "args": {}}
        result = await manager.execute("pre_tool_call", context, "Bash")

        # Context unchanged
        assert result == context


class TestSingleton:
    """Test global hook manager singleton."""

    def test_singleton_caching(self):
        """Multiple calls should return same instance."""
        invalidate_hook_cache()
        manager1 = get_config_hook_manager()
        manager2 = get_config_hook_manager()
        assert manager1 is manager2

    def test_cache_invalidation(self):
        """invalidate_hook_cache should create new instance."""
        invalidate_hook_cache()
        manager1 = get_config_hook_manager()
        invalidate_hook_cache()
        manager2 = get_config_hook_manager()
        assert manager1 is not manager2

    def test_custom_config_bypasses_cache(self):
        """Providing config should create new instance."""
        invalidate_hook_cache()
        manager1 = get_config_hook_manager()
        manager2 = get_config_hook_manager({"hooks": {}})
        assert manager1 is not manager2
