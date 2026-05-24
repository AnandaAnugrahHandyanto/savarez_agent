"""User-defined shell commands for the kanban dashboard."""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any, Optional

_MAX_COMMANDS = 50
_MAX_NAME_LEN = 80
_MAX_ICON_LEN = 16
_MAX_COMMAND_LEN = 4000
_OUTPUT_TAIL = 4000
_DEFAULT_TIMEOUT = 120

_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _normalize_command_list(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_command_item(item, allow_missing_id=True)
        if normalized is None:
            continue
        if normalized["id"] in seen:
            continue
        seen.add(normalized["id"])
        out.append(normalized)
        if len(out) >= _MAX_COMMANDS:
            break
    return out


def load_board_custom_commands(board: Optional[str] = None) -> list[dict[str, Any]]:
    """Return custom commands stored on a kanban board's ``board.json``."""
    from hermes_cli import kanban_db as kb

    meta = kb.read_board_metadata(board)
    return _normalize_command_list(meta.get("custom_commands"))


def save_board_custom_commands(
    board: Optional[str],
    commands: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate and persist custom commands on ``board.json``."""
    from hermes_cli import kanban_db as kb

    slug = kb._normalize_board_slug(board) or kb.DEFAULT_BOARD
    normalized = validate_custom_commands(commands)
    meta = kb.read_board_metadata(slug)
    meta.pop("db_path", None)
    meta["custom_commands"] = normalized
    path = kb.board_metadata_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized


def validate_custom_commands(commands: list[Any]) -> list[dict[str, Any]]:
    if not isinstance(commands, list):
        raise ValueError("commands must be a list")
    if len(commands) > _MAX_COMMANDS:
        raise ValueError(f"at most {_MAX_COMMANDS} custom commands allowed")

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in commands:
        normalized = _normalize_command_item(item, allow_missing_id=False)
        if normalized is None:
            raise ValueError("each command must be an object with name and command")
        cid = normalized["id"]
        if cid in seen:
            raise ValueError(f"duplicate command id: {cid}")
        seen.add(cid)
        out.append(normalized)
    return out


def _normalize_command_item(item: Any, *, allow_missing_id: bool) -> Optional[dict[str, str]]:
    if not isinstance(item, dict):
        return None
    name = str(item.get("name") or "").strip()
    command = str(item.get("command") or "").strip()
    if not name or not command:
        return None
    if len(name) > _MAX_NAME_LEN:
        name = name[:_MAX_NAME_LEN]
    icon = str(item.get("icon") or "").strip()
    if len(icon) > _MAX_ICON_LEN:
        icon = icon[:_MAX_ICON_LEN]
    if "\x00" in command:
        raise ValueError("command must not contain null bytes")
    if len(command) > _MAX_COMMAND_LEN:
        raise ValueError(f"command must be at most {_MAX_COMMAND_LEN} characters")

    cid = str(item.get("id") or "").strip()
    if not cid:
        if allow_missing_id:
            cid = f"cmd_{uuid.uuid4().hex[:12]}"
        else:
            raise ValueError("each command requires an id")
    if not _ID_RE.match(cid):
        raise ValueError(f"invalid command id: {cid!r}")

    return {
        "id": cid,
        "name": name,
        "icon": icon,
        "command": command,
    }


def find_custom_command(commands: list[dict[str, Any]], command_id: str) -> Optional[dict[str, str]]:
    cid = (command_id or "").strip()
    for cmd in commands:
        if cmd.get("id") == cid:
            return cmd
    return None


def run_custom_command_in_workspace(
    workspace: Path,
    command: str,
    *,
    timeout_seconds: int = _DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Run a shell command in ``workspace`` and return captured output."""
    ws = workspace.resolve()
    if not ws.is_dir():
        raise ValueError(f"workspace is not a directory: {ws}")

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds)),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        return {
            "ok": False,
            "exit_code": None,
            "timed_out": True,
            "stdout": stdout[-_OUTPUT_TAIL:],
            "stderr": stderr[-_OUTPUT_TAIL:],
        }

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    return {
        "ok": result.returncode == 0,
        "exit_code": int(result.returncode),
        "timed_out": False,
        "stdout": stdout[-_OUTPUT_TAIL:],
        "stderr": stderr[-_OUTPUT_TAIL:],
    }
