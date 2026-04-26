"""Tests for AIAgent._summarize_background_review_actions.

Regression coverage for issue #14944: the background memory/skill review used
to re-surface tool results that were already present in the conversation
history before the review started (e.g. an earlier "Cron job '...' created.").
"""

import json
import threading
from unittest.mock import patch

import run_agent
from run_agent import AIAgent


_summarize = AIAgent._summarize_background_review_actions


def _tool_msg(tool_call_id, payload):
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(payload),
    }


def test_skips_prior_tool_messages_by_tool_call_id():
    """Stale 'created' tool result from prior history must not be re-surfaced."""
    prior_payload = {"success": True, "message": "Cron job 'remind-me' created."}
    new_payload = {
        "success": True,
        "message": "Entry added",
        "target": "user",
    }

    snapshot = [
        {"role": "user", "content": "create a reminder"},
        _tool_msg("call_old", prior_payload),
        {"role": "assistant", "content": "done"},
    ]
    review_messages = list(snapshot) + [
        {"role": "user", "content": "<review prompt>"},
        _tool_msg("call_new", new_payload),
    ]

    actions = _summarize(review_messages, snapshot)

    assert "Cron job 'remind-me' created." not in actions
    assert "User profile updated" in actions


def test_includes_genuinely_new_actions():
    new_payload = {
        "success": True,
        "message": "Memory entry created.",
    }
    review_messages = [_tool_msg("call_new", new_payload)]

    actions = _summarize(review_messages, prior_snapshot=[])

    assert actions == ["Memory entry created."]


def test_falls_back_to_content_equality_when_tool_call_id_missing():
    """If a tool message has no tool_call_id, match prior entries by content."""
    payload = {"success": True, "message": "Cron job 'X' created."}
    raw = json.dumps(payload)
    prior_msg = {"role": "tool", "content": raw}  # no tool_call_id
    review_messages = [
        {"role": "tool", "content": raw},  # same content -> stale, skip
        _tool_msg("call_new", {"success": True, "message": "Skill created."}),
    ]

    actions = _summarize(review_messages, [prior_msg])

    assert "Cron job 'X' created." not in actions
    assert "Skill created." in actions


def test_ignores_failed_tool_results():
    bad = {"success": False, "message": "something created but failed"}
    review_messages = [_tool_msg("call_new", bad)]

    actions = _summarize(review_messages, [])

    assert actions == []


def test_handles_non_json_tool_content_gracefully():
    review_messages = [
        {"role": "tool", "tool_call_id": "x", "content": "not-json"},
        _tool_msg("call_y", {"success": True, "message": "Memory updated."}),
    ]

    actions = _summarize(review_messages, [])

    assert actions == ["Memory updated."]


def test_empty_inputs():
    assert _summarize([], []) == []
    assert _summarize(None, None) == []


def test_added_message_relabels_by_target():
    review_messages = [
        _tool_msg(
            "c1",
            {"success": True, "message": "Entry added to store.", "target": "memory"},
        )
    ]

    actions = _summarize(review_messages, [])

    assert actions == ["Memory updated"]


def test_removed_or_replaced_relabels_by_target():
    review_messages = [
        _tool_msg(
            "c1",
            {"success": True, "message": "Entry removed.", "target": "user"},
        ),
        _tool_msg(
            "c2",
            {"success": True, "message": "Entry replaced.", "target": "memory"},
        ),
    ]

    actions = _summarize(review_messages, [])

    assert "User profile updated" in actions
    assert "Memory updated" in actions


def test_spawn_background_review_uses_configured_runtime(monkeypatch):
    """Background review agents can be routed away from the active model."""
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
        patch(
            "hermes_cli.config.load_config",
            return_value={
                "background_review": {
                    "model": "qwen3.6-35b-q8",
                    "provider": "artemis-direct",
                    "max_iterations": 4,
                }
            },
        ),
    ):
        agent = AIAgent(
            model="qwen3.6-27b",
            provider="voyager",
            api_key="test-key",
            base_url="http://localhost:8080/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )

    captured = {}

    class FakeReviewAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self._session_messages = []

        def run_conversation(self, **kwargs):
            captured["conversation"] = kwargs

        def close(self):
            captured["closed"] = True

    class ImmediateThread:
        def __init__(self, target, daemon, name):
            self._target = target
            captured["thread"] = {"daemon": daemon, "name": name}

        def start(self):
            self._target()

    monkeypatch.setattr(run_agent, "AIAgent", FakeReviewAgent)
    monkeypatch.setattr(threading, "Thread", ImmediateThread)

    snapshot = [{"role": "user", "content": "hello"}]
    agent._spawn_background_review(snapshot, review_skills=True)

    assert captured["model"] == "qwen3.6-35b-q8"
    assert captured["provider"] == "artemis-direct"
    assert captured["max_iterations"] == 4
    assert captured["parent_session_id"] == agent.session_id
    assert captured["conversation"]["conversation_history"] == snapshot
    assert captured["closed"] is True
