"""Tests for _spawn_background_review model selection.

When smart model routing is active, the current turn's model may be a cheap/
weak model that lacks tool-calling ability. The background review agent should
use the primary (strong) model from config.yaml instead.
"""

from unittest.mock import MagicMock, patch

import pytest

from run_agent import AIAgent


def _make_tool_defs(*names):
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"{n} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for n in names
    ]


@pytest.fixture()
def cheap_agent():
    """Agent whose self.model is a cheap routing model."""
    with (
        patch(
            "run_agent.get_tool_definitions",
            return_value=_make_tool_defs("web_search", "memory"),
        ),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        a = AIAgent(
            api_key="test-key-1234567890",
            model="local-cheap-9b",
            provider="custom",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        a.client = MagicMock()
        a._memory_enabled = True
        a._user_profile_enabled = True
        a._memory_store = MagicMock()
        return a


class TestBackgroundReviewModelSelection:
    """Verify background review reads the primary model from config."""

    def test_review_uses_config_primary_model(self, cheap_agent, monkeypatch):
        """When config has model.default, review agent uses it (not self.model)."""
        created_agents = []

        original_init = AIAgent.__init__

        def tracking_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            created_agents.append({"model": kwargs.get("model"), "provider": kwargs.get("provider")})

        monkeypatch.setattr(
            "hermes_cli.config.load_config",
            lambda: {
                "model": {
                    "default": "strong-cloud-70b",
                    "provider": "openrouter",
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key": "sk-strong-key",
                }
            },
        )

        # Capture AIAgent constructor calls during _spawn_background_review
        with patch.object(AIAgent, "__init__", tracking_init):
            with patch.object(AIAgent, "run_conversation", return_value=None):
                cheap_agent._spawn_background_review(
                    messages_snapshot=[{"role": "user", "content": "test"}],
                    review_memory=True,
                )

                # Wait for the background thread to complete
                import threading
                for t in threading.enumerate():
                    if t.name != "MainThread" and t.is_alive():
                        t.join(timeout=5)

        # The review agent should have been created with the config's primary model
        assert len(created_agents) >= 1
        review = created_agents[-1]
        assert review["model"] == "strong-cloud-70b"
        assert review["provider"] == "openrouter"

    def test_review_falls_back_to_self_model_on_config_error(self, cheap_agent, monkeypatch):
        """When config loading fails, review agent uses self.model as fallback."""
        created_agents = []

        original_init = AIAgent.__init__

        def tracking_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            created_agents.append({"model": kwargs.get("model"), "provider": kwargs.get("provider")})

        monkeypatch.setattr(
            "hermes_cli.config.load_config",
            lambda: (_ for _ in ()).throw(RuntimeError("config broken")),
        )

        with patch.object(AIAgent, "__init__", tracking_init):
            with patch.object(AIAgent, "run_conversation", return_value=None):
                cheap_agent._spawn_background_review(
                    messages_snapshot=[{"role": "user", "content": "test"}],
                    review_memory=True,
                )

                import threading
                for t in threading.enumerate():
                    if t.name != "MainThread" and t.is_alive():
                        t.join(timeout=5)

        assert len(created_agents) >= 1
        review = created_agents[-1]
        # Falls back to cheap_agent's own model
        assert review["model"] == "local-cheap-9b"
