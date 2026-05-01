#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IFIND-like theme enrichment loader for QMT ranking.

Design goal:
- If real IFIND/iFind exports are available, consume them directly.
- If not, build a deterministic proxy theme-strength / theme-money layer from
  current QMT payload so downstream ranking can use a stable schema now.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HOOKS_DIR = Path.home() / ".claude" / "hooks"
try:
    import sys
    if str(HOOKS_DIR) not in sys.path:
        sys.path.append(str(HOOKS_DIR))
    from runtime_utils import load_runtime_env  # type: ignore
except Exception:
    load_runtime_env = None
if load_runtime_env:
    load_runtime_env()

from ifind_client import IFINDClient

THEME_ENRICH_ENV = "QMT_THEME_ENRICH_PATH"
DEFAULT_BASENAMES = (
    "ifind_theme_enrichment.json",
    "theme_enrichment.json",
    "ifind_theme_snapshot.json",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_theme(value: Any) -> str:
    text = str(value or "").strip()
    return text or "未知题材"


def _pick_theme(row: dict) -> str:
    for key in ("trade_theme", "theme"):
        if row.get(key):
            return _normalize_theme(row.get(key))
    for key in ("theme_tags", "concept_tags", "cross_theme_tags", "stock_theme_tags", "sector_tags"):
        tags = row.get(key) or []
        if tags:
            first = str(tags[0]).strip()
            if first:
                if first in {"上证A股", "深证A股", "沪深A股", "A股"}:
                    return "泛市场"
                return first
    return "未知题材"


def _candidate_rows(payload: dict) -> list[dict]:
    rows = payload.get("strategy_candidate_pool") or payload.get("candidates") or []
    return [dict(row) for row in rows]


def _limit_rows(payload: dict) -> list[dict]:
    return [dict(row) for row in (payload.get("limit_up_pool") or [])]


def _discover_enrichment_path(payload_path: str | None = None) -> Path | None:
    env = os.getenv(THEME_ENRICH_ENV, "").strip()
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env).expanduser())
    if payload_path:
        source = Path(payload_path).expanduser()
        search_dirs = []
        if source.is_file():
            search_dirs.append(source.parent)
        search_dirs.extend([Path.cwd(), Path.home() / ".hermes"])
        for base in search_dirs:
            for name in DEFAULT_BASENAMES:
                candidates.append(base / name)
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_external_theme_enrichment(payload_path: str | None = None) -> tuple[dict[str, dict], dict[str, Any]]:
    path = _discover_enrichment_path(payload_path)
    if not path:
        return {}, {"source": "none", "path": ""}
    raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    theme_map = raw.get("themes") if isinstance(raw, dict) else None
    if isinstance(theme_map, list):
        items = {}
        for entry in theme_map:
            if not isinstance(entry, dict):
                continue
            theme = _normalize_theme(entry.get("theme") or entry.get("name"))
            items[theme] = dict(entry)
        return items, {"source": "file", "path": str(path)}
    if isinstance(theme_map, dict):
        return ({_normalize_theme(k): dict(v) for k, v in theme_map.items() if isinstance(v, dict)}, {"source": "file", "path": str(path)})
    if isinstance(raw, dict):
        return ({_normalize_theme(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}, {"source": "file", "path": str(path)})
    return {}, {"source": "file", "path": str(path), "invalid": True}


def build_proxy_theme_enrichment(payload: dict) -> dict[str, dict]:
    candidates = _candidate_rows(payload)
    limit_rows = _limit_rows(payload)
    grouped: dict[str, list[dict]] = defaultdict(list)
    limit_grouped: dict[str, list[dict]] = defaultdict(list)

    for row in candidates:
        grouped[_pick_theme(row)].append(row)
    for row in limit_rows:
        limit_grouped[_pick_theme(row)].append(row)

    out: dict[str, dict] = {}
    all_themes = {
        theme for theme in (set(grouped) | set(limit_grouped))
        if theme not in {"未知题材", "泛市场"}
    }
    for theme in sorted(all_themes):
        members = grouped.get(theme, [])
        limit_members = limit_grouped.get(theme, [])
        amount = sum(_safe_float(x.get("amount")) for x in members)
        pct_values = [_safe_float(x.get("pct")) for x in members]
        auction_values = []
        for row in members:
            bid1 = _safe_float(row.get("bid1"))
            ask1 = _safe_float(row.get("ask1"))
            bid1_vol = _safe_float(row.get("bid1_vol"))
            ask1_vol = _safe_float(row.get("ask1_vol"))
            auction_values.append(max(bid1 * bid1_vol + ask1 * ask1_vol, 0.0))
        ratios = [_safe_float(x.get("bid_ask_ratio")) for x in members if x.get("bid_ask_ratio") is not None]
        highest_board = max((int(_safe_float(x.get("board_count"))) for x in members + limit_members), default=0)
        limit_up_count = len(limit_members)
        rising_count = sum(1 for p in pct_values if p > 0)
        falling_count = sum(1 for p in pct_values if p < 0)
        avg_pct = sum(pct_values) / len(pct_values) if pct_values else 0.0
        avg_ratio = sum(ratios) / len(ratios) if ratios else 0.0
        leader = None
        if members:
            leader = max(
                members,
                key=lambda x: (
                    int(_safe_float(x.get("board_count"))),
                    _safe_float(x.get("pct")),
                    _safe_float(x.get("amount")),
                    _safe_float(x.get("open_pct")),
                ),
            )
        strength_score = (
            limit_up_count * 3.0
            + highest_board * 2.0
            + min(amount / 1_000_000_000, 12.0)
            + max(avg_pct, 0.0) / 2.0
            + min(avg_ratio, 3.0)
        )
        money_score = min(amount / 1_000_000_000, 15.0) + min(sum(auction_values) / 100_000_000, 8.0)
        breadth_score = rising_count - falling_count + limit_up_count * 1.5
        out[theme] = {
            "theme": theme,
            "strength_score": round(strength_score, 4),
            "money_score": round(money_score, 4),
            "breadth_score": round(breadth_score, 4),
            "avg_pct": round(avg_pct, 4),
            "avg_bid_ask_ratio": round(avg_ratio, 4),
            "amount": round(amount, 2),
            "auction_amount": round(sum(auction_values), 2),
            "member_count": len(members),
            "limit_up_count": limit_up_count,
            "highest_board": highest_board,
            "rising_count": rising_count,
            "falling_count": falling_count,
            "leader_code": leader.get("code", "") if leader else "",
            "leader_name": leader.get("name", "") if leader else "",
            "source": "proxy",
        }
    return out


def merge_theme_enrichment(payload: dict, payload_path: str | None = None) -> tuple[dict[str, dict], dict[str, Any]]:
    proxy = build_proxy_theme_enrichment(payload)
    external, external_meta = load_external_theme_enrichment(payload_path)
    ifind_probe = IFINDClient().probe()
    merged: dict[str, dict] = {theme: dict(data) for theme, data in proxy.items()}
    external_count = 0
    for theme, ext in external.items():
        base = dict(merged.get(theme, {"theme": theme}))
        base.update(ext)
        base.setdefault("theme", theme)
        base["source"] = ext.get("source", "external")
        merged[theme] = base
        external_count += 1
    meta = {
        "has_external": bool(external_count),
        "external_theme_count": external_count,
        "proxy_theme_count": len(proxy),
        "source": "external+proxy" if external_count else "proxy",
        "env_var": THEME_ENRICH_ENV,
        "external_meta": external_meta,
        "ifind_probe": ifind_probe,
    }
    return merged, meta


def summarize_theme_enrichment(theme_map: dict[str, dict], top_n: int = 5) -> dict[str, list[tuple[str, float]]]:
    def top_by(key: str) -> list[tuple[str, float]]:
        ranked = sorted(
            ((theme, _safe_float(info.get(key))) for theme, info in theme_map.items()),
            key=lambda item: item[1],
            reverse=True,
        )
        return [(theme, round(score, 4)) for theme, score in ranked[:top_n] if theme]

    return {
        "theme_strength": top_by("strength_score"),
        "theme_money": top_by("money_score"),
        "theme_breadth": top_by("breadth_score"),
    }
