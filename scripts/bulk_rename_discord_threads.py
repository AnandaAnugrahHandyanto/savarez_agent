#!/usr/bin/env python3
"""Bulk-rename accessible Discord threads to short content descriptors.

Uses the configured DISCORD_BOT_TOKEN but never prints it. The script:
- discovers guilds/channels visible to the bot
- collects active + archived public/private threads
- samples recent/oldest thread messages for content
- derives a short descriptor using Hermes' Discord title heuristic
- PATCHes thread names via Discord REST
- records renamed thread IDs in ~/.hermes/discord_auto_renamed_threads.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hermes_cli.env_loader import load_hermes_dotenv  # noqa: E402
from hermes_cli.config import get_hermes_home  # noqa: E402
from gateway.platforms.discord import DiscordAdapter  # noqa: E402

API_BASE = "https://discord.com/api/v10"
THREAD_TYPES = {10, 11, 12}  # news_public_thread, public_thread, private_thread
PARENT_TYPES_WITH_THREADS = {0, 5, 15, 16}  # text, news, forum, media
GENERIC_NAME_PATTERNS = [
    re.compile(r"^new thread$", re.I),
    re.compile(r"^thread$", re.I),
    re.compile(r"^chat$", re.I),
    re.compile(r"^miso chat$", re.I),
    re.compile(r"^hermes chat$", re.I),
    re.compile(r"^help$", re.I),
    re.compile(r"^question$", re.I),
    re.compile(r"^untitled", re.I),
]


@dataclass
class ThreadInfo:
    id: str
    name: str
    parent_id: str | None = None
    guild_id: str | None = None
    parent_name: str | None = None
    category_name: str | None = None
    archived: bool = False


class DiscordREST:
    def __init__(self, token: str, *, verbose: bool = False):
        self.token = token
        self.verbose = verbose
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bot {self.token}",
                "User-Agent": "HermesThreadRenamer/1.0",
                "Content-Type": "application/json",
            }
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def request(self, method: str, path: str, **kwargs) -> Any:
        assert self.session is not None
        url = f"{API_BASE}{path}"
        for attempt in range(6):
            async with self.session.request(method, url, **kwargs) as resp:
                text = await resp.text()
                if resp.status == 429:
                    try:
                        data = json.loads(text)
                        delay = float(data.get("retry_after", 1.0))
                    except Exception:
                        delay = float(resp.headers.get("Retry-After", "1"))
                    await asyncio.sleep(delay + 0.15)
                    continue
                if resp.status in {500, 502, 503, 504} and attempt < 5:
                    await asyncio.sleep(1 + attempt)
                    continue
                if resp.status == 204:
                    return None
                if 200 <= resp.status < 300:
                    return json.loads(text) if text else None
                raise RuntimeError(f"{method} {path} -> HTTP {resp.status}: {text[:500]}")
        raise RuntimeError(f"{method} {path} exhausted retries")

    async def get(self, path: str) -> Any:
        return await self.request("GET", path)

    async def patch(self, path: str, payload: dict[str, Any], reason: str) -> Any:
        headers = {"X-Audit-Log-Reason": reason[:512]}
        return await self.request("PATCH", path, json=payload, headers=headers)


def load_token() -> str:
    load_hermes_dotenv()
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("DISCORD_BOT_TOKEN is not configured in environment/.env")
    return token


def normalize_title(name: str) -> str:
    name = re.sub(r"\s+", " ", name or "").strip()
    name = name[:80].strip(" -_")
    return name or "Hermes Chat"


def is_generic_name(name: str) -> bool:
    stripped = (name or "").strip()
    lower = stripped.lower()
    if any(p.search(stripped) for p in GENERIC_NAME_PATTERNS):
        return True
    if stripped.endswith("...") or len(stripped) >= 70:
        return True
    if re.match(r"^(hey|hi|hello)\s+miso\b", lower):
        return True
    if lower in {"rename all existing threads across", "review last message respond"}:
        return True
    return False


def clean_content(text: str) -> str:
    text = text or ""
    text = re.sub(r"\[CONTEXT COMPACTION[^\]]*\].*", " ", text, flags=re.I | re.S)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"\[[^\]]+\]\s*", " ", text)  # Discord gateway sender prefixes like [Salty]
    text = re.sub(r"\b(CONTEXT|Active Task|Completed Actions|Critical Context)\b.*", " ", text, flags=re.I | re.S)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def title_from_existing_thread_name(thread: ThreadInfo) -> str | None:
    raw = (thread.name or "").strip()
    if not raw:
        return None
    lower = raw.lower()
    if lower == "rename all existing threads across":
        return "Bulk Thread Rename"
    if lower == "review last message respond":
        return "Review Last Message"
    if "agent status channel" in lower:
        return "Agent Status Purpose"
    if "daily briefing channel" in lower:
        return "Daily Briefing Purpose"
    if "decisions channel" in lower:
        return "Decisions Purpose"
    if "gpt 5.5 codex usage" in lower or "codex usage" in lower:
        return "GPT 5.5 Codex Usage"
    if "backup all of the files" in lower and "herm" in lower:
        return "Hermes Backup"
    if "lovable build prompt" in lower:
        return "Lovable Build Skill"
    if "new channel called skills" in lower:
        return "Skills Channel Setup"
    parent = (thread.parent_name or "").strip().replace("-", " ").replace("_", " ")
    if parent and "purpose of this channel" in lower:
        return normalize_title(f"{DiscordAdapter._derive_thread_descriptor(parent)} Purpose")

    # Existing Discord auto-thread titles often contain the original prompt and
    # get truncated with an ellipsis. The prompt is usually better than recent
    # thread tail chatter, so clean it before falling back to messages.
    if raw.endswith("...") or len(raw) >= 70 or re.match(r"^(hey|hi|hello)\b", lower):
        text = raw.replace("…", "...").replace("’", "'").replace("‘", "'")
        text = re.sub(r"\.\.\.$", "", text).strip()
        text = re.sub(r"^(hey|hi|hello)\s+miso[,\s]*", "", text, flags=re.I)
        text = re.sub(r"^(are you able to|can you|could you|please)\s+", "", text, flags=re.I)
        text = re.sub(r"\bwhat('?s| is)\s+the\s+purpose\s+of\s+(the|this)\b", "", text, flags=re.I)
        text = re.sub(r"\bwhat('?s| is)\b", "", text, flags=re.I)
        text = re.sub(r"\bto make it useful\b", "", text, flags=re.I)
        if text:
            return normalize_title(DiscordAdapter._derive_thread_descriptor(text))
    return None


def derive_descriptor(thread: ThreadInfo, messages: list[dict[str, Any]]) -> str:
    from_existing = title_from_existing_thread_name(thread)
    if from_existing:
        return from_existing

    # Prefer human-authored content. If unavailable, fall back to existing name.
    chunks: list[str] = []
    for msg in messages:
        author = msg.get("author") or {}
        if author.get("bot"):
            continue
        content = clean_content(msg.get("content") or "")
        if content:
            chunks.append(content)
    if not chunks:
        for msg in messages:
            content = clean_content(msg.get("content") or "")
            if content:
                chunks.append(content)
    seed = " ".join(chunks[:2]) or thread.name
    title = DiscordAdapter._derive_thread_descriptor(seed)
    return normalize_title(title)


async def paginate_archived(rest: DiscordREST, channel_id: str, kind: str) -> list[dict[str, Any]]:
    # kind: public/private/joined_private
    threads: list[dict[str, Any]] = []
    before: str | None = None
    while True:
        suffix = f"/threads/archived/{kind}?limit=100"
        if before:
            suffix += f"&before={before}"
        data = await rest.get(f"/channels/{channel_id}{suffix}")
        batch = data.get("threads", []) if isinstance(data, dict) else []
        threads.extend(batch)
        has_more = bool(data.get("has_more")) if isinstance(data, dict) else False
        if not has_more or not batch:
            break
        meta = batch[-1].get("thread_metadata") or {}
        before = meta.get("archive_timestamp")
        if not before:
            break
        await asyncio.sleep(0.15)
    return threads


async def collect_threads(rest: DiscordREST) -> tuple[dict[str, ThreadInfo], dict[str, int]]:
    stats = {"guilds": 0, "channels": 0, "active": 0, "archived_public": 0, "archived_private": 0, "archived_joined_private": 0, "collect_errors": 0}
    found: dict[str, ThreadInfo] = {}
    guilds = await rest.get("/users/@me/guilds")
    stats["guilds"] = len(guilds or [])
    for guild in guilds or []:
        guild_id = str(guild.get("id"))
        channel_names: dict[str, str] = {}
        channel_category: dict[str, str] = {}
        parent_channels: list[dict[str, Any]] = []
        try:
            channels = await rest.get(f"/guilds/{guild_id}/channels")
            categories = {str(c.get("id")): c.get("name", "") for c in channels or [] if c.get("type") == 4}
            channel_names = {str(c.get("id")): c.get("name", "") for c in channels or []}
            channel_category = {
                str(c.get("id")): categories.get(str(c.get("parent_id") or ""), "")
                for c in channels or []
            }
            parent_channels = [c for c in channels or [] if c.get("type") in PARENT_TYPES_WITH_THREADS]
            stats["channels"] += len(parent_channels)
        except Exception as exc:
            stats["collect_errors"] += 1
            print(f"WARN channels guild={guild_id}: {exc}")

        try:
            active = await rest.get(f"/guilds/{guild_id}/threads/active")
            for t in active.get("threads", []) if isinstance(active, dict) else []:
                tid = str(t["id"])
                parent_id = str(t.get("parent_id") or "")
                found[tid] = ThreadInfo(
                    tid,
                    t.get("name", ""),
                    parent_id,
                    guild_id,
                    channel_names.get(parent_id),
                    channel_category.get(parent_id),
                    bool((t.get("thread_metadata") or {}).get("archived")),
                )
            stats["active"] += len(active.get("threads", []) if isinstance(active, dict) else [])
        except Exception as exc:
            stats["collect_errors"] += 1
            print(f"WARN active threads guild={guild_id}: {exc}")

        for ch in parent_channels:
            cid = str(ch.get("id"))
            for kind, key in (("public", "archived_public"), ("private", "archived_private"), ("joined-private", "archived_joined_private")):
                try:
                    batch = await paginate_archived(rest, cid, kind)
                    stats[key] += len(batch)
                    for t in batch:
                        tid = str(t["id"])
                        parent_id = str(t.get("parent_id") or cid)
                        found.setdefault(
                            tid,
                            ThreadInfo(
                                tid,
                                t.get("name", ""),
                                parent_id,
                                guild_id,
                                channel_names.get(parent_id),
                                channel_category.get(parent_id),
                                bool((t.get("thread_metadata") or {}).get("archived")),
                            ),
                        )
                except Exception as exc:
                    # Missing permissions for private archives is common. Keep moving.
                    stats["collect_errors"] += 1
                    if "HTTP 403" not in str(exc) and "HTTP 404" not in str(exc):
                        print(f"WARN archived {kind} channel={cid}: {exc}")
                await asyncio.sleep(0.08)
    return found, stats


async def fetch_message_samples(rest: DiscordREST, thread_id: str) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    try:
        recent = await rest.get(f"/channels/{thread_id}/messages?limit=20")
        if isinstance(recent, list):
            samples.extend(reversed(recent))  # oldest-ish among recent first
    except Exception as exc:
        print(f"WARN messages thread={thread_id}: {exc}")
        return samples
    # Try the first messages in the thread by snowflake lower-bound.
    try:
        early = await rest.get(f"/channels/{thread_id}/messages?limit=10&after=0")
        if isinstance(early, list):
            seen = {m.get("id") for m in samples}
            samples = [m for m in reversed(early) if m.get("id") not in seen] + samples
    except Exception:
        pass
    return samples[:30]


async def maybe_unarchive(rest: DiscordREST, thread: ThreadInfo) -> bool:
    if not thread.archived:
        return False
    try:
        await rest.patch(f"/channels/{thread.id}", {"archived": False}, "Hermes bulk thread rename: temporary unarchive")
        await asyncio.sleep(0.25)
        return True
    except Exception as exc:
        print(f"WARN cannot unarchive thread={thread.id}: {exc}")
        return False


async def rename_thread(rest: DiscordREST, thread: ThreadInfo, desired: str, *, dry_run: bool) -> tuple[str, str | None]:
    if dry_run:
        return "dry_run", None
    rearchive = await maybe_unarchive(rest, thread)
    payload = {"name": desired}
    if rearchive:
        payload["archived"] = True
    try:
        await rest.patch(f"/channels/{thread.id}", payload, "Hermes bulk thread descriptor rename")
        return "renamed", None
    except Exception as exc:
        return "failed", str(exc)


def load_renamed_state() -> set[str]:
    path = get_hermes_home() / "discord_auto_renamed_threads.json"
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return {str(x) for x in data}
    except Exception:
        pass
    return set()


def save_renamed_state(ids: set[str]) -> None:
    path = get_hermes_home() / "discord_auto_renamed_threads.json"
    path.write_text(json.dumps(sorted(ids), separators=(",", ":")), encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-already-marked", action="store_true", help="Also rename threads already present in Hermes auto-rename state")
    parser.add_argument("--force", action="store_true", help="Rename even when current title does not look generic/stale")
    parser.add_argument("--limit", type=int, default=0, help="Limit renames for testing")
    args = parser.parse_args()

    token = load_token()
    renamed_state = load_renamed_state()
    started = time.time()
    async with DiscordREST(token) as rest:
        me = await rest.get("/users/@me")
        print(f"Authenticated Discord bot: {me.get('username')}#{me.get('discriminator')} ({me.get('id')})")
        threads, stats = await collect_threads(rest)
        print("Discovery:", json.dumps({**stats, "unique_threads": len(threads)}, sort_keys=True))

        results = {"considered": 0, "skipped_marked": 0, "skipped_same": 0, "skipped_specific": 0, "dry_run": 0, "renamed": 0, "failed": 0}
        failures: list[dict[str, str]] = []
        changes: list[dict[str, str]] = []

        for thread in sorted(threads.values(), key=lambda t: int(t.id)):
            if args.limit and (results["renamed"] + results["dry_run"] >= args.limit):
                break
            results["considered"] += 1
            if not args.include_already_marked and thread.id in renamed_state:
                results["skipped_marked"] += 1
                continue
            messages = await fetch_message_samples(rest, thread.id)
            desired = derive_descriptor(thread, messages)
            if desired == thread.name:
                results["skipped_same"] += 1
                renamed_state.add(thread.id)
                continue
            if not args.force and not is_generic_name(thread.name):
                # Existing name already looks intentional; skip unless force was requested.
                results["skipped_specific"] += 1
                continue
            status, error = await rename_thread(rest, thread, desired, dry_run=args.dry_run)
            results[status] = results.get(status, 0) + 1
            if status in {"renamed", "dry_run"}:
                changes.append({"id": thread.id, "from": thread.name, "to": desired})
                renamed_state.add(thread.id)
                print(f"{status.upper()}: {thread.name!r} -> {desired!r} ({thread.id})")
            else:
                failures.append({"id": thread.id, "name": thread.name, "desired": desired, "error": error or "unknown"})
                print(f"FAILED: {thread.name!r} -> {desired!r} ({thread.id}) :: {error}")
            await asyncio.sleep(0.25)

        if not args.dry_run:
            save_renamed_state(renamed_state)
        out = {
            "elapsed_sec": round(time.time() - started, 2),
            "results": results,
            "changes": changes[-50:],
            "failures": failures[:25],
        }
        print("SUMMARY:", json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
