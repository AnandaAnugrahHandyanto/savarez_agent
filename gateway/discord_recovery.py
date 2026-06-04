"""Bounded Discord → Slack/Kanban recovery bridge.

This module intentionally implements a narrow, fail-closed recovery path:
Discord direct-mention turns can request recovery only when they include
explicit Slack thread and Kanban card metadata.  It does not enable Discord
free-response, route discovery, admin actions, or any protected runtime work.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home
from gateway.config import Platform

logger = logging.getLogger(__name__)

_RECOVERY_INTENT_RE = re.compile(r"(recovery|recover|회수|slack/kanban|slack\s*\+\s*kanban|원스레드)", re.IGNORECASE)
_SLACK_THREAD_RE = re.compile(r"\bslack:(C[A-Z0-9]+):(\d{10,}\.\d{3,})\b")
_KANBAN_RE = re.compile(r"\b([a-z0-9][a-z0-9_-]{1,63})/(t_[a-f0-9]{6,16})\b", re.IGNORECASE)
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_\-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{20,}\b"),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b"),
    re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._\-]{20,}\b"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password|passwd|비밀번호)\s*[:=]\s*\S+"),
)
_PROTECTED_INTENT_RE = re.compile(
    r"(LaunchAgent|launchctl|reset\s+--hard|force\s+push|git\s+push|"
    r"M1|macmini|invest-system|백테스트|KCC\s+source|DB\s*write|주문|계좌)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DiscordRecoveryRequest:
    slack_channel: str
    slack_thread: str
    kanban_board: str
    kanban_card: str
    idempotency_key: str
    discord_chat_id: str
    discord_message_id: str

    @property
    def slack_target(self) -> str:
        return f"slack:{self.slack_channel}:{self.slack_thread}"

    @property
    def kanban_target(self) -> str:
        return f"{self.kanban_board}/{self.kanban_card}"


def _contains_secret_like_value(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in _SECRET_PATTERNS)


def extract_recovery_request(event: Any) -> DiscordRecoveryRequest | None:
    """Extract an explicit, bounded recovery request from a Discord event.

    Required input shape in the Discord message text:
      - recovery intent word (e.g. "회수", "recovery", "Slack/Kanban")
      - explicit Slack thread target: slack:C123:1780000000.123456
      - explicit Kanban card target: ops-build/t_123abcde

    Missing metadata returns None (fail-closed, no guessing).
    Unsafe/protected/secret-like payloads also return None.
    """
    source = getattr(event, "source", None)
    if getattr(source, "platform", None) != Platform.DISCORD:
        return None

    text = (getattr(event, "text", "") or "").strip()
    if not text or not _RECOVERY_INTENT_RE.search(text):
        return None
    if _contains_secret_like_value(text) or _PROTECTED_INTENT_RE.search(text):
        logger.warning("Discord recovery request rejected by safety scan")
        return None

    slack_match = _SLACK_THREAD_RE.search(text)
    kanban_match = _KANBAN_RE.search(text)
    if not slack_match or not kanban_match:
        return None

    discord_chat_id = str(getattr(source, "chat_id", "") or "")
    discord_message_id = str(getattr(event, "message_id", "") or "")
    key_material = "|".join(
        [
            discord_chat_id,
            discord_message_id,
            slack_match.group(1),
            slack_match.group(2),
            kanban_match.group(1),
            kanban_match.group(2),
        ]
    )
    idem = "discord-recovery-" + hashlib.sha256(key_material.encode("utf-8")).hexdigest()[:16]
    return DiscordRecoveryRequest(
        slack_channel=slack_match.group(1),
        slack_thread=slack_match.group(2),
        kanban_board=kanban_match.group(1),
        kanban_card=kanban_match.group(2),
        idempotency_key=idem,
        discord_chat_id=discord_chat_id,
        discord_message_id=discord_message_id,
    )


def _state_path() -> Path:
    return get_hermes_home() / "gateway" / "discord_recovery_seen.json"


def _load_seen() -> set[str]:
    path = _state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return set()
    if isinstance(data, list):
        return {str(x) for x in data}
    return set()


def _mark_seen(key: str) -> None:
    path = _state_path()
    seen = _load_seen()
    seen.add(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_recovery_message(req: DiscordRecoveryRequest, response: str) -> str:
    bounded_response = (response or "").strip().replace("\n", " ")[:500]
    if not bounded_response:
        bounded_response = "[empty response]"
    return (
        "[DISCORD-RECOVERY-AUTO]\n"
        "Discord direct mention 결과를 Slack/Kanban 정본으로 자동 회수 기록했습니다.\n\n"
        f"- Discord chat/thread: {req.discord_chat_id}\n"
        f"- Discord message: {req.discord_message_id or 'unknown'}\n"
        f"- Kanban: {req.kanban_target}\n"
        f"- Idempotency: {req.idempotency_key}\n"
        f"- Response preview: {bounded_response}\n\n"
        "금지 범위: free-response/admin/permission/secret/protected runtime 변경 없음."
    )


async def _comment_kanban(req: DiscordRecoveryRequest, message: str) -> None:
    cmd = [
        "hermes",
        "kanban",
        "--board",
        req.kanban_board,
        "comment",
        req.kanban_card,
        message,
    ]

    def _run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, text=True, capture_output=True, timeout=60)

    proc = await asyncio.to_thread(_run)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "kanban comment failed").strip()[:500])


async def perform_recovery_if_requested(runner: Any, event: Any, response: str) -> dict[str, Any] | None:
    """Send bounded Slack/Kanban recovery records for an explicit request.

    Returns None when the event is not a recovery request.  Returns a status
    dict for duplicate/pass/partial/error cases.  Exceptions are swallowed so a
    recovery failure never blocks the user's Discord response.
    """
    req = extract_recovery_request(event)
    if req is None:
        return None

    if req.idempotency_key in _load_seen():
        logger.info("Discord recovery skipped duplicate: %s", req.idempotency_key)
        return {"status": "duplicate", "idempotency_key": req.idempotency_key}

    message = build_recovery_message(req, response)
    slack_ok = False
    kanban_ok = False
    errors: list[str] = []

    try:
        slack_adapter = getattr(runner, "adapters", {}).get(Platform.SLACK)
        if slack_adapter is None:
            raise RuntimeError("Slack adapter unavailable")
        result = await slack_adapter.send(
            req.slack_channel,
            message,
            metadata={"thread_id": req.slack_thread},
        )
        if getattr(result, "success", False) is False:
            raise RuntimeError(getattr(result, "error", "Slack send failed"))
        slack_ok = True
    except Exception as exc:  # pragma: no cover - logging branch tested via status
        errors.append(f"slack:{exc}")
        logger.warning("Discord recovery Slack send failed: %s", exc)

    try:
        await _comment_kanban(req, message)
        kanban_ok = True
    except Exception as exc:  # pragma: no cover - logging branch tested via status
        errors.append(f"kanban:{exc}")
        logger.warning("Discord recovery Kanban comment failed: %s", exc)

    if slack_ok and kanban_ok:
        _mark_seen(req.idempotency_key)
        logger.info("Discord recovery complete: %s", req.idempotency_key)
        return {"status": "pass", "idempotency_key": req.idempotency_key}

    logger.warning("Discord recovery partial failure: %s errors=%s", req.idempotency_key, errors)
    return {
        "status": "partial_recovery",
        "idempotency_key": req.idempotency_key,
        "slack_ok": slack_ok,
        "kanban_ok": kanban_ok,
        "errors": errors,
    }
