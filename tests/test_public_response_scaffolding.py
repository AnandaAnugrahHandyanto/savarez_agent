from run_agent import AIAgent


def _agent():
    return AIAgent.__new__(AIAgent)


def test_strip_refined_prompt_preamble_from_public_response():
    text = """## Refined Prompt
- **Objective:** Respond to a greeting.
- **Scope:** Friendly acknowledgement.
- **Constraints:** Keep it short.
- **Acceptance criteria:** User feels greeted.
- **Risks/assumptions:** Casual hello.
- **Validation:** Relevant reply.
- **Minimal diffs:** No changes.

Hey! What can I help you with?"""

    assert _agent()._strip_public_response_scaffolding(text) == "Hey! What can I help you with?"


def test_strip_refined_spec_preamble_from_public_response():
    text = """Refined Spec
Objective: Answer directly.
Scope: Discord chat.
Constraints: No tools.
Acceptance criteria: Brief response.
Risks/assumptions: Casual context.
Validation: Conversational.
Minimal diffs: None.

Hi aGamingGod"""

    assert _agent()._strip_public_response_scaffolding(text) == "Hi aGamingGod"


def test_strip_bold_refined_spec_with_blank_line_after_heading():
    text = """**Refined Spec**

- **Objective:** Clarify capabilities.
- **Scope:** Discord chat.
- **Constraints:** Hide internal scaffolding.
- **Acceptance criteria:** Only the answer is visible.
- **Validation:** Public response is direct.
- **Minimal diffs:** No tool/file changes.

I can help with coding, research, files, and automation."""

    assert (
        _agent()._strip_public_response_scaffolding(text)
        == "I can help with coding, research, files, and automation."
    )


def test_strip_thinking_blocks_from_public_response():
    text = "<think>private reasoning</think>\nVisible answer"

    assert _agent()._strip_public_response_scaffolding(text) == "Visible answer"


def test_strip_collapsed_refined_prompt_preamble_from_public_response():
    text = """## Refined Prompt- **Objective:** Test sanitizer.
- **Scope:** Public output.
- **Constraints:** Keep visible answer.
- **Acceptance criteria:** Only final line remains.

VISIBLE_OK"""

    assert _agent()._strip_public_response_scaffolding(text) == "VISIBLE_OK"


def test_preserve_non_scaffolding_refined_prompt_text():
    text = "Refined Prompt\nThis is a title, not the internal response scaffold."

    assert _agent()._strip_public_response_scaffolding(text) == text


def test_stream_filter_buffers_and_strips_refined_prompt_preamble():
    agent = _agent()

    assert agent._filter_public_stream_scaffolding("## Refined") == ""
    assert agent._filter_public_stream_scaffolding(" Prompt\n- **Objective:** Test.\n") == ""
    assert agent._filter_public_stream_scaffolding(
        "- **Acceptance criteria:** Hide scaffold.\n\nVisible stream"
    ) == "Visible stream"


def test_stream_filter_buffers_blank_line_after_refined_spec_heading():
    agent = _agent()

    assert agent._filter_public_stream_scaffolding("**Refined Spec**\n\n") == ""
    assert agent._filter_public_stream_scaffolding(
        "- **Objective:** Test.\n- **Acceptance criteria:** Hide scaffold.\n\nVisible stream"
    ) == "Visible stream"


def test_stream_filter_passes_normal_text_immediately():
    agent = _agent()

    assert agent._filter_public_stream_scaffolding("Hello") == "Hello"
    assert agent._filter_public_stream_scaffolding(" there") == " there"
