"""Tests for skill_commands per-platform cache isolation (#14536)."""
import pytest


class TestSkillCommandsPlatformCache:
    """Per-platform skill caches must be isolated (#14536)."""

    def test_get_skill_commands_accepts_platform(self):
        from agent.skill_commands import get_skill_commands
        import inspect
        sig = inspect.signature(get_skill_commands)
        assert "platform" in sig.parameters

    def test_per_platform_cache_exists(self):
        import agent.skill_commands as mod
        assert hasattr(mod, '_skill_commands_by_platform')

    def test_platform_isolation(self):
        """Different platforms get independent cache entries."""
        import agent.skill_commands as mod
        mod._skill_commands_by_platform.clear()
        mod._skill_commands = {"/test-skill": {"name": "test"}}

        telegram_cmds = mod.get_skill_commands(platform="telegram")
        discord_cmds = mod.get_skill_commands(platform="discord")

        # Remove a skill from telegram's view
        telegram_cmds.pop("/test-skill", None)

        # Discord should still have it
        assert "/test-skill" in discord_cmds, (
            "Removing skill from telegram cache leaked into discord cache"
        )

    def test_no_platform_returns_global(self):
        """Calling without platform returns the global cache."""
        import agent.skill_commands as mod
        mod._skill_commands = {"/global": {"name": "global"}}
        result = mod.get_skill_commands()
        assert "/global" in result
