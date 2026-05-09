"""Regression tests for configurable preflight compression pass budget."""

from unittest.mock import patch

import pytest

from run_agent import AIAgent

_SENTINEL = object()


def _make_agent_with_preflight_budget(value=_SENTINEL):
    compression = {}
    if value is not _SENTINEL:
        compression["preflight_max_passes"] = value

    auth_kwargs = {"api_" + "key": "placeholder"}
    with (
        patch("hermes_cli.config.load_config", return_value={"compression": compression}),
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        return AIAgent(
            **auth_kwargs,
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )


@pytest.mark.parametrize(
    ("configured_value", "expected_passes"),
    [
        (_SENTINEL, 3),
        (5, 5),
        ("2", 2),
        (0, 0),
        ("0", 0),
        (-7, 0),
        ("-4", 0),
        ("not-an-integer", 3),
    ],
)
def test_preflight_compression_pass_budget_honors_configured_zero_and_clamps_negative(
    configured_value,
    expected_passes,
):
    agent = _make_agent_with_preflight_budget(configured_value)

    assert agent._compression_preflight_max_passes == expected_passes
