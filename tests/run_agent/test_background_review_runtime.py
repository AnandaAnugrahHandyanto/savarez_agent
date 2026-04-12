"""Tests for background review agent runtime propagation."""

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

import run_agent


class _ImmediateThread:
    def __init__(self, target=None, daemon=None, name=None):
        self._target = target

    def start(self):
        if self._target:
            self._target()


def test_spawn_background_review_reuses_parent_runtime():
    parent = run_agent.AIAgent.__new__(run_agent.AIAgent)
    parent.model = "MiniMax-M2.7"
    parent.base_url = "https://api.minimax.io/anthropic"
    parent.api_key = "mm-key"
    parent.platform = "telegram"
    parent.provider = "minimax"
    parent.api_mode = "anthropic_messages"
    parent._credential_pool = object()
    parent._memory_store = MagicMock()
    parent._memory_enabled = True
    parent._user_profile_enabled = True
    parent.background_review_callback = None
    parent._safe_print = lambda *args, **kwargs: None

    child = SimpleNamespace(
        _session_messages=[],
        run_conversation=MagicMock(),
        close=MagicMock(),
    )
    child_kwargs = {}

    def _fake_agent(**kwargs):
        child_kwargs.update(kwargs)
        return child

    with (
        patch("run_agent.AIAgent", side_effect=_fake_agent),
        patch("threading.Thread", _ImmediateThread),
    ):
        parent._spawn_background_review(
            messages_snapshot=[{"role": "user", "content": "remember this"}],
            review_memory=True,
        )

    assert child_kwargs["model"] == parent.model
    assert child_kwargs["base_url"] == parent.base_url
    assert child_kwargs["api_key"] == parent.api_key
    assert child_kwargs["provider"] == parent.provider
    assert child_kwargs["api_mode"] == parent.api_mode
    assert child_kwargs["credential_pool"] is parent._credential_pool
    child.run_conversation.assert_called_once()
    child.close.assert_called_once()
