#!/usr/bin/env python3
"""
Think Tool Module - Structured Reasoning for Complex Tasks

Allows the agent to pause and think through complex reasoning without making
external changes. The thought is logged but doesn't obtain new information or
change any state.

Based on Anthropic's research showing 54% performance improvement on complex
tasks when agents use explicit reasoning steps.

Use cases:
- Analyzing tool output before acting on it
- Planning multi-step approaches
- Evaluating tradeoffs between alternatives
- Checking policy compliance before actions
- Debugging why a previous action failed
"""

import json
from typing import Optional
from datetime import datetime


def think_tool(
    thought: str,
    reasoning_type: Optional[str] = None,
    confidence: Optional[float] = None,
) -> str:
    """
    Think about something. Use this tool to reason through complex problems,
    analyze information, or plan approaches without making external changes.

    The thought is appended to the conversation log but does not obtain new
    information or change the database/filesystem.

    Args:
        thought: The reasoning or analysis to record. Be thorough and explicit.
        reasoning_type: Optional category: "analysis", "planning", "evaluation",
                       "debugging", or "policy_check"
        confidence: Optional confidence level (0.0-1.0) in the reasoning

    Returns:
        JSON string confirming the thought was recorded.
    """
    if not thought or not thought.strip():
        return json.dumps({
            "error": "Thought text is required.",
            "hint": "Provide a detailed reasoning about what you're analyzing or planning."
        }, ensure_ascii=False)

    thought = thought.strip()
    
    # Build the response
    result = {
        "status": "thought_recorded",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "thought": thought,
    }
    
    if reasoning_type:
        result["reasoning_type"] = reasoning_type
    
    if confidence is not None:
        # Clamp to 0-1 range
        result["confidence"] = max(0.0, min(1.0, float(confidence)))
    
    # Word count for tracking thinking depth
    word_count = len(thought.split())
    result["word_count"] = word_count
    
    return json.dumps(result, ensure_ascii=False, indent=2)


def check_think_requirements() -> bool:
    """Think tool is available unless agent.think_tool.enabled is explicitly false.

    Default: True (tool stays available when YAML key is absent). Fail-open
    on config-read errors so a corrupt config doesn't strip the tool.
    """
    try:
        from hermes_cli.config import cfg_get, load_config
        return bool(cfg_get(load_config(), "agent", "think_tool", "enabled", default=True))
    except Exception:
        return True


# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================

THINK_SCHEMA = {
    "name": "think",
    "description": (
        "Use this tool to think about something. It will not obtain new information "
        "or change the database, but just append the thought to the log. "
        "Use it when complex reasoning or some cache memory is needed.\n\n"
        "**When to use:**\n"
        "- Analyzing complex tool output before acting on it\n"
        "- Planning multi-step approaches to problems\n"
        "- Evaluating tradeoffs between different alternatives\n"
        "- Checking policy compliance before taking actions\n"
        "- Debugging why a previous action failed\n"
        "- Exploring the repo and brainstorming bug fixes\n"
        "- Reviewing test results and planning fixes\n\n"
        "**When NOT to use:**\n"
        "- Simple tasks that don't require reasoning\n"
        "- When you already know exactly what to do\n"
        "- For obtaining new information (use other tools)\n\n"
        "**Tips for effective use:**\n"
        "- Be explicit and thorough in your reasoning\n"
        "- Consider multiple approaches before deciding\n"
        "- Check your assumptions\n"
        "- Use confidence score when uncertain"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "thought": {
                "type": "string",
                "description": (
                    "A detailed thought to think about. Write your reasoning explicitly "
                    "and thoroughly. This is your scratchpad for complex analysis."
                ),
            },
            "reasoning_type": {
                "type": "string",
                "enum": ["analysis", "planning", "evaluation", "debugging", "policy_check"],
                "description": (
                    "Optional: categorize the type of reasoning. "
                    "analysis=understanding data, planning=deciding steps, "
                    "evaluation=judging options, debugging=finding errors, "
                    "policy_check=verifying compliance"
                ),
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": (
                    "Optional: confidence level in this reasoning (0.0-1.0). "
                    "Use lower values when uncertain or when exploring alternatives."
                ),
            },
        },
        "required": ["thought"],
    },
}


# --- Registry ---
from tools.registry import registry

registry.register(
    name="think",
    toolset="think",  # Dedicated toolset for reasoning tools
    schema=THINK_SCHEMA,
    handler=lambda args, **kw: think_tool(
        thought=args.get("thought", ""),
        reasoning_type=args.get("reasoning_type"),
        confidence=args.get("confidence")),
    check_fn=check_think_requirements,
    emoji="🧠",
)
