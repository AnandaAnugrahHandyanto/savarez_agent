#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run minimal live IFIND business probes after auth succeeds.

Usage:
  python scripts/ifind_live_smoke.py
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HOOKS_DIR = Path.home() / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.append(str(HOOKS_DIR))
try:
    from runtime_utils import load_runtime_env  # type: ignore
except Exception:
    load_runtime_env = None
if load_runtime_env:
    load_runtime_env()

from ifind_client import IFINDBasicIndicator, IFINDClient, SMART_STOCK_PICKING_TYPE_STOCK


def _day_range() -> tuple[str, str]:
    now = datetime.now()
    today = now.strftime("%Y%m%d")
    week_ago = (now - timedelta(days=7)).strftime("%Y%m%d")
    return week_ago, today


def main() -> None:
    startdate, enddate = _day_range()
    client = IFINDClient()

    out = {
        "probe": client.probe(),
        "ensure_access_token": client.ensure_access_token(),
    }
    if not out["ensure_access_token"].get("success"):
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    basic_indicators: list[IFINDBasicIndicator] = [
        {"indicator": "ths_stock_short_name_stock", "indiparams": []},
    ]
    tasks = {
        "real_time_quotation": lambda: client.real_time_quotation("600519.SH", "latest,open,high,low,preclose"),
        "basic_data_service": lambda: client.basic_data_service("600519.SH", basic_indicators),
        "get_trade_dates": lambda: client.get_trade_dates("SSE", startdate, enddate),
        "get_data_volume": client.get_data_volume,
        "smart_stock_picking": lambda: client.smart_stock_picking("机器人", SMART_STOCK_PICKING_TYPE_STOCK),
    }
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {name: executor.submit(fn) for name, fn in tasks.items()}
        for name, future in futures.items():
            try:
                out[name] = future.result()
            except Exception as exc:
                out[name] = {"success": False, "reason": "smoke_task_failed", "error": str(exc)}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
