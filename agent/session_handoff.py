"""Automatic context-refresh handoff helpers.

This module writes a lightweight `/new` continuation handoff when a logical
conversation has been compressed repeatedly. It is intentionally conservative:
prepare a verified file and notify the caller; do not reset the session here.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


_DEFAULT_CONTEXT_REFRESH_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "handoff_after_compressions": 2,
    "mode": "prepare_only",
    "require_safe_turn_boundary": True,
    "require_no_running_processes": True,
    "write_session_handoff": True,
    "write_project_handoff_when_detectable": True,
    "include_sha256": True,
    "max_handoff_lines": 250,
    "handoff_base_dir": "",
}


@dataclass(frozen=True)
class HandoffResult:
    path: Path
    session_id: str
    line_count: int
    byte_count: int
    sha256: str
    resume_prompt: str


def _effective_config(agent: Any) -> Dict[str, Any]:
    cfg = dict(_DEFAULT_CONTEXT_REFRESH_CONFIG)
    try:
        agent_cfg = getattr(agent, "context_refresh_config", None)
        if agent_cfg is None:
            from hermes_cli.config import load_config

            agent_cfg = (load_config() or {}).get("context_refresh", {})
        if isinstance(agent_cfg, dict):
            cfg.update(agent_cfg)
    except Exception:
        pass
    return cfg


def _handoff_base_dir(cfg: Dict[str, Any]) -> Path:
    configured = str(cfg.get("handoff_base_dir") or "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "agent-artifacts"


def _session_title(agent: Any, session_id: str) -> str:
    try:
        db = getattr(agent, "_session_db", None)
        if db:
            return db.get_session_title(session_id) or "untitled"
    except Exception:
        pass
    return "untitled"


def _message_excerpt(messages: list, max_messages: int = 8, max_chars: int = 3000) -> str:
    parts: list[str] = []
    for msg in (messages or [])[-max_messages:]:
        role = msg.get("role") if isinstance(msg, dict) else None
        if role not in {"user", "assistant"}:
            continue
        content = msg.get("content") or ""
        if not isinstance(content, str):
            content = str(content)
        content = content.strip()
        if content:
            parts.append(f"- {role}: {content[:500]}")
    excerpt = "\n".join(parts)
    return excerpt[:max_chars] if excerpt else "- No compact excerpt available; rehydrate from session history."


def _build_handoff_content(
    *,
    agent: Any,
    messages: list,
    session_id: str,
    reason: str,
    compression_count: int,
    cfg: Dict[str, Any],
) -> str:
    title = _session_title(agent, session_id)
    generated = time.strftime("%Y-%m-%d %H:%M:%S %z")
    resume_prompt = _resume_prompt(session_id, _handoff_path(cfg, session_id))
    excerpt = _message_excerpt(messages)
    mode = cfg.get("mode", "prepare_only")

    return f"""# Automatic Context Refresh Handoff

Generated: {generated}
Session ID: {session_id}
Session title/topic: {title}
Reason: {reason}
Compression count: {compression_count}
Mode: {mode}

## Fresh /new Resume Prompt

```text
{resume_prompt}
```

## What This File Is

This is an automatic prepare-only context refresh handoff created after repeated context compression. It preserves continuity for a fresh `/new` session. It does not prove that implementation, repo, GitHub, scheduler, runtime, publication, or audit state is complete.

## Recent Conversation Excerpt

{excerpt}

## Current Known State

- Local repo state: unverified; verify before action
- GitHub push/publication state: unverified; verify before action
- Tests/validators: unverified; verify before action
- Runtime/scheduler/timer state: unverified; verify before action
- External/live calls: unverified; verify before action
- Finished-product status: unverified; verify before action

## Next Valid Actions

1. Start a fresh `/new` session if context drift is becoming a risk.
2. Read this handoff first.
3. Verify current source-of-truth state with tools before making claims or taking side effects.
4. Continue from the user's latest explicit objective, not from stale compacted transcript requests.

## What Not To Do Accidentally

- Do not claim repo/GitHub/runtime/scheduler/publication/test status unless verified.
- Do not treat this prepare-only handoff as proof the task is complete.
- Do not auto-`/new` in the middle of a tool loop.
- Do not overwrite manual session titles while resuming.
"""


def _handoff_path(cfg: Dict[str, Any], session_id: str) -> Path:
    return _handoff_base_dir(cfg) / "session-handoffs" / session_id / "AFTER_SESSION_COMPRESSION_HANDOFF.md"


def _resume_prompt(session_id: str, path: Path) -> str:
    return f"Reference session {session_id}. Read {path} first, then continue from the Next Valid Actions section."


def write_handoff_file(path: Path, content: str, session_id: str) -> HandoffResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    data = path.read_bytes()
    line_count = content.count("\n") + (0 if content.endswith("\n") else 1)
    return HandoffResult(
        path=path,
        session_id=session_id,
        line_count=line_count,
        byte_count=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        resume_prompt=_resume_prompt(session_id, path),
    )


def maybe_prepare_context_refresh_handoff(agent: Any, messages: list, reason: str) -> Optional[HandoffResult]:
    """Prepare a session handoff when compression count reaches threshold.

    Returns a HandoffResult when a new handoff is written, otherwise None.
    """
    cfg = _effective_config(agent)
    if not cfg.get("enabled", True) or not cfg.get("write_session_handoff", True):
        return None
    if cfg.get("mode", "prepare_only") not in {"prepare_only", "auto_new"}:
        return None

    compressor = getattr(agent, "context_compressor", None)
    compression_count = int(getattr(compressor, "compression_count", 0) or 0)
    threshold = int(cfg.get("handoff_after_compressions") or 2)
    if compression_count < threshold:
        return None

    prepared_for = int(getattr(agent, "_context_refresh_handoff_prepared_for_count", 0) or 0)
    if prepared_for >= compression_count:
        return None

    session_id = getattr(agent, "session_id", None) or os.environ.get("HERMES_SESSION_ID") or "unknown-session"
    path = _handoff_path(cfg, session_id)
    content = _build_handoff_content(
        agent=agent,
        messages=messages,
        session_id=session_id,
        reason=reason,
        compression_count=compression_count,
        cfg=cfg,
    )

    result = write_handoff_file(path, content, session_id)
    setattr(agent, "_context_refresh_handoff_prepared_for_count", compression_count)
    setattr(
        agent,
        "_pending_context_refresh",
        {
            "handoff_path": str(result.path),
            "session_id": session_id,
            "reason": reason,
            "compression_count": compression_count,
            "sha256": result.sha256,
            "mode": cfg.get("mode", "prepare_only"),
        },
    )

    notify = getattr(agent, "_emit_warning", None)
    if callable(notify):
        notify(
            "Context refresh handoff ready after "
            f"{compression_count} compressions: {result.path} "
            f"({result.line_count} lines, {result.byte_count} bytes, sha256 {result.sha256}). "
            f"After /new: {result.resume_prompt}"
        )
    return result
