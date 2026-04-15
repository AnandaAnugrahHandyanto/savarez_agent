"""Tests for DELEGATION_GUIDANCE — content, injection, and enforcement interaction."""

from agent.prompt_builder import (
    DELEGATION_GUIDANCE,
    TOOL_USE_ENFORCEMENT_GUIDANCE,
    MEMORY_GUIDANCE,
    SESSION_SEARCH_GUIDANCE,
    SKILLS_GUIDANCE,
)


class TestDelegationGuidanceContent:
    def test_is_string(self):
        assert isinstance(DELEGATION_GUIDANCE, str)

    def test_not_empty(self):
        assert len(DELEGATION_GUIDANCE.strip()) > 50

    def test_within_length_limit(self):
        line_count = DELEGATION_GUIDANCE.count("\n") + 1
        assert 3 <= line_count <= 8, f"Expected 3-8 lines, got {line_count}"

    def test_mentions_delegate_task(self):
        assert "delegate_task" in DELEGATION_GUIDANCE

    def test_uses_prospective_language(self):
        lower = DELEGATION_GUIDANCE.lower()
        assert any(phrase in lower for phrase in [
            "at task intake",
            "when a request",
            "breaks into",
            "will require",
        ])

    def test_no_retrospective_triggers(self):
        assert "would flood" not in DELEGATION_GUIDANCE.lower()
        assert "already doing" not in DELEGATION_GUIDANCE.lower()

    def test_includes_complexity_threshold(self):
        lower = DELEGATION_GUIDANCE.lower()
        assert any(phrase in lower for phrase in ["3 or more", "3+", "multiple"])

    def test_uses_prefer_not_always(self):
        lower = DELEGATION_GUIDANCE.lower()
        assert "prefer" in lower
        assert "always delegate" not in lower
        assert "you must delegate" not in lower

    def test_mentions_independent(self):
        assert "independent" in DELEGATION_GUIDANCE.lower()

    def test_discourages_simple_delegation(self):
        lower = DELEGATION_GUIDANCE.lower()
        assert any(phrase in lower for phrase in ["do not delegate", "simple", "mechanical"])

    def test_mentions_context_for_subagent(self):
        assert "context" in DELEGATION_GUIDANCE.lower()

    def test_consistent_with_other_guidance_style(self):
        assert "```" not in DELEGATION_GUIDANCE
        assert "#" not in DELEGATION_GUIDANCE
        assert "**" not in DELEGATION_GUIDANCE


class TestEnforcementDelegationInteraction:
    def test_enforcement_mentions_delegate_task(self):
        assert "delegate_task" in TOOL_USE_ENFORCEMENT_GUIDANCE

    def test_enforcement_says_delegation_is_tool_use(self):
        lower = TOOL_USE_ENFORCEMENT_GUIDANCE.lower()
        assert "delegation" in lower or "delegating" in lower
        assert "counts as tool use" in lower or "is tool use" in lower or "best way to proceed" in lower

    def test_enforcement_still_has_original_directives(self):
        assert "MUST" in TOOL_USE_ENFORCEMENT_GUIDANCE
        assert "tool call" in TOOL_USE_ENFORCEMENT_GUIDANCE.lower()
        assert "Every response should" in TOOL_USE_ENFORCEMENT_GUIDANCE


class TestDelegationGuidanceInjection:
    def test_all_four_guidance_constants_exist_and_are_strings(self):
        for const in [MEMORY_GUIDANCE, SESSION_SEARCH_GUIDANCE, SKILLS_GUIDANCE, DELEGATION_GUIDANCE]:
            assert isinstance(const, str)
            assert len(const) > 20

    def test_delegation_guidance_does_not_leak_into_other_constants(self):
        for const_name, const in [
            ("MEMORY", MEMORY_GUIDANCE),
            ("SESSION_SEARCH", SESSION_SEARCH_GUIDANCE),
            ("SKILLS", SKILLS_GUIDANCE),
        ]:
            assert "delegate_task" not in const, f"{const_name}_GUIDANCE should not reference delegate_task"

    def test_simulated_injection_pattern(self):
        valid_tool_names = {"memory", "session_search", "skill_manage", "delegate_task"}
        tool_guidance = []
        if "memory" in valid_tool_names:
            tool_guidance.append(MEMORY_GUIDANCE)
        if "session_search" in valid_tool_names:
            tool_guidance.append(SESSION_SEARCH_GUIDANCE)
        if "skill_manage" in valid_tool_names:
            tool_guidance.append(SKILLS_GUIDANCE)
        if "delegate_task" in valid_tool_names:
            tool_guidance.append(DELEGATION_GUIDANCE)

        assert len(tool_guidance) == 4
        combined = " ".join(tool_guidance)
        assert "delegate_task" in combined

    def test_delegation_absent_when_tool_disabled(self):
        valid_tool_names = {"memory", "session_search"}
        tool_guidance = []
        if "memory" in valid_tool_names:
            tool_guidance.append(MEMORY_GUIDANCE)
        if "session_search" in valid_tool_names:
            tool_guidance.append(SESSION_SEARCH_GUIDANCE)
        if "skill_manage" in valid_tool_names:
            tool_guidance.append(SKILLS_GUIDANCE)
        if "delegate_task" in valid_tool_names:
            tool_guidance.append(DELEGATION_GUIDANCE)

        combined = " ".join(tool_guidance)
        assert "delegate_task" not in combined
        assert len(tool_guidance) == 2

    def test_only_delegation_when_sole_tool(self):
        valid_tool_names = {"delegate_task"}
        tool_guidance = []
        if "memory" in valid_tool_names:
            tool_guidance.append(MEMORY_GUIDANCE)
        if "session_search" in valid_tool_names:
            tool_guidance.append(SESSION_SEARCH_GUIDANCE)
        if "skill_manage" in valid_tool_names:
            tool_guidance.append(SKILLS_GUIDANCE)
        if "delegate_task" in valid_tool_names:
            tool_guidance.append(DELEGATION_GUIDANCE)

        assert len(tool_guidance) == 1
        assert tool_guidance[0] == DELEGATION_GUIDANCE


class TestDelegationImportSafety:
    def test_delegation_guidance_importable_from_prompt_builder(self):
        from agent.prompt_builder import DELEGATION_GUIDANCE as dg
        assert isinstance(dg, str)

    def test_no_name_collision_with_existing_constants(self):
        import agent.prompt_builder as pb
        names = [n for n in dir(pb) if n.endswith("_GUIDANCE")]
        assert "DELEGATION_GUIDANCE" in names
        assert names.count("DELEGATION_GUIDANCE") == 1
