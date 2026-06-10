"""M4·A1 — plan-mode gate classifier (TDD)."""
from acp_adapter.plan_gate import (
    MODE_PLAN,
    is_mutating_tool,
    plan_mode_allowed_tools,
    PLAN_BLOCK_FMT,
)


def test_mode_plan_constant():
    assert MODE_PLAN == "plan"


def test_is_mutating_tool_flags_edit_and_execute_kinds():
    for t in ("write_file", "patch", "terminal", "process", "execute_code",
              "delegate_task", "image_generate", "text_to_speech",
              "browser_click", "browser_type"):
        assert is_mutating_tool(t) is True, t


def test_is_mutating_tool_allows_read_only_kinds():
    for t in ("read_file", "search_files", "web_search", "web_extract",
              "browser_snapshot", "browser_vision", "skill_view", "_thinking"):
        assert is_mutating_tool(t) is False, t


def test_plan_mode_allowed_tools_permits_planning_blocks_mutation():
    available = {
        "read_file", "search_files", "web_search", "browser_snapshot",
        "todo", "memory", "session_search", "clarify",
        "write_file", "patch", "terminal", "process", "execute_code", "delegate_task",
    }
    allowed = plan_mode_allowed_tools(available)
    # Read-only + planning-safe tools are permitted (so the agent can form a plan).
    for t in ("read_file", "search_files", "web_search", "browser_snapshot",
              "todo", "memory", "session_search", "clarify"):
        assert t in allowed, f"{t} should be allowed in plan mode"
    # Mutating tools are NOT in the whitelist => the thread whitelist blocks them.
    for t in ("write_file", "patch", "terminal", "process", "execute_code", "delegate_task"):
        assert t not in allowed, f"{t} must be blocked in plan mode"


def test_todo_allowed_so_the_plan_can_be_emitted():
    # `todo` is kind 'other' but emits the AgentPlanUpdate the editor renders.
    assert "todo" in plan_mode_allowed_tools({"todo"})


def test_block_message_mentions_plan_and_formats_tool_name():
    msg = PLAN_BLOCK_FMT.format(tool_name="write_file")
    assert "write_file" in msg
    assert "Plan mode" in msg
