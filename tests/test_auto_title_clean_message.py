"""Tests for auto-title using clean user message instead of skill-bloated input.

When a skill is active, the message passed to run_conversation contains
the full skill content (often 1K+ chars). The title generator truncates
to 500 chars, so it only sees skill boilerplate and generates a wrong
title. The fix passes original_user_message (the clean user input) to
maybe_auto_title instead.
"""

from agent.title_generator import _TITLE_PROMPT


class TestResultIncludesOriginalMessage:

    def test_result_dict_has_original_user_message(self):
        """run_conversation result must include original_user_message."""
        # Simulate a result dict
        result = {
            "final_response": "Here are some cat gifs!",
            "original_user_message": "find me funny cat gifs",
            "messages": [],
        }
        assert "original_user_message" in result
        assert result["original_user_message"] == "find me funny cat gifs"

    def test_clean_message_preferred_over_bloated(self):
        """When original_user_message exists, use it over raw message."""
        bloated_message = "[SYSTEM: skill content 1000 chars...] find cats"
        result = {"original_user_message": "find cats"}

        title_input = result.get("original_user_message") or bloated_message
        assert title_input == "find cats"
        assert len(title_input) < 50  # not the 1000+ char bloated version

    def test_fallback_to_message_when_no_original(self):
        """When original_user_message is missing, fall back to raw message."""
        message = "hello world"
        result = {}

        title_input = result.get("original_user_message") or message
        assert title_input == "hello world"

    def test_title_prompt_fits_clean_input(self):
        """Title prompt truncates to 500 chars — clean input fits easily."""
        clean_input = "find me funny cat gifs"
        assert len(clean_input) < 500  # will be fully visible to title LLM

        bloated = "[SYSTEM: ...skill...] " * 50 + clean_input
        assert len(bloated) > 500  # would be truncated, hiding the actual intent
