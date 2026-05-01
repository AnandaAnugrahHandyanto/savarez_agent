#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local A-share stock-theme library loader built from curated XLSX exports."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from cross_theme_mapper import canonicalize_theme_name, merge_theme_lists

DEFAULT_THEME_LIBRARY_PATH = Path(__file__).resolve().parent / "theme_library" / "a_share_theme_library.json"

_GENERIC_THEME_EXACT = {
    "融资融券",
    "沪股通",
    "深股通",
    "证金持股",
    "同花顺漂亮100",
    "同花顺中特估100",
    "同花顺果指数",
    "高股息精选",
    "沪深300",
    "上证50",
    "中证500",
    "MSCI概念",
    "富时罗素概念股",
    "标普道琼斯A股",
    "ST板块",
    "专精特新",
}
_GENERIC_THEME_CONTAINS = (
    "持股",
    "预增",
    "预亏",
    "预减",
    "龙虎榜",
    "股权激励",
    "股东",
    "转融券",
    "指数",
    "精选",
    "概念股",
)

_THEME_PRIORITY = {
    "CPO": 120,
    "铜缆高速连接": 118,
    "PCB": 115,
    "商业航天": 112,
    "低空经济": 108,
    "AI算力": 104,
    "AI应用": 102,
    "半导体": 98,
    "有色资源": 94,
    "消费电子": 90,
    "机器人": 88,
    "固态电池": 86,
    "新能源汽车": 84,
    "跨境支付": 82,
    "医药": 78,
    "军工": 76,
}
_THEME_PENALTY_CONTAINS = (
    "国企改革",
    "西部大开发",
    "一带一路",
    "华为概念",
    "参股保险",
    "中特估",
)
_INDUSTRY_THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "铜缆高速连接": ("通信线缆", "线缆及配套"),
    "消费电子": ("消费电子", "消费电子零部件", "电子终端"),
    "有色资源": ("小金属", "稀土", "贵金属", "工业金属", "能源金属"),
    "半导体": ("半导体", "集成电路", "电子化学品", "半导体设备", "分立器件"),
    "AI算力": ("算力", "数据中心", "服务器"),
    "跨境支付": ("银行", "金融科技", "支付服务"),
    "医药": ("中药", "化学制药", "生物制品", "医疗器械", "医药商业"),
    "军工": ("航空装备", "航天装备", "地面兵装", "军工电子"),
}
_CANONICAL_THEME_SET = set(_THEME_PRIORITY)
_INDUSTRY_THEME_BOOST = 25
_PRIMARY_SIGNAL_MAX_GAP = 24
_PRIMARY_SIGNAL_MAX_COUNT = 3


def normalize_stock_code(value: Any) -> str:
    if value is None or value != value:
        return ""
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", text):
        return text
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""
    if len(digits) < 6:
        digits = digits.zfill(6)
    if len(digits) != 6:
        return text
    if digits.startswith(("4", "8")):
        return f"{digits}.BJ"
    if digits.startswith(("6", "9")):
        return f"{digits}.SH"
    return f"{digits}.SZ"


def normalize_theme_text(value: Any) -> str:
    if value is None or value != value:
        return ""
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", "", text)
    replacements = {
        "（": "(",
        "）": ")",
        "【": "(",
        "】": ")",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def is_generic_theme(theme: Any) -> bool:
    text = normalize_theme_text(theme)
    if not text:
        return True
    if text in _GENERIC_THEME_EXACT:
        return True
    return any(token in text for token in _GENERIC_THEME_CONTAINS)


def infer_industry_signal_themes(industry: Any) -> list[str]:
    text = normalize_theme_text(industry)
    if not text:
        return []
    hits: list[str] = []
    lowered = text.lower()
    for canonical, keywords in _INDUSTRY_THEME_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            hits.append(canonical)
    return merge_theme_lists(hits)


def score_signal_theme(theme: Any, position: int = 0, preferred_themes: list[Any] | None = None) -> float:
    raw = normalize_theme_text(theme)
    canonical = canonicalize_theme_name(raw)
    score = float(_THEME_PRIORITY.get(canonical, 0))
    if canonical in {canonicalize_theme_name(item) for item in (preferred_themes or []) if normalize_theme_text(item)}:
        score += _INDUSTRY_THEME_BOOST
    if raw != canonical:
        score += 8
    if raw.endswith("概念") and canonical == raw:
        score -= 6
    if any(token in raw for token in _THEME_PENALTY_CONTAINS):
        score -= 24
    score -= position * 0.25
    return round(score, 2)


def rank_signal_themes(themes: list[Any], top_n: int = 6, preferred_themes: list[Any] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    ranked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, theme in enumerate(themes or []):
        raw = normalize_theme_text(theme)
        if not raw:
            continue
        canonical = canonicalize_theme_name(raw)
        if canonical not in _CANONICAL_THEME_SET or canonical in seen:
            continue
        seen.add(canonical)
        ranked.append(
            {
                "theme": canonical,
                "raw_theme": raw,
                "score": score_signal_theme(raw, idx, preferred_themes=preferred_themes),
                "position": idx,
            }
        )
    ranked.sort(key=lambda item: (-float(item["score"]), int(item["position"])))
    primary = [item["theme"] for item in ranked[:top_n]]
    return ranked, primary


def select_primary_signal_themes(
    ranked: list[dict[str, Any]],
    preferred_themes: list[Any] | None = None,
    max_gap: float = _PRIMARY_SIGNAL_MAX_GAP,
    max_count: int = _PRIMARY_SIGNAL_MAX_COUNT,
) -> list[str]:
    if not ranked:
        return []

    preferred = {
        canonicalize_theme_name(item)
        for item in (preferred_themes or [])
        if normalize_theme_text(item)
    }
    top_score = float(ranked[0].get("score", 0) or 0)
    selected: list[str] = []
    for item in ranked:
        theme = canonicalize_theme_name(item.get("theme"))
        if not theme or theme in selected:
            continue
        score = float(item.get("score", 0) or 0)
        if theme in preferred or top_score - score <= max_gap:
            selected.append(theme)
        if len(selected) >= max_count:
            break

    if not selected:
        selected.append(canonicalize_theme_name(ranked[0].get("theme")))
    return [theme for theme in selected if theme]


@lru_cache(maxsize=4)
def _load_theme_library_cached(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.is_file():
        return {
            "meta": {
                "path": str(path),
                "exists": False,
                "total_stocks": 0,
                "total_themes": 0,
            },
            "by_code": {},
        }
    raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    by_code = raw.get("by_code") if isinstance(raw, dict) else {}
    if not isinstance(by_code, dict):
        by_code = {}
    meta = raw.get("meta") if isinstance(raw, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    meta = dict(meta)
    meta.setdefault("path", str(path))
    meta["exists"] = True
    return {
        "meta": meta,
        "by_code": by_code,
    }


def load_stock_theme_library(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path).expanduser() if path else DEFAULT_THEME_LIBRARY_PATH
    return _load_theme_library_cached(str(target))


def get_stock_theme_entry(code: Any, path: str | Path | None = None) -> dict[str, Any]:
    normalized = normalize_stock_code(code)
    if not normalized:
        return {}
    library = load_stock_theme_library(path)
    entry = library.get("by_code", {}).get(normalized, {})
    return dict(entry) if isinstance(entry, dict) else {}


def get_stock_themes(code: Any, path: str | Path | None = None, prefer_signal: bool = True) -> list[str]:
    entry = get_stock_theme_entry(code, path=path)
    if not entry:
        return []
    candidates = []
    if prefer_signal:
        candidates.extend(
            [
                entry.get("primary_signal_themes"),
                [item.get("theme") for item in (entry.get("signal_theme_scores") or []) if isinstance(item, dict)],
                entry.get("signal_themes"),
                entry.get("industry_signal_themes"),
            ]
        )
    else:
        candidates.extend([entry.get("trade_themes"), entry.get("all_themes")])
    for values in candidates:
        if isinstance(values, list) and values:
            return [normalize_theme_text(item) for item in values if normalize_theme_text(item)]
    return []


def summarize_theme_library(codes: list[Any] | None = None, path: str | Path | None = None) -> dict[str, Any]:
    library = load_stock_theme_library(path)
    meta = dict(library.get("meta") or {})
    by_code = library.get("by_code") or {}
    normalized_codes = [normalize_stock_code(code) for code in (codes or []) if normalize_stock_code(code)]
    covered_entries = [by_code.get(code) for code in normalized_codes if code in by_code]
    return {
        "path": meta.get("path", str(DEFAULT_THEME_LIBRARY_PATH)),
        "exists": bool(meta.get("exists")),
        "source_name": meta.get("source_name", ""),
        "source_path": meta.get("source_path", ""),
        "generated_at": meta.get("generated_at", ""),
        "total_stocks": int(meta.get("total_stocks") or len(by_code)),
        "total_themes": int(meta.get("total_themes") or 0),
        "covered_codes": len(covered_entries),
        "requested_codes": len(normalized_codes),
    }
