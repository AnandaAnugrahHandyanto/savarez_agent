"""Local Discord interaction route helpers for the API server.

This module is intentionally small and fail-closed. It only builds the
server-side shape needed to receive Discord interaction callbacks safely:
read raw bytes, verify signature headers first, then build a dry-run ACK
preview. It does not register a Discord endpoint, send network messages, or
apply approval decisions.
"""

from __future__ import annotations

import importlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable


def _aiohttp_web() -> Any:
    return importlib.import_module("aiohttp.web")

DISCORD_INTERACTION_ROUTE = "/discord/interactions/soma"
DISCORD_SIGNATURE_HEADER = "X-Signature-Ed25519"
DISCORD_TIMESTAMP_HEADER = "X-Signature-Timestamp"

_ALLOWED_PUBLIC_KEY_ENV_NAMES = {"DISCORD_APPLICATION_PUBLIC_KEY"}
_BLOCKED_PUBLIC_KEY_ENV_MARKERS = (
    "TOKEN",
    "SECRET",
    "WEBHOOK",
    "TELEGRAM",
    "AUTHORIZATION",
    "BEARER",
)
_CUSTOM_ID_RE = re.compile(r"^mim:soma-review:v1:(approve|reject|defer):([A-Za-z0-9][A-Za-z0-9_.:-]{0,127})$")


@dataclass(frozen=True)
class DiscordInteractionConfig:
    """Resolved local route config.

    `enabled=False` is the safe default. A route becomes active only when the
    API server config explicitly enables it and supplies a Discord application
    public key by value or by the allowlisted public-key environment variable.
    """

    enabled: bool = False
    public_key: str = ""
    route_path: str = DISCORD_INTERACTION_ROUTE


def _looks_like_secret_env(name: str) -> bool:
    upper = name.upper()
    return any(marker in upper for marker in _BLOCKED_PUBLIC_KEY_ENV_MARKERS)


def _safe_route_path(value: Any) -> str:
    path = str(value or DISCORD_INTERACTION_ROUTE).strip()
    if not path.startswith("/") or "//" in path or any(ch in path for ch in "\r\n\x00"):
        return DISCORD_INTERACTION_ROUTE
    return path


def resolve_discord_interaction_config(extra: dict[str, Any] | None) -> DiscordInteractionConfig:
    """Resolve the API-server Discord interaction route config.

    The resolver deliberately ignores token/secret/webhook-looking env names.
    Discord interaction verification needs the application public key, not a
    bot token, client secret, webhook URL, or Telegram credential.
    """

    section = (extra or {}).get("discord_interactions") or {}
    if not isinstance(section, dict) or section.get("enabled") is not True:
        return DiscordInteractionConfig()

    public_key = str(section.get("public_key") or "").strip()
    public_key_env = str(section.get("public_key_env") or "").strip()
    if not public_key and public_key_env:
        if public_key_env not in _ALLOWED_PUBLIC_KEY_ENV_NAMES or _looks_like_secret_env(public_key_env):
            return DiscordInteractionConfig(route_path=_safe_route_path(section.get("route") or section.get("route_path")))
        public_key = os.getenv(public_key_env, "").strip()

    route_path = _safe_route_path(section.get("route") or section.get("route_path"))
    if not public_key:
        return DiscordInteractionConfig(route_path=route_path)

    return DiscordInteractionConfig(enabled=True, public_key=public_key, route_path=route_path)


def default_discord_signature_verifier(*, public_key: str, timestamp: str, signature: str, body: bytes) -> bool:
    """Fail-closed verifier placeholder.

    Real Ed25519 verification may be wired later if the active Hermes checkout
    already has a supported dependency or the user approves adding one. Until
    then, production defaults to disabled/fail-closed; tests may inject a
    verifier callable to exercise the route contract without live credentials.
    """

    _ = (public_key, timestamp, signature, body)
    return False


def _error_response(code: str, status: int):
    return _aiohttp_web().json_response({"error": code}, status=status)


def _parse_component(payload: dict[str, Any]) -> tuple[str, str] | None:
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    custom_id = data.get("custom_id")
    if not isinstance(custom_id, str) or len(custom_id) > 180:
        return None
    match = _CUSTOM_ID_RE.match(custom_id)
    if not match:
        return None
    return match.group(1), match.group(2)


def build_discord_ack_preview(payload: dict[str, Any], dry_run_result: Any = None) -> dict[str, Any] | None:
    """Build a Discord interaction ACK preview after signature verification.

    Type 1 is Discord PING and must return PONG (`{"type": 1}`). Type 3 is a
    component interaction; this helper returns an ephemeral dry-run message. It
    never applies approval decisions or writes runtime state.
    """

    if payload.get("type") == 1:
        return {"type": 1}

    if payload.get("type") != 3:
        return None

    parsed = _parse_component(payload)
    if parsed is None:
        return None
    action, review_id = parsed
    result_suffix = ""
    if isinstance(dry_run_result, dict) and dry_run_result.get("status"):
        result_suffix = f" ({dry_run_result['status']})"
    return {
        "type": 4,
        "data": {
            "flags": 64,
            "content": f"MIM dry-run{result_suffix}: {action} / {review_id}",
        },
    }


async def handle_discord_interaction_request(
    request,
    *,
    config: DiscordInteractionConfig,
    verifier: Callable[..., bool] | None = None,
    dry_run_handler: Callable[[dict[str, Any]], Any] | None = None,
):
    """Handle a Discord interaction callback in local/dry-run mode.

    Safety order:
    1. Read raw bytes.
    2. Verify timestamp/signature headers against the raw body.
    3. Only then parse JSON and build ACK previews.
    """

    if not config.enabled or not config.public_key:
        return _error_response("discord_interactions_disabled", 404)

    body = await request.read()
    timestamp = request.headers.get(DISCORD_TIMESTAMP_HEADER, "")
    signature = request.headers.get(DISCORD_SIGNATURE_HEADER, "")
    if not timestamp or not signature:
        return _error_response("missing_signature", 401)

    verify = verifier or default_discord_signature_verifier
    if not verify(public_key=config.public_key, timestamp=timestamp, signature=signature, body=body):
        return _error_response("invalid_signature", 401)

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error_response("invalid_json", 400)
    if not isinstance(payload, dict):
        return _error_response("invalid_payload", 400)

    if payload.get("type") == 3 and _parse_component(payload) is None:
        return _error_response("invalid_component", 400)

    dry_run_result = None
    if payload.get("type") == 3 and dry_run_handler is not None:
        dry_run_result = dry_run_handler(payload)

    ack = build_discord_ack_preview(payload, dry_run_result)
    if ack is None:
        return _error_response("unsupported_interaction", 400)
    return _aiohttp_web().json_response(ack)
