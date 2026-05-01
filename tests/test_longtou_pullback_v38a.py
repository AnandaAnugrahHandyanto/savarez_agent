import importlib.util
from pathlib import Path

SCRIPT_PATH = Path.home() / ".hermes" / "scripts" / "backtest_longtou_pullback_v38_a.py"


def load_v38a_module():
    spec = importlib.util.spec_from_file_location("backtest_longtou_pullback_v38_a", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v38a_profile_matches_selected_parameters():
    mod = load_v38a_module()
    profile = mod.V38A_PROFILE

    assert profile["name"] == "v3.8-A 胜率优先版"
    assert profile["top_n"] == 5
    assert profile["daily_cap"] == 2
    assert profile["strategy_min"] == 70
    assert profile["entry_min"] == 48
    assert profile["entry_sig_min"] == 0
    assert profile["min_pct"] == -2
    assert profile["max_pct"] == 3.5
    assert profile["max_consecutive"] == 4
    assert profile["dedupe_days"] == 3
    assert profile["hold_days"] == 10
    assert profile["tp"] == 0.20
    assert profile["sl"] == 0.08
    assert profile["day1_take"] == 0.08


def test_choose_v38a_filters_ranks_caps_and_dedupes():
    mod = load_v38a_module()
    fetch_dates = ["20260420", "20260421", "20260422", "20260423"]
    universe = [
        {"date": "20260420", "code": "A", "rank": 1, "strategy_score": 71, "entry_score": 60, "entry_signal_score": 0, "pct_chg": 1.0, "max_consecutive": 4, "decision_action": "enter"},
        {"date": "20260420", "code": "B", "rank": 2, "strategy_score": 72, "entry_score": 59, "entry_signal_score": 0, "pct_chg": 1.2, "max_consecutive": 4, "decision_action": "enter"},
        {"date": "20260420", "code": "C", "rank": 3, "strategy_score": 99, "entry_score": 58, "entry_signal_score": 0, "pct_chg": 1.3, "max_consecutive": 4, "decision_action": "enter"},
        {"date": "20260421", "code": "A", "rank": 1, "strategy_score": 90, "entry_score": 80, "entry_signal_score": 0, "pct_chg": 1.0, "max_consecutive": 4, "decision_action": "enter"},
        {"date": "20260421", "code": "D", "rank": 6, "strategy_score": 90, "entry_score": 80, "entry_signal_score": 0, "pct_chg": 1.0, "max_consecutive": 4, "decision_action": "enter"},
        {"date": "20260421", "code": "E", "rank": 2, "strategy_score": 69, "entry_score": 80, "entry_signal_score": 0, "pct_chg": 1.0, "max_consecutive": 4, "decision_action": "enter"},
        {"date": "20260421", "code": "F", "rank": 2, "strategy_score": 90, "entry_score": 47, "entry_signal_score": 0, "pct_chg": 1.0, "max_consecutive": 4, "decision_action": "enter"},
        {"date": "20260421", "code": "G", "rank": 2, "strategy_score": 90, "entry_score": 80, "entry_signal_score": 0, "pct_chg": 4.0, "max_consecutive": 4, "decision_action": "enter"},
        {"date": "20260421", "code": "H", "rank": 2, "strategy_score": 90, "entry_score": 80, "entry_signal_score": 0, "pct_chg": 1.0, "max_consecutive": 5, "decision_action": "enter"},
        {"date": "20260421", "code": "I", "rank": 2, "strategy_score": 90, "entry_score": 80, "entry_signal_score": 0, "pct_chg": 1.0, "max_consecutive": 4, "decision_action": "wait"},
    ]

    chosen = mod.choose_v38a(universe, fetch_dates)

    assert [row["code"] for row in chosen] == ["A", "B"]


def test_classify_v38a_signal_keeps_high_risk_rows_as_reference_not_primary():
    mod = load_v38a_module()

    primary = {"code": "P", "rank": 1, "strategy_score": 70, "entry_score": 48, "entry_signal_score": 0, "pct_chg": 2.5, "max_consecutive": 4, "decision_action": "enter"}
    high_board = {"code": "H", "rank": 1, "strategy_score": 94, "entry_score": 57, "entry_signal_score": 1.5, "pct_chg": 2.1, "max_consecutive": 8, "decision_action": "enter"}
    hot_weak_score = {"code": "W", "rank": 1, "strategy_score": 62, "entry_score": 55, "entry_signal_score": 0, "pct_chg": 3.6, "max_consecutive": 4, "decision_action": "enter"}

    assert mod.classify_v38a_signal(primary)["bucket"] == "primary"
    assert mod.classify_v38a_signal(high_board)["bucket"] == "reference"
    assert "高位连续强势风险" in mod.classify_v38a_signal(high_board)["risk_flags"]
    assert mod.classify_v38a_signal(hot_weak_score)["bucket"] == "reference"
    assert "涨幅偏大且策略分不足" in mod.classify_v38a_signal(hot_weak_score)["risk_flags"]


def test_partition_v38a_signals_returns_primary_and_reference_pools():
    mod = load_v38a_module()
    fetch_dates = ["20260420", "20260421"]
    universe = [
        {"date": "20260420", "code": "P", "rank": 1, "strategy_score": 70, "entry_score": 48, "entry_signal_score": 0, "pct_chg": 2.5, "max_consecutive": 4, "decision_action": "enter"},
        {"date": "20260420", "code": "H", "rank": 2, "strategy_score": 94, "entry_score": 57, "entry_signal_score": 1.5, "pct_chg": 2.1, "max_consecutive": 8, "decision_action": "enter"},
        {"date": "20260420", "code": "W", "rank": 3, "strategy_score": 62, "entry_score": 55, "entry_signal_score": 0, "pct_chg": 3.6, "max_consecutive": 4, "decision_action": "enter"},
    ]

    partition = mod.partition_v38a_signals(universe, fetch_dates)

    assert [row["code"] for row in partition["primary"]] == ["P"]
    assert [row["code"] for row in partition["reference"]] == ["H", "W"]
    assert all(row["v38a_bucket"] == "reference" for row in partition["reference"])
    assert partition["reference_summary"]["count"] == 2


def test_eval_trade_v38a_day1_take_precedes_20pct_take_profit():
    mod = load_v38a_module()
    sig = {"date": "20260420", "code": "A", "buy_price": 10.0}
    fetch_dates = ["20260420", "20260421", "20260422"]
    daily_history = {
        "20260421": {"A": {"high": 12.5, "low": 9.5, "close": 11.0}},
        "20260422": {"A": {"high": 13.0, "low": 12.0, "close": 12.5}},
    }

    trade = mod.eval_trade_v38a(sig, fetch_dates, daily_history)

    assert trade["exit_date"] == "20260421"
    assert trade["exit_reason"] == "D1止盈8%"
    assert trade["profit_pct"] == 8.0
