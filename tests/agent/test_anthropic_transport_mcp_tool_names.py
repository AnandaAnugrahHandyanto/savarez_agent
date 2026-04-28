from types import SimpleNamespace

import pytest

from agent.transports.anthropic import AnthropicTransport


@pytest.mark.parametrize(
    ("wire_name", "expected_name"),
    [
        ("mcp_terminal", "terminal"),
        ("mcp_Terminal", "terminal"),
    ],
)
def test_normalize_response_strips_mcp_prefix_from_tool_name(
    wire_name,
    expected_name,
):
    block = SimpleNamespace(
        type="tool_use",
        id="toolu_terminal",
        name=wire_name,
        input={"command": "printf OPUS_TOOL_OK"},
    )
    response = SimpleNamespace(content=[block], stop_reason="tool_use")

    normalized = AnthropicTransport().normalize_response(
        response,
        strip_tool_prefix=True,
    )

    assert normalized.tool_calls is not None
    assert normalized.tool_calls[0].name == expected_name
