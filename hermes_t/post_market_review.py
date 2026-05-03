"""Standalone post-market review for T-trading state snapshots.

Reads execution_state.json, position.json and dispatch_ledger.jsonl from a state
folder and returns a pure computed review payload.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_POSITION_FILENAME = "position.json"
_EXECUTION_STATE_FILENAME = "execution_state.json"
_LEDGER_FILENAME = "dispatch_ledger.jsonl"
TRADE_DATE_REQUIRED = "trade_date is required"


def _coerce_state_dir(state_dir: str | Path) -> Path:
    return Path(state_dir)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return _load_json(path)
    except Exception:
        return None


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _calc_round_trip_pnl(pairs: list[tuple[float, float, int]]) -> float:
    total = 0.0
    for sell_px, buy_px, shares in pairs:
        total += (sell_px - buy_px) * shares
    return total


def _pair_actions(actions: list[dict]) -> tuple[list[tuple[float, float, int]], int, int]:
    pairs: list[tuple[float, float, int]] = []
    open_sells: list[list[float | int]] = []
    unpaired_buy_shares = 0

    for action in actions:
        a_action = str(action.get("action", "") or "").strip().lower()
        shares_remaining = int(action.get("shares", 0) or 0)
        price = float(action.get("price", 0) or 0)

        if shares_remaining <= 0:
            continue

        if a_action == "sell":
            open_sells.append([price, shares_remaining])
            continue

        if a_action != "buy":
            continue

        while shares_remaining > 0 and open_sells:
            sell_price, sell_shares_remaining = open_sells[0]
            matched_shares = min(int(sell_shares_remaining), shares_remaining)
            pairs.append((float(sell_price), price, matched_shares))
            shares_remaining -= matched_shares
            sell_shares_remaining = int(sell_shares_remaining) - matched_shares

            if sell_shares_remaining == 0:
                open_sells.pop(0)
            else:
                open_sells[0][1] = sell_shares_remaining

        if shares_remaining > 0:
            unpaired_buy_shares += shares_remaining

    unpaired_sell_shares = sum(int(item[1]) for item in open_sells)
    return pairs, unpaired_sell_shares, unpaired_buy_shares


def _summarize_month_ledger(state_dir: Path, *, trade_date: str) -> float:
    month_prefix = trade_date[:7]
    total = 0.0
    for row in _read_jsonl(state_dir / _LEDGER_FILENAME):
        row_trade_date = str(row.get("trade_date", "") or "")
        if row_trade_date:
            if month_prefix and not row_trade_date.startswith(month_prefix):
                continue
            if row_trade_date == trade_date:
                continue
        profit = row.get("profit")
        if profit is not None:
            total += float(profit)
    return total


def build_post_market_review(
    state_dir: str | Path,
    *,
    trade_date: str = "",
    symbol: str = "",
) -> dict[str, Any]:
    if not trade_date:
        raise ValueError(TRADE_DATE_REQUIRED)

    state_dir = _coerce_state_dir(state_dir)
    exec_state = _load_optional_json(state_dir / _EXECUTION_STATE_FILENAME) or {}
    actions: list[dict] = list(exec_state.get("actions") or [])
    position = _load_optional_json(state_dir / _POSITION_FILENAME)

    review_symbol = symbol
    if position:
        review_symbol = str(position.get("symbol", review_symbol))

    if position:
        total_shares = int(position.get("total_shares", 0) or 0)
        avg_cost_before = float(position.get("avg_cost", 0.0) or 0.0)
        available_cash = float(position.get("available_cash", 0.0) or 0.0)
        month_start_cost = float(position.get("month_start_cost", avg_cost_before) or avg_cost_before)
        month_target_pct = float(position.get("month_target_reduction_pct", 0.03) or 0.03) * 100.0
    else:
        total_shares = 0
        avg_cost_before = 0.0
        available_cash = 0.0
        month_start_cost = 0.0
        month_target_pct = 3.0

    sell_count = sum(1 for a in actions if str(a.get("action", "") or "").strip().lower() == "sell")
    buy_count = sum(1 for a in actions if str(a.get("action", "") or "").strip().lower() == "buy")
    pairs, unpaired_sell_shares, unpaired_buy_shares = _pair_actions(actions)

    realized_pnl = _calc_round_trip_pnl(pairs)
    net_shares_sold = unpaired_sell_shares - unpaired_buy_shares

    cost_reduction_per_share = 0.0
    avg_cost_after = avg_cost_before
    if total_shares > 0:
        reduction_abs = realized_pnl / total_shares
        cost_reduction_per_share = reduction_abs
        avg_cost_after = avg_cost_before - reduction_abs

    prior_month_pnl = _summarize_month_ledger(state_dir, trade_date=trade_date)
    month_cumulative_pnl = prior_month_pnl + realized_pnl
    month_cumulative_reduction_per_share = 0.0
    if total_shares > 0:
        month_cumulative_reduction_per_share = month_cumulative_pnl / total_shares

    month_target_met = False
    if total_shares > 0 and month_start_cost > 0:
        target_per_share = (month_target_pct / 100.0) * month_start_cost
        month_target_met = month_cumulative_reduction_per_share >= target_per_share

    cash_flow = 0.0
    for a in actions:
        px = float(a.get("price", 0) or 0)
        shares = int(a.get("shares", 0) or 0)
        a_action = str(a.get("action", "") or "").strip().lower()
        if a_action == "sell":
            cash_flow += px * shares
        elif a_action == "buy":
            cash_flow -= px * shares

    trades_out = [
        {
            "seq": int(a.get("seq", 0) or 0),
            "action": str(a.get("action", "") or ""),
            "price": float(a.get("price", 0) or 0),
            "shares": int(a.get("shares", 0) or 0),
            "signal": str(a.get("signal", "") or ""),
            "score": int(a.get("score", 0) or 0),
            "timestamp": str(a.get("timestamp", "") or ""),
        }
        for a in actions
    ]

    return {
        "trade_date": trade_date,
        "symbol": review_symbol,
        "summary": {
            "total_trades": sell_count + buy_count,
            "sell_count": sell_count,
            "buy_count": buy_count,
            "net_shares_sold": net_shares_sold,
            "realized_pnl": realized_pnl,
            "avg_cost_before": round(avg_cost_before, 3),
            "avg_cost_after": round(avg_cost_after, 6),
            "cost_reduction_per_share": round(cost_reduction_per_share, 8),
            "month_cumulative_pnl": round(month_cumulative_pnl, 2),
            "month_cumulative_reduction_per_share": round(month_cumulative_reduction_per_share, 8),
            "month_target_pct": round(month_target_pct, 2),
            "month_target_met": month_target_met,
            "available_cash": round(available_cash + cash_flow, 2),
            "available_cash_change": round(cash_flow, 2),
        },
        "trades": trades_out,
    }
