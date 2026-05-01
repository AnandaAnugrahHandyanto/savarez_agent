#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import a local stock-theme XLSX/CSV into Hermes standard JSON library."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stock_theme_library import (
    infer_industry_signal_themes,
    is_generic_theme,
    normalize_stock_code,
    normalize_theme_text,
    rank_signal_themes,
    select_primary_signal_themes,
)
from cross_theme_mapper import merge_theme_lists


COLUMN_ALIASES = {
    "code": ["股票代码", "证券代码", "代码", "ts_code", "code"],
    "name": ["名称", "股票名称", "证券简称", "name"],
    "industry": ["行业", "行业分类", "申万行业", "所属行业"],
    "region": ["地区", "所属地区", "省份"],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _normalize_col(col: Any) -> str:
    return str(col or "").strip().lower().replace(" ", "")


def _pick_column(columns: list[str], aliases: list[str]) -> str | None:
    mapping = {_normalize_col(col): col for col in columns}
    for alias in aliases:
        found = mapping.get(_normalize_col(alias))
        if found:
            return found
    return None


def _guess_industry_column(df: pd.DataFrame, exclude: set[str]) -> str | None:
    candidates: list[tuple[float, str]] = []
    for col in df.columns:
        col_name = str(col)
        if col_name in exclude:
            continue
        series = df[col].dropna().astype(str).str.strip()
        series = series[series != ""]
        if series.empty:
            continue
        sample = series.head(50)
        hyphen_ratio = float(sample.str.contains(r"[-—/]", regex=True).mean())
        length_ratio = float((sample.str.len() >= 6).mean())
        unnamed_bonus = 0.15 if col_name.lower().startswith("unnamed:") else 0.0
        score = hyphen_ratio * 0.7 + length_ratio * 0.2 + unnamed_bonus
        if score >= 0.55:
            candidates.append((score, col_name))
    candidates.sort(reverse=True)
    return candidates[0][1] if candidates else None


def load_table(path: Path, sheet: str | None = None) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet or 0)
    if path.suffix.lower() == ".csv":
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
            try:
                return pd.read_csv(path, encoding=encoding)
            except UnicodeDecodeError:
                continue
    raise ValueError(f"Unsupported file type: {path}")


def detect_columns(df: pd.DataFrame) -> dict[str, str]:
    columns = [str(col) for col in df.columns]
    picked: dict[str, str] = {}
    for key, aliases in COLUMN_ALIASES.items():
        found = _pick_column(columns, aliases)
        if found:
            picked[key] = found
    if "code" not in picked or "name" not in picked:
        raise ValueError(f"Missing required code/name columns. available={columns}")
    if "industry" not in picked:
        guessed = _guess_industry_column(df, set(picked.values()))
        if guessed:
            picked["industry"] = guessed
    return picked


def collect_theme_columns(df: pd.DataFrame) -> list[str]:
    out = []
    for col in df.columns:
        text = str(col or "").strip()
        if text.startswith("题材") or text.lower().startswith("theme"):
            out.append(str(col))
    if not out:
        raise ValueError("No theme columns found (expected columns like 题材1/题材2/...) ")
    return out


def build_library(df: pd.DataFrame, source_path: Path, sheet: str | None = None, source_name: str = "4月最新") -> dict[str, Any]:
    columns = detect_columns(df)
    theme_columns = collect_theme_columns(df)
    by_code: dict[str, dict[str, Any]] = {}
    theme_counter: Counter[str] = Counter()
    signal_counter: Counter[str] = Counter()
    primary_counter: Counter[str] = Counter()
    generic_counter: Counter[str] = Counter()

    for _, row in df.iterrows():
        code = normalize_stock_code(row.get(columns["code"]))
        name = str(row.get(columns["name"], "") or "").strip()
        if not code or not name:
            continue
        industry = str(row.get(columns.get("industry"), "") or "").strip()
        region = str(row.get(columns.get("region"), "") or "").strip()
        all_themes: list[str] = []
        seen_all: set[str] = set()
        for col in theme_columns:
            raw = normalize_theme_text(row.get(col))
            if not raw or raw in seen_all:
                continue
            seen_all.add(raw)
            all_themes.append(raw)
            theme_counter[raw] += 1
        trade_themes = [theme for theme in all_themes if not is_generic_theme(theme)]
        industry_signal_themes = infer_industry_signal_themes(industry)
        ranked_signal_inputs = merge_theme_lists(industry_signal_themes, trade_themes)
        signal_theme_scores, _ = rank_signal_themes(
            ranked_signal_inputs,
            preferred_themes=industry_signal_themes,
        )
        primary_signal_themes = select_primary_signal_themes(
            signal_theme_scores,
            preferred_themes=industry_signal_themes,
        )
        signal_themes = [item["theme"] for item in signal_theme_scores]
        for theme in signal_themes:
            signal_counter[theme] += 1
        for theme in primary_signal_themes:
            primary_counter[theme] += 1
        for theme in all_themes:
            if theme not in trade_themes:
                generic_counter[theme] += 1
        by_code[code] = {
            "code": code,
            "name": name,
            "industry": industry,
            "region": region,
            "all_themes": all_themes,
            "trade_themes": trade_themes,
            "industry_signal_themes": industry_signal_themes,
            "signal_themes": signal_themes,
            "signal_theme_scores": signal_theme_scores,
            "primary_signal_themes": primary_signal_themes,
        }

    return {
        "meta": {
            "source_name": source_name,
            "source_path": str(source_path),
            "sheet": sheet or "",
            "generated_at": _now_iso(),
            "total_stocks": len(by_code),
            "total_themes": len(theme_counter),
            "top_raw_themes": [{"theme": k, "count": v} for k, v in theme_counter.most_common(30)],
            "top_signal_themes": [{"theme": k, "count": v} for k, v in signal_counter.most_common(30)],
            "top_primary_signal_themes": [{"theme": k, "count": v} for k, v in primary_counter.most_common(20)],
            "top_generic_themes": [{"theme": k, "count": v} for k, v in generic_counter.most_common(20)],
            "theme_columns": theme_columns,
            "column_mapping": columns,
        },
        "by_code": by_code,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sheet", default="题材库")
    parser.add_argument("--source-name", default="4月最新")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()
    df = load_table(input_path, sheet=args.sheet)
    payload = build_library(df, source_path=input_path, sheet=args.sheet, source_name=args.source_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output_path),
        "total_stocks": payload["meta"]["total_stocks"],
        "total_themes": payload["meta"]["total_themes"],
        "top_signal_themes": payload["meta"]["top_signal_themes"][:10],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
