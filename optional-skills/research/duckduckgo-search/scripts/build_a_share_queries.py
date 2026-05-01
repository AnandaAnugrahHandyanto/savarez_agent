#!/usr/bin/env python3
"""Emit A-share short-term DuckDuckGo query templates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


TEMPLATES = [
    {
        "name": "盘前公告催化",
        "query": 'site:cninfo.com.cn OR site:sse.com.cn OR site:szse.cn 股票 公告 业绩预增 回购 中标 合同',
        "use_case": "盘前快速找公告催化与交易所披露",
    },
    {
        "name": "监管与问询",
        "query": 'site:csrc.gov.cn OR site:sse.com.cn OR site:szse.cn 问询函 监管函 关注函 立案',
        "use_case": "排查监管风险与问询压制",
    },
    {
        "name": "题材催化",
        "query": 'A股 题材 催化 龙头 最新 消息',
        "use_case": "追踪题材扩散与龙头催化",
    },
    {
        "name": "媒体快讯",
        "query": 'site:cls.cn OR site:stcn.com A股 快讯 涨停 龙头',
        "use_case": "补证券时报/财联社类快讯检索",
    },
    {
        "name": "公司传闻补证",
        "query": '{ticker_or_name} A股 公告 最新 消息 证券时报 财联社',
        "use_case": "对单只股票做传闻/异动的二次确认",
    },
]


def build_payload() -> dict:
    return {
        "purpose": "A股短线 DuckDuckGo 检索模板",
        "templates": TEMPLATES,
        "notes": [
            "优先把公司名或股票简称替换进 ticker_or_name 占位符",
            "重要结论需回到交易所/公告原文做最终确认",
            "DuckDuckGo 适合补证，不替代正式公告源",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = build_payload()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(args.output), "template_count": len(payload["templates"])} , ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
