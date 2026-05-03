"""Post-market review for T-trading: P&L, cost reduction, position tracking.

Reads execution state + position config, computes daily and monthly summary.
No state mutation — pure reader + calculator.
"""

from __future__ import annotations

from typing import Any

from hermes_olin.store import TradingStateStore

# ── helpers ───────────────────────────────────────────────────────────────────

_POSITION_FILENAME = "position.json"


def _load_position(store: TradingStateStore) -> dict | None:
    """Load position.json from store's state directory."""
    pos_path = store.state_dir / _POSITION_FILENAME
    if not pos_path.exists():
        return None
    try:
        return store.load_json(_POSITION_FILENAME)
    except Exception:
        return None


def _calc_round_trip_pnl(pairs: list[tuple[dict, dict]]) -> float:
    """Calculate realized P&L from paired sell→buy sequences.

    Each pair is (sell_action, buy_action).
    P&L per round = (sell_price - buy_price) * shares
    """
    total = 0.0
    for sell, buy in pairs:
        sell_px = float(sell.get("price", 0) or 0)
        buy_px = float(buy.get("price", 0) or 0)
        # Use min shares between sell and buy to cap at round-trip size
        shares = min(
            int(sell.get("shares", 0) or 0),
            int(buy.get("shares", 0) or 0),
        )
        total += (sell_px - buy_px) * shares
    return total


def _pair_actions(actions: list[dict]) -> tuple[list[tuple[dict, dict]], int, int]:
    """Greedy pair sell→buy sequences from an ordered action list.

    Returns (pairs, unpaired_sell_shares, unpaired_buy_shares).
    Only pairs if a sell is followed by a buy (T-short-first pattern).
    """
    sells: list[dict] = []
    buys: list[dict] = []
    for a in actions:
        a_action = str(a.get("action", "") or "").strip().lower()
        if a_action == "sell":
            sells.append(a)
        elif a_action == "buy":
            buys.append(a)

    # Greedy pairing: pair sells[i] with buys[i] in order
    min_len = min(len(sells), len(buys))
    pairs: list[tuple[dict, dict]] = []
    for i in range(min_len):
        pairs.append((sells[i], buys[i]))

    unpaired_sells = sells[min_len:]
    unpaired_buys = buys[min_len:]

    unpaired_sell_shares = sum(int(a.get("shares", 0) or 0) for a in unpaired_sells)
    unpaired_buy_shares = sum(int(a.get("shares", 0) or 0) for a in unpaired_buys)

    return pairs, unpaired_sell_shares, unpaired_buy_shares


def _summarize_month_ledger(store: TradingStateStore, *, trade_date: str) -> float:
    """Read dispatch_ledger.jsonl and sum same-month prior realized P&L only.

    Rows from other months are ignored. Rows with a matching trade_date are also
    skipped to avoid double-counting today's realized P&L, which is already
    computed from today's execution actions. If a row has no trade_date field,
    keep backward compatibility by including it.
    """
    month_prefix = trade_date[:7]
    rows = store.read_jsonl("dispatch_ledger.jsonl")
    total = 0.0
    for row in rows:
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


# ── main entry ───────────────────────────────────────────────────────────────

TRADE_DATE_REQUIRED = "trade_date is required"


def build_post_market_review(
    store: TradingStateStore,
    *,
    trade_date: str = "",
) -> dict[str, Any]:
    """Build a post-market review from store state.

    Args:
        store: TradingStateStore pointing to the profile's state directory.
        trade_date: YYYY-MM-DD trade date (required).

    Returns:
        dict with keys: trade_date, symbol, summary, trades
    """
    if not trade_date:
        raise ValueError(TRADE_DATE_REQUIRED)

    exec_state = store.load_execution_state()
    actions: list[dict] = list(exec_state.get("actions") or [])
    position = _load_position(store)

    # ── symbol ──────────────────────────────────────────────────────────
    symbol = str(store.profile.symbol)
    if position:
        symbol = str(position.get("symbol", symbol))

    # ── position stats ──────────────────────────────────────────────────
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

    # ── tally ───────────────────────────────────────────────────────────
    sell_count = sum(1 for a in actions if str(a.get("action", "") or "").strip().lower() == "sell")
    buy_count = sum(1 for a in actions if str(a.get("action", "") or "").strip().lower() == "buy")

    pairs, unpaired_sell_shares, unpaired_buy_shares = _pair_actions(actions)

    realized_pnl = _calc_round_trip_pnl(pairs)
    net_shares_sold = unpaired_sell_shares - unpaired_buy_shares

    # ── cost reduction ──────────────────────────────────────────────────
    cost_reduction_per_share = 0.0
    avg_cost_after = avg_cost_before
    if total_shares > 0:
        reduction_abs = realized_pnl / total_shares
        cost_reduction_per_share = reduction_abs
        avg_cost_after = avg_cost_before - reduction_abs

    # ── month cumulative ────────────────────────────────────────────────
    prior_month_pnl = _summarize_month_ledger(store, trade_date=trade_date)
    month_cumulative_pnl = prior_month_pnl + realized_pnl
    month_cumulative_reduction_per_share = 0.0
    if total_shares > 0:
        month_cumulative_reduction_abs = month_cumulative_pnl / total_shares
        month_cumulative_reduction_per_share = month_cumulative_reduction_abs
    month_target_met = False
    if total_shares > 0 and month_start_cost > 0:
        target_per_share = (month_target_pct / 100.0) * month_start_cost
        month_target_met = month_cumulative_reduction_per_share >= target_per_share

    # ── available_cash change estimation ────────────────────────────────
    # Net cash flow: sells bring in cash, buys take it out
    cash_flow = 0.0
    for a in actions:
        px = float(a.get("price", 0) or 0)
        shares = int(a.get("shares", 0) or 0)
        a_action = str(a.get("action", "") or "").strip().lower()
        if a_action == "sell":
            cash_flow += px * shares
        elif a_action == "buy":
            cash_flow -= px * shares

    available_cash_after = available_cash + cash_flow

    # ── build output ────────────────────────────────────────────────────
    trades_out = []
    for a in actions:
        trades_out.append({
            "seq": int(a.get("seq", 0) or 0),
            "action": str(a.get("action", "") or ""),
            "price": float(a.get("price", 0) or 0),
            "shares": int(a.get("shares", 0) or 0),
            "signal": str(a.get("signal", "") or ""),
            "score": int(a.get("score", 0) or 0),
            "timestamp": str(a.get("timestamp", "") or ""),
        })

    return {
        "trade_date": trade_date,
        "symbol": symbol,
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
            "available_cash": round(available_cash_after, 2),
            "available_cash_change": round(cash_flow, 2),
        },
        "trades": trades_out,
    }
