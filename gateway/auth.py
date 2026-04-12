"""Gateway user authorization.

Extracted from `gateway/run.py` so the large `GatewayRunner` class doesn't
own platform allowlist logic. Tests can import `is_user_authorized` directly
without instantiating the full runner.

Rules, in order:
  1. Home Assistant / Webhook sources are always authorized (they have
     their own transport-level auth).
  2. Per-platform `*_ALLOW_ALL_USERS` flag grants universal access.
  3. Pairing store approval grants access.
  4. Per-platform + global allowlists match.
  5. Fallback: global `GATEWAY_ALLOW_ALL_USERS`.
  6. Default: deny.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol, Set


_PLATFORM_ENV_MAP = {
    "telegram": "TELEGRAM_ALLOWED_USERS",
    "discord": "DISCORD_ALLOWED_USERS",
    "whatsapp": "WHATSAPP_ALLOWED_USERS",
    "slack": "SLACK_ALLOWED_USERS",
    "signal": "SIGNAL_ALLOWED_USERS",
    "email": "EMAIL_ALLOWED_USERS",
    "sms": "SMS_ALLOWED_USERS",
    "mattermost": "MATTERMOST_ALLOWED_USERS",
    "matrix": "MATRIX_ALLOWED_USERS",
    "dingtalk": "DINGTALK_ALLOWED_USERS",
    "feishu": "FEISHU_ALLOWED_USERS",
    "wecom": "WECOM_ALLOWED_USERS",
}

_PLATFORM_ALLOW_ALL_MAP = {
    "telegram": "TELEGRAM_ALLOW_ALL_USERS",
    "discord": "DISCORD_ALLOW_ALL_USERS",
    "whatsapp": "WHATSAPP_ALLOW_ALL_USERS",
    "slack": "SLACK_ALLOW_ALL_USERS",
    "signal": "SIGNAL_ALLOW_ALL_USERS",
    "email": "EMAIL_ALLOW_ALL_USERS",
    "sms": "SMS_ALLOW_ALL_USERS",
    "mattermost": "MATTERMOST_ALLOW_ALL_USERS",
    "matrix": "MATRIX_ALLOW_ALL_USERS",
    "dingtalk": "DINGTALK_ALLOW_ALL_USERS",
    "feishu": "FEISHU_ALLOW_ALL_USERS",
    "wecom": "WECOM_ALLOW_ALL_USERS",
}

_TRANSPORT_AUTHED_PLATFORMS = {"homeassistant", "webhook"}


def normalize_whatsapp_identifier(value: str) -> str:
    """Strip WhatsApp JID/LID syntax down to its stable numeric identifier."""
    return (
        str(value or "")
        .strip()
        .replace("+", "", 1)
        .split(":", 1)[0]
        .split("@", 1)[0]
    )


def expand_whatsapp_auth_aliases(identifier: str, hermes_home: Path) -> Set[str]:
    """Resolve WhatsApp phone/LID aliases using bridge session mapping files."""
    normalized = normalize_whatsapp_identifier(identifier)
    if not normalized:
        return set()

    session_dir = hermes_home / "whatsapp" / "session"
    resolved: Set[str] = set()
    queue = [normalized]

    while queue:
        current = queue.pop(0)
        if not current or current in resolved:
            continue

        resolved.add(current)
        for suffix in ("", "_reverse"):
            mapping_path = session_dir / f"lid-mapping-{current}{suffix}.json"
            if not mapping_path.exists():
                continue
            try:
                mapped = normalize_whatsapp_identifier(
                    json.loads(mapping_path.read_text(encoding="utf-8"))
                )
            except Exception:
                continue
            if mapped and mapped not in resolved:
                queue.append(mapped)

    return resolved


class _PairingStoreLike(Protocol):
    def is_approved(self, platform: str, user_id: str) -> bool: ...


def is_user_authorized(
    source: Any,
    pairing_store: _PairingStoreLike,
    hermes_home: Path,
) -> bool:
    """Return True when `source` (a SessionSource) is allowed to use the bot."""
    platform = getattr(source, "platform", None)
    platform_name = platform.value if platform and hasattr(platform, "value") else str(platform or "")
    platform_key = platform_name.lower()

    if platform_key in _TRANSPORT_AUTHED_PLATFORMS:
        return True

    user_id = getattr(source, "user_id", "")
    if not user_id:
        return False

    allow_all_var = _PLATFORM_ALLOW_ALL_MAP.get(platform_key, "")
    if allow_all_var and os.getenv(allow_all_var, "").lower() in ("true", "1", "yes"):
        return True

    if pairing_store.is_approved(platform_name, user_id):
        return True

    platform_allowlist = os.getenv(_PLATFORM_ENV_MAP.get(platform_key, ""), "").strip()
    global_allowlist = os.getenv("GATEWAY_ALLOWED_USERS", "").strip()

    if not platform_allowlist and not global_allowlist:
        return os.getenv("GATEWAY_ALLOW_ALL_USERS", "").lower() in ("true", "1", "yes")

    allowed_ids: Set[str] = set()
    if platform_allowlist:
        allowed_ids.update(uid.strip() for uid in platform_allowlist.split(",") if uid.strip())
    if global_allowlist:
        allowed_ids.update(uid.strip() for uid in global_allowlist.split(",") if uid.strip())

    if "*" in allowed_ids:
        return True

    check_ids = {user_id}
    if "@" in user_id:
        check_ids.add(user_id.split("@")[0])

    if platform_key == "whatsapp":
        normalized_allowed: Set[str] = set()
        for allowed_id in allowed_ids:
            normalized_allowed.update(expand_whatsapp_auth_aliases(allowed_id, hermes_home))
        if normalized_allowed:
            allowed_ids = normalized_allowed

        check_ids.update(expand_whatsapp_auth_aliases(user_id, hermes_home))
        normalized_user_id = normalize_whatsapp_identifier(user_id)
        if normalized_user_id:
            check_ids.add(normalized_user_id)

    return bool(check_ids & allowed_ids)
