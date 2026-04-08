"""Tests for context-aware tool result budgeting."""

import pytest


class TestEffectiveBudget:

    def test_large_context_empty_conversation(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=200_000, config={})
        budget = tb.effective_budget_chars(current_token_usage=0)
        assert budget == 200_000

    def test_small_context_empty_conversation(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={})
        budget = tb.effective_budget_chars(current_token_usage=0)
        assert budget == 32_000

    def test_small_context_mostly_full(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={})
        budget = tb.effective_budget_chars(current_token_usage=28_800)
        assert budget == 12_800  # (32000 - 28800) * 4

    def test_budget_never_below_floor(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={"floor_tokens": 2000})
        budget = tb.effective_budget_chars(current_token_usage=31_500)
        assert budget == 8_000

    def test_budget_at_zero_available(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={})
        budget = tb.effective_budget_chars(current_token_usage=32_000)
        assert budget == 8_000

    def test_custom_result_pct(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=100_000, config={"result_pct": 0.10})
        budget = tb.effective_budget_chars(current_token_usage=0)
        assert budget == 40_000

    def test_frontier_model_never_constrains(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=1_000_000, config={})
        budget = tb.effective_budget_chars(current_token_usage=0)
        assert budget == 1_000_000

    def test_over_capacity_clamps_to_floor(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={})
        budget = tb.effective_budget_chars(current_token_usage=40_000)
        assert budget == 8_000


class TestShouldCompactFirst:

    def test_no_compact_when_result_fits(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={})
        assert not tb.should_compact_first(
            result_chars=5_000, current_token_usage=10_000
        )

    def test_compact_when_tight_and_result_exceeds_available(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={})
        assert tb.should_compact_first(
            result_chars=20_000, current_token_usage=28_000
        )

    def test_no_compact_when_disabled(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={"compact_before_spill": False})
        assert not tb.should_compact_first(
            result_chars=20_000, current_token_usage=28_000
        )

    def test_no_compact_when_plenty_of_room(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=200_000, config={})
        assert not tb.should_compact_first(
            result_chars=20_000, current_token_usage=10_000
        )

    def test_no_compact_when_result_fits_in_available(self):
        """Even if available < baseline, no compact needed if result fits."""
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={})
        # available = (32000 - 28000) * 4 = 16000, baseline = 32000
        # result = 10000 fits in available
        assert not tb.should_compact_first(
            result_chars=10_000, current_token_usage=28_000
        )


class TestApplyBudget:

    def test_small_result_passes_through(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=200_000, config={})
        result, spilled = tb.apply("hello world", "t-1", current_token_usage=0)
        assert result == "hello world"
        assert not spilled

    def test_oversized_result_truncated_with_footer(self, tmp_path):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={}, spill_dir=str(tmp_path))
        big = "x" * 100_000
        result, spilled = tb.apply(big, "t-2", current_token_usage=0)
        assert spilled
        assert len(result) < 100_000
        assert "read_file" in result
        assert "offset" in result

    def test_spill_file_created(self, tmp_path):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={}, spill_dir=str(tmp_path))
        big = "line\n" * 20_000
        result, spilled = tb.apply(big, "t-3", current_token_usage=0)
        assert spilled
        spill_files = list(tmp_path.glob("*.txt"))
        assert len(spill_files) == 1
        assert spill_files[0].read_text() == big

    def test_preview_contains_line_count_info(self, tmp_path):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={}, spill_dir=str(tmp_path))
        big = "\n".join(f"line {i}" for i in range(5000))
        result, spilled = tb.apply(big, "t-4", current_token_usage=0)
        assert spilled
        assert "5,000" in result

    def test_same_result_passes_on_frontier_model(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=1_000_000, config={})
        big = "x" * 100_000
        result, spilled = tb.apply(big, "t-5", current_token_usage=0)
        assert result == big
        assert not spilled

    def test_context_pressure_triggers_smaller_budget(self, tmp_path):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={}, spill_dir=str(tmp_path))
        medium = "x" * 20_000
        _, spilled_relaxed = tb.apply(medium, "t-6a", current_token_usage=0)
        _, spilled_tight = tb.apply(medium, "t-6b", current_token_usage=28_000)
        assert not spilled_relaxed
        assert spilled_tight

    def test_truncation_at_line_boundary(self, tmp_path):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={}, spill_dir=str(tmp_path))
        lines = [f"line {i}: {'x' * 50}" for i in range(2000)]
        big = "\n".join(lines)
        result, spilled = tb.apply(big, "t-7", current_token_usage=0)
        assert spilled
        preview_part = result.split("\n\n[Showing")[0]
        assert preview_part.endswith("\n") or preview_part[-1] != "\n"


class TestTurnBudget:

    def test_default_turn_budget(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=32_000, config={})
        assert tb.turn_budget_chars == 64_000

    def test_custom_turn_pct(self):
        from agent.tool_budget import ToolBudget
        tb = ToolBudget(context_length=100_000, config={"turn_pct": 0.30})
        assert tb.turn_budget_chars == 120_000


class TestFindLineBoundary:

    def test_within_limit(self):
        from agent.tool_budget import ToolBudget
        assert ToolBudget._find_line_boundary("abc\ndef\n", 100) == 8

    def test_cuts_at_newline(self):
        from agent.tool_budget import ToolBudget
        assert ToolBudget._find_line_boundary("abc\ndef\nghi\n", 6) == 4

    def test_no_newline_uses_max(self):
        from agent.tool_budget import ToolBudget
        assert ToolBudget._find_line_boundary("abcdefgh", 5) == 5
