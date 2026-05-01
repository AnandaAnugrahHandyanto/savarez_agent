#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Import IFIND theme strength/fund data from Excel/CSV into Hermes standard JSON.

Supports:
- .xlsx / .xls via pandas/openpyxl
- .csv via pandas
- loose column naming in Chinese/English

Examples:
  python scripts/import_ifind_theme_table.py \
    --input /path/to/ifind_export.xlsx \
    --sheet 概念资金热度 \
    --output qmt_sync/reports/20260415/ifind_theme_enrichment.json

  python scripts/import_ifind_theme_table.py \
    --input /path/to/ifind_export.csv \
    --output /tmp/ifind_theme_enrichment.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

THEME_ALIASES = [
    "题材", "概念", "概念名称", "题材名称", "板块", "板块名称", "主题", "theme", "name",
]
STRENGTH_ALIASES = [
    "题材强度", "概念强度", "热度", "热度分", "强度分", "theme_strength", "strength_score",
]
MONEY_ALIASES = [
    "题材资金", "概念资金", "主力净流入", "净流入", "净额", "资金强度", "theme_money", "money_score",
]
BREADTH_ALIASES = [
    "题材广度", "概念广度", "上涨家数净值", "breadth", "theme_breadth", "breadth_score",
]
AMOUNT_ALIASES = [
    "成交额", "概念成交额", "题材成交额", "amount", "turnover",
]
AUCTION_AMOUNT_ALIASES = [
    "竞价额", "竞价成交额", "auction_amount",
]
LIMIT_UP_COUNT_ALIASES = [
    "涨停家数", "封板家数", "limit_up_count",
]
HIGHEST_BOARD_ALIASES = [
    "最高板", "连板高度", "highest_board",
]
MEMBER_COUNT_ALIASES = [
    "成分股数", "股票数", "member_count",
]
RISING_COUNT_ALIASES = [
    "上涨家数", "rising_count",
]
FALLING_COUNT_ALIASES = [
    "下跌家数", "falling_count",
]
AVG_PCT_ALIASES = [
    "平均涨幅", "avg_pct", "涨幅均值",
]
AVG_RATIO_ALIASES = [
    "平均承接比", "avg_bid_ask_ratio",
]
LEADER_CODE_ALIASES = [
    "龙头代码", "领涨股代码", "leader_code",
]
LEADER_NAME_ALIASES = [
    "龙头名称", "领涨股", "leader_name",
]

ALL_ALIASES = {
    "theme": THEME_ALIASES,
    "strength_score": STRENGTH_ALIASES,
    "money_score": MONEY_ALIASES,
    "breadth_score": BREADTH_ALIASES,
    "amount": AMOUNT_ALIASES,
    "auction_amount": AUCTION_AMOUNT_ALIASES,
    "limit_up_count": LIMIT_UP_COUNT_ALIASES,
    "highest_board": HIGHEST_BOARD_ALIASES,
    "member_count": MEMBER_COUNT_ALIASES,
    "rising_count": RISING_COUNT_ALIASES,
    "falling_count": FALLING_COUNT_ALIASES,
    "avg_pct": AVG_PCT_ALIASES,
    "avg_bid_ask_ratio": AVG_RATIO_ALIASES,
    "leader_code": LEADER_CODE_ALIASES,
    "leader_name": LEADER_NAME_ALIASES,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _normalize_col(col: Any) -> str:
    return str(col or "").strip().lower().replace(" ", "").replace("_", "")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            text = value.strip().replace(",", "")
            if text.endswith("亿"):
                return float(text[:-1]) * 100000000
            if text.endswith("万"):
                return float(text[:-1]) * 10000
            if text.endswith("%"):
                return float(text[:-1])
            if not text:
                return default
            return float(text)
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(str(value).replace(',', '').replace('%', '')))
    except (TypeError, ValueError):
        return default


def _pick_column(columns: list[str], aliases: list[str]) -> str | None:
    normalized = {_normalize_col(col): col for col in columns}
    for alias in aliases:
        found = normalized.get(_normalize_col(alias))
        if found:
            return found
    return None


def load_table(path: Path, sheet: str | None = None) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet or 0)
    if suffix == ".csv":
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
            try:
                return pd.read_csv(path, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Failed to decode CSV: {path}")
    raise ValueError(f"Unsupported file type: {path.suffix}. Supported: .xlsx .xls .csv")


def normalize_dataframe(df: pd.DataFrame, source: str) -> tuple[dict[str, dict], dict[str, str]]:
    columns = [str(col) for col in df.columns]
    mapping: dict[str, str] = {}
    for target, aliases in ALL_ALIASES.items():
        col = _pick_column(columns, aliases)
        if col:
            mapping[target] = col
    if "theme" not in mapping:
        raise ValueError(f"No theme column found. Available columns: {columns}")

    themes: dict[str, dict] = {}
    for _, row in df.iterrows():
        theme = str(row.get(mapping["theme"], "") or "").strip()
        if not theme:
            continue
        item = {
            "theme": theme,
            "strength_score": round(_safe_float(row.get(mapping.get("strength_score"))), 4),
            "money_score": round(_safe_float(row.get(mapping.get("money_score"))), 4),
            "breadth_score": round(_safe_float(row.get(mapping.get("breadth_score"))), 4),
            "amount": round(_safe_float(row.get(mapping.get("amount"))), 2),
            "auction_amount": round(_safe_float(row.get(mapping.get("auction_amount"))), 2),
            "limit_up_count": _safe_int(row.get(mapping.get("limit_up_count"))),
            "highest_board": _safe_int(row.get(mapping.get("highest_board"))),
            "member_count": _safe_int(row.get(mapping.get("member_count"))),
            "rising_count": _safe_int(row.get(mapping.get("rising_count"))),
            "falling_count": _safe_int(row.get(mapping.get("falling_count"))),
            "avg_pct": round(_safe_float(row.get(mapping.get("avg_pct"))), 4),
            "avg_bid_ask_ratio": round(_safe_float(row.get(mapping.get("avg_bid_ask_ratio"))), 4),
            "leader_code": str(row.get(mapping.get("leader_code"), "") or "").strip(),
            "leader_name": str(row.get(mapping.get("leader_name"), "") or "").strip(),
            "source": source,
        }
        themes[theme] = item
    return themes, mapping


def build_output(themes: dict[str, dict], mapping: dict[str, str], input_path: Path, source: str, sheet: str | None) -> dict:
    return {
        "meta": {
            "source": source,
            "vendor": "同花顺 iFind",
            "generated_at": _now_iso(),
            "market": "A股",
            "input_path": str(input_path),
            "sheet": sheet or "",
            "column_mapping": mapping,
        },
        "themes": themes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sheet")
    parser.add_argument("--source", default="ifind-table")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    df = load_table(input_path, sheet=args.sheet)
    themes, mapping = normalize_dataframe(df, args.source)
    output = build_output(themes, mapping, input_path, args.source, args.sheet)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)
    print(json.dumps({"theme_count": len(themes), "column_mapping": mapping}, ensure_ascii=False))


if __name__ == "__main__":
    main()
