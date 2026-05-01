#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IFIND board/industry enrichment for scored QMT candidates.

Uses authenticated IFIND smart_stock_picking queries to attach:
- 上证/市场范围确认
- 行业/细分行业确认
- 题材关键词板块确认（best-effort)

This is deliberately conservative: if IFIND query fails or no data is found,
we return empty confirmation rather than inventing labels.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

HOOKS_DIR = Path.home() / ".claude" / "hooks"
try:
    import sys
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    from runtime_utils import load_runtime_env  # type: ignore
except Exception:
    load_runtime_env = None
if load_runtime_env:
    load_runtime_env()

from ifind_client import IFINDClient


def _extract_codes(rows: list[dict[str, Any]]) -> set[str]:
    out = set()
    for row in rows:
        code = str(row.get("股票代码") or row.get("thscode") or "").strip()
        if code:
            out.add(code)
    return out


def build_ifind_board_context(scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
    client = IFINDClient()
    probe = client.probe()
    context: dict[str, Any] = {
        "probe": probe,
        "by_code": {},
        "market_scope": [],
        "industry_leads": [],
        "theme_candidates": {},
        "missing_core_candidates": [],
        "theme_leaderboard": {},
        "event_signals": {},
    }
    if not probe.get("can_attempt_network"):
        return context

    scope_result = client.smart_stock_picking("上证板块", "block")
    scope_rows = client.extract_first_table_rows(scope_result, limit=5000)
    scope_codes = _extract_codes(scope_rows)
    context["market_scope"] = scope_rows[:20]

    industry_counter: Counter[str] = Counter()
    missing_core: list[dict[str, Any]] = []

    for row in scored_rows:
        code = str(row.get("code") or "").strip()
        theme = str(row.get("theme") or row.get("semantics", {}).get("trade_theme") or "").strip()
        name = str(row.get("name") or "").strip()
        theme_result = client.smart_stock_picking(theme, "block") if theme else {"success": False, "raw": {}}
        theme_rows = client.extract_first_table_rows(theme_result, limit=200)
        theme_codes = _extract_codes(theme_rows)
        matched = next((r for r in theme_rows if str(r.get("股票代码") or "").strip() == code), None)
        industry_name = ""
        if matched:
            industry_name = str(matched.get("所属同花顺行业") or matched.get("股票市场类型") or "").strip()
            if industry_name:
                industry_counter[industry_name] += 1
        alignment = 0.0
        alignment += 1.5 if code in scope_codes else 0.0
        alignment += 2.0 if matched else 0.0
        alignment += 1.0 if industry_name else 0.0
        context["by_code"][code] = {
            "is_sse_scope": code in scope_codes,
            "theme_query": theme,
            "theme_match": bool(matched),
            "industry_name": industry_name,
            "board_alignment_score": round(alignment, 2),
            "theme_member_count": len(theme_rows),
            "theme_preview": theme_rows[:5],
        }
        if row.get("semantics", {}).get("chain_role") in {"主线龙头候选", "主线前排"} and not matched and theme_rows:
            missing_core.append({
                "code": code,
                "name": name,
                "theme": theme,
                "hint_members": theme_rows[:3],
            })
        if theme and theme not in context["theme_candidates"]:
            context["theme_candidates"][theme] = {
                "success": theme_result.get("success"),
                "errorcode": theme_result.get("errorcode"),
                "errmsg": theme_result.get("errmsg"),
                "rows": theme_rows[:10],
                "member_count": len(theme_rows),
            }
            context["theme_leaderboard"][theme] = [
                {
                    "code": str(r.get("股票代码") or r.get("thscode") or "").strip(),
                    "name": str(r.get("股票简称") or r.get("security_name") or "").strip(),
                    "industry": str(r.get("所属同花顺行业") or r.get("股票市场类型") or "").strip(),
                }
                for r in theme_rows[:5]
            ]
            context["event_signals"][theme] = {
                "report_query_ready": True,
                "report_hint": f"可对 {theme} 或核心股补跑 report_query",
            }

    context["industry_leads"] = [{"industry": name, "count": count} for name, count in industry_counter.most_common(10)]
    context["missing_core_candidates"] = missing_core[:10]
    return context
