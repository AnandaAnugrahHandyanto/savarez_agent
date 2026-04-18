#!/usr/bin/env python3
"""Daily standup — Hermes posts a morning briefing to #hermes-inbox.

Contents:
- Outstanding tasks per agent (who's holding what)
- Tasks completed / failed / timed out in the last 24h
- Repeated failures that deserve user attention
- Count of fresh learnings now searchable in the vault

Posted as the Hermes bot (xoxb) tagging the first user in SLACK_ALLOWED_USERS.
Idempotent per calendar day — won't double-post if re-run same day.
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_bus import core, storage
from agent_bus.core import (
    SLACK_CHANNEL_HERMES_INBOX,
    _home_channel,
    _load_token_from_env_file,
    _user_mention,
)

STANDUP_MARKER = Path.home() / ".hermes" / "last_standup_date"
WINDOW_SECONDS = 24 * 3600


def _already_posted_today() -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        return STANDUP_MARKER.read_text(encoding="utf-8").strip() == today
    except FileNotFoundError:
        return False


def _mark_posted_today() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    STANDUP_MARKER.parent.mkdir(parents=True, exist_ok=True)
    STANDUP_MARKER.write_text(today, encoding="utf-8")


def _fmt_task_line(t: dict, prefix: str = "") -> str:
    tid = t["task_id"]
    goal = (t.get("goal") or "").strip().replace("\n", " ")
    if len(goal) > 70:
        goal = goal[:67] + "…"
    return f"{prefix}`{tid}` {t['from_agent']}→{t['to_agent']}: {goal}"


def build_summary() -> str:
    now = time.time()
    cutoff = now - WINDOW_SECONDS

    hermes_inbox = core.get_outstanding("hermes", limit=20)
    openclaw_inbox = core.get_outstanding("openclaw", limit=20)

    recent = storage.query_tasks(
        status_in=["done", "fail", "timeout"], limit=200
    )
    window = [t for t in recent if (t.get("completed_at") or 0) >= cutoff]
    by_status: dict = {"done": [], "fail": [], "timeout": []}
    for t in window:
        by_status.setdefault(t["status"], []).append(t)

    # Repeat-offender detection: same (to_agent + goal prefix) failing >=2x
    fails = by_status["fail"] + by_status["timeout"]
    fail_keys: dict = {}
    for t in fails:
        key = (t.get("to_agent"), (t.get("goal") or "").strip()[:60])
        fail_keys.setdefault(key, []).append(t)
    repeats = [(k, v) for k, v in fail_keys.items() if len(v) >= 2]

    # Wiki learnings written today
    wiki_mem = Path.home() / "wiki" / "memory"
    today = datetime.now().strftime("%Y-%m-%d")
    learnings_today = list(wiki_mem.glob(f"{today}_agent-bus_*.md")) if wiki_mem.exists() else []

    mention = _user_mention()
    now_hhmm = datetime.now().strftime("%H:%M")

    lines: list = [
        f"☀️ {mention}早安 — 雙 agent 隔夜小結（{datetime.now():%m/%d} {now_hhmm}）",
        "",
    ]

    total_open = len(hermes_inbox) + len(openclaw_inbox)
    done_n = len(by_status["done"])
    fail_n = len(by_status["fail"])
    to_n = len(by_status["timeout"])

    lines.append(
        f"*昨日 24h*：✅ {done_n} · ❌ {fail_n} · ⏰ {to_n} · 📬 目前在手 {total_open}"
    )
    lines.append("")

    if hermes_inbox:
        lines.append(f"*Hermes 待辦 ({len(hermes_inbox)})：*")
        for t in hermes_inbox[:5]:
            lines.append(_fmt_task_line(t, prefix="• "))
        if len(hermes_inbox) > 5:
            lines.append(f"• _(+{len(hermes_inbox) - 5} 更多)_")
        lines.append("")

    if openclaw_inbox:
        lines.append(f"*OpenClaw 待辦 ({len(openclaw_inbox)})：*")
        for t in openclaw_inbox[:5]:
            lines.append(_fmt_task_line(t, prefix="• "))
        if len(openclaw_inbox) > 5:
            lines.append(f"• _(+{len(openclaw_inbox) - 5} 更多)_")
        lines.append("")

    if by_status["done"]:
        lines.append(f"*昨日完成 ({done_n})：*")
        for t in by_status["done"][:5]:
            lines.append(_fmt_task_line(t, prefix="✅ "))
        if done_n > 5:
            lines.append(f"_(+{done_n - 5} 更多)_")
        lines.append("")

    if fail_n or to_n:
        lines.append("*昨日卡關：*")
        for t in by_status["fail"][:3]:
            reason = (t.get("result") or "").strip().replace("\n", " ")[:80]
            lines.append(_fmt_task_line(t, prefix="❌ ") + (f" — {reason}" if reason else ""))
        for t in by_status["timeout"][:3]:
            lines.append(_fmt_task_line(t, prefix="⏰ "))
        lines.append("")

    if repeats:
        lines.append("⚠️ *連續失敗（該升級人工處理）：*")
        for (to_agent, goal_prefix), ts in repeats:
            lines.append(
                f"• `{to_agent}` × `{goal_prefix[:60]}…` — 已失敗 {len(ts)} 次"
            )
        lines.append("")

    lines.append(
        f"🧠 昨日新增 {len(learnings_today)} 條 wiki learning "
        f"— 用 `agent_bus action=wiki_query query=...` 可查"
    )

    return "\n".join(lines)


def post_standup() -> int:
    if _already_posted_today():
        print("standup already posted today; exiting")
        return 0

    token = (
        os.environ.get("SLACK_BOT_TOKEN")
        or _load_token_from_env_file("SLACK_BOT_TOKEN")
    )
    if not token:
        print("no SLACK_BOT_TOKEN available", file=sys.stderr)
        return 2

    text = build_summary()

    from slack_sdk import WebClient
    try:
        WebClient(token=token).chat_postMessage(
            channel=_home_channel(),
            text=text,
            unfurl_links=False,
            unfurl_media=False,
        )
    except Exception as exc:
        print(f"post failed: {exc}", file=sys.stderr)
        return 1

    _mark_posted_today()
    print("standup posted")
    return 0


if __name__ == "__main__":
    raise SystemExit(post_standup())
