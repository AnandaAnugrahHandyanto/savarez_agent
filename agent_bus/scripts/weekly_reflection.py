#!/usr/bin/env python3
"""Weekly reflection — consolidate raw learnings into higher-order rules.

Triggered by launchd every Sunday 23:00. Dispatches a task to OpenClaw via
the bus asking it to:
  1. Read the past 7 days of `~/wiki/memory/*_agent-bus_*.md`
  2. Identify repeated patterns (success patterns + failure patterns)
  3. Write consolidated rules to `~/wiki/rules/YYYY-WW.md`
  4. Update `~/wiki/rules/index.md` with the new digest

This turns scattered per-task learnings into rules that both agents load
at startup (see ~/wiki/rules/ — included in the vault's bootstrap layer).
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_bus import core

REFLECTION_MARKER = Path.home() / ".hermes" / "last_reflection_iso_week"


def _iso_week() -> str:
    dt = datetime.now()
    return f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}"


def _already_ran_this_week() -> bool:
    try:
        return REFLECTION_MARKER.read_text(encoding="utf-8").strip() == _iso_week()
    except FileNotFoundError:
        return False


def _mark_ran() -> None:
    REFLECTION_MARKER.parent.mkdir(parents=True, exist_ok=True)
    REFLECTION_MARKER.write_text(_iso_week(), encoding="utf-8")


def main() -> int:
    if _already_ran_this_week():
        print(f"weekly reflection already ran for {_iso_week()}; exit")
        return 0

    week_tag = _iso_week()
    goal = (
        f"每週反省 — 把 ~/wiki/memory/ 過去 7 天的所有 agent-bus learning 收斂成規則。"
        f"輸出到 ~/wiki/rules/{week_tag}.md，格式："
        f"\n---\ntitle: 週反省 {week_tag}\ntype: rule\nupdated: {datetime.now():%Y-%m-%d}\n---"
        f"\n## 成功模式（重複做對的）\n- ...\n## 失敗模式（重複踩坑的）\n- ...\n## 下週注意\n- ..."
        f"\n\n最後 append 一行到 ~/wiki/rules/index.md：`- [[rules/{week_tag}]] — 週反省摘要`。"
    )
    context = (
        "閱讀 ~/wiki/memory/YYYY-MM-DD_agent-bus_T-*.md（最近 7 天）。"
        "用你自己的 daily-self-evolution-review 技能的思路做法分析。"
        "如果 ~/wiki/rules/ 不存在，先建立它。"
        "Rules 檔要短、具體、可行動 — 不要寫超過 20 行。"
    )
    success = f"~/wiki/rules/{week_tag}.md 存在 + rules/index.md 多一行"

    try:
        task = core.assign_task(
            from_agent="hermes",
            to_agent="openclaw",
            goal=goal,
            success_criteria=success,
            context=context,
            priority="P2",
            deadline_minutes=45,
            skip_prior_learnings=True,  # the task IS the retrospective
        )
    except Exception as exc:
        print(f"failed to dispatch reflection: {exc}", file=sys.stderr)
        return 1

    print(f"dispatched weekly reflection task: {task['task_id']} (week {week_tag})")
    _mark_ran()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
