#!/usr/bin/env python3
"""Capture an X/Twitter URL via bird-smart and materialize it into a GBrain repo.

Writes:
- raw JSON sidecar under .raw/social/x/
- markdown source note under sources/social/x/

This is intentionally filesystem-first so the caller can run `gbrain sync` after the
capture without needing any GBrain Python API.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

BIRD_SMART = "/home/sparta/.local/bin/bird-smart"


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"^-+|-+$", "", value)
    return value or "x-capture"


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _truncate(text: str, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _first_present(obj: Dict[str, Any], keys: Iterable[str], default: Any = "") -> Any:
    for key in keys:
        value = obj.get(key)
        if value not in (None, ""):
            return value
    return default


def _parse_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    for candidate in (value, value.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _extract_author(root: Dict[str, Any]) -> Tuple[str, str]:
    user = root.get("user") or root.get("author") or {}
    handle = _safe_text(
        _first_present(user, ["username", "screen_name", "handle"]) or _first_present(root, ["username", "screen_name", "handle"])
    ).lstrip("@")
    name = _safe_text(_first_present(user, ["name", "displayname", "displayName"]))
    if not handle and name:
        handle = _slugify(name)
    if not name and handle:
        name = handle
    return handle or "unknown", name or handle or "unknown"


def _collect_tweets(payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not payload:
        return []
    tweets = payload.get("tweets")
    if isinstance(tweets, list):
        return [t for t in tweets if isinstance(t, dict)]
    if isinstance(payload, dict) and payload.get("id"):
        return [payload]
    return []


def _summarize_reply(reply: Dict[str, Any]) -> str:
    handle, _name = _extract_author(reply)
    text = _truncate(_safe_text(reply.get("text", "")), 220)
    likes = _first_present(reply, ["likeCount", "favoriteCount"], 0)
    replies = _first_present(reply, ["replyCount"], 0)
    return f"- @{handle}: {text} (likes={likes}, replies={replies})"


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_markdown(url: str, capture: Dict[str, Any], raw_path: Path) -> str:
    root = capture.get("root") or {}
    handle, author_name = _extract_author(root)
    post_id = _safe_text(_first_present(root, ["id", "rest_id", "tweet_id"], "unknown"))
    text = _safe_text(root.get("text", "")).strip()
    title = _truncate(text, 90) or f"X capture {post_id}"
    classification = capture.get("classification") or []
    surfaces = capture.get("fetched_surfaces") or []
    created_at = _safe_text(_first_present(root, ["createdAt", "created_at", "date"], ""))
    stats = {
        "likes": _first_present(root, ["likeCount", "favoriteCount"], 0),
        "reposts": _first_present(root, ["retweetCount", "retweet_count"], 0),
        "replies": _first_present(root, ["replyCount", "reply_count"], 0),
        "quotes": _first_present(root, ["quoteCount", "quote_count"], 0),
    }

    thread_tweets = _collect_tweets(capture.get("thread"))
    reply_tweets = _collect_tweets(capture.get("replies"))

    summary_bits = []
    if text:
        summary_bits.append(_truncate(text, 500))
    if len(thread_tweets) > 1:
        summary_bits.append(f"Thread expansion recovered {len(thread_tweets)} tweets.")
    if reply_tweets:
        summary_bits.append(f"Reply expansion fetched {len(reply_tweets)} replies; only notable ones should be synthesized.")

    notable_replies = sorted(
        reply_tweets,
        key=lambda r: (
            int(_first_present(r, ["likeCount", "favoriteCount"], 0) or 0),
            int(_first_present(r, ["replyCount"], 0) or 0),
        ),
        reverse=True,
    )[:5]

    body = [
        "---",
        f'title: "{title.replace(chr(34), chr(39))}"',
        f'type: source',
        f'created: {datetime.now(timezone.utc).date().isoformat()}',
        f'updated: {datetime.now(timezone.utc).date().isoformat()}',
        f'author_handle: "@{handle}"',
        f'post_id: "{post_id}"',
        f'source_url: "{url}"',
        f'classification: [{", ".join(json.dumps(x) for x in classification)}]',
        f'fetched_surfaces: [{", ".join(json.dumps(x) for x in surfaces)}]',
        f'raw_capture: "{raw_path.as_posix()}"',
        "tags: [social-media, x, source]",
        "---",
        "",
        f"# X capture: @{handle} / {post_id}",
        "",
        "## Summary",
        "",
        " ".join(summary_bits).strip() or "Captured via bird-smart.",
        "",
        "## Source metadata",
        "",
        f"- Author: {author_name} (@{handle})",
        f"- URL: {url}",
        f"- Post ID: {post_id}",
        f"- Created at: {created_at or 'unknown'}",
        f"- Classification: {', '.join(classification) if classification else 'unknown'}",
        f"- Fetched surfaces: {', '.join(surfaces) if surfaces else 'read'}",
        f"- Engagement: likes={stats['likes']}, reposts={stats['reposts']}, replies={stats['replies']}, quotes={stats['quotes']}",
        "",
        "## Root post",
        "",
        text or "(no text returned)",
    ]

    if len(thread_tweets) > 1:
        body.extend([
            "",
            "## Thread expansion",
            "",
            f"Recovered {len(thread_tweets)} tweets in the conversation.",
        ])
        for idx, tweet in enumerate(thread_tweets, start=1):
            tweet_text = _truncate(_safe_text(tweet.get("text", "")), 400)
            tweet_id = _safe_text(_first_present(tweet, ["id", "rest_id", "tweet_id"], ""))
            body.extend(["", f"### Thread item {idx} ({tweet_id})", "", tweet_text or "(no text returned)"])

    if notable_replies:
        body.extend(["", "## Notable replies", "", "Only replies with some measurable engagement are summarized here."])
        body.extend(["", *[_summarize_reply(reply) for reply in notable_replies]])

    body.extend([
        "",
        "## Raw capture",
        "",
        f"- Raw JSON: `{raw_path.as_posix()}`",
        "- After reviewing this source note, update the relevant entity/concept pages and run `gbrain sync --no-pull --no-embed`.",
        "",
    ])
    return "\n".join(body)


def run_capture(url: str, include_replies: str, reply_threshold: int, max_thread_pages: int, timeout: int, json_full: bool) -> Dict[str, Any]:
    cmd = [
        BIRD_SMART,
        url,
        "--include-replies",
        include_replies,
        "--reply-threshold",
        str(reply_threshold),
        "--max-thread-pages",
        str(max_thread_pages),
        "--timeout",
        str(timeout),
    ]
    if json_full:
        cmd.append("--json-full")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture an X URL via bird-smart into a GBrain repo")
    parser.add_argument("--url", required=True, help="X/Twitter status URL or ID")
    parser.add_argument("--brain-repo", required=True, help="Path to the markdown brain repo")
    parser.add_argument("--include-replies", choices=["auto", "yes", "no"], default="auto")
    parser.add_argument("--reply-threshold", type=int, default=3)
    parser.add_argument("--max-thread-pages", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--json-full", action="store_true")
    parser.add_argument("--sync", action="store_true", help="Run gbrain sync --no-pull --no-embed after writing files")
    args = parser.parse_args()

    brain_repo = Path(args.brain_repo).expanduser().resolve()
    capture = run_capture(
        url=args.url,
        include_replies=args.include_replies,
        reply_threshold=args.reply_threshold,
        max_thread_pages=args.max_thread_pages,
        timeout=args.timeout,
        json_full=args.json_full,
    )

    root = capture.get("root") or {}
    handle, _author_name = _extract_author(root)
    post_id = _safe_text(_first_present(root, ["id", "rest_id", "tweet_id"], "unknown"))
    created_at = _parse_dt(_safe_text(_first_present(root, ["createdAt", "created_at", "date"], "")))
    date_prefix = (created_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    slug = f"x-{date_prefix}-{_slugify(handle)}-{_slugify(post_id)}"

    raw_rel = Path(".raw") / "social" / "x" / f"{slug}.json"
    md_rel = Path("sources") / "social" / "x" / f"{slug}.md"
    raw_path = brain_repo / raw_rel
    md_path = brain_repo / md_rel

    _write_json(raw_path, capture)
    markdown = build_markdown(args.url, capture, raw_rel)
    _write_text(md_path, markdown)

    if args.sync:
        subprocess.run(["gbrain", "sync", "--no-pull", "--no-embed"], cwd=str(brain_repo), check=True)

    print(json.dumps({
        "success": True,
        "url": args.url,
        "brain_repo": str(brain_repo),
        "markdown_path": str(md_path),
        "raw_path": str(raw_path),
        "classification": capture.get("classification") or [],
        "fetched_surfaces": capture.get("fetched_surfaces") or [],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
