#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def build_payload() -> dict:
    prompts = {
        "pre_market": {
            "schedule": "0 30 8 * * 1-5",
            "goal": "盘前公告与快讯扫描",
            "prompt": "扫描 blogwatcher 未读文章；聚焦A股主板、非ST、短线龙头、次日溢价相关催化；按【公告/监管/媒体快讯/题材催化】分类输出，并标出最值得开盘前跟踪的3-5项。对非RSS关键线索，追加用 duckduckgo-search 做二跳补证。",
        },
        "midday": {
            "schedule": "0 35 11 * * 1-5",
            "goal": "午间增量扫描",
            "prompt": "扫描 blogwatcher 午间新增内容；聚焦A股主板、非ST、龙头分歧转强、监管问询、快讯异动；输出午后值得继续观察的事项。对不清晰线索，用 duckduckgo-search 补证原始来源。",
        },
        "intraday": {
            "schedule": "0 30 14 * * 1-5",
            "goal": "盘中异动扫描",
            "prompt": "扫描 blogwatcher 盘中新内容；聚焦题材催化、公告异动、监管动态、权威媒体快讯；筛出可能影响尾盘博弈与次日溢价预期的增量。必要时用 duckduckgo-search 快速交叉确认。",
        },
        "post_market": {
            "schedule": "0 30 20 * * 1-5",
            "goal": "盘后整理与次日关注点输出",
            "prompt": "整理 blogwatcher 当日未读与新增文章；聚焦A股主板、非ST、龙头、次日溢价相关催化；输出【公告/监管/媒体快讯/题材催化】四栏摘要，并给出次日优先跟踪清单。对模糊或疑似传闻线索，追加用 duckduckgo-search 做补证。",
        },
    }
    return {
        "purpose": "A股短线 blogwatcher + duckduckgo cron 闭环模板",
        "skills": ["blogwatcher-a-share", "duckduckgo-search"],
        "jobs": prompts,
        "notes": [
            "blogwatcher 负责稳定RSS监控",
            "duckduckgo-search 负责非RSS线索补证与二跳确认",
            "最终关键事实仍需回到交易所/公告原文确认",
        ],
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build A-share cron closure templates")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = build_payload()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "job_count": len(payload["jobs"]), "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
