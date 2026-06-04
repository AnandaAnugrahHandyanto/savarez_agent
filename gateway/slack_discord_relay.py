"""Bounded Slack → Discord/Kanban relay bridge.

This module implements a narrow, fail-closed relay path:
Slack turns can ask Hermes to relay a bounded status/review packet to Discord
only when the message includes an explicit Discord target and Kanban card.
It does not enable bot-to-bot loops, Discord free-response, route discovery,
admin actions, permission changes, or protected runtime work.
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

_RELAY_INTENT_RE = re.compile(
    r"(relay|cross[-_ ]?relay|중계|전달|디스코드|Discord)",
    re.IGNORECASE,
)
_DISCORD_TARGET_RE = re.compile(r"\bdiscord:([#A-Za-z0-9_\-가-힣]+)\b")
_NATURAL_DISCORD_CHANNEL_RE = re.compile(r"#[A-Za-z0-9_\-가-힣]+")
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
class SlackDiscordRelayRequest:
    discord_target: str
    kanban_board: str
    kanban_card: str
    idempotency_key: str
    slack_channel: str
    slack_thread: str
    slack_message_id: str

    @property
    def kanban_target(self) -> str:
        return f"{self.kanban_board}/{self.kanban_card}"

    @property
    def slack_target(self) -> str:
        if self.slack_thread:
            return f"slack:{self.slack_channel}:{self.slack_thread}"
        return f"slack:{self.slack_channel}"


def _contains_secret_like_value(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in _SECRET_PATTERNS)


def _extract_discord_target(text: str) -> str | None:
    """Extract an explicit Discord target without requiring operator test syntax."""
    discord_match = _DISCORD_TARGET_RE.search(text)
    if discord_match:
        return discord_match.group(1)

    if not re.search(r"(디스코드|Discord)", text or "", re.IGNORECASE):
        return None

    channel_match = _NATURAL_DISCORD_CHANNEL_RE.search(text)
    if channel_match:
        return re.sub(r"(으로|에게|에서|까지|로|에|를|을)$", "", channel_match.group(0))
    return None


def extract_relay_request(event: Any) -> SlackDiscordRelayRequest | None:
    """Extract an explicit, bounded Slack → Discord relay request.

    Required Slack message text shape:
      - relay intent word (e.g. "중계", "전달", "relay", "Discord")
      - explicit Discord target: discord:#agent-review-lab or discord:<id>
      - explicit Kanban card target: hermes-ops/t_123abcde

    Missing metadata returns None (fail-closed, no guessing).
    Unsafe/protected/secret-like payloads also return None.
    """
    source = getattr(event, "source", None)
    if getattr(source, "platform", None) != Platform.SLACK:
        return None

    text = (getattr(event, "text", "") or "").strip()
    if not text or not _RELAY_INTENT_RE.search(text):
        return None
    if _contains_secret_like_value(text) or _PROTECTED_INTENT_RE.search(text):
        logger.warning("Slack→Discord relay request rejected by safety scan")
        return None

    discord_target = _extract_discord_target(text)
    kanban_match = _KANBAN_RE.search(text)
    if not discord_target or not kanban_match:
        return None

    slack_channel = str(getattr(source, "chat_id", "") or "")
    slack_thread = str(getattr(source, "thread_id", "") or "")
    slack_message_id = str(getattr(event, "message_id", "") or "")
    key_material = "|".join(
        [
            slack_channel,
            slack_thread,
            slack_message_id,
            discord_target,
            kanban_match.group(1),
            kanban_match.group(2),
        ]
    )
    idem = "slack-discord-relay-" + hashlib.sha256(key_material.encode("utf-8")).hexdigest()[:16]
    return SlackDiscordRelayRequest(
        discord_target=discord_target,
        kanban_board=kanban_match.group(1),
        kanban_card=kanban_match.group(2),
        idempotency_key=idem,
        slack_channel=slack_channel,
        slack_thread=slack_thread,
        slack_message_id=slack_message_id,
    )


def _state_path() -> Path:
    return get_hermes_home() / "gateway" / "slack_discord_relay_seen.json"


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


def build_discord_relay_message(req: SlackDiscordRelayRequest, response: str) -> str:
    bounded_response = (response or "").strip().replace("\n", " ")[:700]
    if not bounded_response:
        bounded_response = "[empty response]"
    return (
        "[SLACK-DISCORD-RELAY-AUTO]\n"
        "Slack thread 요청을 Discord 보조 채널로 bounded relay 했습니다.\n\n"
        f"- Slack source: {req.slack_target}\n"
        f"- Slack message: {req.slack_message_id or 'unknown'}\n"
        f"- Kanban: {req.kanban_target}\n"
        f"- Idempotency: {req.idempotency_key}\n"
        f"- Response preview: {bounded_response}\n\n"
        "금지 범위: bot-loop/free-response/admin/permission/secret/protected runtime 변경 없음."
    )


async def _comment_kanban(req: SlackDiscordRelayRequest, message: str) -> None:
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


def _resolve_discord_send_target(target: str) -> str:
    """Resolve a bounded Discord relay target into an adapter-sendable ID."""
    raw = (target or "").strip()
    if raw.isdigit():
        return raw

    from gateway.channel_directory import resolve_channel_name

    resolved = resolve_channel_name("discord", raw)
    if not resolved:
        raise RuntimeError(f"Discord target not found in channel directory: {raw}")
    return resolved


async def perform_relay_if_requested(runner: Any, event: Any, response: str) -> dict[str, Any] | None:

    """Send bounded Discord/Kanban relay records for an explicit Slack request."""
    req = extract_relay_request(event)
    if req is None:
        return None

    if req.idempotency_key in _load_seen():
        logger.info("Slack→Discord relay skipped duplicate: %s", req.idempotency_key)
        return {"status": "duplicate", "idempotency_key": req.idempotency_key}

    message = build_discord_relay_message(req, response)
    discord_ok = False
    kanban_ok = False
    errors: list[str] = []

    try:
        discord_adapter = getattr(runner, "adapters", {}).get(Platform.DISCORD)
        if discord_adapter is None:
            raise RuntimeError("Discord adapter unavailable")
        discord_send_target = _resolve_discord_send_target(req.discord_target)
        result = await discord_adapter.send(discord_send_target, message)
        if getattr(result, "success", False) is False:
            raise RuntimeError(getattr(result, "error", "Discord send failed"))
        discord_ok = True
    except Exception as exc:  # pragma: no cover - logging branch tested via status
        errors.append(f"discord:{exc}")
        logger.warning("Slack→Discord relay send failed: %s", exc)

    try:
        await _comment_kanban(req, message)
        kanban_ok = True
    except Exception as exc:  # pragma: no cover - logging branch tested via status
        errors.append(f"kanban:{exc}")
        logger.warning("Slack→Discord relay Kanban comment failed: %s", exc)

    if discord_ok and kanban_ok:
        _mark_seen(req.idempotency_key)
        logger.info("Slack→Discord relay complete: %s", req.idempotency_key)
        return {"status": "pass", "idempotency_key": req.idempotency_key}

    logger.warning("Slack→Discord relay partial failure: %s errors=%s", req.idempotency_key, errors)
    return {
        "status": "partial_relay",
        "idempotency_key": req.idempotency_key,
        "discord_ok": discord_ok,
        "kanban_ok": kanban_ok,
        "errors": errors,
    }
