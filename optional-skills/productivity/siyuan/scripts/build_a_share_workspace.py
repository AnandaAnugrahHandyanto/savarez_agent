#!/usr/bin/env python3
"""Generate SiYuan A-share workspace templates for notes, review, and knowledge handoff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_payload() -> dict:
    notebooks = [
        {
            "name": "A股-日复盘",
            "path": "/A股-日复盘",
            "documents": [
                "盘前计划.md",
                "午间观察.md",
                "盘后复盘.md",
            ],
            "purpose": "记录盘前预案、盘中验证、盘后复盘。",
        },
        {
            "name": "A股-题材库",
            "path": "/A股-题材库",
            "documents": [
                "主线题材.md",
                "龙头股映射.md",
                "催化跟踪.md",
            ],
            "purpose": "沉淀主线/支线题材、龙头、补涨与催化映射。",
        },
        {
            "name": "A股-风险与风控",
            "path": "/A股-风险与风控",
            "documents": [
                "风险信号库.md",
                "炸板案例.md",
                "仓位纪律.md",
            ],
            "purpose": "沉淀风险样本、风控规则与失败案例。",
        },
    ]

    templates = {
        "盘前计划.md": "# 盘前计划\n\n## 关注方向\n- \n\n## 候选标的\n- 标的：\n  - 竞价预期：\n  - 催化：\n  - 风险：\n\n## 放弃项\n- ",
        "午间观察.md": "# 午间观察\n\n## 盘口验证\n- \n\n## 情绪判断\n- \n\n## 午后预案\n- ",
        "盘后复盘.md": "# 盘后复盘\n\n## 今日核心龙头\n- \n\n## 高价值催化\n- \n\n## 失误与修正\n- \n\n## 次日预案\n- ",
        "主线题材.md": "# 主线题材\n\n| 题材 | 强度 | 龙头 | 补涨 | 催化 | 备注 |\n|---|---|---|---|---|---|\n",
        "龙头股映射.md": "# 龙头股映射\n\n| 股票 | 题材 | 地位 | 竞价特征 | 风险点 |\n|---|---|---|---|---|\n",
        "催化跟踪.md": "# 催化跟踪\n\n| 日期 | 类型 | 事件 | 影响题材 | 跟踪动作 |\n|---|---|---|---|---|\n",
        "风险信号库.md": "# 风险信号库\n\n| 信号 | 描述 | 典型后果 | 应对 |\n|---|---|---|---|\n",
        "炸板案例.md": "# 炸板案例\n\n| 日期 | 标的 | 原因 | 盘面特征 | 复盘结论 |\n|---|---|---|---|---|\n",
        "仓位纪律.md": "# 仓位纪律\n\n- 单笔上限：\n- 单日回撤阈值：\n- 风险否决条件：\n",
    }

    return {
        "purpose": "A股短线 SiYuan 知识库模板",
        "notebooks": notebooks,
        "templates": templates,
        "next_steps": [
            "先运行 python ~/.hermes/skills/productivity/siyuan/scripts/check_siyuan.py 确认连接",
            "再按 notebook/path 在 SiYuan 中创建目录或调用 createDocWithMd 导入模板",
            "把日复盘、题材库、风险库拆开，避免混在一个文档里降低检索质量",
        ],
        "acceptance": [
            "至少创建 3 个 notebook/目录分区",
            "至少写入 1 份盘前计划与 1 份盘后复盘模板",
            "能通过 SiYuan 全文检索找到‘竞价’‘龙头’‘风险’等关键词",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an A-share SiYuan workspace template payload")
    parser.add_argument("--output", required=True, help="Path to write JSON output")
    args = parser.parse_args()

    payload = build_payload()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output_path), "notebook_count": len(payload["notebooks"])} , ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
