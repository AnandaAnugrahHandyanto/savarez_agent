#!/usr/bin/env python3
"""Build A-share short-term watchlist feeds for the blogwatcher optional skill."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_FEEDS = [
    {
        "name": "上交所上市公司公告",
        "url": "https://www.sse.com.cn/disclosure/listedinfo/announcement/rss.xml",
        "category": "exchange-announcement",
    },
    {
        "name": "深交所上市公司公告",
        "url": "https://www.szse.cn/api/report/index/companyGeneralization?random=0.1",
        "category": "exchange-announcement",
        "notes": "深交所缺稳定 RSS，需后续改为定制抓取或替换为可用 feed。",
    },
    {
        "name": "巨潮资讯-公告检索",
        "url": "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
        "category": "announcement-search",
        "notes": "非 RSS，适合后续做 scrapling/parallel-cli 定制抓取。",
    },
    {
        "name": "证券时报-快讯",
        "url": "https://www.stcn.com/rss/rss.xml",
        "category": "market-news",
    },
    {
        "name": "财联社",
        "url": "https://www.cls.cn/rss.xml",
        "category": "market-news",
    },
    {
        "name": "中国证监会-新闻发布",
        "url": "http://www.csrc.gov.cn/csrc/c100027/common_list.shtml",
        "category": "regulation",
        "notes": "非 RSS，优先作为后续监控源候选。",
    },
]


def build_payload() -> dict:
    return {
        "purpose": "A股短线情报监控",
        "feeds": DEFAULT_FEEDS,
        "next_actions": [
            "优先给有稳定 RSS 的源接入 blogwatcher-cli",
            "对非 RSS 页面转为 scrapling / parallel-cli / duckduckgo-search 定制抓取",
            "结合 cronjob 做盘前/盘中/盘后轮询",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Output JSON file path")
    args = parser.parse_args()

    payload = build_payload()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(args.output), "feed_count": len(payload["feeds"])} , ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
