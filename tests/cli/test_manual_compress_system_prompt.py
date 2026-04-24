"""Tests for manual /compress system prompt handling.

When _manual_compress invokes _compress_context, it must pass None
as system_message to avoid duplicating the agent identity block.
Issue #15281.
"""
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch


class TestManualCompressSystemMessage(unittest.TestCase):
    """Verify _manual_compress avoids system prompt duplication."""

    def _make_cli_with_agent(self):
        """Create a minimal CLI mock with enough state for _manual_compress."""
        from cli import HermesCLI

        cli = MagicMock(spec=HermesCLI)
        cli.conversation_history = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
            {"role": "user", "content": "msg2"},
            {"role": "assistant", "content": "resp2"},
            {"role": "user", "content": "msg3"},
            {"role": "assistant", "content": "resp3"},
        ]
        cli.agent = MagicMock()
        cli.agent.compression_enabled = True
        cli.agent._cached_system_prompt = "You are Hermes, a helpful AI assistant."
        cli.agent.session_id = "test-session-id"
        cli.session_id = "test-session-id"
        cli.agent._compress_context.return_value = (
            [{"role": "assistant", "content": "[compressed summary]"}],
            50,
        )

        @contextmanager
        def _busy_stub(msg):
            yield

        cli._busy_command = _busy_stub
        return cli

    @patch(
        "agent.manual_compression_feedback.summarize_manual_compression",
        return_value="Compressed 6 → 1",
    )
    @patch(
        "agent.model_metadata.estimate_messages_tokens_rough",
        return_value=5000,
    )
    def test_compress_context_receives_none_system_message(
        self, _mock_tokens, _mock_summary
    ):
        """_compress_context must receive None, not the cached system prompt."""
        from cli import HermesCLI

        cli = self._make_cli_with_agent()
        HermesCLI._manual_compress(cli)

        cli.agent._compress_context.assert_called_once()
        args, kwargs = cli.agent._compress_context.call_args
        # Second positional arg is system_message — must be None
        self.assertIsNone(
            args[1],
            "_compress_context should receive None as system_message, "
            "not the cached prompt, to avoid identity duplication",
        )

    @patch(
        "agent.manual_compression_feedback.summarize_manual_compression",
        return_value="Compressed",
    )
    @patch(
        "agent.model_metadata.estimate_messages_tokens_rough",
        return_value=5000,
    )
    def test_compress_context_receives_focus_topic(
        self, _mock_tokens, _mock_summary
    ):
        """Focus topic from /compress <topic> should be forwarded."""
        from cli import HermesCLI

        cli = self._make_cli_with_agent()
        HermesCLI._manual_compress(cli, cmd_original="/compress database schema")

        cli.agent._compress_context.assert_called_once()
        _, kwargs = cli.agent._compress_context.call_args
        self.assertEqual(kwargs.get("focus_topic"), "database schema")
