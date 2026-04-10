"""Tests for provider prefix stripping from model names.

When users set model names with provider prefixes (e.g. "zai/glm-5.1"),
the prefix should be stripped for direct API providers that don't accept
the "provider/model" format.  Only OpenRouter natively supports prefixed
model names.

See: https://github.com/NousResearch/hermes-agent/issues/6211
"""

import os
import sys
import types
from unittest.mock import patch, MagicMock

import pytest

sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

from run_agent import AIAgent


# ── Helpers ──────────────────────────────────────────────────────────────────

class _FakeOpenAI:
    def __init__(self, **kw):
        self.api_key = kw.get("api_key", "test")
        self.base_url = kw.get("base_url", "http://test")
    def close(self):
        pass


def _make_agent(monkeypatch, model, provider, base_url):
    monkeypatch.setattr("run_agent.get_tool_definitions", lambda **kw: [])
    monkeypatch.setattr("run_agent.check_toolset_requirements", lambda: {})
    monkeypatch.setattr("run_agent.OpenAI", _FakeOpenAI)
    return AIAgent(
        model=model,
        api_key="test-key",
        base_url=base_url,
        provider=provider,
        max_iterations=1,
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )


# ── Tests ────────────────────────────────────────────────────────────────────

class TestStripProviderPrefix:
    """Provider prefix should be stripped for direct providers, kept for OpenRouter."""

    @pytest.mark.parametrize("model,expected", [
        ("zai/glm-5.1", "glm-5.1"),
        ("google/gemini-3-flash-preview", "gemini-3-flash-preview"),
        ("kimi/kimi-k2-turbo", "kimi-k2-turbo"),
        ("minimax/MiniMax-M2.7", "MiniMax-M2.7"),
        ("deepseek/deepseek-chat", "deepseek-chat"),
    ])
    def test_strips_prefix_for_direct_providers(self, monkeypatch, model, expected):
        agent = _make_agent(monkeypatch, model, "zai", "https://api.z.ai/api/paas/v4")
        assert agent.model == expected

    def test_keeps_prefix_for_openrouter(self, monkeypatch):
        agent = _make_agent(
            monkeypatch, "zai/glm-5.1", "openrouter",
            "https://openrouter.ai/api/v1",
        )
        assert agent.model == "zai/glm-5.1"

    def test_no_prefix_unchanged(self, monkeypatch):
        agent = _make_agent(
            monkeypatch, "glm-5.1", "zai",
            "https://api.z.ai/api/paas/v4",
        )
        assert agent.model == "glm-5.1"

    def test_preserves_original_model(self, monkeypatch):
        agent = _make_agent(
            monkeypatch, "zai/glm-5.1", "zai",
            "https://api.z.ai/api/paas/v4",
        )
        assert agent._original_model == "zai/glm-5.1"
        assert agent.model == "glm-5.1"
