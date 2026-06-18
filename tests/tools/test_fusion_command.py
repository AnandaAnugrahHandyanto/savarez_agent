"""Tests for the /fusion slash command registration and gateway handler."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from hermes_cli.commands import (
    COMMAND_REGISTRY,
    GATEWAY_KNOWN_COMMANDS,
    resolve_command,
)


# ---------------------------------------------------------------------------
# Command registration
# ---------------------------------------------------------------------------

class TestFusionCommandRegistration:
    def test_fusion_is_in_registry(self):
        cmd = resolve_command("fusion")
        assert cmd is not None
        assert cmd.name == "fusion"

    def test_fusion_is_gateway_known(self):
        assert "fusion" in GATEWAY_KNOWN_COMMANDS

    def test_fusion_is_not_cli_only(self):
        cmd = resolve_command("fusion")
        assert cmd.cli_only is False

    def test_fusion_requires_prompt_arg(self):
        cmd = resolve_command("fusion")
        assert cmd.args_hint == "<prompt>"

    def test_fusion_category(self):
        cmd = resolve_command("fusion")
        assert cmd.category == "Tools & Skills"


# ---------------------------------------------------------------------------
# Gateway handler
# ---------------------------------------------------------------------------

def _make_event(args: str = ""):
    """Return a minimal MessageEvent-like object for testing."""
    return SimpleNamespace(
        get_command_args=lambda: args,
        source=SimpleNamespace(platform="discord", chat_id="123"),
        text=f"/fusion {args}",
    )


@pytest.mark.asyncio
class TestFusionGatewayHandler:
    async def test_empty_prompt_returns_usage(self):
        from gateway.run import GatewayRunner

        runner = GatewayRunner.__new__(GatewayRunner)
        event = _make_event("")
        result = await runner._handle_fusion_command(event)
        assert "Usage" in result
        assert "/fusion" in result

    async def test_success_returns_fused_answer(self):
        from gateway.run import GatewayRunner

        runner = GatewayRunner.__new__(GatewayRunner)
        event = _make_event("核實這個說法")

        fake_result = json.dumps({
            "success": True,
            "response": "The claim is partially correct.",
            "outer_model": "~anthropic/claude-opus-latest",
            "usage": {"total_tokens": 42},
            "processing_time_seconds": 12.3,
        })

        with patch(
            "tools.openrouter_fusion_tool.openrouter_fusion_tool",
            new=AsyncMock(return_value=fake_result),
        ):
            result = await runner._handle_fusion_command(event)

        assert "Fusion verdict" in result
        assert "partially correct" in result
        assert "12.3s" in result

    async def test_failure_returns_error(self):
        from gateway.run import GatewayRunner

        runner = GatewayRunner.__new__(GatewayRunner)
        event = _make_event("test prompt")

        fake_result = json.dumps({
            "success": False,
            "error": "ConnectionError: timeout",
        })

        with patch(
            "tools.openrouter_fusion_tool.openrouter_fusion_tool",
            new=AsyncMock(return_value=fake_result),
        ):
            result = await runner._handle_fusion_command(event)

        assert "Fusion failed" in result
        assert "ConnectionError" in result
