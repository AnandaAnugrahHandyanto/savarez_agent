"""Regression guard for #31273: HTTP 402 billing errors must abort
immediately when credential pool recovery is unavailable.

When an LLM provider returns HTTP 402 (Payment Required — out of credits),
the error is classified as FailoverReason.billing with retryable=False.
However, billing was excluded from the is_client_error fast-exit check
(to give credential pool rotation a chance). If the pool has no available
credentials (single-key or all keys exhausted), the agent should abort
immediately instead of retrying max_retries times against the same
depleted account.
"""

import pytest
from unittest.mock import MagicMock, patch

from run_agent import AIAgent
from agent.error_classifier import classify_api_error, FailoverReason


def _make_tool_defs(*names):
    """Minimal tool definitions for agent init."""
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"Test tool {n}",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for n in names
    ]


def _make_402_error(message="Insufficient credits"):
    """Create an exception that mimics a 402 HTTP billing error."""
    err = Exception(message)
    err.status_code = 402
    return err


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
        return a


# ---------------------------------------------------------------------------
# Unit tests: error classifier correctly classifies 402 as billing
# ---------------------------------------------------------------------------

class Test402Classification:
    """Verify that 402 errors are classified as billing (retryable=False)."""

    def test_402_classified_as_billing(self):
        """A plain 402 should be classified as billing, not rate_limit."""
        err = _make_402_error("Insufficient credits")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.billing
        assert result.retryable is False
        assert result.should_rotate_credential is True
        assert result.should_fallback is True

    def test_402_with_transient_usage_limit_classified_as_rate_limit(self):
        """A 402 with transient signals (e.g. 'try again in 5 minutes') is
        a periodic quota, not billing exhaustion."""
        err = _make_402_error("Usage limit exceeded. Try again in 5 minutes.")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.rate_limit
        assert result.retryable is True

    def test_402_with_payment_required_is_billing(self):
        """A 402 with 'payment required' in the message is billing."""
        err = _make_402_error("Payment required: please top up your credits")
        result = classify_api_error(err)
        assert result.reason == FailoverReason.billing
        assert result.retryable is False

    def test_billing_not_treated_as_client_error(self):
        """FailoverReason.billing must NOT be treated as is_client_error.
        This is by design — billing gets special handling (pool rotation
        attempt + fast-exit when pool unavailable), not the generic
        client-error abort."""
        assert classify_api_error(_make_402_error("Insufficient credits")).reason == FailoverReason.billing
        assert not classify_api_error(_make_402_error("Insufficient credits")).retryable

    def test_auth_is_retryable_false(self):
        """Auth errors are not retryable — they get the generic client-error abort."""
        err = Exception("Unauthorized")
        err.status_code = 401
        result = classify_api_error(err)
        assert result.retryable is False


# ---------------------------------------------------------------------------
# Integration tests: billing fast-exit in the agent loop
# ---------------------------------------------------------------------------

class TestBillingFastExit:
    """402 billing errors with no pool recovery should abort after a single
    API call, not burn through max_retries."""

    def test_402_billing_no_pool_aborts_immediately(self, agent):
        """Single-credential user gets 402 — must abort on first attempt,
        not retry 3 times."""
        err_402 = _make_402_error("Insufficient credits")
        # Provide enough items so StopIteration doesn't mask the real result.
        # If the bug is present, all 3 are consumed (3 retries).
        # If the fix works, only the first is consumed.
        agent.client.chat.completions.create.side_effect = [
            err_402,   # first call
            err_402,   # would be second call (bug: retried)
            err_402,   # would be third call (bug: retried)
        ]

        with (
            patch.object(agent, "_persist_session"),
            patch.object(agent, "_save_trajectory"),
            patch.object(agent, "_cleanup_task_resources"),
            patch.object(agent, "_try_activate_fallback", return_value=False),
        ):
            result = agent.run_conversation("hello")

        assert result["failed"] is True
        assert result["completed"] is False
        # Only ONE API call — not 3 retries
        assert agent.client.chat.completions.create.call_count == 1

    def test_402_billing_no_pool_fallback_attempted(self, agent):
        """Before aborting, the agent should try the fallback provider."""
        err_402 = _make_402_error("Insufficient credits")
        agent.client.chat.completions.create.side_effect = [err_402]

        with (
            patch.object(agent, "_persist_session"),
            patch.object(agent, "_save_trajectory"),
            patch.object(agent, "_cleanup_task_resources"),
            patch.object(agent, "_try_activate_fallback", return_value=False) as mock_fallback,
        ):
            result = agent.run_conversation("hello")

        assert result["failed"] is True
        mock_fallback.assert_called_once()

    def test_non_billing_401_is_client_error_aborts(self, agent):
        """A 401 auth error (is_client_error=True) should also abort
        immediately — this tests that the billing fast-exit doesn't
        interfere with the existing client-error path."""
        err_401 = Exception("Unauthorized")
        err_401.status_code = 401
        agent.client.chat.completions.create.side_effect = [
            err_401, err_401, err_401,
        ]

        with (
            patch.object(agent, "_persist_session"),
            patch.object(agent, "_save_trajectory"),
            patch.object(agent, "_cleanup_task_resources"),
            patch.object(agent, "_try_activate_fallback", return_value=False),
        ):
            result = agent.run_conversation("hello")

        assert result["failed"] is True
        assert agent.client.chat.completions.create.call_count == 1
