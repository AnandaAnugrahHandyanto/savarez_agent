#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build an IFIND-compatible theme enrichment JSON for Hermes.

Usage examples:
  python scripts/build_ifind_theme_enrichment.py \
    --input examples/ifind_theme_source.sample.json \
    --output qmt_sync/reports/20260414/ifind_theme_enrichment.json

  python scripts/build_ifind_theme_enrichment.py \
    --input /path/to/raw_ifind_export.json \
    --source ifind \
    --output /tmp/ifind_theme_enrichment.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SOURCE = "ifind"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def normalize_theme_entry(entry: dict, source: str) -> tuple[str, dict]:
    theme = str(entry.get("theme") or entry.get("name") or "").strip()
    if not theme:
        raise ValueError(f"Theme entry missing theme/name: {entry}")
    normalized = {
        "theme": theme,
        "strength_score": round(_safe_float(entry.get("strength_score", entry.get("theme_strength"))), 4),
        "money_score": round(_safe_float(entry.get("money_score", entry.get("theme_money"))), 4),
        "breadth_score": round(_safe_float(entry.get("breadth_score", entry.get("theme_breadth"))), 4),
        "amount": round(_safe_float(entry.get("amount")), 2),
        "auction_amount": round(_safe_float(entry.get("auction_amount")), 2),
        "limit_up_count": _safe_int(entry.get("limit_up_count")),
        "highest_board": _safe_int(entry.get("highest_board")),
        "member_count": _safe_int(entry.get("member_count")),
        "rising_count": _safe_int(entry.get("rising_count")),
        "falling_count": _safe_int(entry.get("falling_count")),
        "avg_pct": round(_safe_float(entry.get("avg_pct")), 4),
        "avg_bid_ask_ratio": round(_safe_float(entry.get("avg_bid_ask_ratio")), 4),
        "leader_code": str(entry.get("leader_code") or "").strip(),
        "leader_name": str(entry.get("leader_name") or "").strip(),
        "source": str(entry.get("source") or source),
    }
    return theme, normalized


def load_input(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if isinstance(raw, dict) and isinstance(raw.get("themes"), dict):
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("themes"), list):
        return raw
    if isinstance(raw, list):
        return {"themes": raw}
    raise ValueError("Unsupported input format. Expected dict with 'themes' or a list.")


def build_output(raw: dict, source: str) -> dict:
    theme_entries = raw.get("themes", {})
    normalized_themes: dict[str, dict] = {}
    if isinstance(theme_entries, dict):
        iterable = []
        for key, value in theme_entries.items():
            item = dict(value or {})
            item.setdefault("theme", key)
            iterable.append(item)
    elif isinstance(theme_entries, list):
        iterable = [dict(item) for item in theme_entries if isinstance(item, dict)]
    else:
        raise ValueError("Invalid 'themes' payload")

    for entry in iterable:
        theme, normalized = normalize_theme_entry(entry, source)
        normalized_themes[theme] = normalized

    meta = dict(raw.get("meta") or {})
    meta.setdefault("source", source)
    meta.setdefault("generated_at", _now_iso())
    meta.setdefault("market", "A股")
    return {
        "meta": meta,
        "themes": normalized_themes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    payload = build_output(load_input(input_path), args.source)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
