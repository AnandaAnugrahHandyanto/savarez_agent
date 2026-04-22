"""Tests for vault auto-injection integration with _build_system_prompt.

Verifies that vault content appears in the system prompt when vault is
configured, and is absent otherwise.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_minimal_agent(**overrides):
    """Create a minimal AIAgent for testing, with vault attrs settable."""
    from run_agent import AIAgent

    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        a = AIAgent(
            api_key="test-k...7890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        a.client = MagicMock()

    # Apply overrides after creation
    for k, v in overrides.items():
        setattr(a, k, v)

    return a


class TestVaultSystemPromptIntegration:
    """Test that _build_system_prompt injects vault content when configured."""

    def test_vault_not_injected_when_disabled(self, tmp_path):
        """Vault content should not appear when vault_enabled=False."""
        vault_dir = tmp_path / "vault"
        agent_dir = vault_dir / "Agent-Hermes"
        agent_dir.mkdir(parents=True)
        (agent_dir / "working-context.md").write_text("Active task X", encoding="utf-8")

        agent = _make_minimal_agent(
            _vault_enabled=False,
            _vault_path=str(vault_dir),
        )

        prompt = agent._build_system_prompt()
        assert "VAULT: WORKING CONTEXT" not in prompt
        assert "Active task X" not in prompt

    def test_vault_injected_when_enabled(self, tmp_path):
        """Vault content should appear in system prompt when vault_enabled=True."""
        vault_dir = tmp_path / "vault"
        agent_dir = vault_dir / "Agent-Hermes"
        shared_dir = vault_dir / "Agent-Shared"
        agent_dir.mkdir(parents=True)
        shared_dir.mkdir(parents=True)
        (agent_dir / "working-context.md").write_text(
            "---\ndate: 2026-04-22\n---\n## Status\nActive: vault fix",
            encoding="utf-8",
        )
        (shared_dir / "user-profile.md").write_text(
            "# User Profile\n\nName: Test User",
            encoding="utf-8",
        )

        agent = _make_minimal_agent(
            _vault_enabled=True,
            _vault_path=str(vault_dir),
        )

        prompt = agent._build_system_prompt()
        assert "VAULT: WORKING CONTEXT" in prompt
        assert "Active: vault fix" in prompt
        assert "VAULT: USER PROFILE" in prompt
        assert "Name: Test User" in prompt

    def test_vault_after_memory_blocks(self, tmp_path):
        """Vault injection should appear after Layer 1 memory blocks."""
        # Set up memory files
        mem_dir = tmp_path / "memories"
        mem_dir.mkdir(parents=True)
        (mem_dir / "MEMORY.md").write_text("Layer 1 memory note", encoding="utf-8")

        # Set up vault files
        vault_dir = tmp_path / "vault"
        agent_dir = vault_dir / "Agent-Hermes"
        agent_dir.mkdir(parents=True)
        (agent_dir / "working-context.md").write_text("Vault content", encoding="utf-8")

        # Create agent with memory enabled
        from run_agent import AIAgent
        from tools.memory_tool import MemoryStore

        with (
            patch("run_agent.get_tool_definitions", return_value=[]),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
            patch(
                "hermes_cli.config.load_config",
                return_value={
                    "memory": {
                        "memory_enabled": True,
                        "user_profile_enabled": False,
                        "memory_char_limit": 2200,
                        "user_char_limit": 1375,
                    },
                },
            ),
        ):
            monkeypatch_env = {}
            # Set HERMES_HOME so MemoryStore reads from tmp_path
            os.environ["HERMES_HOME"] = str(tmp_path)
            try:
                a = AIAgent(
                    api_key="test-k...7890",
                    base_url="https://openrouter.ai/api/v1",
                    quiet_mode=True,
                    skip_context_files=True,
                    skip_memory=False,
                )
                a.client = MagicMock()
            finally:
                del os.environ["HERMES_HOME"]

        a._vault_enabled = True
        a._vault_path = str(vault_dir)

        prompt = a._build_system_prompt()
        mem_pos = prompt.find("MEMORY (your personal notes)")
        vault_pos = prompt.find("VAULT: WORKING CONTEXT")
        assert mem_pos > 0, "Layer 1 memory block not found in prompt"
        assert vault_pos > 0, "Vault block not found in prompt"
        assert mem_pos < vault_pos, "Vault should appear after Layer 1 memory"

    def test_missing_vault_path_graceful(self, tmp_path):
        """Agent works fine even if vault path doesn't exist."""
        agent = _make_minimal_agent(
            _vault_enabled=True,
            _vault_path="/nonexistent/vault/path",
        )

        # Should not crash
        prompt = agent._build_system_prompt()
        assert "VAULT:" not in prompt

    def test_no_vault_config_graceful(self):
        """Agent works fine with no vault set (defaults)."""
        agent = _make_minimal_agent(
            _vault_enabled=False,
            _vault_path="",
        )

        prompt = agent._build_system_prompt()
        assert "VAULT:" not in prompt