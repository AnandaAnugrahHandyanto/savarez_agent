import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path.home() / ".hermes" / "scripts" / "backtest_0927_next_day.py"


def load_module():
    spec = importlib.util.spec_from_file_location("backtest_0927_next_day", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_result_row_sells_next_auction_when_not_open_limit_up():
    mod = load_module()
    candidate = {
        "action": "观察",
        "priority": "B1",
        "ts_code": "600338.SH",
        "name": "西藏珠峰",
        "open_pct": 1.02,
        "auction_price": 22.8,
        "volume_ratio": 6.59828,
        "primary_theme": "有色资源",
    }
    d1 = {"ts_code": "600338.SH", "open": 24.92, "pre_close": 24.83, "pct_chg": 1.0874}

    row = mod.build_result_row(candidate, d1, {})

    assert row["missing"] is False
    assert row["buy_price"] == 22.8
    assert row["sell_price"] == 24.92
    assert row["sell_action"] == "D+1竞价未涨停卖出"
    assert row["d1_open_pct"] == 0.36
    assert row["auction_return_pct"] == 9.3


def test_build_result_row_marks_hold_when_next_auction_opens_limit_up():
    mod = load_module()
    candidate = {
        "action": "观察",
        "priority": "A1",
        "ts_code": "000001.SZ",
        "name": "测试股",
        "open_pct": 1.0,
        "auction_price": 10.0,
        "volume_ratio": 2.0,
        "primary_theme": "测试题材",
    }
    d1 = {"ts_code": "000001.SZ", "open": 11.0, "pre_close": 10.0, "pct_chg": 10.0}

    row = mod.build_result_row(candidate, d1, {"limit": "U"})

    assert row["sell_action"] == "D+1竞价涨停暂不卖"
    assert row["sell_price"] is None
    assert row["auction_return_pct"] is None
    assert row["d1_open_pct"] == 10.0


def test_resolve_trade_date_silent_on_non_trading_day(monkeypatch, capsys):
    mod = load_module()
    monkeypatch.setenv("BACKTEST_0927_TODAY", "20260501")
    monkeypatch.setattr(mod, "is_trade_date_open", lambda trade_date, token: False)

    assert mod.resolve_trade_date(["backtest_0927_next_day.py"], "token") is None
    assert capsys.readouterr().out.strip() == "[SILENT]"


def test_resolve_trade_date_uses_previous_trade_day_on_trading_day(monkeypatch):
    mod = load_module()
    monkeypatch.setenv("BACKTEST_0927_TODAY", "20260506")
    monkeypatch.setattr(mod, "is_trade_date_open", lambda trade_date, token: True)
    monkeypatch.setattr(mod, "previous_trade_date", lambda anchor_date, token: "20260430")

    assert mod.resolve_trade_date(["backtest_0927_next_day.py"], "token") == "20260430"


@pytest.mark.parametrize("holiday", ["20260501", "20260502", "20260503", "20260504", "20260505"])
def test_labour_day_holiday_window_stays_silent(monkeypatch, capsys, holiday):
    """5/1-5/5 休市窗口不得提前触发 4/30 候选回测。"""
    mod = load_module()
    monkeypatch.setenv("BACKTEST_0927_TODAY", holiday)
    monkeypatch.setattr(mod, "is_trade_date_open", lambda trade_date, token: False)

    assert mod.resolve_trade_date(["backtest_0927_next_day.py"], "token") is None
    assert capsys.readouterr().out.strip() == "[SILENT]"


def test_labour_day_next_open_triggers_april_30_candidates(monkeypatch):
    """5/6 开市后才选择 4/30 作为 D 日。"""
    mod = load_module()
    monkeypatch.setenv("BACKTEST_0927_TODAY", "20260506")
    monkeypatch.setattr(mod, "is_trade_date_open", lambda trade_date, token: True)
    monkeypatch.setattr(mod, "previous_trade_date", lambda anchor_date, token: "20260430")

    assert mod.resolve_trade_date(["backtest_0927_next_day.py"], "token") == "20260430"


def test_next_trade_date_sorts_calendar_before_selecting_next_open(monkeypatch):
    """Tushare 日历若倒序返回，也必须选到 4/30 后第一个开市日 5/6。"""
    mod = load_module()
    monkeypatch.setattr(
        mod,
        "post_tushare",
        lambda api, params, token: [
            {"cal_date": "20260506", "is_open": 1},
            {"cal_date": "20260505", "is_open": 0},
            {"cal_date": "20260504", "is_open": 0},
            {"cal_date": "20260501", "is_open": 0},
            {"cal_date": "20260430", "is_open": 1},
        ],
    )

    assert mod.next_trade_date("20260430", "token") == "20260506"
