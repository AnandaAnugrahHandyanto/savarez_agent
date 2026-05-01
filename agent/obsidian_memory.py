"""Local Obsidian vault helpers for Hermes memory downshift workflows.

This module provides a lightweight file-backed note writer for long-form
memory overflow and compression downshift paths. It is intentionally local
and import-safe — no external Obsidian APIs, just markdown files inside a
vault directory.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from hermes_constants import get_hermes_home

_DEFAULT_OBSIDIAN_DIRNAME = "Obsidian Vault"
_DEFAULT_DOWNSHIFT_SUBDIR = Path("Inbox") / "Hermes"


def get_obsidian_vault_path() -> Path:
    """Resolve the Obsidian vault path.

    Resolution order:
    1. OBSIDIAN_VAULT_PATH env var
    2. ~/Documents/Obsidian Vault
    """
    raw = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / "Documents" / _DEFAULT_OBSIDIAN_DIRNAME


def obsidian_vault_exists() -> bool:
    """Return True when the resolved vault directory exists."""
    return get_obsidian_vault_path().is_dir()


def get_obsidian_downshift_dir() -> Path:
    """Return the directory used for Hermes-managed auto-downshift notes."""
    return get_obsidian_vault_path() / _DEFAULT_DOWNSHIFT_SUBDIR


def _slugify(value: str, *, fallback: str = "note") -> str:
    text = re.sub(r"\s+", "-", (value or "").strip().lower())
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-._")
    return text or fallback


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 16)].rstrip() + "\n...[truncated]..."


def _note_title(trigger: str, title_hint: str = "") -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H%M")
    hint = _slugify(title_hint, fallback=trigger).replace("-", " ").strip()
    hint = hint[:80].strip() or trigger
    return f"{stamp} {hint}".strip()


def _note_filename(trigger: str, title_hint: str = "") -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    hint = _slugify(title_hint, fallback=trigger)[:80]
    return f"{stamp}-{_slugify(trigger)}-{hint}.md"


def _dedupe_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for idx in range(2, 1000):
        candidate = path.with_name(f"{stem}-{idx}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not allocate unique note path for {path}")


def _render_note(
    *,
    trigger: str,
    content: str,
    title_hint: str = "",
    route_reason: str = "",
    session_id: str = "",
    target: str = "memory",
    original_usage: str = "",
) -> str:
    title = _note_title(trigger, title_hint)
    created_at = datetime.now(timezone.utc).isoformat()
    summary = _truncate_text((content or "").strip(), 800)
    body = _truncate_text((content or "").strip(), 12000)
    lines = [
        "---",
        f"title: {title}",
        "source: hermes-memory-downshift",
        f"trigger: {trigger}",
        f"target: {target}",
        f"created_at: {created_at}",
    ]
    if session_id:
        lines.append(f"session_id: {session_id}")
    if route_reason:
        lines.append(f"route_reason: {route_reason}")
    if original_usage:
        lines.append(f"original_usage: {original_usage}")
    lines.extend([
        "tags:",
        "  - hermes",
        "  - memory-downshift",
        f"  - {trigger}",
        "---",
        "",
        f"# {title}",
        "",
        "## Summary",
        summary or "- (empty)",
        "",
        "## Details",
        body or "(empty)",
        "",
    ])
    return "\n".join(lines)


def write_obsidian_downshift_note(
    *,
    trigger: str,
    content: str,
    title_hint: str = "",
    route_reason: str = "",
    session_id: str = "",
    target: str = "memory",
    original_usage: str = "",
) -> dict:
    """Write a Hermes-managed markdown note into the Obsidian vault.

    Returns a compact dict with success flag and note metadata. If the vault is
    unavailable, returns success=False without creating directories.
    """
    vault = get_obsidian_vault_path()
    if not vault.is_dir():
        return {
            "success": False,
            "error": f"Obsidian vault not found: {vault}",
            "vault_path": str(vault),
        }

    note_dir = get_obsidian_downshift_dir()
    note_dir.mkdir(parents=True, exist_ok=True)
    filename = _note_filename(trigger, title_hint)
    path = _dedupe_path(note_dir / filename)
    rendered = _render_note(
        trigger=trigger,
        content=content,
        title_hint=title_hint,
        route_reason=route_reason,
        session_id=session_id,
        target=target,
        original_usage=original_usage,
    )
    path.write_text(rendered, encoding="utf-8")
    return {
        "success": True,
        "path": str(path),
        "vault_path": str(vault),
        "trigger": trigger,
        "title": path.stem,
    }


def get_memory_downshift_log_path() -> Path:
    """Local fallback log for downshift failures/diagnostics under HERMES_HOME."""
    return get_hermes_home() / "logs" / "memory_downshift.log"
