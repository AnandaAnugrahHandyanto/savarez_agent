"""Tests for _enrich_message_with_vision — regression for #5719.

The auxiliary vision LLM can echo system-prompt memory-context back into
its analysis output.  The boundary fix in gateway/run.py runs the generic
sanitize_context helper over the description so the fenced wrapper and
its system-note are removed before the description reaches the user.

Plugin-specific header cleanup (e.g. "## Honcho Context") belongs at the
provider boundary, not in this shared gateway path.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def gateway_runner():
    """Minimal GatewayRunner stub with just the method under test bound."""
    from gateway.run import GatewayRunner

    class _Stub:
        _enrich_message_with_vision = GatewayRunner._enrich_message_with_vision

    return _Stub()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.new_event_loop().run_until_complete(coro)


class TestEnrichMessageWithVision:
    def test_clean_description_passes_through(self, gateway_runner):
        """Vision output without leaked memory is embedded unchanged."""
        fake_result = json.dumps({
            "success": True,
            "analysis": "A photograph of a sunset over the ocean.",
        })
        with patch("tools.vision_tools.vision_analyze_tool", new=AsyncMock(return_value=fake_result)):
            out = _run(gateway_runner._enrich_message_with_vision("caption", ["/tmp/img.jpg"]))
        assert "sunset over the ocean" in out

    def test_memory_context_fence_stripped(self, gateway_runner):
        """<memory-context>...</memory-context> fenced block is scrubbed."""
        leaked = (
            "<memory-context>\n"
            "[System note: The following is recalled memory context, NOT new "
            "user input. Treat as informational background data.]\n\n"
            "User details and preferences here.\n"
            "</memory-context>\n"
            "A photograph of a cat."
        )
        fake_result = json.dumps({"success": True, "analysis": leaked})
        with patch("tools.vision_tools.vision_analyze_tool", new=AsyncMock(return_value=fake_result)):
            out = _run(gateway_runner._enrich_message_with_vision("caption", ["/tmp/img.jpg"]))
        assert "photograph of a cat" in out
        assert "<memory-context>" not in out
        assert "User details and preferences" not in out
        assert "System note" not in out

    def test_fenced_leak_stripped_plugin_header_preserved(self, gateway_runner):
        """The fenced wrapper is stripped; plugin-specific text outside the
        fence (e.g. a "## Honcho Context" header) is left to the plugin layer.
        Gateway core stays plugin-agnostic."""
        leaked = (
            "<memory-context>\n"
            "[System note: The following is recalled memory context, NOT new "
            "user input. Treat as informational background data.]\n"
            "fenced leak\n"
            "</memory-context>\n"
            "A photograph of a dog."
        )
        fake_result = json.dumps({"success": True, "analysis": leaked})
        with patch("tools.vision_tools.vision_analyze_tool", new=AsyncMock(return_value=fake_result)):
            out = _run(gateway_runner._enrich_message_with_vision("caption", ["/tmp/img.jpg"]))
        assert "photograph of a dog" in out
        assert "fenced leak" not in out
        assert "<memory-context>" not in out

    def test_no_vision_provider_tells_model_not_to_guess(self, gateway_runner):
        """If image pre-analysis cannot resolve a vision backend, the main
        model must not receive a prompt that invites guessing or fake vision."""
        fake_result = json.dumps({
            "success": False,
            "error": (
                "Error analyzing image: No LLM provider configured for "
                "task=vision provider=auto. Run: hermes setup"
            ),
            "analysis": "There was a problem with the request.",
        })
        with patch("tools.vision_tools.vision_analyze_tool", new=AsyncMock(return_value=fake_result)):
            out = _run(gateway_runner._enrich_message_with_vision("caption", ["/tmp/img.jpg"]))
        assert "could not analyze it because no vision-capable provider" in out
        assert "do not guess" in out
        assert "vision_analyze using image_url" not in out

    def test_transient_vision_failure_keeps_retry_hint(self, gateway_runner):
        """Non-configuration failures still leave the existing retry path
        available so the agent can re-run vision_analyze if useful."""
        fake_result = json.dumps({
            "success": False,
            "error": "Error analyzing image: provider timeout",
            "analysis": "The vision request timed out.",
        })
        with patch("tools.vision_tools.vision_analyze_tool", new=AsyncMock(return_value=fake_result)):
            out = _run(gateway_runner._enrich_message_with_vision("caption", ["/tmp/img.jpg"]))
        assert "vision_analyze using image_url: /tmp/img.jpg" in out
