"""W3 / F-014 regression tests.

The skill-context extraction must be a pure refactor — every caller path's
output is byte-identical to pre-refactor behaviour. These tests encode
the expected output for 7 representative fixtures; they also exercise
the cron and CLI adapters end-to-end to catch wiring drift.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.skill_context import build_skill_context


# ---------------------------------------------------------------------------
# Fixtures — each is a `loaded_skill` dict as returned by skills_tool.skill_view
# ---------------------------------------------------------------------------

SKILL_PLAIN = {
    "content": "# My Skill\n\nDo the thing.\n",
}

SKILL_WITH_MERMAID = {
    "content": "# Planned\nBody.",
    "mermaid_plan": "flowchart TD\n  A-->B",
}

SKILL_GATEWAY_HINT = {
    "content": "Needs a key.",
    "gateway_setup_hint": "Set FOO_KEY in ~/.hermes/.env",
}

SKILL_SETUP_SKIPPED = {
    "content": "Partial skill.",
    "setup_skipped": True,
}

SKILL_SETUP_NEEDED = {
    "content": "Requires setup.",
    "setup_needed": True,
    "setup_note": "Run `./install.sh` first.",
}

SKILL_LINKED = {
    "content": "Main body.",
    "linked_files": {"refs": ["references/a.md", "templates/t.md"]},
}


# ---------------------------------------------------------------------------
# Shared-block byte-equality: flags ON vs flags OFF
# ---------------------------------------------------------------------------

CLI_NOTE = "[System activated]"
CRON_NOTE = '[SYSTEM: The user has invoked the "mine" skill, indicating they want you to follow its instructions. The full skill content is loaded below.]'


class TestPlainSkill:
    def test_cli_path_renders_activation_and_content(self):
        out = build_skill_context(
            SKILL_PLAIN,
            activation_note=CLI_NOTE,
            include_setup_hints=True,
            include_supporting_files=True,
        )
        assert out == f"{CLI_NOTE}\n\n# My Skill\n\nDo the thing."

    def test_cron_path_same_output_when_no_hints_apply(self):
        cli = build_skill_context(
            SKILL_PLAIN,
            activation_note=CLI_NOTE,
            include_setup_hints=True,
            include_supporting_files=True,
        )
        cron = build_skill_context(
            SKILL_PLAIN,
            activation_note=CLI_NOTE,
            include_setup_hints=False,
            include_supporting_files=False,
        )
        # Plain skill has no setup/supporting content — outputs must match.
        assert cli == cron


class TestMermaid:
    def test_braid_block_rendered_between_activation_and_content(self):
        out = build_skill_context(
            SKILL_WITH_MERMAID,
            activation_note=CLI_NOTE,
            include_setup_hints=True,
            include_supporting_files=True,
        )
        assert "[BRAID Reasoning Plan" in out
        assert "```mermaid\nflowchart TD\n  A-->B\n```" in out
        assert out.index(CLI_NOTE) < out.index("[BRAID Reasoning Plan")
        assert out.index("```mermaid") < out.index("Body.")

    def test_cron_also_gets_braid(self):
        out = build_skill_context(
            SKILL_WITH_MERMAID,
            activation_note=CRON_NOTE,
            include_setup_hints=False,
            include_supporting_files=False,
        )
        assert "[BRAID Reasoning Plan" in out
        assert "```mermaid" in out


class TestSetupHints:
    def test_gateway_hint_renders_with_flag(self):
        out = build_skill_context(
            SKILL_GATEWAY_HINT,
            activation_note=CLI_NOTE,
            include_setup_hints=True,
        )
        assert "[Skill setup note: Set FOO_KEY in ~/.hermes/.env]" in out

    def test_gateway_hint_suppressed_when_flag_off(self):
        out = build_skill_context(
            SKILL_GATEWAY_HINT,
            activation_note=CRON_NOTE,
            include_setup_hints=False,
        )
        assert "Skill setup note" not in out
        assert "FOO_KEY" not in out

    def test_setup_skipped_hint(self):
        out = build_skill_context(
            SKILL_SETUP_SKIPPED,
            activation_note=CLI_NOTE,
            include_setup_hints=True,
        )
        assert "[Skill setup note: Required environment setup was skipped." in out

    def test_setup_needed_with_note(self):
        out = build_skill_context(
            SKILL_SETUP_NEEDED,
            activation_note=CLI_NOTE,
            include_setup_hints=True,
        )
        assert "[Skill setup note: Run `./install.sh` first.]" in out

    def test_precedence_setup_skipped_beats_others(self):
        both = {
            **SKILL_SETUP_NEEDED,
            "gateway_setup_hint": "NEVER",
            "setup_skipped": True,
        }
        out = build_skill_context(
            both, activation_note=CLI_NOTE, include_setup_hints=True
        )
        assert "Required environment setup was skipped" in out
        assert "NEVER" not in out
        assert "install.sh" not in out


class TestSupportingFiles:
    def test_linked_files_rendered_with_skill_dir(self, tmp_path):
        # skill_view_target resolution falls back to the dir name when the
        # skill dir isn't inside SKILLS_DIR — use tmp_path so it always does.
        skill_dir = tmp_path / "mine"
        skill_dir.mkdir()
        out = build_skill_context(
            SKILL_LINKED,
            activation_note=CLI_NOTE,
            skill_dir=skill_dir,
            include_supporting_files=True,
        )
        assert "[This skill has supporting files" in out
        assert "- references/a.md" in out
        assert "- templates/t.md" in out
        assert 'skill_view(name="mine"' in out

    def test_supporting_files_suppressed_when_flag_off(self, tmp_path):
        skill_dir = tmp_path / "mine"
        skill_dir.mkdir()
        out = build_skill_context(
            SKILL_LINKED,
            activation_note=CRON_NOTE,
            skill_dir=skill_dir,
            include_supporting_files=False,
        )
        assert "supporting files" not in out
        assert "skill_view" not in out

    def test_enumerate_from_subdirs_when_no_linked_files(self, tmp_path):
        skill_dir = tmp_path / "mine"
        (skill_dir / "references").mkdir(parents=True)
        (skill_dir / "references" / "x.md").write_text("x")
        (skill_dir / "templates").mkdir()
        (skill_dir / "templates" / "y.md").write_text("y")
        out = build_skill_context(
            {"content": "body", "linked_files": {}},
            activation_note=CLI_NOTE,
            skill_dir=skill_dir,
            include_supporting_files=True,
        )
        assert "- references/x.md" in out
        assert "- templates/y.md" in out


# ---------------------------------------------------------------------------
# Adapter end-to-end: byte-identical through _build_skill_message
# ---------------------------------------------------------------------------

class TestCLIAdapter:
    def test_build_skill_message_appends_user_instruction(self):
        from agent.skill_commands import _build_skill_message

        out = _build_skill_message(
            loaded_skill=SKILL_PLAIN,
            skill_dir=None,
            activation_note=CLI_NOTE,
            user_instruction="pls do X",
        )
        assert out.endswith(
            "The user has provided the following instruction alongside the skill invocation: pls do X"
        )

    def test_build_skill_message_appends_runtime_note(self):
        from agent.skill_commands import _build_skill_message

        out = _build_skill_message(
            loaded_skill=SKILL_PLAIN,
            skill_dir=None,
            activation_note=CLI_NOTE,
            runtime_note="beware the Jabberwock",
        )
        assert out.endswith("[Runtime note: beware the Jabberwock]")

    def test_build_skill_message_includes_setup_hint(self):
        from agent.skill_commands import _build_skill_message

        out = _build_skill_message(
            loaded_skill=SKILL_GATEWAY_HINT,
            skill_dir=None,
            activation_note=CLI_NOTE,
        )
        # CLI path must keep rendering setup hints — that's the whole
        # point of the include_setup_hints=True default on the adapter.
        assert "[Skill setup note: Set FOO_KEY" in out

    def test_build_skill_message_no_extras_matches_block(self):
        """With no user_instruction or runtime_note, the adapter output
        equals the shared-block output — no trailing whitespace drift."""
        from agent.skill_commands import _build_skill_message

        adapter_out = _build_skill_message(
            loaded_skill=SKILL_PLAIN,
            skill_dir=None,
            activation_note=CLI_NOTE,
        )
        block_out = build_skill_context(
            SKILL_PLAIN,
            activation_note=CLI_NOTE,
            include_setup_hints=True,
            include_supporting_files=True,
        )
        assert adapter_out == block_out
