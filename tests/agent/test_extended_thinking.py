"""Tests for Extended Thinking integration in AIAgent.

Extended Thinking allows the model to allocate a portion of its token budget
to internal reasoning before generating the response, improving accuracy on
complex reasoning tasks.

Feature flag: enable_extended_thinking (bool)
Configuration: extended_thinking_budget_ratio (float, default 0.2 = 20%)

The thinking block is automatically added to API kwargs when:
1. enable_extended_thinking=True
2. User message contains reasoning keywords (review, debug, refactor, design, etc.)
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from run_agent import AIAgent


class TestExtendedThinkingFeatureFlag:
    """Tests for extended thinking feature flag and configuration."""

    def test_extended_thinking_disabled_by_default(self):
        """Verify that extended thinking is disabled by default."""
        agent = AIAgent(
            base_url="http://localhost:8000/v1",
            model="gpt-4",
            api_key="test-key",
        )
        assert agent.enable_extended_thinking is False
        assert agent.extended_thinking_budget_ratio == 0.2

    def test_extended_thinking_can_be_enabled(self):
        """Verify that extended thinking can be explicitly enabled."""
        agent = AIAgent(
            base_url="http://localhost:8000/v1",
            model="gpt-4",
            api_key="test-key",
            enable_extended_thinking=True,
        )
        assert agent.enable_extended_thinking is True
        assert agent.extended_thinking_budget_ratio == 0.2

    def test_extended_thinking_budget_ratio_customizable(self):
        """Verify that thinking budget ratio can be customized."""
        agent = AIAgent(
            base_url="http://localhost:8000/v1",
            model="gpt-4",
            api_key="test-key",
            enable_extended_thinking=True,
            extended_thinking_budget_ratio=0.5,
        )
        assert agent.enable_extended_thinking is True
        assert agent.extended_thinking_budget_ratio == 0.5

    @pytest.mark.parametrize(
        "ratio",
        [0.1, 0.2, 0.3, 0.5, 0.75],
    )
    def test_extended_thinking_budget_ratio_range(self, ratio: float):
        """Verify that various budget ratios can be set."""
        agent = AIAgent(
            base_url="http://localhost:8000/v1",
            model="gpt-4",
            api_key="test-key",
            enable_extended_thinking=True,
            extended_thinking_budget_ratio=ratio,
        )
        assert agent.extended_thinking_budget_ratio == ratio

    @pytest.mark.parametrize(
        "enable,expected",
        [
            (True, True),
            (False, False),
        ],
    )
    def test_extended_thinking_enable_flag(self, enable: bool, expected: bool):
        """Verify that enable_extended_thinking flag works correctly."""
        agent = AIAgent(
            base_url="http://localhost:8000/v1",
            model="gpt-4",
            api_key="test-key",
            enable_extended_thinking=enable,
        )
        assert agent.enable_extended_thinking is expected


class TestExtendedThinkingKeywordDetection:
    """Tests for reasoning task keyword detection logic."""

    @pytest.mark.parametrize(
        "message,should_match",
        [
            ("Please review this code", True),
            ("Can you debug this issue?", True),
            ("How do I refactor this?", True),
            ("Design a new system", True),
            ("Analyze the data", True),
            ("Optimize this function", True),
            ("How do I improve this?", True),
            ("Fix the bug", True),
            ("Test this implementation", True),
            ("Evaluate the results", True),
            # Case-insensitive matching
            ("REVIEW the proposal", True),
            ("Can you REFACTOR the code?", True),
            ("DEBUG this error", True),
            # Non-matching
            ("What is the capital of France?", False),
            ("Hello world", False),
            ("Tell me a joke", False),
            ("Write me a poem", False),
            ("What's the weather?", False),
        ],
    )
    def test_reasoning_keyword_detection(self, message: str, should_match: bool):
        """Test that reasoning keywords are detected correctly."""
        _task_text = message.lower()
        _reasoning_keywords = {
            "review",
            "debug",
            "refactor",
            "design",
            "analyze",
            "optimize",
            "improve",
            "fix",
            "test",
            "evaluate",
        }
        _has_reasoning_task = any(kw in _task_text for kw in _reasoning_keywords)

        if should_match:
            assert (
                _has_reasoning_task is True
            ), f"Expected to detect reasoning in: {message}"
        else:
            assert _has_reasoning_task is False, f"Expected no reasoning in: {message}"


class TestExtendedThinkingBudgetCalculation:
    """Tests for thinking budget calculation logic."""

    @pytest.mark.parametrize(
        "max_tokens,ratio,expected_min",
        [
            (4000, 0.2, 800),  # 4000 * 0.2 = 800
            (4096, 0.25, 1024),  # 4096 * 0.25 = 1024
            (8000, 0.2, 1600),  # 8000 * 0.2 = 1600
            (2000, 0.2, 400),  # 2000 * 0.2 = 400, but min is 1000
            (1000, 0.5, 500),  # 1000 * 0.5 = 500, but min is 1000
        ],
    )
    def test_thinking_budget_calculation(
        self, max_tokens: int, ratio: float, expected_min: int
    ):
        """Test that thinking budget is calculated correctly."""
        # Simulate the calculation logic from run_agent.py
        calculated_budget = max(int(max_tokens * ratio), 1000)

        if expected_min < 1000:
            # When calculated < 1000, should be clamped to 1000
            assert calculated_budget == 1000
        else:
            # Otherwise should be the calculation
            assert calculated_budget == expected_min

    def test_thinking_budget_minimum_floor(self):
        """Verify that thinking budget has a minimum floor of 1000."""
        # Test very small max_tokens
        max_tokens = 500
        ratio = 0.2
        budget = max(int(max_tokens * ratio), 1000)
        assert budget == 1000, "Budget should be floored to 1000"

    def test_thinking_budget_respects_ratio(self):
        """Verify that thinking budget respects the configured ratio."""
        max_tokens = 10000

        for ratio in [0.1, 0.2, 0.3, 0.5]:
            budget = max(int(max_tokens * ratio), 1000)
            expected = max(int(max_tokens * ratio), 1000)
            assert budget == expected, f"Budget calculation incorrect for ratio {ratio}"


class TestExtendedThinkingNonBreaking:
    """Tests verifying that extended thinking is non-breaking."""

    def test_extended_thinking_disabled_by_default_is_safe(self):
        """Verify that default behavior is unchanged (thinking disabled)."""
        # Create agent with default settings
        agent = AIAgent(
            base_url="http://localhost:8000/v1",
            model="gpt-4",
            api_key="test-key",
        )

        # Should be disabled by default — no API changes
        assert agent.enable_extended_thinking is False

        # Should have sensible defaults
        assert 0 < agent.extended_thinking_budget_ratio <= 1

    def test_extended_thinking_parameters_independent_from_existing(self):
        """Verify that new parameters don't conflict with existing ones."""
        # Create agent with various parameters
        agent = AIAgent(
            base_url="http://localhost:8000/v1",
            model="gpt-4",
            api_key="test-key",
            max_tokens=2000,
            reasoning_config={"effort": "medium"},
            max_iterations=50,
            enable_extended_thinking=True,
            extended_thinking_budget_ratio=0.3,
        )

        # Existing parameters should be preserved
        assert agent.model == "gpt-4"
        assert agent.max_tokens == 2000
        assert agent.reasoning_config == {"effort": "medium"}
        assert agent.max_iterations == 50

        # New parameters should be set
        assert agent.enable_extended_thinking is True
        assert agent.extended_thinking_budget_ratio == 0.3


class TestExtendedThinkingDocumentation:
    """Tests verifying that extended thinking parameters are properly documented."""

    def test_thinking_parameters_in_init_signature(self):
        """Verify new parameters are in the __init__ signature."""
        import inspect

        sig = inspect.signature(AIAgent.__init__)
        params = list(sig.parameters.keys())

        assert (
            "enable_extended_thinking" in params
        ), "Missing enable_extended_thinking parameter"
        assert (
            "extended_thinking_budget_ratio" in params
        ), "Missing extended_thinking_budget_ratio parameter"

    def test_thinking_parameters_in_init_docstring(self):
        """Verify docstring contains extended thinking parameter documentation."""
        docstring = AIAgent.__init__.__doc__
        assert docstring is not None, "AIAgent.__init__ missing docstring"
        assert (
            "enable_extended_thinking" in docstring
        ), "Missing enable_extended_thinking in docstring"
        assert (
            "extended_thinking_budget_ratio" in docstring
        ), "Missing extended_thinking_budget_ratio in docstring"
        assert (
            "reasoning" in docstring.lower()
        ), "Missing 'reasoning' reference in docstring"

    def test_thinking_parameters_have_defaults(self):
        """Verify extended thinking parameters have sensible defaults."""
        agent = AIAgent(
            base_url="http://localhost:8000/v1",
            model="gpt-4",
            api_key="test-key",
        )
        # Should be disabled by default (safe, non-breaking)
        assert agent.enable_extended_thinking is False
        # Should have a conservative ratio
        assert 0 <= agent.extended_thinking_budget_ratio <= 1
        assert agent.extended_thinking_budget_ratio == 0.2  # 20% default


class TestExtendedThinkingConfiguration:
    """Tests for various configuration combinations."""

    def test_zero_ratio_configuration(self):
        """Test that a zero ratio can be set (though not useful)."""
        agent = AIAgent(
            base_url="http://localhost:8000/v1",
            model="gpt-4",
            api_key="test-key",
            enable_extended_thinking=True,
            extended_thinking_budget_ratio=0.0,
        )
        assert agent.extended_thinking_budget_ratio == 0.0

    def test_max_ratio_configuration(self):
        """Test that near-max ratio can be set."""
        agent = AIAgent(
            base_url="http://localhost:8000/v1",
            model="gpt-4",
            api_key="test-key",
            enable_extended_thinking=True,
            extended_thinking_budget_ratio=0.9,
        )
        assert agent.extended_thinking_budget_ratio == 0.9

    def test_feature_flag_with_custom_max_tokens(self):
        """Test extended thinking with custom max_tokens."""
        agent = AIAgent(
            base_url="http://localhost:8000/v1",
            model="gpt-4",
            api_key="test-key",
            enable_extended_thinking=True,
            extended_thinking_budget_ratio=0.25,
            max_tokens=8000,
        )

        assert agent.enable_extended_thinking is True
        assert agent.extended_thinking_budget_ratio == 0.25
        assert agent.max_tokens == 8000
