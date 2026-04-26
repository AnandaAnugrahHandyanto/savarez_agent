"""Regression tests for background review runtime inheritance.

Background review forks a secondary AIAgent after the main reply. When the
main session uses a named custom provider resolved to provider='custom' with
explicit runtime credentials, the fork must inherit those runtime fields.
Otherwise the review agent re-initializes as a bare custom/main provider and
fails with "No LLM provider configured".
"""

from __future__ import annotations

import threading

import pytest
import yaml

import run_agent as run_agent_module
from hermes_cli.runtime_provider import resolve_runtime_provider
from run_agent import AIAgent


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    config = {
        "model": {
            "default": "gpt-5.4",
            "provider": "newapi-openai",
            "api_mode": "codex_responses",
        },
        "providers": {
            "newapi-openai": {
                "api": "https://newapi.example.invalid/v1",
                "name": "newapi-openai",
                "api_key": "test-key",
                "default_model": "gpt-5.4",
                "transport": "codex_responses",
                "api_mode": "codex_responses",
            }
        },
        "memory": {
            "memory_enabled": True,
            "user_profile_enabled": True,
        },
        "skills": {
            "creation_nudge_interval": 10,
        },
    }
    (hermes_home / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")


class _ImmediateThread:
    def __init__(self, *, target=None, **kwargs):
        self._target = target

    def start(self):
        if self._target:
            self._target()


class _SpyReviewAgent:
    init_kwargs: dict | None = None
    prompts: list[str] = []

    def __init__(self, **kwargs):
        type(self).init_kwargs = kwargs
        self._session_messages = []
        self.closed = False

    def run_conversation(self, user_message, conversation_history=None):
        type(self).prompts.append(user_message)
        return {"final_response": "Nothing to save."}

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    ("review_memory", "review_skills", "expected_prompt"),
    [
        (True, False, AIAgent._MEMORY_REVIEW_PROMPT),
        (False, True, AIAgent._SKILL_REVIEW_PROMPT),
        (True, True, AIAgent._COMBINED_REVIEW_PROMPT),
    ],
)
def test_background_review_inherits_runtime_fields(
    monkeypatch,
    review_memory,
    review_skills,
    expected_prompt,
):
    runtime = resolve_runtime_provider(requested="newapi-openai")
    agent = AIAgent(
        model="gpt-5.4",
        provider=runtime.get("provider"),
        base_url=runtime.get("base_url"),
        api_key=runtime.get("api_key"),
        api_mode=runtime.get("api_mode"),
        quiet_mode=True,
        max_iterations=1,
    )

    _SpyReviewAgent.init_kwargs = None
    _SpyReviewAgent.prompts = []
    monkeypatch.setattr(threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(run_agent_module, "AIAgent", _SpyReviewAgent)

    agent._spawn_background_review(
        messages_snapshot=[{"role": "user", "content": "hi"}],
        review_memory=review_memory,
        review_skills=review_skills,
    )

    assert _SpyReviewAgent.init_kwargs is not None
    assert _SpyReviewAgent.init_kwargs["provider"] == "custom"
    assert _SpyReviewAgent.init_kwargs["base_url"] == "https://newapi.example.invalid/v1"
    assert _SpyReviewAgent.init_kwargs["api_key"] == "test-key"
    assert _SpyReviewAgent.init_kwargs["api_mode"] == "codex_responses"
    assert _SpyReviewAgent.prompts == [expected_prompt]

    agent.close()
