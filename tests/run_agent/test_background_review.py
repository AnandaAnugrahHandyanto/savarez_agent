"""Regression tests for background review agent cleanup."""

from __future__ import annotations

import json

import run_agent as run_agent_module
from run_agent import AIAgent


def _bare_agent() -> AIAgent:
    agent = object.__new__(AIAgent)
    agent.model = "fake-model"
    agent.platform = "telegram"
    agent.provider = "openai"
    agent.base_url = ""
    agent.api_key = ""
    agent.api_mode = ""
    agent.session_id = "test-session"
    agent._parent_session_id = ""
    agent._credential_pool = None
    agent.enabled_toolsets = ["memory", "skills"]
    agent.disabled_toolsets = ["browser"]
    agent._memory_store = object()
    agent._memory_enabled = True
    agent._user_profile_enabled = False
    agent._MEMORY_REVIEW_PROMPT = "review memory"
    agent._SKILL_REVIEW_PROMPT = "review skills"
    agent._COMBINED_REVIEW_PROMPT = "review both"
    agent.background_review_callback = None
    agent.status_callback = None
    agent._safe_print = lambda *_args, **_kwargs: None
    return agent


class ImmediateThread:
    def __init__(self, *, target, daemon=None, name=None):
        self._target = target

    def start(self):
        self._target()


def test_background_review_shuts_down_memory_provider_before_close(monkeypatch):
    events = []

    class FakeReviewAgent:
        def __init__(self, **kwargs):
            events.append(("init", kwargs))
            self._session_messages = []

        def run_conversation(self, **kwargs):
            events.append(("run_conversation", kwargs))

        def shutdown_memory_provider(self):
            events.append(("shutdown_memory_provider", None))

        def close(self):
            events.append(("close", None))

    monkeypatch.setattr(run_agent_module, "AIAgent", FakeReviewAgent)
    monkeypatch.setattr(run_agent_module.threading, "Thread", ImmediateThread)

    agent = _bare_agent()

    AIAgent._spawn_background_review(
        agent,
        messages_snapshot=[{"role": "user", "content": "hello"}],
        review_memory=True,
    )

    assert [name for name, _payload in events] == [
        "init",
        "run_conversation",
        "shutdown_memory_provider",
        "close",
    ]
    init_kwargs = events[0][1]
    assert init_kwargs["enabled_toolsets"] == ["memory", "skills"]
    assert init_kwargs["disabled_toolsets"] == ["browser"]


def test_background_review_emits_audit_started_tool_result_and_completed(monkeypatch):
    audit_events = []

    class FakeReviewAgent:
        def __init__(self, **kwargs):
            self._session_messages = [
                {
                    "role": "tool",
                    "tool_call_id": "call_new",
                    "content": json.dumps(
                        {"success": True, "message": "Memory entry created."}
                    ),
                }
            ]

        def run_conversation(self, **kwargs):
            pass

        def shutdown_memory_provider(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(run_agent_module, "AIAgent", FakeReviewAgent)
    monkeypatch.setattr(run_agent_module.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(
        run_agent_module,
        "append_reviewer_audit_event",
        lambda event, kind, **fields: audit_events.append((event, kind, fields)),
    )

    agent = _bare_agent()

    AIAgent._spawn_background_review(
        agent,
        messages_snapshot=[{"role": "user", "content": "remember this"}],
        review_memory=True,
    )

    assert [event for event, _kind, _fields in audit_events] == [
        "review.started",
        "review.tool_result",
        "review.completed",
    ]
    assert [kind for _event, kind, _fields in audit_events] == ["memory"] * 3
    assert audit_events[0][2]["session_id"] == "test-session"
    assert audit_events[0][2]["platform"] == "telegram"
    assert audit_events[1][2]["action"] == "Memory entry created."
    assert audit_events[2][2]["status"] == "accepted"
    assert audit_events[2][2]["summary"] == "Memory entry created."


def test_background_review_emits_audit_failed(monkeypatch):
    audit_events = []

    class FakeReviewAgent:
        def __init__(self, **kwargs):
            self._session_messages = []

        def run_conversation(self, **kwargs):
            raise RuntimeError("review exploded")

        def shutdown_memory_provider(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(run_agent_module, "AIAgent", FakeReviewAgent)
    monkeypatch.setattr(run_agent_module.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(
        run_agent_module,
        "append_reviewer_audit_event",
        lambda event, kind, **fields: audit_events.append((event, kind, fields)),
    )

    agent = _bare_agent()

    AIAgent._spawn_background_review(
        agent,
        messages_snapshot=[{"role": "user", "content": "hello"}],
        review_skills=True,
    )

    assert [event for event, _kind, _fields in audit_events] == [
        "review.started",
        "review.failed",
    ]
    assert [kind for _event, kind, _fields in audit_events] == ["skill", "skill"]
    assert audit_events[1][2]["status"] == "failed"
    assert audit_events[1][2]["error_type"] == "RuntimeError"
    assert "review exploded" in audit_events[1][2]["error"]
