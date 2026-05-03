"""Tests for hermes_t.post_market_review — TDD RED phase."""

import json
from pathlib import Path

import pytest

from hermes_olin.profile import RuntimeProfile
from hermes_olin.store import TradingStateStore


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def position_data() -> dict:
    return {
        "symbol": "688319",
        "total_shares": 220000,
        "avg_cost": 16.685,
        "t_shares": 40000,
        "available_cash": 1_000_000.0,
        "month_start_cost": 16.685,
        "month_target_reduction_pct": 0.03,
    }


@pytest.fixture
def t_store(tmp_path: Path, position_data: dict) -> TradingStateStore:
    profile = RuntimeProfile(
        profile_id="olin-688319",
        symbol="688319",
        trade_unit=10000,
        max_trades=4,
    )
    store = TradingStateStore(base_dir=str(tmp_path), profile=profile)
    # write empty execution state
    store.save_execution_state({
        "trade_date": "2026-05-03",
        "sell_count": 0,
        "buy_count": 0,
        "actions": [],
        "active_signal": None,
        "last_signal_id": None,
        "last_signal_action": None,
        "last_signal_status": None,
        "last_signal_at": None,
    })
    # write position file
    pos_path = store.state_dir / "position.json"
    pos_path.write_text(json.dumps(position_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return store


# ── tests ─────────────────────────────────────────────────────────────────────

def test_review_with_no_trades_returns_zero_pnl(t_store: TradingStateStore):
    """RED: when no trades occurred, review shows zero P&L and same avg cost."""
    from hermes_t.post_market_review import build_post_market_review

    review = build_post_market_review(t_store, trade_date="2026-05-03")

    assert review["trade_date"] == "2026-05-03"
    assert review["symbol"] == "688319"
    assert review["summary"]["total_trades"] == 0
    assert review["summary"]["sell_count"] == 0
    assert review["summary"]["buy_count"] == 0
    assert review["summary"]["net_shares_sold"] == 0
    assert review["summary"]["realized_pnl"] == 0.0
    assert review["summary"]["avg_cost_before"] == 16.685
    assert review["summary"]["avg_cost_after"] == 16.685
    assert review["summary"]["cost_reduction_per_share"] == 0.0
    assert review["summary"]["available_cash"] == 1_000_000.0
    assert review["trades"] == []


def test_review_with_single_sell_detects_net_position_change(
    t_store: TradingStateStore,
):
    """RED: a sell-only action reduces position; review must reflect net shares sold."""
    from hermes_t.post_market_review import build_post_market_review

    action = {
        "seq": 1,
        "action": "sell",
        "price": 17.20,
        "shares": 10000,
        "signal": "sell",
        "score": 20,
        "timestamp": "2026-05-03 10:00:00",
    }
    t_store.save_execution_state({
        "trade_date": "2026-05-03",
        "sell_count": 1,
        "buy_count": 0,
        "actions": [action],
        "active_signal": None,
        "last_signal_id": "sig-001",
        "last_signal_action": "sell",
        "last_signal_status": "dispatched",
        "last_signal_at": "2026-05-03 10:00:00",
    })

    review = build_post_market_review(t_store, trade_date="2026-05-03")

    assert review["summary"]["total_trades"] == 1
    assert review["summary"]["sell_count"] == 1
    assert review["summary"]["buy_count"] == 0
    assert review["summary"]["net_shares_sold"] == 10000
    assert len(review["trades"]) == 1
    assert review["trades"][0]["action"] == "sell"
    assert review["trades"][0]["price"] == 17.20


def test_review_with_complete_t_trade_calculates_pnl(
    t_store: TradingStateStore,
):
    """RED: sell at 17.20 then buy back at 16.80 should show 0.40 * 10000 = 4000 P&L."""
    from hermes_t.post_market_review import build_post_market_review

    t_store.save_execution_state({
        "trade_date": "2026-05-03",
        "sell_count": 1,
        "buy_count": 1,
        "actions": [
            {
                "seq": 1,
                "action": "sell",
                "price": 17.20,
                "shares": 10000,
                "signal": "sell",
                "score": 20,
                "timestamp": "2026-05-03 10:00:00",
            },
            {
                "seq": 2,
                "action": "buy",
                "price": 16.80,
                "shares": 10000,
                "signal": "buy",
                "score": -15,
                "timestamp": "2026-05-03 11:00:00",
            },
        ],
        "active_signal": None,
        "last_signal_id": "sig-002",
        "last_signal_action": "buy",
        "last_signal_status": "dispatched",
        "last_signal_at": "2026-05-03 11:00:00",
    })

    review = build_post_market_review(t_store, trade_date="2026-05-03")

    assert review["summary"]["total_trades"] == 2
    assert review["summary"]["sell_count"] == 1
    assert review["summary"]["buy_count"] == 1
    assert review["summary"]["net_shares_sold"] == 0  # 10000 - 10000 = 0
    assert review["summary"]["realized_pnl"] == pytest.approx(4000.0)
    assert review["summary"]["avg_cost_before"] == 16.685
    # cost reduction: 4000 / 220000 = ~0.01818
    expected_reduction = 4000.0 / 220000
    assert review["summary"]["cost_reduction_per_share"] == pytest.approx(expected_reduction, rel=1e-6)
    # avg_cost_after: 16.685 - reduction
    assert review["summary"]["avg_cost_after"] == pytest.approx(16.685 - expected_reduction, rel=1e-6)
    assert len(review["trades"]) == 2


def test_review_with_losing_t_trade_increases_avg_cost(
    t_store: TradingStateStore,
):
    """RED: a losing sell-then-buy round should raise avg_cost_after and show negative per-share reduction."""
    from hermes_t.post_market_review import build_post_market_review

    t_store.save_execution_state({
        "trade_date": "2026-05-03",
        "sell_count": 1,
        "buy_count": 1,
        "actions": [
            {"seq": 1, "action": "sell", "price": 16.80, "shares": 10000, "signal": "sell", "score": 20, "timestamp": "2026-05-03 10:00:00"},
            {"seq": 2, "action": "buy", "price": 17.20, "shares": 10000, "signal": "buy", "score": -15, "timestamp": "2026-05-03 11:00:00"},
        ],
        "active_signal": None,
        "last_signal_id": "sig-loss-001",
    })

    review = build_post_market_review(t_store, trade_date="2026-05-03")

    expected_reduction = -4000.0 / 220000
    assert review["summary"]["realized_pnl"] == pytest.approx(-4000.0)
    assert review["summary"]["cost_reduction_per_share"] == pytest.approx(expected_reduction, rel=1e-6)
    assert review["summary"]["avg_cost_after"] == pytest.approx(16.685 - expected_reduction, rel=1e-6)
    assert review["summary"]["month_cumulative_pnl"] == pytest.approx(-4000.0)
    assert review["summary"]["month_cumulative_reduction_per_share"] == pytest.approx(expected_reduction, rel=1e-6)


def test_review_with_multiple_t_trades_accumulates_pnl(
    t_store: TradingStateStore,
):
    """RED: two complete T-rounds accumulate P&L correctly."""
    from hermes_t.post_market_review import build_post_market_review

    t_store.save_execution_state({
        "trade_date": "2026-05-03",
        "sell_count": 2,
        "buy_count": 2,
        "actions": [
            {"seq": 1, "action": "sell", "price": 17.20, "shares": 10000, "signal": "sell", "score": 20, "timestamp": "2026-05-03 10:00:00"},
            {"seq": 2, "action": "buy", "price": 16.80, "shares": 10000, "signal": "buy", "score": -15, "timestamp": "2026-05-03 11:00:00"},
            {"seq": 3, "action": "sell", "price": 17.50, "shares": 10000, "signal": "sell", "score": 25, "timestamp": "2026-05-03 13:00:00"},
            {"seq": 4, "action": "buy", "price": 16.90, "shares": 10000, "signal": "buy", "score": -10, "timestamp": "2026-05-03 14:00:00"},
        ],
        "active_signal": None,
        "last_signal_id": "sig-004",
    })

    review = build_post_market_review(t_store, trade_date="2026-05-03")

    # First round: (17.20 - 16.80) * 10000 = 4000
    # Second round: (17.50 - 16.90) * 10000 = 6000
    # Total: 10000
    assert review["summary"]["realized_pnl"] == pytest.approx(10000.0)
    assert review["summary"]["total_trades"] == 4
    assert review["summary"]["sell_count"] == 2
    assert review["summary"]["buy_count"] == 2
    assert review["summary"]["net_shares_sold"] == 0
    assert len(review["trades"]) == 4


def test_review_with_unpaired_buy_sell_treats_as_net_position_change(
    t_store: TradingStateStore,
):
    """RED: when sell > buy, the difference is a net position decrease (no P&L for unmatched)."""
    from hermes_t.post_market_review import build_post_market_review

    t_store.save_execution_state({
        "trade_date": "2026-05-03",
        "sell_count": 2,
        "buy_count": 1,
        "actions": [
            {"seq": 1, "action": "sell", "price": 17.20, "shares": 10000, "signal": "sell", "score": 20, "timestamp": "2026-05-03 10:00:00"},
            {"seq": 2, "action": "sell", "price": 17.50, "shares": 10000, "signal": "sell", "score": 25, "timestamp": "2026-05-03 11:00:00"},
            {"seq": 3, "action": "buy", "price": 16.80, "shares": 10000, "signal": "buy", "score": -15, "timestamp": "2026-05-03 14:00:00"},
        ],
        "active_signal": None,
        "last_signal_id": "sig-005",
    })

    review = build_post_market_review(t_store, trade_date="2026-05-03")
    # Pair: first sell+first buy = 10000 round, P&L = (17.20-16.80)*10000 = 4000
    # Net: 10000 shares sold extra
    assert review["summary"]["realized_pnl"] == pytest.approx(4000.0)
    assert review["summary"]["net_shares_sold"] == 10000


def test_review_infers_symbol_from_store_if_position_missing(
    tmp_path: Path, t_store: TradingStateStore,
):
    """RED: when position.json is missing, use store.profile.symbol as fallback."""
    from hermes_t.post_market_review import build_post_market_review

    # remove position file
    pos_path = t_store.state_dir / "position.json"
    if pos_path.exists():
        pos_path.unlink()

    review = build_post_market_review(t_store, trade_date="2026-05-03")

    assert review["symbol"] == "688319"
    assert review["summary"]["realized_pnl"] == 0.0
    # Without position, avg_cost_before defaults to 0.0
    assert review["summary"]["avg_cost_before"] == 0.0


def test_review_rejects_missing_trade_date(t_store: TradingStateStore):
    """RED: trade_date is required."""
    from hermes_t.post_market_review import build_post_market_review

    with pytest.raises(ValueError, match="trade_date"):
        build_post_market_review(t_store, trade_date="")


def test_review_month_cumulative_accumulation(
    t_store: TradingStateStore,
):
    """RED: tracks this month's cumulative cost reduction by reading from store."""
    from hermes_t.post_market_review import build_post_market_review

    # simulate a prior day's dispatch record in ledger
    t_store.record_dispatch_event("sent", {
        "signal_id": "sig-prev",
        "trade_date": "2026-05-02",
        "action": "sell",
        "sequence": 1,
        "profit": 2000.0,
    })

    # today's trades: P&L 4000
    t_store.save_execution_state({
        "trade_date": "2026-05-03",
        "sell_count": 1,
        "buy_count": 1,
        "actions": [
            {"seq": 1, "action": "sell", "price": 17.20, "shares": 10000, "signal": "sell", "score": 20, "timestamp": "2026-05-03 10:00:00"},
            {"seq": 2, "action": "buy", "price": 16.80, "shares": 10000, "signal": "buy", "score": -15, "timestamp": "2026-05-03 11:00:00"},
        ],
        "active_signal": None,
        "last_signal_id": "sig-003",
    })

    review = build_post_market_review(t_store, trade_date="2026-05-03")
    # Total month P&L from ledger: 2000
    # Today's P&L: 4000
    # Month cumulative: 6000
    assert review["summary"]["month_cumulative_pnl"] == pytest.approx(6000.0)
    # 3% monthly target means 16.685 * 3% = 0.50055 元/股; 6000/220000=0.02727, not met.
    assert review["summary"]["month_target_met"] is False


def test_review_dispatch_ledger_missing_does_not_crash(
    t_store: TradingStateStore,
):
    """RED: when dispatch_ledger.jsonl doesn't exist, month cumulative is just today's P&L."""
    from hermes_t.post_market_review import build_post_market_review

    # write ledger as a non-existent / empty scenario
    ledger_path = t_store.state_dir / "dispatch_ledger.jsonl"
    if ledger_path.exists():
        ledger_path.unlink()

    t_store.save_execution_state({
        "trade_date": "2026-05-03",
        "sell_count": 2,
        "buy_count": 2,
        "actions": [
            {"seq": 1, "action": "sell", "price": 17.20, "shares": 10000, "signal": "sell", "score": 20, "timestamp": "2026-05-03 10:00:00"},
            {"seq": 2, "action": "buy", "price": 16.80, "shares": 10000, "signal": "buy", "score": -15, "timestamp": "2026-05-03 11:00:00"},
        ],
        "active_signal": None,
    })

    review = build_post_market_review(t_store, trade_date="2026-05-03")
    assert review["summary"]["month_cumulative_pnl"] == pytest.approx(4000.0)
    assert review["summary"]["month_cumulative_reduction_per_share"] == pytest.approx(4000.0 / 220000, rel=1e-6)


def test_review_skips_same_day_ledger_profit_to_avoid_double_counting(
    t_store: TradingStateStore,
):
    """RED: same-day ledger profit must not be added on top of today's action-derived P&L."""
    from hermes_t.post_market_review import build_post_market_review

    t_store.record_dispatch_event("sent", {
        "signal_id": "sig-prev",
        "trade_date": "2026-05-02",
        "action": "sell",
        "sequence": 1,
        "profit": 2000.0,
    })
    t_store.record_dispatch_event("sent", {
        "signal_id": "sig-today",
        "trade_date": "2026-05-03",
        "action": "sell",
        "sequence": 1,
        "profit": 4000.0,
    })

    t_store.save_execution_state({
        "trade_date": "2026-05-03",
        "sell_count": 1,
        "buy_count": 1,
        "actions": [
            {"seq": 1, "action": "sell", "price": 17.20, "shares": 10000, "signal": "sell", "score": 20, "timestamp": "2026-05-03 10:00:00"},
            {"seq": 2, "action": "buy", "price": 16.80, "shares": 10000, "signal": "buy", "score": -15, "timestamp": "2026-05-03 11:00:00"},
        ],
        "active_signal": None,
        "last_signal_id": "sig-003",
    })

    review = build_post_market_review(t_store, trade_date="2026-05-03")
    # prior day ledger 2000 + today's action-derived 4000; same-day ledger 4000 should be ignored
    assert review["summary"]["month_cumulative_pnl"] == pytest.approx(6000.0)
    assert review["summary"]["month_cumulative_reduction_per_share"] == pytest.approx(6000.0 / 220000, rel=1e-6)


def test_review_ignores_prior_month_ledger_profit(
    t_store: TradingStateStore,
):
    """RED: monthly cumulative should exclude prior-month ledger profit."""
    from hermes_t.post_market_review import build_post_market_review

    t_store.record_dispatch_event("sent", {
        "signal_id": "sig-apr",
        "trade_date": "2026-04-30",
        "action": "sell",
        "sequence": 1,
        "profit": 9000.0,
    })
    t_store.record_dispatch_event("sent", {
        "signal_id": "sig-may-prev",
        "trade_date": "2026-05-02",
        "action": "sell",
        "sequence": 1,
        "profit": 2000.0,
    })

    t_store.save_execution_state({
        "trade_date": "2026-05-03",
        "sell_count": 1,
        "buy_count": 1,
        "actions": [
            {"seq": 1, "action": "sell", "price": 17.20, "shares": 10000, "signal": "sell", "score": 20, "timestamp": "2026-05-03 10:00:00"},
            {"seq": 2, "action": "buy", "price": 16.80, "shares": 10000, "signal": "buy", "score": -15, "timestamp": "2026-05-03 11:00:00"},
        ],
        "active_signal": None,
        "last_signal_id": "sig-004",
    })

    review = build_post_market_review(t_store, trade_date="2026-05-03")
    # only same-month prior 2000 + today 4000; April 9000 must be excluded
    assert review["summary"]["month_cumulative_pnl"] == pytest.approx(6000.0)
