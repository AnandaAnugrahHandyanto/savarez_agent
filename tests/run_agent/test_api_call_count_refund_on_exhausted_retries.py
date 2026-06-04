"""Regression test for issue #38445 — the successful-API-call counter must be
refunded when every retry is exhausted.

``run_conversation`` increments ``api_call_count`` optimistically at the top of
each loop iteration (before the API call is actually made/succeeds).  When a
call ultimately fails after all retries are exhausted, that optimistic bump must
be refunded so the count that is logged/returned/persisted reflects only the
*successful* API calls — not the failed attempt.

Before the fix, a turn whose single API call failed after exhausting retries
returned ``api_calls == 1`` instead of ``0``: one too high.

The mocking style (the ``agent`` fixture, ``_mock_response``, forced backoff
short-circuit) mirrors ``tests/run_agent/test_413_compression.py``.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from run_agent import AIAgent
import run_agent


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    """Make retry backoff instant so the test does not actually wait."""
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda *_a, **_k: None)
    # conversation_loop imports jittered_backoff directly, so patch it there.
    monkeypatch.setattr(
        "agent.conversation_loop.jittered_backoff", lambda *a, **k: 0.0
    )
    monkeypatch.setattr(run_agent, "jittered_backoff", lambda *a, **k: 0.0)


def _make_tool_defs(*names: str) -> list:
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


def _mock_response(content="Hello", finish_reason="stop", tool_calls=None):
    msg = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        reasoning_content=None,
        reasoning=None,
    )
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    resp = SimpleNamespace(choices=[choice], model="test/model")
    resp.usage = None
    return resp


@pytest.fixture()
def agent():
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        a = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        a.client = MagicMock()
        a._cached_system_prompt = "You are helpful."
        a._use_prompt_caching = False
        a.tool_delay = 0
        a.compression_enabled = False
        a.save_trajectories = False
        # Keep retries low so the exhausted-retries path is reached quickly.
        a._api_max_retries = 2
        return a


def _retryable_error():
    """A transient transport error: no status_code → classified retryable,
    routed through the normal retry/backoff path (not compression/auth/4xx)."""
    return ConnectionError("Connection reset by peer")


class TestApiCallCountRefundOnExhaustedRetries:
    def test_api_calls_refunded_when_all_retries_fail(self, agent):
        """A turn whose only API call fails after exhausting retries must report
        ``api_calls == 0`` — the optimistic bump is refunded."""
        agent.client.chat.completions.create.side_effect = _retryable_error()

        with (
            # Force the terminal "max retries exhausted" path: no transport
            # recovery and no fallback provider to switch to.
            patch.object(agent, "_try_recover_primary_transport", return_value=False),
            patch.object(agent, "_try_activate_fallback", return_value=False),
            patch.object(agent, "_has_pending_fallback", return_value=False),
            patch.object(agent, "_persist_session"),
            patch.object(agent, "_save_trajectory"),
            patch.object(agent, "_cleanup_task_resources"),
        ):
            result = agent.run_conversation("hello")

        assert result.get("failed") is True
        assert result["completed"] is False
        # The single attempt failed → zero successful API calls.
        assert result["api_calls"] == 0, (
            f"api_calls should be refunded to 0 when all retries fail, "
            f"got {result['api_calls']}"
        )
        # The mirror attribute on the agent must match the returned count.
        assert agent._api_call_count == 0

    def test_api_calls_count_accurate_after_one_success_then_exhaustion(self, agent):
        """After one successful call, a second turn that fully fails must not
        leave the count inflated: success counts once, the failed attempt is
        refunded."""
        ok_resp = _mock_response(content="done", finish_reason="stop")
        # First the turn succeeds in a single call.
        agent.client.chat.completions.create.side_effect = [ok_resp]

        with (
            patch.object(agent, "_persist_session"),
            patch.object(agent, "_save_trajectory"),
            patch.object(agent, "_cleanup_task_resources"),
        ):
            ok_result = agent.run_conversation("hello")

        assert ok_result["completed"] is True
        assert ok_result["api_calls"] == 1

        # Now a fresh turn that fails after exhausting retries.
        agent.client.chat.completions.create.side_effect = _retryable_error()
        with (
            patch.object(agent, "_try_recover_primary_transport", return_value=False),
            patch.object(agent, "_try_activate_fallback", return_value=False),
            patch.object(agent, "_has_pending_fallback", return_value=False),
            patch.object(agent, "_persist_session"),
            patch.object(agent, "_save_trajectory"),
            patch.object(agent, "_cleanup_task_resources"),
        ):
            fail_result = agent.run_conversation("again")

        assert fail_result.get("failed") is True
        assert fail_result["api_calls"] == 0
