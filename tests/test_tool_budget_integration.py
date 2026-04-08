"""Integration tests for tool budget wiring in the agent loop.

Tests ToolBudget behavior through an agent-like stub without
instantiating a full AIAgent.
"""

import types

import pytest


def _make_agent_stub(
    context_length: int = 32_000,
    current_token_usage: int = 0,
    budget_config: dict | None = None,
):
    """Build a minimal AIAgent-like stub with budget layer attached."""
    from agent.tool_budget import ToolBudget

    stub = types.SimpleNamespace(
        context_compressor=types.SimpleNamespace(context_length=context_length),
        _tool_budget=ToolBudget(
            context_length=context_length,
            config=budget_config or {},
        ),
        quiet_mode=True,
    )
    return stub


class TestBudgetInitialization:
    def test_budget_created_from_context_length(self):
        stub = _make_agent_stub(context_length=32_000)
        assert stub._tool_budget is not None
        assert stub._tool_budget.context_length == 32_000
        assert stub._tool_budget.baseline_chars == 32_000

    def test_frontier_model_has_large_budget(self):
        stub = _make_agent_stub(context_length=1_000_000)
        assert stub._tool_budget.baseline_chars == 1_000_000

    def test_config_overrides(self):
        stub = _make_agent_stub(
            context_length=32_000,
            budget_config={"result_pct": 0.10, "floor_tokens": 1000},
        )
        assert stub._tool_budget.baseline_chars == 12_800
        assert stub._tool_budget.floor_chars == 4_000


class TestBudgetAppliedToResults:
    def test_small_result_unchanged(self):
        stub = _make_agent_stub(context_length=200_000)
        result, spilled = stub._tool_budget.apply(
            result="short output", tool_use_id="t1", current_token_usage=0,
        )
        assert result == "short output"
        assert not spilled

    def test_large_result_on_small_model_gets_truncated(self, tmp_path):
        stub = _make_agent_stub(context_length=32_000)
        stub._tool_budget.spill_dir = str(tmp_path)
        big = "x" * 100_000
        result, spilled = stub._tool_budget.apply(
            result=big, tool_use_id="t2", current_token_usage=0,
        )
        assert spilled
        assert len(result) < 100_000
        assert "read_file" in result

    def test_same_result_on_frontier_model_passes_through(self):
        stub = _make_agent_stub(context_length=1_000_000)
        big = "x" * 100_000
        result, spilled = stub._tool_budget.apply(
            result=big, tool_use_id="t3", current_token_usage=0,
        )
        assert result == big
        assert not spilled

    def test_context_pressure_triggers_smaller_budget(self, tmp_path):
        stub = _make_agent_stub(context_length=32_000)
        stub._tool_budget.spill_dir = str(tmp_path)
        medium = "x" * 20_000
        _, spilled_relaxed = stub._tool_budget.apply(
            result=medium, tool_use_id="t4", current_token_usage=0,
        )
        _, spilled_tight = stub._tool_budget.apply(
            result=medium, tool_use_id="t5", current_token_usage=28_000,
        )
        assert not spilled_relaxed
        assert spilled_tight


class TestDynamicTurnBudget:
    def test_turn_budget_scales_with_context(self):
        stub_small = _make_agent_stub(context_length=32_000)
        stub_big = _make_agent_stub(context_length=200_000)
        assert stub_small._tool_budget.turn_budget_chars < stub_big._tool_budget.turn_budget_chars

    def test_turn_budget_config_override(self):
        stub = _make_agent_stub(context_length=100_000, budget_config={"turn_pct": 0.30})
        assert stub._tool_budget.turn_budget_chars == 120_000


class TestCompactBeforeSpill:
    def test_should_compact_when_tight(self):
        stub = _make_agent_stub(context_length=32_000)
        assert stub._tool_budget.should_compact_first(
            result_chars=20_000, current_token_usage=28_000,
        )

    def test_should_not_compact_when_plenty_of_room(self):
        stub = _make_agent_stub(context_length=200_000)
        assert not stub._tool_budget.should_compact_first(
            result_chars=20_000, current_token_usage=10_000,
        )

    def test_compact_disabled_via_config(self):
        stub = _make_agent_stub(
            context_length=32_000,
            budget_config={"compact_before_spill": False},
        )
        assert not stub._tool_budget.should_compact_first(
            result_chars=20_000, current_token_usage=28_000,
        )


class TestSpillFileContents:
    def test_full_content_preserved_in_spill(self, tmp_path):
        stub = _make_agent_stub(context_length=32_000)
        stub._tool_budget.spill_dir = str(tmp_path)
        content = "\n".join(f"line {i}: data" for i in range(5000))
        result, spilled = stub._tool_budget.apply(
            result=content, tool_use_id="spill-test", current_token_usage=0,
        )
        assert spilled
        spill_file = tmp_path / "spill-test.txt"
        assert spill_file.exists()
        assert spill_file.read_text() == content

    def test_preview_instructs_read_file(self, tmp_path):
        stub = _make_agent_stub(context_length=32_000)
        stub._tool_budget.spill_dir = str(tmp_path)
        content = "x\n" * 50_000
        result, spilled = stub._tool_budget.apply(
            result=content, tool_use_id="rf-test", current_token_usage=0,
        )
        assert spilled
        assert "read_file" in result
        assert "offset=" in result
