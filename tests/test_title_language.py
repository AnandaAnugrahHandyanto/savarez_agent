"""Test that session title generation prompt includes language-matching.

Session titles should be generated in the same language as the
conversation. A Japanese user chatting in Japanese should get a
Japanese title, not an English one.
"""

from agent.title_generator import _TITLE_PROMPT


def test_title_prompt_includes_language_matching():
    """The system prompt must instruct the LLM to match the conversation language."""
    assert "same language" in _TITLE_PROMPT.lower()
