"""OpenRouter Fusion server-tool integration for Hermes.

Fusion is OpenRouter's bounded multi-model deliberation pipeline.  This module
wraps it as an explicit Hermes tool so agents can ask for a model panel only on
high-value research / verification tasks instead of making it part of normal
chat traffic.
"""

from __future__ import annotations

import datetime
import json
import logging
from typing import Any, Dict, List, Optional

from tools.openrouter_client import check_api_key, get_async_client
from tools.registry import registry

logger = logging.getLogger(__name__)

# Keep the default explicit invocation cost-controlled.  The quality preset is
# OpenRouter's upstream default when ``analysis_models`` is omitted; budget uses
# the cheaper panel from the Fusion docs/blog family.
DEFAULT_OUTER_MODEL = "~anthropic/claude-opus-latest"
DEFAULT_JUDGE_MODEL = "~anthropic/claude-opus-latest"
BUDGET_ANALYSIS_MODELS = [
    "~google/gemini-flash-latest",
    "deepseek/deepseek-v3.2",
    "~moonshotai/kimi-latest",
]
QUALITY_ANALYSIS_MODELS: Optional[List[str]] = None  # Let OpenRouter apply its quality preset.

PRESETS = {"budget", "quality", "custom"}


def check_openrouter_fusion_requirements() -> bool:
    """Return True when OpenRouter credentials are configured."""
    return check_api_key()


def _clean_models(models: Optional[List[str]]) -> List[str]:
    """Normalize and validate custom analysis model slugs."""
    if not models:
        return []
    cleaned = [m.strip() for m in models if isinstance(m, str) and m.strip()]
    # OpenRouter Fusion allows 1-8 panel models.
    if len(cleaned) > 8:
        raise ValueError("OpenRouter Fusion accepts at most 8 analysis models")
    return cleaned


def _build_fusion_parameters(
    *,
    preset: str,
    analysis_models: Optional[List[str]],
    judge_model: Optional[str],
    max_tool_calls: Optional[int],
    max_completion_tokens: Optional[int],
    temperature: Optional[float],
    reasoning: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the OpenRouter ``openrouter:fusion`` parameters object."""
    preset = (preset or "budget").lower()
    if preset not in PRESETS:
        raise ValueError(f"Unknown Fusion preset '{preset}'. Expected one of: {', '.join(sorted(PRESETS))}")

    params: Dict[str, Any] = {}

    if preset == "budget":
        params["analysis_models"] = BUDGET_ANALYSIS_MODELS
    elif preset == "custom":
        custom_models = _clean_models(analysis_models)
        if not custom_models:
            raise ValueError("custom Fusion preset requires at least one analysis model")
        params["analysis_models"] = custom_models
    # quality intentionally omits analysis_models to use OpenRouter's quality preset.

    if judge_model:
        params["model"] = judge_model
    if max_tool_calls is not None:
        if not 1 <= int(max_tool_calls) <= 16:
            raise ValueError("max_tool_calls must be between 1 and 16")
        params["max_tool_calls"] = int(max_tool_calls)
    if max_completion_tokens is not None:
        if int(max_completion_tokens) <= 0:
            raise ValueError("max_completion_tokens must be positive")
        params["max_completion_tokens"] = int(max_completion_tokens)
    if temperature is not None:
        if not 0 <= float(temperature) <= 2:
            raise ValueError("temperature must be between 0 and 2")
        params["temperature"] = float(temperature)
    if reasoning:
        params["reasoning"] = reasoning

    return params


def _message_content(message: Any) -> str:
    """Extract message content from OpenAI SDK response objects or dicts."""
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                if isinstance(part.get("text"), str):
                    parts.append(part["text"])
                elif isinstance(part.get("content"), str):
                    parts.append(part["content"])
        return "\n".join(parts)
    return "" if content is None else str(content)


def _usage_to_dict(usage: Any) -> Optional[Dict[str, Any]]:
    """Serialize usage metadata without depending on a specific SDK version."""
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    result: Dict[str, Any] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage, key, None)
        if value is not None:
            result[key] = value
    return result or None


async def openrouter_fusion_tool(
    prompt: str,
    *,
    preset: str = "budget",
    analysis_models: Optional[List[str]] = None,
    judge_model: Optional[str] = None,
    outer_model: Optional[str] = None,
    max_tool_calls: Optional[int] = 8,
    max_completion_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    reasoning: Optional[Dict[str, Any]] = None,
    force: bool = True,
) -> str:
    """Ask OpenRouter Fusion to deliberate over ``prompt`` and return JSON."""
    start_time = datetime.datetime.now()
    try:
        if not prompt or not prompt.strip():
            raise ValueError("prompt is required")

        fusion_parameters = _build_fusion_parameters(
            preset=preset,
            analysis_models=analysis_models,
            judge_model=judge_model or DEFAULT_JUDGE_MODEL,
            max_tool_calls=max_tool_calls,
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
            reasoning=reasoning,
        )
        tool_entry: Dict[str, Any] = {"type": "openrouter:fusion"}
        if fusion_parameters:
            tool_entry["parameters"] = fusion_parameters

        model = outer_model or judge_model or DEFAULT_OUTER_MODEL
        client = get_async_client()
        create_kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [tool_entry],
        }
        if force:
            create_kwargs["tool_choice"] = "required"

        response = await client.chat.completions.create(**create_kwargs)
        message = response.choices[0].message
        content = _message_content(message)
        elapsed = (datetime.datetime.now() - start_time).total_seconds()
        result = {
            "success": True,
            "response": content,
            "preset": preset,
            "outer_model": model,
            "fusion_tool": tool_entry,
            "forced": force,
            "usage": _usage_to_dict(getattr(response, "usage", None)),
            "processing_time_seconds": elapsed,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as exc:
        elapsed = (datetime.datetime.now() - start_time).total_seconds()
        logger.error("OpenRouter Fusion processing failed: %s", exc, exc_info=True)
        result = {
            "success": False,
            "response": "OpenRouter Fusion failed. Fall back to normal research or a single-model answer.",
            "error": f"{type(exc).__name__}: {exc}",
            "preset": preset,
            "processing_time_seconds": elapsed,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)


OPENROUTER_FUSION_SCHEMA = {
    "name": "openrouter_fusion",
    "description": (
        "Run OpenRouter Fusion multi-model deliberation for high-stakes verification, "
        "research, compare/contrast, model-benchmark, or expensive-to-be-wrong questions. "
        "This makes external OpenRouter model calls; use sparingly and avoid private local data."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The question or claim to analyze with OpenRouter Fusion.",
            },
            "preset": {
                "type": "string",
                "enum": ["budget", "quality", "custom"],
                "description": "budget uses a cheaper Gemini/DeepSeek/Kimi panel; quality uses OpenRouter's default quality panel; custom uses analysis_models.",
                "default": "budget",
            },
            "analysis_models": {
                "type": "array",
                "items": {"type": "string"},
                "description": "1-8 OpenRouter model slugs for custom preset only.",
            },
            "judge_model": {
                "type": "string",
                "description": "Optional OpenRouter model slug for the Fusion judge/synthesis model.",
            },
            "outer_model": {
                "type": "string",
                "description": "Optional outer model that receives the Fusion tool result and writes the final answer.",
            },
            "max_tool_calls": {
                "type": "integer",
                "minimum": 1,
                "maximum": 16,
                "description": "Max web_search/web_fetch steps for each panel model and judge.",
                "default": 8,
            },
            "max_completion_tokens": {
                "type": "integer",
                "minimum": 1,
                "description": "Optional max output tokens per inner panel/judge call.",
            },
            "temperature": {
                "type": "number",
                "minimum": 0,
                "maximum": 2,
                "description": "Optional temperature forwarded to panel/judge calls.",
            },
            "reasoning": {
                "type": "object",
                "description": "Optional OpenRouter reasoning config forwarded to panel/judge calls.",
            },
            "force": {
                "type": "boolean",
                "description": "When true, set tool_choice=required so Fusion is invoked for this explicit Hermes tool call.",
                "default": True,
            },
        },
        "required": ["prompt"],
    },
}


registry.register(
    name="openrouter_fusion",
    toolset="fusion",
    schema=OPENROUTER_FUSION_SCHEMA,
    handler=lambda args, **kw: openrouter_fusion_tool(
        prompt=args.get("prompt", ""),
        preset=args.get("preset", "budget"),
        analysis_models=args.get("analysis_models"),
        judge_model=args.get("judge_model"),
        outer_model=args.get("outer_model"),
        max_tool_calls=args.get("max_tool_calls", 8),
        max_completion_tokens=args.get("max_completion_tokens"),
        temperature=args.get("temperature"),
        reasoning=args.get("reasoning"),
        force=args.get("force", True),
    ),
    check_fn=check_openrouter_fusion_requirements,
    requires_env=["OPENROUTER_API_KEY"],
    is_async=True,
    emoji="🧬",
)
