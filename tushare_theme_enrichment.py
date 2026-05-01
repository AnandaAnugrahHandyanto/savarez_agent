#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tushare-based theme enrichment for QMT daily reporting.

Focus:
- hot themes / concept universe
- industry money ranking
- derived theme strength ranking
- market money summary
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from typing import Any

import requests

from cross_theme_mapper import build_code_theme_map, summarize_canonical_hot_themes

TUSHARE_TOKEN_ENV = "TUSHARE_TOKEN"
TUSHARE_BASE_URL = "https://api.tushare.pro"


def _post(api_name: str, params: dict[str, Any] | None = None, fields: str = "") -> dict[str, Any]:
    token = os.getenv(TUSHARE_TOKEN_ENV, "").strip()
    if not token:
        return {"success": False, "reason": "missing_tushare_token"}
    payload = {
        "api_name": api_name,
        "token": token,
        "params": params or {},
        "fields": fields,
    }
    try:
        r = requests.post(TUSHARE_BASE_URL, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            return {"success": False, "reason": "api_error", "api_name": api_name, "raw": data}
        return {"success": True, "api_name": api_name, "raw": data}
    except Exception as exc:
        return {"success": False, "reason": "request_failed", "api_name": api_name, "error": str(exc)}


def _rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    raw = result.get("raw") if isinstance(result, dict) else None
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        return []
    fields = data.get("fields") or []
    items = data.get("items") or []
    out = []
    for item in items:
        row = {}
        for idx, field in enumerate(fields):
            row[field] = item[idx] if idx < len(item) else None
        out.append(row)
    return out


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except (TypeError, ValueError):
        return default


def fetch_tushare_theme_enrichment(trade_date: str) -> dict[str, Any]:
    concept = _post("concept")
    ths_index = _post("ths_index")
    moneyflow_ind = _post("moneyflow_ind_ths", {"trade_date": trade_date})
    limit_list = _post("limit_list_ths", {"trade_date": trade_date})
    market_money = _post("moneyflow_mkt_dc", {"trade_date": trade_date})
    top_inst = _post("top_inst", {"trade_date": trade_date})
    moneyflow_stock = _post("moneyflow", {"trade_date": trade_date})

    concept_rows = _rows(concept)
    ths_index_rows = _rows(ths_index)
    money_rows = _rows(moneyflow_ind)
    limit_rows = _rows(limit_list)
    market_rows = _rows(market_money)
    top_inst_rows = _rows(top_inst)
    moneyflow_stock_rows = _rows(moneyflow_stock)

    concept_names = {str(r.get("name") or "").strip() for r in concept_rows if r.get("name")}
    ths_names = {str(r.get("name") or "").strip() for r in ths_index_rows if r.get("name")}

    hot_counter: Counter[str] = Counter()
    hot_leads: dict[str, str] = {}
    for row in limit_rows:
        desc = str(row.get("lu_desc") or "")
        for part in desc.replace("+", "|").replace("、", "|").split("|"):
            name = part.strip()
            if not name:
                continue
            if name in concept_names or name in ths_names or len(name) >= 2:
                hot_counter[name] += 1
                hot_leads.setdefault(name, str(row.get("name") or ""))

    theme_money_rank = []
    theme_strength_rank = []
    for row in money_rows:
        name = str(row.get("industry") or "").strip()
        if not name:
            continue
        net_amount = _safe_float(row.get("net_amount"))
        pct_change = _safe_float(row.get("pct_change"))
        pct_change_stock = _safe_float(row.get("pct_change_stock"))
        company_num = _safe_float(row.get("company_num"))
        strength = pct_change * 2.0 + pct_change_stock * 0.6 + min(company_num / 20.0, 5.0) + max(net_amount, 0.0) / 20.0
        theme_money_rank.append({
            "theme": name,
            "lead_stock": row.get("lead_stock"),
            "net_amount": net_amount,
            "pct_change": pct_change,
            "pct_change_stock": pct_change_stock,
            "company_num": company_num,
        })
        theme_strength_rank.append({
            "theme": name,
            "lead_stock": row.get("lead_stock"),
            "strength_score": round(strength, 2),
            "pct_change": pct_change,
            "pct_change_stock": pct_change_stock,
            "net_amount": net_amount,
            "company_num": company_num,
        })

    theme_money_rank.sort(key=lambda x: x.get("net_amount", 0), reverse=True)
    theme_strength_rank.sort(key=lambda x: x.get("strength_score", 0), reverse=True)

    hot_theme_rank = []
    for name, count in hot_counter.most_common(20):
        hot_theme_rank.append({
            "theme": name,
            "hot_count": count,
            "lead_stock": hot_leads.get(name, ""),
        })

    code_theme_map = build_code_theme_map(limit_rows)
    canonical_hot_theme_rank = summarize_canonical_hot_themes(limit_rows, top_n=20)

    market_summary = market_rows[0] if market_rows else {}
    limit_up_count = len(limit_rows)
    highest_board = max((_safe_int(row.get("open_num")) for row in limit_rows), default=0)
    first_board_count = sum(1 for row in limit_rows if _safe_int(row.get("open_num")) <= 1)
    multi_board_count = sum(1 for row in limit_rows if _safe_int(row.get("open_num")) >= 2)
    strongest_limit_stocks = [
        {
            "ts_code": row.get("ts_code"),
            "name": row.get("name"),
            "tag": row.get("tag"),
            "limit": row.get("limit"),
            "open_num": _safe_int(row.get("open_num")),
            "lu_desc": row.get("lu_desc"),
        }
        for row in sorted(limit_rows, key=lambda x: (_safe_int(x.get("open_num")), _safe_float(x.get("fd_amount"))), reverse=True)[:10]
    ]
    market_sentiment = {
        "limit_up_count": limit_up_count,
        "first_board_count": first_board_count,
        "multi_board_count": multi_board_count,
        "highest_board": highest_board,
        "first_board_ratio": round(first_board_count / limit_up_count, 4) if limit_up_count else 0.0,
        "multi_board_ratio": round(multi_board_count / limit_up_count, 4) if limit_up_count else 0.0,
    }
    lhb_focus = [
        {
            "ts_code": row.get("ts_code"),
            "name": row.get("name"),
            "net_buy": _safe_float(row.get("net_buy")),
            "amount": _safe_float(row.get("amount")),
            "buy": _safe_float(row.get("buy")),
            "sell": _safe_float(row.get("sell")),
        }
        for row in sorted(top_inst_rows, key=lambda x: _safe_float(x.get("net_buy")), reverse=True)[:10]
    ]
    stock_moneyflow_focus = [
        {
            "ts_code": row.get("ts_code"),
            "buy_sm_amount": _safe_float(row.get("buy_sm_amount")),
            "buy_md_amount": _safe_float(row.get("buy_md_amount")),
            "buy_lg_amount": _safe_float(row.get("buy_lg_amount")),
            "buy_elg_amount": _safe_float(row.get("buy_elg_amount")),
            "net_mf_amount": _safe_float(row.get("net_mf_amount")),
        }
        for row in sorted(moneyflow_stock_rows, key=lambda x: _safe_float(x.get("net_mf_amount")), reverse=True)[:10]
    ]
    return {
        "success": True,
        "trade_date": trade_date,
        "concept_count": len(concept_rows),
        "ths_index_count": len(ths_index_rows),
        "theme_money_rank": theme_money_rank[:20],
        "theme_strength_rank": theme_strength_rank[:20],
        "hot_theme_rank": hot_theme_rank[:20],
        "canonical_hot_theme_rank": canonical_hot_theme_rank[:20],
        "code_theme_map": code_theme_map,
        "market_money_summary": market_summary,
        "market_sentiment": market_sentiment,
        "strongest_limit_stocks": strongest_limit_stocks,
        "lhb_focus": lhb_focus,
        "stock_moneyflow_focus": stock_moneyflow_focus,
        "sources": {
            "concept": concept.get("success"),
            "ths_index": ths_index.get("success"),
            "moneyflow_ind_ths": moneyflow_ind.get("success"),
            "limit_list_ths": limit_list.get("success"),
            "moneyflow_mkt_dc": market_money.get("success"),
            "top_inst": top_inst.get("success"),
            "moneyflow": moneyflow_stock.get("success"),
        },
    }


if __name__ == "__main__":
    import sys
    date_arg = sys.argv[1] if len(sys.argv) > 1 else "20260414"
    print(json.dumps(fetch_tushare_theme_enrichment(date_arg), ensure_ascii=False, indent=2))
