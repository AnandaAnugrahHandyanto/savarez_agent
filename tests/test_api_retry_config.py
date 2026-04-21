"""Regression tests for configurable API and stream retries."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, __file__.replace("tests/test_api_retry_config.py", ""))


def _make_tool_defs(*names: str) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"{name} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for name in names
    ]


def _make_agent(**kwargs):
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        from run_agent import AIAgent

        agent = AIAgent(
            api_key="test-key-1234567890",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            **kwargs,
        )
        agent.client = MagicMock()
        agent._persist_session = lambda *args, **kwargs: None
        agent._save_trajectory = lambda *args, **kwargs: None
        agent._save_session_log = lambda *args, **kwargs: None
        agent._cleanup_task_resources = lambda *args, **kwargs: None
        return agent


class _RateLimitError(Exception):
    def __init__(self, retry_after=None):
        super().__init__("Error code: 429 - rate limit exceeded")
        self.status_code = 429
        headers = {}
        if retry_after is not None:
            headers["retry-after"] = str(retry_after)
        self.response = SimpleNamespace(headers=headers) if headers else None


class _RetryableServerError(Exception):
    def __init__(self):
        super().__init__("Error code: 503 - overloaded")
        self.status_code = 503


def _chat_completion_response(text="Done"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text, tool_calls=None),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        model="test-model",
    )


def _run_with_error(*, agent, error):
    call_count = {"n": 0}

    def fake_api(_api_kwargs):
        call_count["n"] += 1
        raise error

    agent._interruptible_api_call = fake_api

    time_counter = {"n": 0}

    def fake_time():
        time_counter["n"] += 1
        return float(time_counter["n"] * 1000)

    with (
        patch("run_agent.time.sleep"),
        patch("run_agent.time.time", side_effect=fake_time),
    ):
        result = agent.run_conversation("hello")

    return result, call_count["n"]


class TestAgentRetrySettings:
    def test_defaults_are_applied(self):
        agent = _make_agent()
        assert agent.max_api_retries == 3
        assert agent.max_stream_retries == 2

    def test_invalid_values_fall_back_to_defaults(self):
        agent = _make_agent(max_api_retries=-1, max_stream_retries="bogus")
        assert agent.max_api_retries == 3
        assert agent.max_stream_retries == 2

    def test_values_are_coerced_to_non_negative_ints(self):
        agent = _make_agent(max_api_retries="5", max_stream_retries="4")
        assert agent.max_api_retries == 5
        assert agent.max_stream_retries == 4


class TestRetryDelayComputation:
    def test_retry_after_is_honored(self):
        agent = _make_agent()
        wait_time = agent._compute_retry_wait_time(
            retry_count=1,
            is_rate_limited=True,
            api_error=_RateLimitError(retry_after=45),
        )
        assert wait_time == 45

    def test_retry_after_is_capped_at_five_minutes(self):
        agent = _make_agent()
        wait_time = agent._compute_retry_wait_time(
            retry_count=1,
            is_rate_limited=True,
            api_error=_RateLimitError(retry_after=600),
        )
        assert wait_time == 300

    def test_rate_limit_backoff_uses_centered_jitter(self):
        agent = _make_agent()
        with patch("run_agent.random.uniform", return_value=0.2) as mock_uniform:
            wait_time = agent._compute_retry_wait_time(
                retry_count=2,
                is_rate_limited=True,
            )
        mock_uniform.assert_called_once_with(-0.2, 0.2)
        assert wait_time == pytest.approx(12.0)

    def test_generic_retry_backoff_is_exponential_and_capped(self):
        agent = _make_agent()
        assert agent._compute_retry_wait_time(retry_count=1, is_rate_limited=False) == 1.0
        assert agent._compute_retry_wait_time(retry_count=3, is_rate_limited=False) == 4.0
        assert agent._compute_retry_wait_time(retry_count=8, is_rate_limited=False) == 60.0


class TestOuterRetryLoop:
    def test_max_api_retries_zero_means_no_retry(self):
        agent = _make_agent(max_api_retries=0)
        result, calls = _run_with_error(agent=agent, error=_RetryableServerError())
        assert result.get("failed") is True
        assert calls == 1

    def test_max_api_retries_two_means_three_total_attempts(self):
        agent = _make_agent(max_api_retries=2)
        result, calls = _run_with_error(agent=agent, error=_RetryableServerError())
        assert result.get("failed") is True
        assert calls == 3

    def test_non_retryable_errors_are_not_retried(self):
        agent = _make_agent(max_api_retries=5)
        result, calls = _run_with_error(agent=agent, error=ValueError("bad request args"))
        assert result.get("failed") is True
        assert calls == 1


class TestStreamRetryLoop:
    @patch("run_agent.AIAgent._interruptible_api_call")
    @patch("run_agent.AIAgent._replace_primary_openai_client")
    @patch("run_agent.AIAgent._create_request_openai_client")
    @patch("run_agent.AIAgent._close_request_openai_client")
    def test_max_stream_retries_respected_and_primary_client_rebuilt(
        self,
        mock_close,
        mock_create,
        mock_replace_primary,
        mock_non_stream,
    ):
        import httpx

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = httpx.ReadTimeout(
            "stream timed out",
            request=httpx.Request("POST", "https://example.com/v1/chat/completions"),
        )
        mock_create.return_value = mock_client
        mock_non_stream.return_value = _chat_completion_response("fallback after retries")

        agent = _make_agent(max_stream_retries=4)
        agent.api_mode = "chat_completions"
        agent._interrupt_requested = False

        response = agent._interruptible_streaming_api_call({})

        assert response.choices[0].message.content == "fallback after retries"
        assert mock_client.chat.completions.create.call_count == 5
        assert mock_replace_primary.call_count == 4
        assert mock_close.call_count >= 4
