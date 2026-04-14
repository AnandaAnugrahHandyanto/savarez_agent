"""Tests for @-context completion self fix.

Regression tests for: NameError name 'self' is not defined
in _context_completions (was a @staticmethod removed without adjusting
the method signature to accept self).
"""

from hermes_cli.commands import SlashCommandCompleter
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

def _completions(completer: SlashCommandCompleter, text: str):
    return list(
        completer.get_completions(
            Document(text=text),
            CompleteEvent(completion_requested=True),
        )
    )

class TestAtContextCompletion:
    """Tests that @-context completions work without NameError.

    Regression test for: Exception name 'self' is not defined
    in _context_completions (was a @staticmethod incorrectly removed).
    """

    def test_at_symbol_does_not_crash(self):
        """Typing @ should not raise NameError."""
        completer = SlashCommandCompleter()
        # Should not raise — the old bug would crash here with
        # NameError: name 'self' is not defined
        completions = _completions(completer, "@")
        # May or may not return completions (depends on cwd files),
        # but should never crash.
        assert isinstance(completions, list)

    def test_at_with_query_does_not_crash(self):
        """Typing @<query> should not raise NameError."""
        completer = SlashCommandCompleter()
        completions = _completions(completer, "@README")
        assert isinstance(completions, list)

    def test_at_after_text_does_not_crash(self):
        """Typing text@ should not trigger @-completion."""
        completer = SlashCommandCompleter()
        completions = _completions(completer, "hello@world")
        assert isinstance(completions, list)

    def test_slash_commands_still_work_alongside_at(self):
        """Normal slash commands should still work after the self fix."""
        completer = SlashCommandCompleter()
        completions = _completions(completer, "/help")
        assert len(completions) == 1
        assert completions[0].text == "help "
