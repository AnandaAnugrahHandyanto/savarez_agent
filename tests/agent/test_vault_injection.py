"""Tests for agent/vault_injection.py — Obsidian vault auto-injection into system prompt."""

import pytest
import os
from pathlib import Path

from agent.vault_injection import (
    build_vault_system_prompt,
    _read_vault_file,
    _strip_yaml_frontmatter,
    WORKING_CONTEXT_CHAR_LIMIT,
    USER_PROFILE_CHAR_LIMIT,
)


# ---------------------------------------------------------------------------
# _strip_yaml_frontmatter
# ---------------------------------------------------------------------------

class TestStripYamlFrontmatter:
    def test_strips_simple_frontmatter(self):
        content = "---\ndate: 2026-04-22\n---\nHello world"
        assert _strip_yaml_frontmatter(content) == "Hello world"

    def test_no_frontmatter(self):
        content = "Just some text"
        assert _strip_yaml_frontmatter(content) == "Just some text"

    def test_frontmatter_with_blank_lines(self):
        content = "---\ndate: 2026-04-22\nprojects: [X]\n---\n\nActual content here"
        result = _strip_yaml_frontmatter(content)
        assert result == "Actual content here"

    def test_unclosed_frontmatter_returns_original(self):
        content = "---\ndate: 2026-04-22\nNo closing dashes"
        assert _strip_yaml_frontmatter(content) == content


# ---------------------------------------------------------------------------
# _read_vault_file
# ---------------------------------------------------------------------------

class TestReadVaultFile:
    def test_reads_existing_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("some content", encoding="utf-8")
        result = _read_vault_file(f, 4000)
        assert result == "some content"

    def test_returns_none_for_missing_file(self, tmp_path):
        f = tmp_path / "nonexistent.md"
        result = _read_vault_file(f, 4000)
        assert result is None

    def test_returns_none_for_empty_file(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("", encoding="utf-8")
        result = _read_vault_file(f, 4000)
        assert result is None

    def test_returns_none_for_whitespace_only(self, tmp_path):
        f = tmp_path / "ws.md"
        f.write_text("   \n\n  ", encoding="utf-8")
        result = _read_vault_file(f, 4000)
        assert result is None

    def test_strips_frontmatter(self, tmp_path):
        f = tmp_path / "frontmatter.md"
        f.write_text("---\ndate: 2026-04-22\n---\nReal content", encoding="utf-8")
        result = _read_vault_file(f, 4000)
        assert result == "Real content"

    def test_truncates_long_file(self, tmp_path):
        f = tmp_path / "long.md"
        long_content = "x" * 5000
        f.write_text(long_content, encoding="utf-8")
        result = _read_vault_file(f, 100)
        assert len(result) < 200  # truncation + notice
        assert "truncated" in result

    def test_truncation_at_newline(self, tmp_path):
        f = tmp_path / "multiline.md"
        lines = ["line " + str(i) for i in range(100)]
        content = "\n".join(lines)
        f.write_text(content, encoding="utf-8")
        # Small limit, should truncate at a newline boundary
        result = _read_vault_file(f, 50)
        assert "truncated" in result
        # Should not cut mid-line
        for line in result.split("\n"):
            if line and "truncated" not in line:
                assert line.startswith("line")


# ---------------------------------------------------------------------------
# build_vault_system_prompt
# ---------------------------------------------------------------------------

class TestBuildVaultSystemPrompt:
    def test_empty_path_returns_empty(self):
        assert build_vault_system_prompt("") == ""

    def test_nonexistent_path_returns_empty(self, tmp_path):
        assert build_vault_system_prompt(str(tmp_path / "nope")) == ""

    def test_empty_vault_dir_returns_empty(self, tmp_path):
        assert build_vault_system_prompt(str(tmp_path)) == ""

    def test_injects_working_context(self, tmp_path):
        vault = tmp_path / "vault"
        agent_dir = vault / "Agent-Hermes"
        agent_dir.mkdir(parents=True)
        wc = agent_dir / "working-context.md"
        wc.write_text("---\ndate: 2026-04-22\n---\n## Current Status\n- Status: Active", encoding="utf-8")

        result = build_vault_system_prompt(str(vault))
        assert "VAULT: WORKING CONTEXT" in result
        assert "Status: Active" in result

    def test_injects_user_profile(self, tmp_path):
        vault = tmp_path / "vault"
        shared_dir = vault / "Agent-Shared"
        shared_dir.mkdir(parents=True)
        up = shared_dir / "user-profile.md"
        up.write_text("# User Profile\n\nName: AJ", encoding="utf-8")

        result = build_vault_system_prompt(str(vault))
        assert "VAULT: USER PROFILE" in result
        assert "Name: AJ" in result

    def test_injects_both_files(self, tmp_path):
        vault = tmp_path / "vault"
        agent_dir = vault / "Agent-Hermes"
        shared_dir = vault / "Agent-Shared"
        agent_dir.mkdir(parents=True)
        shared_dir.mkdir(parents=True)

        (agent_dir / "working-context.md").write_text(
            "---\ndate: 2026-04-22\n---\nWorking on X", encoding="utf-8"
        )
        (shared_dir / "user-profile.md").write_text(
            "# User Profile\n\nName: AJ", encoding="utf-8"
        )

        result = build_vault_system_prompt(str(vault))
        assert "VAULT: WORKING CONTEXT" in result
        assert "VAULT: USER PROFILE" in result
        assert "Working on X" in result
        assert "Name: AJ" in result

    def test_skips_empty_working_context(self, tmp_path):
        vault = tmp_path / "vault"
        agent_dir = vault / "Agent-Hermes"
        shared_dir = vault / "Agent-Shared"
        agent_dir.mkdir(parents=True)
        shared_dir.mkdir(parents=True)

        (agent_dir / "working-context.md").write_text("", encoding="utf-8")
        (shared_dir / "user-profile.md").write_text("Name: AJ", encoding="utf-8")

        result = build_vault_system_prompt(str(vault))
        assert "VAULT: WORKING CONTEXT" not in result
        assert "VAULT: USER PROFILE" in result

    def test_format_matches_memory_block_style(self, tmp_path):
        vault = tmp_path / "vault"
        agent_dir = vault / "Agent-Hermes"
        agent_dir.mkdir(parents=True)
        (agent_dir / "working-context.md").write_text("Active task", encoding="utf-8")

        result = build_vault_system_prompt(str(vault))
        # Should use the same separator as memory_tool (═══)
        assert "\u2550" in result  # ═ character
        assert "VAULT: WORKING CONTEXT" in result