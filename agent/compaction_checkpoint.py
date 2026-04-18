"""Canonical compaction checkpoint artifacts for Book/JSONL memory.

This module writes a structured continuation artifact every time Hermes
compacts context. The artifact is canonical/local-first and intentionally
separate from derived recall systems like Rasputin.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from hermes_constants import get_hermes_home


def write_compaction_checkpoint(
    *,
    session_id: str,
    messages: List[Dict[str, Any]],
    preservation_notes: str,
    approx_tokens: int | None,
    context_length: int,
    threshold_tokens: int,
) -> Dict[str, str]:
    """Write canonical continuation artifacts for an imminent compaction.

    Returns a dict of artifact paths for logging/testing. All writes are local,
    profile-scoped, and safe to call repeatedly.
    """
    timestamp = datetime.now(timezone.utc)
    timestamp_iso = timestamp.isoformat().replace("+00:00", "Z")
    timestamp_slug = timestamp.strftime("%Y%m%d-%H%M%S")
    safe_session_id = (session_id or "unknown-session").strip() or "unknown-session"

    hermes_home = get_hermes_home()
    workspace_dir = hermes_home / "workspace"
    memory_root = _resolve_memory_root(workspace_dir)
    handoffs_dir = memory_root / "handoffs"
    daily_dir = memory_root / "daily"
    events_dir = memory_root / "events"
    checkpoints_dir = memory_root / "context-checkpoints" / "completed"
    for directory in (handoffs_dir, daily_dir, events_dir, checkpoints_dir):
        directory.mkdir(parents=True, exist_ok=True)

    profile = _infer_profile_name(hermes_home)
    fleet = _infer_fleet(profile)
    context_percent = _compute_context_percent(approx_tokens, context_length)

    recent_user_messages = _recent_messages(messages, roles={"user"}, limit=3)
    recent_assistant_messages = _recent_messages(messages, roles={"assistant", "tool"}, limit=4)
    last_user_message = recent_user_messages[-1] if recent_user_messages else ""

    handoff_md = _render_handoff_markdown(
        session_id=safe_session_id,
        profile=profile,
        fleet=fleet,
        saved_at=timestamp_iso,
        approx_tokens=approx_tokens,
        context_length=context_length,
        threshold_tokens=threshold_tokens,
        context_percent=context_percent,
        preservation_notes=preservation_notes,
        recent_user_messages=recent_user_messages,
        recent_assistant_messages=recent_assistant_messages,
    )

    handoff_path = handoffs_dir / f"{safe_session_id}-compaction-{timestamp_slug}.md"
    handoff_path.write_text(handoff_md, encoding="utf-8")

    latest_handoff_path = handoffs_dir / "latest.md"
    latest_handoff_path.write_text(handoff_md, encoding="utf-8")

    checkpoint_payload = {
        "session_id": safe_session_id,
        "saved_at": timestamp_iso,
        "status": "pending_compaction",
        "profile": profile,
        "fleet": fleet,
        "context_tokens": approx_tokens,
        "context_length": context_length,
        "threshold_tokens": threshold_tokens,
        "context_percent": context_percent,
        "last_user_message": last_user_message,
        "recent_user_messages": recent_user_messages,
        "recent_assistant_messages": recent_assistant_messages,
        "preservation_notes": preservation_notes,
        "handoff_path": str(handoff_path),
    }
    checkpoint_json_path = checkpoints_dir / f"{safe_session_id}-{timestamp_slug}.json"
    checkpoint_json_path.write_text(json.dumps(checkpoint_payload, indent=2), encoding="utf-8")

    event_payload = {
        "kind": "compaction_checkpoint",
        "session_id": safe_session_id,
        "saved_at": timestamp_iso,
        "profile": profile,
        "fleet": fleet,
        "context_tokens": approx_tokens,
        "context_length": context_length,
        "threshold_tokens": threshold_tokens,
        "context_percent": context_percent,
        "handoff_path": str(handoff_path),
        "checkpoint_json_path": str(checkpoint_json_path),
    }
    event_path = events_dir / f"{timestamp.strftime('%Y-%m-%d')}.jsonl"
    with event_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event_payload, ensure_ascii=False) + "\n")

    daily_path = daily_dir / f"{timestamp.strftime('%Y-%m-%d')}.md"
    with daily_path.open("a", encoding="utf-8") as f:
        f.write(
            "\n## Compaction Checkpoint\n"
            f"- Timestamp: {timestamp_iso}\n"
            f"- Session: {safe_session_id}\n"
            f"- Profile/Fleet: {profile} / {fleet}\n"
            f"- Context: {approx_tokens if approx_tokens is not None else 'unknown'} / {context_length}"
            f" (threshold {threshold_tokens}, {context_percent}%)\n"
            f"- Handoff: `{handoff_path}`\n"
            f"- Note: {preservation_notes.strip() or 'No preservation notes.'}\n"
        )

    return {
        "handoff_path": str(handoff_path),
        "latest_handoff_path": str(latest_handoff_path),
        "checkpoint_json_path": str(checkpoint_json_path),
        "event_path": str(event_path),
        "daily_path": str(daily_path),
    }


def _infer_profile_name(hermes_home: Path) -> str:
    if hermes_home.parent.name == "profiles":
        return hermes_home.name
    return "default"


def _resolve_memory_root(workspace_dir: Path) -> Path:
    candidates = [
        workspace_dir / "memory",
        workspace_dir / "pantheon-migrated" / "workspace-generic" / "memory",
        workspace_dir / "workspace-generic" / "memory",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _infer_fleet(profile: str) -> str:
    name = (profile or "").strip().lower()
    if any(token in name for token in ("bharat", "fitlife", "bd")):
        return "bd"
    if any(token in name for token in ("swivo", "rani", "rs")):
        return "rs"
    return "generic"


def _compute_context_percent(approx_tokens: int | None, context_length: int) -> float:
    if not approx_tokens or context_length <= 0:
        return 0.0
    return round((approx_tokens / context_length) * 100, 1)


def _recent_messages(
    messages: Iterable[Dict[str, Any]], *, roles: set[str], limit: int
) -> List[str]:
    collected: List[str] = []
    for msg in messages:
        if msg.get("role") not in roles:
            continue
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                str(item.get("text", "")) if isinstance(item, dict) else str(item)
                for item in content
            )
        text = " ".join(str(content).split()).strip()
        if text:
            collected.append(text[:600])
    return collected[-limit:]


def _render_handoff_markdown(
    *,
    session_id: str,
    profile: str,
    fleet: str,
    saved_at: str,
    approx_tokens: int | None,
    context_length: int,
    threshold_tokens: int,
    context_percent: float,
    preservation_notes: str,
    recent_user_messages: List[str],
    recent_assistant_messages: List[str],
) -> str:
    user_block = "\n".join(f"- {item}" for item in recent_user_messages) or "- None captured."
    assistant_block = "\n".join(f"- {item}" for item in recent_assistant_messages) or "- None captured."
    return (
        f"# Compaction Checkpoint — {saved_at}\n\n"
        f"- Session ID: `{session_id}`\n"
        f"- Profile: `{profile}`\n"
        f"- Fleet: `{fleet}`\n"
        f"- Status: pending compaction\n"
        f"- Context usage: `{approx_tokens if approx_tokens is not None else 'unknown'}` / `{context_length}`"
        f" (threshold `{threshold_tokens}`, `{context_percent}%`)\n\n"
        "## Preserve Exactly\n"
        f"{preservation_notes.strip() or 'No explicit preservation notes.'}\n\n"
        "## Recent User Asks\n"
        f"{user_block}\n\n"
        "## Recent Assistant / Tool State\n"
        f"{assistant_block}\n\n"
        "## Continuation Guidance\n"
        "- Resume from the latest user ask and the recent assistant/tool state above.\n"
        "- Treat this file as a canonical pre-compaction handoff artifact.\n"
        "- Cross-check with the session tail and current workspace state before repeating work.\n"
    )
