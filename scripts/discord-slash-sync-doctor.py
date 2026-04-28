#!/usr/bin/env python3
"""Diagnose Discord slash-command sync without mutating Discord.

The gateway sync path is intentionally conservative, but Discord can return
server-filled defaults that make every command look different. This script
rebuilds Hermes' desired command payloads, fetches the currently registered
global commands, and prints the dry-run sync plan plus timing for each phase.

Usage:
  python scripts/discord-slash-sync-doctor.py
  HERMES_HOME=/path/to/.hermes python scripts/discord-slash-sync-doctor.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

API_BASE = "https://discord.com/api/v10"


def _load_token() -> str:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if token:
        return token

    hermes_home = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))
    env_path = hermes_home / ".env"
    if not env_path.exists():
        raise SystemExit("DISCORD_BOT_TOKEN is not set and ~/.hermes/.env was not found")

    for line in env_path.read_text().splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key == "DISCORD_BOT_TOKEN":
            value = value.strip().strip('"').strip("'")
            if value:
                return value
    raise SystemExit("DISCORD_BOT_TOKEN was not found")


def _request_json(token: str, path: str, timeout: float = 30.0) -> tuple[float, Any]:
    request = urllib.request.Request(
        API_BASE + path,
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": "Hermes Discord slash sync doctor",
        },
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise SystemExit(f"Discord API returned HTTP {exc.code} for {path}: {body[:500]}") from exc
    return time.monotonic() - start, payload


def _command_key(payload: dict[str, Any]) -> tuple[int, str]:
    return (int(payload.get("type", 1) or 1), str(payload.get("name", "") or "").lower())


async def main() -> None:
    token = _load_token()

    from gateway.config import PlatformConfig
    from gateway.platforms.discord import DiscordAdapter
    import discord
    from discord.ext import commands

    adapter = DiscordAdapter(PlatformConfig(enabled=True, token=token))
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
    adapter._client = bot

    start = time.monotonic()
    adapter._register_slash_commands()
    register_seconds = time.monotonic() - start
    desired_payloads = [command.to_dict(bot.tree) for command in bot.tree.get_commands()]

    app_seconds, app = _request_json(token, "/oauth2/applications/@me")
    app_id = app.get("id")
    if not app_id:
        raise SystemExit("Could not resolve Discord application id")

    fetch_seconds, existing_payloads = _request_json(token, f"/applications/{app_id}/commands")
    if not isinstance(existing_payloads, list):
        raise SystemExit("Unexpected Discord commands response")

    desired_by_key = {_command_key(payload): payload for payload in desired_payloads}
    existing_by_key = {_command_key(payload): payload for payload in existing_payloads}

    unchanged: list[str] = []
    edit: list[str] = []
    recreate: list[str] = []
    create: list[str] = []

    for key, desired in desired_by_key.items():
        existing = existing_by_key.pop(key, None)
        if existing is None:
            create.append(str(desired.get("name", "")))
            continue

        current_payload = adapter._canonicalize_app_command_payload(existing)
        desired_payload = adapter._canonicalize_app_command_payload(desired)
        current_payload = adapter._normalize_discord_server_defaults(
            current_payload, desired_payload
        )
        if current_payload == desired_payload:
            unchanged.append(str(desired.get("name", "")))
            continue

        if adapter._patchable_app_command_payload(existing) == adapter._patchable_app_command_payload(desired):
            recreate.append(str(desired.get("name", "")))
        else:
            edit.append(str(desired.get("name", "")))

    delete = [str(payload.get("name", "")) for payload in existing_by_key.values()]

    print(json.dumps({
        "application_id": app_id,
        "application_name": app.get("name"),
        "timing_seconds": {
            "build_desired": round(register_seconds, 3),
            "fetch_application": round(app_seconds, 3),
            "fetch_existing_commands": round(fetch_seconds, 3),
        },
        "counts": {
            "desired": len(desired_payloads),
            "existing": len(existing_payloads),
            "unchanged": len(unchanged),
            "edit": len(edit),
            "recreate": len(recreate),
            "create": len(create),
            "delete": len(delete),
        },
        "mutations": {
            "edit": edit,
            "recreate": recreate,
            "create": create,
            "delete": delete,
        },
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
