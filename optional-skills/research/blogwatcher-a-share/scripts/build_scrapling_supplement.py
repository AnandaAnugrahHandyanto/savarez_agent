from __future__ import annotations

import json
from pathlib import Path

TARGETS = [
    {
        "name": "szse-announcements",
        "type": "non_rss",
        "source": "https://www.szse.cn/disclosure/listed/notice/index.html",
        "recommended_flow": ["duckduckgo-search", "scrapling"],
        "goal": "抓取深交所上市公司公告页中的最新公告标题、时间与链接",
        "selectors": [
            ".list li",
            ".article-list li",
            "a[href*='disc']",
        ],
    },
    {
        "name": "cninfo-announcements",
        "type": "non_rss",
        "source": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/notice",
        "recommended_flow": ["duckduckgo-search", "scrapling"],
        "goal": "抓取巨潮资讯公告检索结果中的标题、代码、日期与详情链接",
        "selectors": [
            ".announcement-list li",
            ".list-box li",
            "a[title]",
        ],
    },
    {
        "name": "csrc-news",
        "type": "non_rss",
        "source": "http://www.csrc.gov.cn/csrc/c100027/common_list.shtml",
        "recommended_flow": ["duckduckgo-search", "scrapling"],
        "goal": "抓取证监会新闻/发布栏目最近更新，用于监管动态补证",
        "selectors": [
            ".list li",
            ".news-list li",
            "a[href*='csrc']",
        ],
    },
]


def build_payload(output_dir: str = "/tmp/a_share_scrapling") -> dict:
    jobs = []
    for target in TARGETS:
        slug = target["name"]
        output = f"{output_dir}/{slug}.md"
        selector = target["selectors"][0]
        jobs.append(
            {
                "name": slug,
                "source": target["source"],
                "goal": target["goal"],
                "selector_candidates": target["selectors"],
                "recommended_flow": target["recommended_flow"],
                "output": output,
                "scrapling_extract_get": f"scrapling extract get '{target['source']}' {output} --css-selector '{selector}'",
                "scrapling_extract_fetch": f"scrapling extract fetch '{target['source']}' {output} --css-selector '{selector}' --network-idle --disable-resources",
                "verify_steps": [
                    f"test -f {output}",
                    f"grep -E '公告|监管|问询|披露|股份|公司' {output} | head",
                ],
            }
        )
    return {
        "purpose": "A股非RSS信源 Scrapling 补链模板",
        "output_dir": output_dir,
        "jobs": jobs,
        "acceptance": [
            "至少 1 个非RSS页面可成功输出 markdown/text",
            "输出中可见标题/日期/链接等关键字段",
            "补证时仍回到交易所/监管原文确认",
        ],
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build A-share scrapling supplement templates")
    parser.add_argument("--output", required=True)
    parser.add_argument("--output-dir", default="/tmp/a_share_scrapling")
    args = parser.parse_args()

    payload = build_payload(output_dir=args.output_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "job_count": len(payload["jobs"]), "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
