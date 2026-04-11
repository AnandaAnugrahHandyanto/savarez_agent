#!/usr/bin/env python3
"""
Advisor Tool -- Strategic Guidance from a More Capable Model

An application-level advisor pattern tool. The executor model (e.g., local
Ollama gemma4) can call this tool to get strategic guidance from a more
capable advisor model (e.g., Claude Opus via API). This is inspired by
Claude's advisor tool but implemented at the application level so it works
with ANY executor model.

Flow:
    Executor (any model, e.g., local gemma4 via Ollama)
        ↓ tool_call: ask_advisor(question="How should I approach this?")
        ↓ sends conversation context + question
    Advisor (e.g., Claude Opus via API)
        ↓ returns 400-700 token strategic plan
    Executor receives plan and continues executing

The advisor is configured via config.yaml:
    advisor:
        enabled: true
        provider: anthropic
        model: claude-sonnet-4-20250514
        base_url: ""
        api_key: ""
        max_tokens: 700
"""

import json
import logging
import traceback

logger = logging.getLogger(__name__)

from tools.registry import registry, tool_error, tool_result


# ---------------------------------------------------------------------------
# Config check
# ---------------------------------------------------------------------------

def check_advisor_requirements() -> bool:
    """Return True when the advisor is enabled and has a provider configured."""
    try:
        from hermes_cli.config import load_config
        config = load_config()
        advisor = config.get("advisor", {})
        if not isinstance(advisor, dict):
            return False
        if not advisor.get("enabled", False):
            return False
        # Need at least a provider or base_url to know where to send the request
        if not advisor.get("provider") and not advisor.get("base_url"):
            return False
        return True
    except Exception:
        logger.debug("advisor check_fn raised", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

ASK_ADVISOR_SCHEMA = {
    "name": "ask_advisor",
    "description": (
        "Consult a more capable model for strategic guidance on a complex task. "
        "The advisor sees your question and returns a concise plan (400-700 tokens). "
        "Use this when:\n"
        "- You're unsure about the best approach for a complex task\n"
        "- You need help with architectural or design decisions\n"
        "- You've been stuck or making errors for multiple iterations\n"
        "The advisor provides a strategic plan — follow it yourself using your available tools."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Your strategic question for the advisor. Be specific about what you need help with.",
            },
            "context": {
                "type": "string",
                "description": (
                    "Optional extra context to include. The advisor already sees "
                    "your conversation history; use this for additional details "
                    "or constraints not captured in the conversation."
                ),
            },
        },
        "required": ["question"],
    },
}


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def _build_advisor_messages(question: str, context: str = None) -> list:
    """Build the message list sent to the advisor model."""
    system_prompt = (
        "You are an expert advisor providing strategic guidance to another AI "
        "assistant (the executor). The executor has access to terminal, file, "
        "web, and other tools and will carry out your plan.\n\n"
        "Guidelines:\n"
        "- Provide a clear, actionable plan (400-700 tokens)\n"
        "- Be specific: mention exact commands, file paths, or approaches\n"
        "- Consider edge cases and potential pitfalls\n"
        "- Prioritize the most effective approach over the most obvious one\n"
        "- If multiple steps are needed, order them logically\n"
        "- Don't just describe what to do — explain *how* to do it\n"
        "- The executor will follow your plan using its own tools\n"
    )
    user_parts = [f"## Question\n\n{question}"]
    if context and context.strip():
        user_parts.append(f"\n## Additional Context\n\n{context}")
    user_parts.append(
        "\nProvide a concise strategic plan that the executor can follow "
        "using its available tools (terminal, file operations, web search, etc.)."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def ask_advisor_handler(args: dict, **kwargs) -> str:
    """Handle the ask_advisor tool call.

    Reads advisor config, builds a prompt, calls the advisor model, and
    returns the response as a JSON string.
    """
    question = args.get("question", "")
    context = args.get("context")

    if not question or not question.strip():
        return tool_error("question is required and must be a non-empty string.")

    question = question.strip()

    # Load advisor configuration
    try:
        from hermes_cli.config import load_config
        config = load_config()
    except Exception as exc:
        return tool_error(f"Failed to load config: {exc}")

    advisor = config.get("advisor", {})
    if not isinstance(advisor, dict):
        return tool_error("Advisor configuration is invalid (expected a dict).")

    provider = advisor.get("provider", "").strip()
    model = advisor.get("model", "").strip()
    base_url = advisor.get("base_url", "").strip()
    api_key = advisor.get("api_key", "").strip()
    max_tokens = advisor.get("max_tokens", 700)

    if not provider and not base_url:
        return tool_error(
            "Advisor is not configured. Set advisor.provider or "
            "advisor.base_url in config.yaml."
        )

    # Build messages
    messages = _build_advisor_messages(question, context)

    # Call the advisor model using call_llm with explicit provider/model
    try:
        from agent.auxiliary_client import call_llm
        response = call_llm(
            provider=provider or None,
            model=model or None,
            base_url=base_url or None,
            api_key=api_key or None,
            messages=messages,
            max_tokens=int(max_tokens),
            temperature=0.3,
        )
    except Exception as exc:
        logger.error("Advisor call failed: %s\n%s", exc, traceback.format_exc())
        return tool_error(f"Advisor call failed: {type(exc).__name__}: {exc}")

    # Extract response content
    try:
        content = None
        if hasattr(response, "choices") and response.choices:
            content = response.choices[0].message.content
        elif hasattr(response, "content"):
            content = response.content
        elif isinstance(response, dict):
            content = response.get("content") or response.get("text")

        if not content or not content.strip():
            return tool_error("Advisor returned an empty response.")

        return tool_result({
            "advisor_response": content.strip(),
            "model": model or provider or "unknown",
        })
    except Exception as exc:
        return tool_error(f"Failed to parse advisor response: {exc}")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

registry.register(
    name="ask_advisor",
    toolset="advisor",
    schema=ASK_ADVISOR_SCHEMA,
    handler=ask_advisor_handler,
    check_fn=check_advisor_requirements,
    emoji="🧠",
)
