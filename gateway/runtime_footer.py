"""Gateway runtime-metadata footer.

Renders a compact footer showing runtime state and appends it to the FINAL
message of an agent turn when enabled. Off by default to keep replies minimal.

Config (``~/.hermes/config.yaml``)::

    display:
      runtime_footer:
        enabled: true
        fields: [model, context_pct, tokens, api_calls, cost]

Per-platform overrides live under ``display.platforms.<platform>.runtime_footer``.
Users can toggle the global setting with ``/footer on|off`` from both the CLI
and any gateway platform.

Supported fields:
- model
- context_pct
- cwd
- tokens
- api_calls
- cost
- token_breakdown

The footer is appended to the final response text in ``gateway/run.py`` right
before returning the response to the adapter send path — so it only lands on
the final message a user sees, not on tool-progress updates or streaming
partials.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Optional

_DEFAULT_FIELDS: tuple[str, ...] = ("model", "context_pct", "cwd")
_SEP = " · "


def _home_relative_cwd(cwd: str) -> str:
    """Return *cwd* with ``$HOME`` collapsed to ``~``. Empty string if unset."""
    if not cwd:
        return ""
    try:
        home = os.path.expanduser("~")
        p = os.path.abspath(cwd)
        if home and (p == home or p.startswith(home + os.sep)):
            return "~" + p[len(home):]
        return p
    except Exception:
        return cwd



def _model_short(model: Optional[str]) -> str:
    """Drop ``vendor/`` prefix for readability (``openai/gpt-5.4`` → ``gpt-5.4``)."""
    if not model:
        return ""
    return model.rsplit("/", 1)[-1]



def _format_int(value: Optional[int]) -> str:
    if value is None:
        return ""
    try:
        return f"{int(value):,}"
    except Exception:
        return ""



def _format_tokens(total_tokens: Optional[int]) -> str:
    rendered = _format_int(total_tokens)
    return f"{rendered} tok" if rendered else ""



def _format_api_calls(api_calls: Optional[int]) -> str:
    try:
        if api_calls is None:
            return ""
        calls = int(api_calls)
    except Exception:
        return ""
    if calls < 0:
        return ""
    return f"{calls} call" if calls == 1 else f"{calls} calls"



def _format_cost(estimated_cost_usd: Optional[float], cost_status: Optional[str]) -> str:
    status = (cost_status or "").strip().lower()
    if status == "included":
        return "cost included"
    if estimated_cost_usd is None:
        return ""
    try:
        amount = float(estimated_cost_usd)
    except Exception:
        return ""
    if amount < 0:
        return ""
    prefix = "~" if status == "estimated" else ""
    return f"{prefix}${amount:.3f}"



def _format_token_breakdown(
    *,
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    cache_read_tokens: Optional[int],
    cache_write_tokens: Optional[int],
    reasoning_tokens: Optional[int],
) -> str:
    parts: list[str] = []
    prompt = _format_int(prompt_tokens)
    completion = _format_int(completion_tokens)
    cache_read = _format_int(cache_read_tokens)
    cache_write = _format_int(cache_write_tokens)
    reasoning = _format_int(reasoning_tokens)

    if prompt:
        parts.append(f"tok in {prompt}")
    if completion:
        parts.append(f"out {completion}")
    if cache_read:
        parts.append(f"cache r {cache_read}")
    if cache_write:
        parts.append(f"cache w {cache_write}")
    if reasoning:
        parts.append(f"reason {reasoning}")
    return _SEP.join(parts)



def resolve_footer_config(
    user_config: dict[str, Any] | None,
    platform_key: str | None = None,
) -> dict[str, Any]:
    """Resolve effective runtime-footer config for *platform_key*.

    Merge order (later wins):
        1. Built-in defaults (enabled=False)
        2. ``display.runtime_footer``
        3. ``display.platforms.<platform_key>.runtime_footer``
    """
    resolved = {"enabled": False, "fields": list(_DEFAULT_FIELDS)}
    cfg = (user_config or {}).get("display") or {}

    global_cfg = cfg.get("runtime_footer")
    if isinstance(global_cfg, dict):
        if "enabled" in global_cfg:
            resolved["enabled"] = bool(global_cfg.get("enabled"))
        if isinstance(global_cfg.get("fields"), list) and global_cfg["fields"]:
            resolved["fields"] = [str(f) for f in global_cfg["fields"]]

    if platform_key:
        platforms = cfg.get("platforms") or {}
        plat_cfg = platforms.get(platform_key)
        if isinstance(plat_cfg, dict):
            plat_footer = plat_cfg.get("runtime_footer")
            if isinstance(plat_footer, dict):
                if "enabled" in plat_footer:
                    resolved["enabled"] = bool(plat_footer.get("enabled"))
                if isinstance(plat_footer.get("fields"), list) and plat_footer["fields"]:
                    resolved["fields"] = [str(f) for f in plat_footer["fields"]]

    return resolved



def format_runtime_footer(
    *,
    model: Optional[str],
    context_tokens: int,
    context_length: Optional[int],
    cwd: Optional[str] = None,
    total_tokens: Optional[int] = None,
    api_calls: Optional[int] = None,
    estimated_cost_usd: Optional[float] = None,
    cost_status: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    cache_read_tokens: Optional[int] = None,
    cache_write_tokens: Optional[int] = None,
    reasoning_tokens: Optional[int] = None,
    fields: Iterable[str] = _DEFAULT_FIELDS,
) -> str:
    """Render the footer line, or return "" if no fields have data.

    Fields are skipped silently when their underlying data is missing — a
    partially-populated footer is better than a line with placeholders.
    """
    parts: list[str] = []
    for field in fields:
        if field == "model":
            m = _model_short(model)
            if m:
                parts.append(m)
        elif field == "context_pct":
            if context_length and context_length > 0 and context_tokens >= 0:
                pct = max(0, min(100, round((context_tokens / context_length) * 100)))
                parts.append(f"{pct}%")
        elif field == "cwd":
            rel = _home_relative_cwd(cwd or os.environ.get("TERMINAL_CWD", ""))
            if rel:
                parts.append(rel)
        elif field == "tokens":
            rendered = _format_tokens(total_tokens)
            if rendered:
                parts.append(rendered)
        elif field == "api_calls":
            rendered = _format_api_calls(api_calls)
            if rendered:
                parts.append(rendered)
        elif field == "cost":
            rendered = _format_cost(estimated_cost_usd, cost_status)
            if rendered:
                parts.append(rendered)
        elif field == "token_breakdown":
            rendered = _format_token_breakdown(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cache_read_tokens=cache_read_tokens,
                cache_write_tokens=cache_write_tokens,
                reasoning_tokens=reasoning_tokens,
            )
            if rendered:
                parts.append(rendered)
        # Unknown field names are silently ignored.

    if not parts:
        return ""
    return _SEP.join(parts)



def build_footer_line(
    *,
    user_config: dict[str, Any] | None,
    platform_key: str | None,
    model: Optional[str],
    context_tokens: int,
    context_length: Optional[int],
    cwd: Optional[str] = None,
    total_tokens: Optional[int] = None,
    api_calls: Optional[int] = None,
    estimated_cost_usd: Optional[float] = None,
    cost_status: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    cache_read_tokens: Optional[int] = None,
    cache_write_tokens: Optional[int] = None,
    reasoning_tokens: Optional[int] = None,
) -> str:
    """Top-level entry point used by gateway/run.py.

    Returns the footer text (empty string when disabled or no data). Callers
    append this to the final response themselves, preserving a single blank
    line of separation.
    """
    cfg = resolve_footer_config(user_config, platform_key)
    if not cfg.get("enabled"):
        return ""
    return format_runtime_footer(
        model=model,
        context_tokens=context_tokens,
        context_length=context_length,
        cwd=cwd,
        total_tokens=total_tokens,
        api_calls=api_calls,
        estimated_cost_usd=estimated_cost_usd,
        cost_status=cost_status,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        reasoning_tokens=reasoning_tokens,
        fields=cfg.get("fields") or _DEFAULT_FIELDS,
    )
