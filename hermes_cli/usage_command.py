#!/usr/bin/env python3
import json

from agent.account_usage import fetch_account_usage, render_account_usage_lines
from agent.usage_pricing import CanonicalUsage, estimate_usage_cost
from hermes_cli.colors import Colors, color
from hermes_state import SessionDB

def _format_token(n: int) -> str:
    return f"{n:,}"

def _json_cost(value):
    return float(value)

def cmd_usage(args):
    """Show token usage for the current session and account limits."""
    db = SessionDB()
    # Get the most recent session
    with db._lock:
        cursor = db._conn.execute(
            "SELECT id, model, billing_provider, billing_base_url, "
            "input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, api_call_count "
            "FROM sessions ORDER BY started_at DESC LIMIT 1"
        )
        row = cursor.fetchone()

    if not row:
        if args.json:
            print(json.dumps({"error": "No sessions found"}, indent=2))
        else:
            print(color("No session history found.", Colors.YELLOW))
        return

    session_id, model, provider, base_url, input_tokens, output_tokens, cache_read, cache_write, api_calls = row

    # Resolve API key for provider account fetch if needed.
    # Codex and Anthropic are handled internally by fetch_account_usage().
    api_key = None
    if provider == "openrouter":
        try:
            from hermes_cli.auth import resolve_api_key_provider_credentials
            creds = resolve_api_key_provider_credentials("openrouter")
            api_key = creds.get("api_key")
        except Exception:
            pass

    # Cost estimation
    try:
        cost_result = estimate_usage_cost(
            model,
            CanonicalUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
            ),
            provider=provider,
            base_url=base_url,
        )
        cost_usd = cost_result.amount_usd
        cost_status = cost_result.status
    except Exception:
        cost_usd = None
        cost_status = "unknown"

    # Fetch account usage
    try:
        account_snapshot = fetch_account_usage(provider, base_url=base_url, api_key=api_key)
    except Exception:
        account_snapshot = None

    if args.json:
        data = {
            "session_id": session_id,
            "model": model,
            "provider": provider,
            "tokens": {
                "input": input_tokens,
                "output": output_tokens,
                "cache_read": cache_read,
                "cache_write": cache_write,
                "total": input_tokens + output_tokens + cache_read + cache_write
            },
            "api_calls": api_calls,
        }
        
        if cost_usd is not None:
            data["cost"] = {
                "amount_usd": _json_cost(cost_usd),
                "status": cost_status
            }
        
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
        
        print(json.dumps(data, indent=2))
        return

    # Text output
    print()
    print(color(f"📊 Session Token Usage ({session_id[:8]})", Colors.CYAN, Colors.BOLD))
    print(f"  Model:        {color(model, Colors.BOLD)}")
    print(f"  Input:        {_format_token(input_tokens)}")
    if cache_read:
        print(f"  Cache Read:   {_format_token(cache_read)}")
    if cache_write:
        print(f"  Cache Write:  {_format_token(cache_write)}")
    print(f"  Output:       {_format_token(output_tokens)}")
    print(f"  Total:        {color(_format_token(input_tokens + output_tokens + cache_read + cache_write), Colors.BOLD)}")
    print(f"  API Calls:    {api_calls}")
    if cost_usd is not None:
        prefix = "~" if cost_status == "estimated" else ""
        print(f"  Cost:         {prefix}${cost_usd:.4f}")

    if account_snapshot:
        print()
        lines = render_account_usage_lines(account_snapshot, markdown=False)
        for line in lines:
            print(f"  {line}")
    print()
