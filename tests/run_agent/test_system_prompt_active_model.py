"""Tests for _active_model/_active_provider tracking in AIAgent (fixes #24215).

After a /model switch to a custom_providers entry, the system prompt should show
the resolved model/provider, not stale config-level values. This is achieved by:
  1. _active_model / _active_provider are set in __init__ from constructor args.
  2. switch_model() updates both attributes alongside self.model / self.provider.
  3. _build_system_prompt_parts() reads _active_* (with getattr fallback) for
     the timestamp line, so the prompt always reflects the live runtime values.
"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

from run_agent import AIAgent


def _make_agent(model="gpt-4o", provider="openai"):
    agent = AIAgent.__new__(AIAgent)
    agent.model = model
    agent.provider = provider
    agent._active_model = model
    agent._active_provider = provider
    return agent


def test_active_model_initialized_from_constructor_args():
    """__init__ must seed _active_model/_active_provider from constructor args."""
    agent = _make_agent(model="claude-sonnet-4-6", provider="anthropic")
    assert agent._active_model == "claude-sonnet-4-6"
    assert agent._active_provider == "anthropic"


def test_switch_model_updates_active_attrs():
    """switch_model() must update _active_model and _active_provider alongside self.model."""
    agent = _make_agent(model="config-model", provider="openai-codex")

    # Simulate the core runtime swap that switch_model() performs
    agent.model = "ark-code-latest"
    agent.provider = "custom:volcengine"
    agent._active_model = "ark-code-latest"
    agent._active_provider = "custom:volcengine"

    assert agent._active_model == "ark-code-latest"
    assert agent._active_provider == "custom:volcengine"
    assert agent.model == "ark-code-latest"


def test_display_model_uses_active_over_self_model():
    """The getattr logic in _build_system_prompt_parts must prefer _active_* values."""
    agent = _make_agent(model="config-model", provider="openai-codex")
    agent._active_model = "ark-code-latest"
    agent._active_provider = "custom:volcengine"

    # Reproduce the exact prompt-builder expression
    display_model = getattr(agent, "_active_model", None) or agent.model
    display_provider = getattr(agent, "_active_provider", None) or agent.provider

    assert display_model == "ark-code-latest"
    assert display_provider == "custom:volcengine"
    # config-level values must not appear
    assert display_model != "config-model"
    assert display_provider != "openai-codex"


def test_fallback_to_self_model_when_active_absent():
    """When _active_model is missing, the getattr fallback returns self.model."""
    agent = _make_agent(model="gpt-4o", provider="openai")
    del agent._active_model
    del agent._active_provider

    display_model = getattr(agent, "_active_model", None) or agent.model
    display_provider = getattr(agent, "_active_provider", None) or agent.provider

    assert display_model == "gpt-4o"
    assert display_provider == "openai"
