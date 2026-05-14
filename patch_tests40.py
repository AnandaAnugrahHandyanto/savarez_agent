import re
with open("tests/run_agent/test_run_agent.py", "r") as f:
    content = f.read()

# Add our tests at the end inside the TestRunConversation class
new_tests = """
    @patch("run_agent.parse_available_output_tokens_from_error")
    @patch("run_agent.classify_api_error")
    def test_context_error_reduces_max_tokens_when_available_out_is_sufficient(self, mock_classify, mock_parse, agent):
        from unittest.mock import MagicMock
        class _ContextError(Exception):
            status_code = 400
            def __str__(self):
                return "max_tokens too large"

        responses = [_ContextError(), _mock_response(content="Success!")]

        def _fake_api_call(api_kwargs):
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        agent.suppress_status_output = True
        agent._interruptible_api_call = _fake_api_call
        agent._persist_session = lambda *args, **kwargs: None
        agent._save_trajectory = lambda *args, **kwargs: None
        agent._save_session_log = lambda *args, **kwargs: None

        from agent.error_classifier import ClassifiedError, FailoverReason
        mock_classify.return_value = ClassifiedError(
            reason=FailoverReason.context_overflow,
            message="Prompt too long",
            retryable=True,
        )
        mock_parse.return_value = 1000
        agent._compress_context = MagicMock()

        from unittest.mock import patch
        with patch("run_agent.time.sleep"):
            result = agent.run_conversation("test query")

        assert result["completed"] is True
        assert agent._ephemeral_max_output_tokens == 936
        agent._compress_context.assert_not_called()

    @patch("run_agent.parse_available_output_tokens_from_error")
    @patch("run_agent.classify_api_error")
    @patch("run_agent.get_next_probe_tier")
    def test_context_error_compresses_context_when_available_out_is_too_small(self, mock_probe, mock_classify, mock_parse, agent):
        from unittest.mock import MagicMock
        class _ContextError(Exception):
            status_code = 400
            def __str__(self):
                return "max_tokens too large"

        responses = [_ContextError(), _mock_response(content="Success!")]

        def _fake_api_call(api_kwargs):
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        agent.suppress_status_output = True
        agent._interruptible_api_call = _fake_api_call
        agent._persist_session = lambda *args, **kwargs: None
        agent._save_trajectory = lambda *args, **kwargs: None
        agent._save_session_log = lambda *args, **kwargs: None

        from agent.error_classifier import ClassifiedError, FailoverReason
        mock_classify.return_value = ClassifiedError(
            reason=FailoverReason.context_overflow,
            message="Prompt too long",
            retryable=True,
        )
        mock_parse.return_value = 500
        mock_probe.return_value = agent.context_compressor.context_length
        agent._compress_context = MagicMock(return_value=([{"role": "user", "content": "compressed"}], "system"))

        from unittest.mock import patch
        with patch("run_agent.time.sleep"):
            result = agent.run_conversation("test query")

        assert result["completed"] is True
        assert agent._ephemeral_max_output_tokens is None
        agent._compress_context.assert_called_once()
"""

# Let's insert it inside TestRunConversation but at the top so we don't mess up the indentation of the rest
content = content.replace("class TestRunConversation:\n", "class TestRunConversation:\n" + new_tests)

with open("tests/run_agent/test_run_agent.py", "w") as f:
    f.write(content)
