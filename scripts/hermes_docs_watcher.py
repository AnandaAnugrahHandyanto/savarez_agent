#!/usr/bin/env python3
"""M6: fetch public Hermes docs + User Stories; hash-only watermark (no auto-refresh).

Silent stdout when unchanged (exit 0). On change, prints a one-screen report.
Cron wiring is intentionally out of scope until operator approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SOURCES: dict[str, str] = {
    "sitemap_xml": "https://hermes-agent.nousresearch.com/docs/sitemap.xml",
    "llms_txt": "https://hermes-agent.nousresearch.com/docs/llms.txt",
    "llms_full_txt": "https://hermes-agent.nousresearch.com/docs/llms-full.txt",
    "user_stories_json": (
        "https://raw.githubusercontent.com/NousResearch/hermes-agent/main/"
        "website/src/data/userStories.json"
    ),
}

DEFAULT_WATERMARK = Path.home() / ".hermes/profiles/auto-coder/docs-watcher-watermark.json"


def _fetch(url: str, timeout: int = 60) -> tuple[bytes, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": "hermes-docs-watcher/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(), None
    except urllib.error.HTTPError as e:
        return b"", f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return b"", str(e.reason)


def _snapshot(sources: dict[str, str], timeout: int) -> dict[str, Any]:
    out: dict[str, Any] = {"captured_at_utc": datetime.now(timezone.utc).isoformat(), "sources": {}}
    for key, url in sources.items():
        body, err = _fetch(url, timeout=timeout)
        if err:
            out["sources"][key] = {"url": url, "error": err, "sha256": None, "bytes": 0}
            continue
        out["sources"][key] = {
            "url": url,
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
            "error": None,
        }
        if key == "user_stories_json" and body:
            try:
                data = json.loads(body.decode("utf-8"))
                if isinstance(data, list):
                    out["sources"][key]["story_count"] = len(data)
            except json.JSONDecodeError:
                out["sources"][key]["story_count"] = None
        if key == "sitemap_xml" and body:
            out["sources"][key]["sitemap_url_count"] = body.decode("utf-8", errors="replace").count("<url>")
    return out


def _fingerprint(snap: dict[str, Any]) -> dict[str, Any]:
    fp: dict[str, Any] = {}
    for key, meta in snap.get("sources", {}).items():
        fp[key] = {
            "sha256": meta.get("sha256"),
            "bytes": meta.get("bytes"),
            "story_count": meta.get("story_count"),
            "sitemap_url_count": meta.get("sitemap_url_count"),
        }
    return fp


def _diff(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key in sorted(set(old) | set(new)):
        o, n = old.get(key), new.get(key)
        if o == n:
            continue
        lines.append(f"- {key}: {o} -> {n}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes docs/User Stories hash watcher (M6)")
    parser.add_argument("--watermark", type=Path, default=DEFAULT_WATERMARK)
    parser.add_argument("--receipt-dir", type=Path, default=None, help="Write sources.json + report on change")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--force-report", action="store_true", help="Print report even if unchanged (debug)")
    args = parser.parse_args()

    snap = _snapshot(DEFAULT_SOURCES, timeout=args.timeout)
    fp = _fingerprint(snap)
    errors = [k for k, v in snap["sources"].items() if v.get("error")]

    prev: dict[str, Any] = {}
    if args.watermark.exists():
        try:
            prev = json.loads(args.watermark.read_text(encoding="utf-8")).get("fingerprint", {})
        except json.JSONDecodeError:
            prev = {}

    changed = fp != prev or bool(errors)
    if not changed and not args.force_report:
        return 0

    lines = [
        "Hermes docs watcher: change detected" if fp != prev else "Hermes docs watcher: fetch errors",
        f"captured_at_utc: {snap['captured_at_utc']}",
    ]
    if errors:
        lines.append(f"errors: {', '.join(errors)}")
    if prev:
        lines.extend(_diff(prev, fp))
    else:
        lines.append("(no prior watermark — baseline stored)")
    lines.append("")
    lines.append("Next: run bounded docs-refresh DWF; do not auto-patch skills.")

    report = "\n".join(lines)
    print(report)

    args.watermark.parent.mkdir(parents=True, exist_ok=True)
    args.watermark.write_text(
        json.dumps({"fingerprint": fp, "last_snap": snap}, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.receipt_dir:
        args.receipt_dir.mkdir(parents=True, exist_ok=True)
        (args.receipt_dir / "sources.json").write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")
        (args.receipt_dir / "report.txt").write_text(report + "\n", encoding="utf-8")

    return 2 if errors and fp == prev else 0


if __name__ == "__main__":
    sys.exit(main())