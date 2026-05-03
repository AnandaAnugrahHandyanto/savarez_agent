"""Focused tests for standalone hermes_t.post_market_review."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


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
def state_dir(tmp_path: Path, position_data: dict) -> Path:
    _write_json(
        tmp_path / "execution_state.json",
        {
            "trade_date": "2026-05-03",
            "sell_count": 0,
            "buy_count": 0,
            "actions": [],
        },
    )
    _write_json(tmp_path / "position.json", position_data)
    return tmp_path


def test_review_with_no_trades_returns_zero_pnl(state_dir: Path):
    from hermes_t.post_market_review import build_post_market_review

    review = build_post_market_review(state_dir, trade_date="2026-05-03")

    assert review["trade_date"] == "2026-05-03"
    assert review["symbol"] == "688319"
    assert review["summary"]["total_trades"] == 0
    assert review["summary"]["realized_pnl"] == 0.0
    assert review["summary"]["avg_cost_before"] == 16.685
    assert review["summary"]["avg_cost_after"] == 16.685
    assert review["summary"]["cost_reduction_per_share"] == 0.0
    assert review["summary"]["available_cash"] == 1_000_000.0
    assert review["trades"] == []


def test_review_with_complete_t_trade_calculates_pnl(state_dir: Path):
    from hermes_t.post_market_review import build_post_market_review

    _write_json(
        state_dir / "execution_state.json",
        {
            "trade_date": "2026-05-03",
            "sell_count": 1,
            "buy_count": 1,
            "actions": [
                {"seq": 1, "action": "sell", "price": 17.20, "shares": 10000, "signal": "sell", "score": 20, "timestamp": "2026-05-03 10:00:00"},
                {"seq": 2, "action": "buy", "price": 16.80, "shares": 10000, "signal": "buy", "score": -15, "timestamp": "2026-05-03 11:00:00"},
            ],
        },
    )

    review = build_post_market_review(state_dir, trade_date="2026-05-03")

    expected_reduction = 4000.0 / 220000
    assert review["summary"]["realized_pnl"] == pytest.approx(4000.0)
    assert review["summary"]["cost_reduction_per_share"] == pytest.approx(expected_reduction, rel=1e-6)
    assert review["summary"]["avg_cost_after"] == pytest.approx(16.685 - expected_reduction, rel=1e-6)


def test_review_with_losing_t_trade_increases_avg_cost(state_dir: Path):
    from hermes_t.post_market_review import build_post_market_review

    _write_json(
        state_dir / "execution_state.json",
        {
            "trade_date": "2026-05-03",
            "sell_count": 1,
            "buy_count": 1,
            "actions": [
                {"seq": 1, "action": "sell", "price": 16.80, "shares": 10000, "signal": "sell", "score": 20, "timestamp": "2026-05-03 10:00:00"},
                {"seq": 2, "action": "buy", "price": 17.20, "shares": 10000, "signal": "buy", "score": -15, "timestamp": "2026-05-03 11:00:00"},
            ],
        },
    )

    review = build_post_market_review(state_dir, trade_date="2026-05-03")

    expected_reduction = -4000.0 / 220000
    assert review["summary"]["realized_pnl"] == pytest.approx(-4000.0)
    assert review["summary"]["cost_reduction_per_share"] == pytest.approx(expected_reduction, rel=1e-6)
    assert review["summary"]["avg_cost_after"] == pytest.approx(16.685 - expected_reduction, rel=1e-6)
    assert review["summary"]["month_cumulative_reduction_per_share"] == pytest.approx(expected_reduction, rel=1e-6)


def test_same_day_ledger_rows_are_not_double_counted(state_dir: Path):
    from hermes_t.post_market_review import build_post_market_review

    _write_json(
        state_dir / "execution_state.json",
        {
            "trade_date": "2026-05-03",
            "sell_count": 1,
            "buy_count": 1,
            "actions": [
                {"seq": 1, "action": "sell", "price": 17.20, "shares": 10000, "timestamp": "2026-05-03 10:00:00"},
                {"seq": 2, "action": "buy", "price": 16.80, "shares": 10000, "timestamp": "2026-05-03 11:00:00"},
            ],
        },
    )
    _write_jsonl(
        state_dir / "dispatch_ledger.jsonl",
        [
            {"trade_date": "2026-05-03", "profit": 4000.0},
            {"trade_date": "2026-05-02", "profit": 2000.0},
        ],
    )

    review = build_post_market_review(state_dir, trade_date="2026-05-03")

    assert review["summary"]["realized_pnl"] == pytest.approx(4000.0)
    assert review["summary"]["month_cumulative_pnl"] == pytest.approx(6000.0)


def test_prior_month_ledger_rows_are_excluded_from_current_month(state_dir: Path):
    from hermes_t.post_market_review import build_post_market_review

    _write_jsonl(
        state_dir / "dispatch_ledger.jsonl",
        [
            {"trade_date": "2026-04-30", "profit": 9000.0},
            {"trade_date": "2026-05-02", "profit": 2000.0},
        ],
    )

    review = build_post_market_review(state_dir, trade_date="2026-05-03")

    assert review["summary"]["month_cumulative_pnl"] == pytest.approx(2000.0)


def test_missing_position_can_fall_back_to_explicit_symbol(tmp_path: Path):
    from hermes_t.post_market_review import build_post_market_review

    _write_json(tmp_path / "execution_state.json", {"trade_date": "2026-05-03", "actions": []})

    review = build_post_market_review(tmp_path, trade_date="2026-05-03", symbol="688319")

    assert review["symbol"] == "688319"
    assert review["summary"]["avg_cost_before"] == 0.0
    assert review["summary"]["available_cash"] == 0.0
