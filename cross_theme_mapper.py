#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical cross-theme helpers for A-share concept merging."""

from __future__ import annotations

from collections import Counter
from typing import Any

CANONICAL_THEME_ALIASES: dict[str, tuple[str, ...]] = {
    "CPO": (
        "cpo",
        "共封装光学(cpo)",
        "光模块",
        "光通信",
        "光芯片",
        "硅光",
        "800g",
        "1.6t",
    ),
    "PCB": (
        "pcb",
        "pcb概念",
        "印制电路板",
        "fpc",
        "覆铜板",
        "高频高速板",
    ),
    "商业航天": (
        "商业航天",
        "卫星互联网",
        "低轨卫星",
        "卫星导航",
        "商业卫星",
        "卫星",
        "航天",
    ),
    "低空经济": (
        "低空经济",
        "evtol",
        "飞行汽车",
        "通用航空",
        "低空飞行",
    ),
    "铜缆高速连接": (
        "铜缆高速连接",
        "铜缆",
        "高速连接",
        "dac",
    ),
    "AI算力": (
        "ai算力",
        "算力",
        "服务器",
        "液冷",
        "液冷服务器",
        "数据中心",
        "东数西算",
        "东数西算(算力)",
        "gpu",
    ),
    "AI应用": (
        "ai应用",
        "ai智能体",
        "deepseek概念",
        "大模型",
        "多模态ai",
        "多模态",
        "aigc应用",
    ),
    "半导体": (
        "半导体",
        "芯片",
        "芯片概念",
        "存储",
        "封测",
        "晶圆",
        "光刻",
        "eda",
        "第三代半导体",
        "先进封装",
    ),
    "消费电子": (
        "消费电子",
        "消费电子概念",
        "苹果概念",
        "mr",
        "vr",
        "折叠屏",
    ),
    "机器人": (
        "机器人",
        "机器人概念",
        "人形机器人",
        "减速器",
        "机器视觉",
        "工业机器人",
    ),
    "固态电池": (
        "固态电池",
        "锂电池概念",
        "钠离子电池",
        "高压快充",
        "充电桩",
        "燃料电池",
    ),
    "新能源汽车": (
        "新能源汽车",
        "新能源车",
        "比亚迪概念",
        "智能驾驶",
        "无人驾驶",
        "汽配",
    ),
    "跨境支付": (
        "跨境支付",
        "跨境支付(cips)",
        "cips",
        "数字货币",
        "人民币跨境",
    ),
    "军工": (
        "军工",
        "军工信息化",
        "大飞机",
        "兵装重组",
    ),
    "有色资源": (
        "有色",
        "有色资源",
        "稀土",
        "钴",
        "锂",
        "小金属",
        "黄金",
        "铜",
        "铝",
    ),
    "医药": (
        "医药",
        "创新药",
        "中药",
        "医疗器械",
        "cro",
        "cxo",
        "减肥药",
    ),
}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def canonicalize_theme_name(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    lowered = text.lower()
    for canonical, aliases in CANONICAL_THEME_ALIASES.items():
        if lowered == canonical.lower():
            return canonical
        for alias in aliases:
            alias_l = alias.lower()
            if lowered == alias_l or alias_l in lowered:
                return canonical
    return text


def parse_theme_tokens(text: Any) -> list[str]:
    raw = _normalize_text(text)
    if not raw:
        return []
    for sep in ("+", "、", "|", "/", ",", "，", ";", "；"):
        raw = raw.replace(sep, "|")
    out: list[str] = []
    seen: set[str] = set()
    for part in raw.split("|"):
        token = canonicalize_theme_name(part)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def merge_theme_lists(*theme_lists: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for theme_list in theme_lists:
        if not theme_list:
            continue
        items = theme_list if isinstance(theme_list, (list, tuple, set)) else [theme_list]
        for item in items:
            for token in parse_theme_tokens(item):
                if token not in seen:
                    seen.add(token)
                    out.append(token)
    if "PCB" in seen and "半导体" in seen:
        out = [item for item in out if item != "半导体"]
    if "CPO" in seen and "AI算力" in seen:
        out = [item for item in out if item != "AI算力"]
    if "商业航天" in seen and "军工" in seen:
        out = [item for item in out if item != "军工"]
    if "低空经济" in seen and "军工" in seen:
        out = [item for item in out if item != "军工"]
    if "AI应用" in seen and "AI算力" in seen:
        out = [item for item in out if item != "AI算力"]
    if "机器人" in seen and "消费电子" in seen and len(out) > 2:
        out = [item for item in out if item != "消费电子"]
    return out


def build_code_theme_map(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for row in rows:
        code = _normalize_text(row.get("ts_code") or row.get("code"))
        tokens = merge_theme_lists(row.get("lu_desc"), row.get("theme"))
        if code and tokens:
            mapping[code] = tokens
    return mapping


def summarize_canonical_hot_themes(rows: list[dict[str, Any]], top_n: int = 10) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    leads: dict[str, str] = {}
    for row in rows:
        lead = _normalize_text(row.get("name") or row.get("lead_stock"))
        for token in merge_theme_lists(row.get("lu_desc"), row.get("theme"), row.get("name")):
            counter[token] += 1
            leads.setdefault(token, lead)
    summary = []
    for theme, hot_count in counter.most_common(top_n):
        summary.append(
            {
                "theme": theme,
                "hot_count": hot_count,
                "lead_stock": leads.get(theme, ""),
            }
        )
    return summary
