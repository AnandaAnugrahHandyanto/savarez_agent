"""Helpers for Hermes Feishu/Lark run-stat footer formatting."""

from __future__ import annotations

from typing import Any


def format_usage_compact(value: int) -> str:
    """Format token counts in a compact, chat-friendly form."""
    value = int(value or 0)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}m".replace(".0m", "m")
    if value >= 100_000:
        return f"{value / 1_000:.0f}k"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k".replace(".0k", "k")
    return str(value)


def format_elapsed_compact(seconds: float) -> str:
    """Format elapsed time for Feishu footer summaries."""
    seconds = max(0.0, float(seconds or 0))
    if seconds < 60:
        label = f"{seconds:.1f}".rstrip("0").rstrip(".")
        return f"{label}s"
    total_seconds = int(round(seconds))
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def build_feishu_usage_footer(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
    last_prompt_tokens: int,
    response_time: float,
    provider: str = "",
    base_url: str = "",
    api_key: str = "",
) -> str:
    """Build the two-line usage footer shown in Feishu interactive cards."""
    context_length = 0
    try:
        from agent.model_metadata import get_model_context_length

        context_length = int(
            get_model_context_length(
                model=model,
                provider=provider,
                base_url=base_url,
                api_key=api_key,
            ) or 0
        )
    except Exception:
        context_length = 0

    cache_base = input_tokens + cache_read_tokens + cache_write_tokens
    cache_pct = min(100, (cache_read_tokens / cache_base * 100)) if cache_base > 0 else 0
    line1 = f"已完成 · 耗时 {format_elapsed_compact(response_time)} · {model}"
    line2 = (
        f"↑ {format_usage_compact(input_tokens)}"
        f" ↓ {format_usage_compact(output_tokens)}"
        f" · 缓存 {format_usage_compact(cache_read_tokens)}/{format_usage_compact(cache_write_tokens)} ({cache_pct:.0f}%)"
    )
    if context_length > 0:
        context_pct = min(100, (last_prompt_tokens / context_length * 100))
        line2 += (
            f" · 上下文 {format_usage_compact(last_prompt_tokens)}"
            f"/{format_usage_compact(context_length)} ({context_pct:.0f}%)"
        )
    return f"{line1}\n{line2}"


def build_feishu_usage_footer_from_agent_result(
    agent_result: dict[str, Any],
    *,
    response_time: float,
    provider: str = "",
    base_url: str = "",
    api_key: str = "",
    default_model: str = "unknown",
) -> str:
    """Convenience wrapper for the common agent_result footer path."""
    model = str(agent_result.get("model") or default_model).strip() or default_model
    return build_feishu_usage_footer(
        model=model,
        input_tokens=int(agent_result.get("input_tokens") or 0),
        output_tokens=int(agent_result.get("output_tokens") or 0),
        cache_read_tokens=int(agent_result.get("cache_read_tokens") or 0),
        cache_write_tokens=int(agent_result.get("cache_write_tokens") or 0),
        last_prompt_tokens=int(agent_result.get("last_prompt_tokens") or 0),
        response_time=response_time,
        provider=provider,
        base_url=base_url,
        api_key=api_key,
    )
