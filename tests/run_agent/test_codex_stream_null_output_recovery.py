"""Regression test for the May 2026 ``response.completed`` ``output=null`` bug.

The ``chatgpt.com/backend-api/codex`` endpoint started intermittently sending
``response.completed`` SSE events whose ``response.output`` field is ``null``
(observed on ``gpt-5.5``).  The OpenAI SDK's ``parse_response()`` then does
``for output in response.output:`` and raises::

    TypeError: 'NoneType' object is not iterable

The outer conversation loop classifies that as a non-retryable local
validation error and aborts the turn — the user sees a generic
"I encountered an error" line instead of the model's actual answer, even
though every text delta was already streamed to us.

``run_codex_stream`` now catches that specific ``TypeError`` and recovers
by synthesizing a response from the deltas / output items it already
collected, the same backfill the post-stream path runs when
``get_final_response()`` returns an empty output list.  When nothing was
collected we fall back to ``run_codex_create_stream_fallback``.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _make_codex_agent():
    """Build a minimal AIAgent wired for codex_responses streaming tests."""
    from run_agent import AIAgent

    agent = AIAgent(
        api_key="test-key",
        base_url="https://chatgpt.com/backend-api/codex",
        model="gpt-5.5",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )
    agent.api_mode = "codex_responses"
    agent.provider = "openai-codex"
    agent._interrupt_requested = False
    return agent


class _StreamWithTypeError:
    """Context manager that yields deltas, then raises the SDK's TypeError.

    Mirrors what the OpenAI SDK does when the Codex backend sends
    ``response.completed`` with ``output=null`` — the SDK iterates the
    null output inside its own event loop, so the TypeError surfaces
    from inside our ``for event in stream:`` loop, after we've already
    consumed delta events.
    """

    def __init__(self, deltas):
        self._deltas = deltas

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        for delta_text in self._deltas:
            yield SimpleNamespace(
                type="response.output_text.delta",
                delta=delta_text,
            )
        raise TypeError("'NoneType' object is not iterable")


def test_codex_stream_recovers_from_null_output_using_collected_deltas():
    """When the backend sends response.completed with output=null, recover
    by synthesizing a response from the text deltas already streamed.

    The synthesized response carries the text the model actually produced
    so the agent can continue the turn instead of aborting with a
    "non-retryable client error" and showing the user a generic error.
    """
    agent = _make_codex_agent()

    mock_client = MagicMock()
    mock_client.responses.stream.return_value = _StreamWithTypeError(
        ["Hello, ", "world!"]
    )

    # If we accidentally fall back to create(stream=True), the test should
    # fail loudly — recovery from in-stream deltas should not need a 2nd call.
    with patch.object(
        agent, "_run_codex_create_stream_fallback",
        side_effect=AssertionError("must not fall back when deltas are present"),
    ):
        result = agent._run_codex_stream(
            {"model": "gpt-5.5"}, client=mock_client,
        )

    assert getattr(result, "status", None) == "completed"
    assert getattr(result, "output_text", None) == "Hello, world!"
    output = getattr(result, "output", None)
    assert isinstance(output, list) and len(output) == 1
    synthesized = output[0]
    assert synthesized.type == "message"
    assert synthesized.role == "assistant"
    assert synthesized.content[0].type == "output_text"
    assert synthesized.content[0].text == "Hello, world!"


def test_codex_stream_null_output_with_no_content_falls_back():
    """When the backend sends output=null AND no deltas were collected,
    fall back to create(stream=True) so we still get a chance at a real
    response or a surfaced provider error.
    """
    agent = _make_codex_agent()

    mock_client = MagicMock()
    # No deltas, just the immediate TypeError — same shape as a Codex
    # response.completed with output=null and no prior text events.
    mock_client.responses.stream.return_value = _StreamWithTypeError([])

    fallback_response = SimpleNamespace(
        output=[SimpleNamespace(
            type="message",
            content=[SimpleNamespace(type="output_text", text="fallback ok")],
        )],
        status="completed",
    )
    with patch.object(
        agent, "_run_codex_create_stream_fallback", return_value=fallback_response,
    ) as mock_fallback:
        result = agent._run_codex_stream(
            {"model": "gpt-5.5"}, client=mock_client,
        )

    assert result is fallback_response
    mock_fallback.assert_called_once()


def test_codex_stream_unrelated_typeerror_still_raises():
    """Only the specific ``'NoneType' object is not iterable`` message
    should trigger recovery — unrelated TypeErrors must propagate so we
    don't mask real bugs."""
    agent = _make_codex_agent()

    class _StreamWithUnrelatedTypeError:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def __iter__(self):
            raise TypeError("unrelated programming bug")

    mock_client = MagicMock()
    mock_client.responses.stream.return_value = _StreamWithUnrelatedTypeError()

    with patch.object(agent, "_run_codex_create_stream_fallback") as mock_fallback:
        with pytest.raises(TypeError, match="unrelated programming bug"):
            agent._run_codex_stream({"model": "gpt-5.5"}, client=mock_client)

    mock_fallback.assert_not_called()
