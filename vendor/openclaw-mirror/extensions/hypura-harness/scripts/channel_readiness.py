"""Redacted LINE/Telegram readiness diagnostics for the Hypura harness."""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any


TELEGRAM_SENT_MESSAGE_TTL_MS = 24 * 60 * 60 * 1000
LINE_ID_RE = re.compile(r"^(?:line:(?:user|group|room):)?([UCR][a-f0-9]{32})$", re.I)
TELEGRAM_CHAT_RE = re.compile(r"^(?:telegram:)?(-?\d{5,})$", re.I)
SECRET_PATH_TOKENS = ("token", "secret", "apikey", "api_key", "password")
LINE_TARGET_KEYS = {
    "allowfrom",
    "userid",
    "groupid",
    "roomid",
    "recipient",
    "recipientid",
    "to",
    "target",
    "destination",
    "defaultto",
}
TELEGRAM_TARGET_KEYS = {
    "allowfrom",
    "chatid",
    "userid",
    "groupid",
    "recipient",
    "recipientid",
    "to",
    "target",
    "destination",
    "defaultto",
}
SESSION_ROUTE_TARGET_KEYS = {
    "from",
    "groupsubject",
    "lastto",
    "originatingto",
    "to",
}


def _strip_jsonc(text: str) -> str:
    """Remove common JSONC comments without touching string contents."""
    chars: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if in_string:
            chars.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            chars.append(char)
            index += 1
            continue
        if char == "/" and next_char == "/":
            index += 2
            while index < len(text) and text[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < len(text) and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue
        chars.append(char)
        index += 1
    without_comments = "".join(chars)
    return re.sub(r",(\s*[}\]])", r"\1", without_comments)


def _read_jsonc(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    data = json.loads(_strip_jsonc(text))
    return data if isinstance(data, dict) else {}


def _safe_config_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _path_has_secret(path: tuple[str, ...]) -> bool:
    normalized = ".".join(path).lower()
    return any(token in normalized for token in SECRET_PATH_TOKENS)


def _normalize_key(key: str) -> str:
    return key.replace("_", "").replace("-", "").lower()


def _iter_target_strings(
    value: Any,
    *,
    path: tuple[str, ...] = (),
    target_keys: set[str],
):
    if _path_has_secret(path):
        return
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = (*path, str(key))
            normalized_key = _normalize_key(str(key))
            if isinstance(child, str) and normalized_key in target_keys:
                yield child
            elif isinstance(child, list) and normalized_key in target_keys:
                for item in child:
                    if isinstance(item, (str, int)):
                        yield str(item)
            if isinstance(child, (dict, list)):
                yield from _iter_target_strings(child, path=key_path, target_keys=target_keys)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_target_strings(
                child,
                path=(*path, str(index)),
                target_keys=target_keys,
            )


def _read_allow_from_store_entries(credentials_dir: Path, channel: str) -> list[str]:
    if not credentials_dir.exists():
        return []
    entries: list[str] = []
    seen_paths: set[Path] = set()
    for candidate in [
        credentials_dir / f"{channel}-default-allowFrom.json",
        credentials_dir / f"{channel}-allowFrom.json",
        *credentials_dir.glob(f"{channel}-*-allowFrom.json"),
    ]:
        if candidate in seen_paths or not candidate.exists():
            continue
        seen_paths.add(candidate)
        try:
            data = json.loads(candidate.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        raw_entries = data.get("allowFrom") if isinstance(data, dict) else None
        if not isinstance(raw_entries, list):
            continue
        for item in raw_entries:
            if isinstance(item, (str, int)):
                normalized = str(item).strip()
                if normalized:
                    entries.append(normalized)
    return list(dict.fromkeys(entries))


def _read_telegram_sent_message_targets(state_root: Path, now_ms: int | None = None) -> list[str]:
    agents_dir = state_root / "agents"
    if not agents_dir.exists():
        return []
    resolved_now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    targets: list[str] = []
    for candidate in agents_dir.glob("*/sessions/*.telegram-sent-messages.json"):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for raw_chat_id, raw_messages in data.items():
            chat_id = str(raw_chat_id).strip()
            match = TELEGRAM_CHAT_RE.match(chat_id)
            if not match or not isinstance(raw_messages, dict):
                continue
            for timestamp in raw_messages.values():
                if (
                    isinstance(timestamp, (int, float))
                    and math.isfinite(timestamp)
                    and resolved_now_ms - int(timestamp) <= TELEGRAM_SENT_MESSAGE_TTL_MS
                ):
                    targets.append(match.group(1))
                    break
    return list(dict.fromkeys(targets))


def _read_session_route_targets(state_root: Path) -> list[str]:
    agents_dir = state_root / "agents"
    if not agents_dir.exists():
        return []
    targets: list[str] = []
    for candidate in agents_dir.glob("*/sessions/sessions.json"):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        for raw in _iter_target_strings(data, target_keys=SESSION_ROUTE_TARGET_KEYS):
            normalized = str(raw).strip()
            if normalized:
                targets.append(normalized)
    return list(dict.fromkeys(targets))


def _count_line_targets(line_cfg: dict[str, Any], store_entries: list[str] | None = None) -> dict[str, int]:
    counts = {"directUsers": 0, "groups": 0, "rooms": 0}
    seen: set[str] = set()

    groups = line_cfg.get("groups")
    if isinstance(groups, dict):
        for key in groups:
            match = LINE_ID_RE.match(str(key).strip())
            if match:
                seen.add(match.group(1).upper())

    for raw in _iter_target_strings(line_cfg, target_keys=LINE_TARGET_KEYS):
        match = LINE_ID_RE.match(str(raw).strip())
        if match:
            seen.add(match.group(1).upper())
    for raw in store_entries or []:
        match = LINE_ID_RE.match(str(raw).strip())
        if match:
            seen.add(match.group(1).upper())

    for target in seen:
        if target.startswith("U"):
            counts["directUsers"] += 1
        elif target.startswith("C"):
            counts["groups"] += 1
        elif target.startswith("R"):
            counts["rooms"] += 1
    return counts


def _count_telegram_targets(
    telegram_cfg: dict[str, Any],
    store_entries: list[str] | None = None,
) -> dict[str, int]:
    counts = {"directChats": 0, "groupChats": 0}
    seen: set[str] = set()

    groups = telegram_cfg.get("groups")
    if isinstance(groups, dict):
        for key in groups:
            raw = str(key).strip()
            match = TELEGRAM_CHAT_RE.match(raw)
            if match:
                seen.add(match.group(1))

    for raw in _iter_target_strings(telegram_cfg, target_keys=TELEGRAM_TARGET_KEYS):
        normalized = str(raw).strip()
        match = TELEGRAM_CHAT_RE.match(normalized)
        if match:
            seen.add(match.group(1))
    for raw in store_entries or []:
        normalized = str(raw).strip()
        match = TELEGRAM_CHAT_RE.match(normalized)
        if match:
            seen.add(match.group(1))

    for target in seen:
        if target.startswith("-"):
            counts["groupChats"] += 1
        else:
            counts["directChats"] += 1
    return counts


def _has_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _line_readiness(channels: dict[str, Any], store_entries: list[str]) -> dict[str, Any]:
    line_cfg = channels.get("line")
    if not isinstance(line_cfg, dict):
        return {
            "configured": False,
            "credentialPresence": {"channelAccessToken": False, "channelSecret": False},
            "candidateTargets": {"directUsers": 0, "groups": 0, "rooms": 0},
            "liveRoundtripReady": False,
            "needs": ["configure channels.line"],
        }
    credentials = {
        "channelAccessToken": _has_non_empty_string(line_cfg.get("channelAccessToken")),
        "channelSecret": _has_non_empty_string(line_cfg.get("channelSecret")),
    }
    targets = _count_line_targets(line_cfg, store_entries)
    needs: list[str] = []
    if not all(credentials.values()):
        needs.append("configure LINE channel access token and channel secret")
    if sum(targets.values()) == 0:
        needs.append("receive one LINE message or configure a real userId/groupId/roomId target")
    return {
        "configured": True,
        "credentialPresence": credentials,
        "candidateTargets": targets,
        "liveRoundtripReady": all(credentials.values()) and sum(targets.values()) > 0,
        "needs": needs,
    }


def _telegram_readiness(channels: dict[str, Any], store_entries: list[str]) -> dict[str, Any]:
    telegram_cfg = channels.get("telegram")
    if not isinstance(telegram_cfg, dict):
        return {
            "configured": False,
            "credentialPresence": {"botToken": False},
            "candidateTargets": {"directChats": 0, "groupChats": 0},
            "liveRoundtripReady": False,
            "needs": ["configure channels.telegram"],
        }
    credentials = {"botToken": _has_non_empty_string(telegram_cfg.get("botToken"))}
    targets = _count_telegram_targets(telegram_cfg, store_entries)
    needs: list[str] = []
    if not credentials["botToken"]:
        needs.append("configure Telegram bot token")
    if sum(targets.values()) == 0:
        needs.append("receive one Telegram update or configure a real chat id target")
    return {
        "configured": True,
        "credentialPresence": credentials,
        "candidateTargets": targets,
        "liveRoundtripReady": credentials["botToken"] and sum(targets.values()) > 0,
        "needs": needs,
    }


def build_channel_readiness(config_path: Path, repo_root: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {
            "success": False,
            "config": {
                "present": False,
                "path": _safe_config_path(config_path, repo_root),
            },
            "channels": {},
            "error": "config_not_found",
        }

    try:
        cfg = _read_jsonc(config_path)
    except Exception as exc:  # noqa: BLE001 - diagnostics should report parse class
        return {
            "success": False,
            "config": {
                "present": True,
                "path": _safe_config_path(config_path, repo_root),
            },
            "channels": {},
            "error": "config_parse_failed",
            "detail": type(exc).__name__,
        }

    channels = cfg.get("channels")
    channel_cfg = channels if isinstance(channels, dict) else {}
    credentials_dir = config_path.parent / "credentials"
    session_route_targets = _read_session_route_targets(config_path.parent)
    line = _line_readiness(
        channel_cfg,
        [
            *_read_allow_from_store_entries(credentials_dir, "line"),
            *session_route_targets,
        ],
    )
    telegram = _telegram_readiness(
        channel_cfg,
        [
            *_read_allow_from_store_entries(credentials_dir, "telegram"),
            *session_route_targets,
            *_read_telegram_sent_message_targets(config_path.parent),
        ],
    )
    return {
        "success": True,
        "config": {
            "present": True,
            "path": _safe_config_path(config_path, repo_root),
        },
        "channels": {
            "line": line,
            "telegram": telegram,
        },
        "liveRoundtripReady": {
            "line": bool(line["liveRoundtripReady"]),
            "telegram": bool(telegram["liveRoundtripReady"]),
        },
    }
