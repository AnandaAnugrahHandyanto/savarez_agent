"""Pure budget status formatting for CMH subprocess wrapper foundations."""

from __future__ import annotations

from typing import Any

from agent.cmh_subprocess.envelope import allocation_cap


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _line(label: str, record: dict[str, Any]) -> str:
    used = int(record.get("envelope_messages_used_5h", 0))
    cap = allocation_cap(record)
    available = max(cap - used, 0)
    window = record.get("window_start_iso")
    if window:
        return f"{label} envelope: {used}/{cap} used, {available} available, window started {window}"
    return f"{label} envelope: {used}/{cap} used, {available} available, window not started"


def format_budget_status(envelope_state: dict[str, dict[str, Any]], halt_flags: dict[str, bool]) -> str:
    """Return a secret-free local budget status string."""
    lines = [
        _line("Cowork", envelope_state["anthropic_max"]),
        _line("Codex", envelope_state["chatgpt_pro"]),
        "Halt flags: "
        f"all={_bool_text(halt_flags.get('all', False))}, "
        f"cowork_headless={_bool_text(halt_flags.get('cowork_headless', False))}, "
        f"codex_auto_dispatch={_bool_text(halt_flags.get('codex_auto_dispatch', False))}",
    ]
    return "\n".join(lines)
