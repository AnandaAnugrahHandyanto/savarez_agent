#!/usr/bin/env python3
"""
Usage Tool Module

Provides the agent with access to current session token usage and provider
account limits. This enables quota-aware planning for large tasks.
"""

import json

from agent.account_usage import fetch_account_usage

def _json_cost(value):
    return float(value)

def get_usage_tool(agent=None) -> str:
    """
    Get current session token usage and provider account limits.
    
    Args:
        agent: The AIAgent instance (passed by run_agent.py)
    """
    if not agent:
        return json.dumps({"error": "Agent instance not provided to get_usage tool."})

    # Local session usage
    input_tokens = getattr(agent, "session_input_tokens", 0)
    output_tokens = getattr(agent, "session_output_tokens", 0)
    cache_read = getattr(agent, "session_cache_read_tokens", 0)
    cache_write = getattr(agent, "session_cache_write_tokens", 0)
    api_calls = getattr(agent, "session_api_calls", 0)

    data = {
        "model": agent.model,
        "provider": agent.provider,
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "cache_read": cache_read,
            "cache_write": cache_write,
            "total": input_tokens + output_tokens + cache_read + cache_write
        },
        "api_calls": api_calls,
    }

    # Cost estimation
    try:
        from agent.usage_pricing import CanonicalUsage, estimate_usage_cost
        cost_result = estimate_usage_cost(
            agent.model,
            CanonicalUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
            ),
            provider=agent.provider,
            base_url=getattr(agent, "base_url", None),
        )
        if cost_result.amount_usd is not None:
            data["cost"] = {
                "amount_usd": _json_cost(cost_result.amount_usd),
                "status": cost_result.status
            }
    except Exception:
        pass

    # Context window info
    if hasattr(agent, "context_limit"):
        data["context"] = {
            "limit": agent.context_limit,
            "used": agent.last_context_tokens if hasattr(agent, "last_context_tokens") else None
        }
        if data["context"]["used"] and agent.context_limit:
            data["context"]["percent"] = round((data["context"]["used"] / agent.context_limit) * 100)

    # Fetch account usage
    try:
        account_snapshot = fetch_account_usage(
            agent.provider,
            base_url=getattr(agent, "base_url", None),
            api_key=getattr(agent, "api_key", None)
        )
    except Exception:
        account_snapshot = None

    if account_snapshot:
        data["account"] = {
            "plan": account_snapshot.plan,
            "windows": [
                {
                    "label": w.label,
                    "used_percent": w.used_percent,
                    "remaining_percent": 100 - w.used_percent if w.used_percent is not None else None,
                    "resets_at": w.reset_at.isoformat() if w.reset_at else None,
                    "detail": w.detail
                }
                for w in account_snapshot.windows
            ],
            "details": list(account_snapshot.details)
        }

    return json.dumps(data, indent=2, ensure_ascii=False)


GET_USAGE_SCHEMA = {
    "name": "get_usage",
    "description": (
        "Get live token usage for the current session and account quota limits from the provider. "
        "Use this before starting large tasks (repo analysis, long coding tasks, large file reads) "
        "to ensure you have enough remaining quota."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}

# --- Registry ---
from tools.registry import registry

registry.register(
    name="get_usage",
    toolset="usage",
    schema=GET_USAGE_SCHEMA,
    handler=lambda args, **kw: get_usage_tool(agent=kw.get("agent")),
    check_fn=lambda: True,
    emoji="📊",
)
