from __future__ import annotations

import json
from pathlib import Path

A_SHARE_COLLECTIONS = [
    {
        "name": "a-review-daily",
        "relative_path": "review-daily",
        "description": "A股短线每日复盘，关注情绪、连板、炸板、次日溢价",
    },
    {
        "name": "a-morning-plan",
        "relative_path": "morning-plan",
        "description": "A股短线盘前计划，关注竞价、龙头、主板、非ST",
    },
    {
        "name": "a-catalysts",
        "relative_path": "catalysts",
        "description": "题材催化、公告与新闻线索",
    },
    {
        "name": "a-risk-notes",
        "relative_path": "risk-notes",
        "description": "失败样本、风险复核、仓位与止损经验",
    },
    {
        "name": "a-cio-memos",
        "relative_path": "cio-memos",
        "description": "CIO 决策备忘与关键取舍",
    },
    {
        "name": "a-playbooks",
        "relative_path": "playbooks",
        "description": "固定战法模板与案例",
    },
]


def build_payload(base_dir: str = "research/a_share_kb") -> dict:
    collections = []
    next_steps = []
    for item in A_SHARE_COLLECTIONS:
        rel = f"{base_dir}/{item['relative_path']}"
        collections.append(
            {
                "name": item["name"],
                "path": rel,
                "add_command": f"qmd collection add {rel} --name {item['name']}",
                "context_command": f"qmd context add qmd://{item['name']} \"{item['description']}\"",
                "description": item["description"],
            }
        )
    next_steps.extend(
        [
            f"mkdir -p {base_dir}/{{review-daily,morning-plan,catalysts,risk-notes,cio-memos,playbooks}}",
            *(c["add_command"] for c in collections),
            *(c["context_command"] for c in collections),
            "qmd embed",
            "qmd status",
        ]
    )
    return {
        "purpose": "A股短线 QMD 知识库 bootstrap",
        "base_dir": base_dir,
        "collections": collections,
        "acceptance": [
            "qmd status 正常",
            "qmd collection list 能看到至少 1 个 A股 collection",
            "qmd search \"竞价\" --limit 3 能返回结果",
        ],
        "next_steps": next_steps,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build A-share qmd bootstrap plan")
    parser.add_argument("--base-dir", default="research/a_share_kb")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = build_payload(base_dir=args.base_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "base_dir": args.base_dir,
                "collection_count": len(payload["collections"]),
                "output": str(output_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
