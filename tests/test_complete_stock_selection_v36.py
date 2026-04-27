import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "qmt_complete_stock_selection_v36.py"


def load_v36_module():
    spec = importlib.util.spec_from_file_location("complete_stock_selection_v36", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_history():
    code = "000001.SZ"
    idx = "000001.SH"
    dates = [f"202604{i:02d}" for i in range(1, 22)]
    history = {}
    for n, d in enumerate(dates, 1):
        history[d] = {
            code: {
                "ts_code": code,
                "open": 10 + n * 0.2,
                "high": 10.5 + n * 0.2,
                "low": 9.8 + n * 0.2,
                "close": 10.2 + n * 0.2,
                "vol": 100000 + n * 1000,
                "amount": 200000000 + n * 1000000,
                "pct_chg": 1.0,
                "turnover_rate": 8.0,
            },
            idx: {"pct_chg": -0.3 + n * 0.03},
        }
    for d in ["20260410", "20260411", "20260412", "20260413"]:
        history[d][code]["limit"] = "U"
    history["20260421"][code].update({
        "open": 13.8,
        "high": 14.2,
        "low": 13.2,
        "close": 13.9,
        "vol": 60000,
        "amount": 320000000,
        "pct_chg": -2.2,
        "turnover_rate": 9.0,
    })
    return code, history, "20260421"


class FakeFetcher:
    def __init__(self, token):
        pass

    def get_recent_trade_dates(self, days=30):
        return ["20260420", "20260421"]


class FakeDetector:
    def check_signal(self, recent_daily):
        return {"score": 66, "signals": ["止跌企稳"], "breakdown": {"kline_pattern": 24, "volume_price": 22, "support_pressure": 20}}


class FakeDecisionMaker:
    def decide(self, signal_result, trade_date):
        return {"action": "wait", "reason": "测试观察", "timing": "等待确认"}


def test_v36_main_banner_and_score_labels_are_current(monkeypatch):
    mod = load_v36_module()
    code, history, latest = sample_history()

    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")
    monkeypatch.setattr(mod, "TushareDataFetcher", FakeFetcher)
    monkeypatch.setattr(mod, "StopFallingSignalDetectorV2", FakeDetector)
    monkeypatch.setattr(mod, "EntryDecisionMaker", FakeDecisionMaker)
    monkeypatch.setattr(mod, "find_stocks_with_4plus_limits", lambda daily_history, current_date, lookback_days=20: [code])
    monkeypatch.setattr(mod, "calculate_strategy_score_v36", lambda *args, **kwargs: {
        "total": 88,
        "limit_strength": 12,
        "pullback_depth": 10,
        "volume_shrink": 14,
        "volume_ratio_health": 12,
        "support": 12,
        "rebound_signal": 5,
        "trend": 3,
        "sector_heat": 3,
        "leader_risk": 0,
        "turnover_risk": 0,
        "time_dimension": 0,
        "sector_strength": 8,
        "market_sentiment": 4,
        "hot_tracking": 10,
        "max_consecutive": 4,
    })
    monkeypatch.setattr(mod, "post_tushare", lambda api, params, token: [])
    monkeypatch.setattr(mod.Path, "write_text", lambda self, *args, **kwargs: None)

    def fake_post_tushare(api, params, token):
        if api == "daily":
            return [history[params["trade_date"]][code]]
        if api == "daily_basic":
            return [{"ts_code": code, "turnover_rate": history[params["trade_date"]][code].get("turnover_rate")}]
        if api == "limit_list_d":
            return [{"ts_code": code, "limit": "U", "amount": 300000000}] if history[params["trade_date"]][code].get("limit") == "U" else []
        if api == "stock_basic":
            return [{"ts_code": code, "name": "测试股份"}]
        if api == "index_daily":
            return [{"ts_code": "000001.SH", "pct_chg": history[params["trade_date"]]["000001.SH"]["pct_chg"]}]
        return []

    monkeypatch.setattr(mod, "post_tushare", fake_post_tushare)

    buf = io.StringIO()
    with redirect_stdout(buf):
        mod.main()
    output = buf.getvalue()

    assert "龙头回调策略 v3.6 - 完整选股系统" in output
    assert "策略评分（125分）+ 买入确认信号 + 低吸位置建议" in output
    assert "v3.2" not in output
    assert "策略评分:" in output and "/125" in output
    assert "正在计算策略评分 v3.6" in output


def test_macro_factors_use_market_and_limit_data_not_static_defaults(monkeypatch):
    mod = load_v36_module()
    code, history, current_date = sample_history()

    def fake_post_tushare(api, params, token):
        if api == "index_daily":
            return [{"ts_code": "000001.SH", "pct_chg": 1.6}]
        if api == "limit_list_d":
            return [{"ts_code": f"000{i:03d}.SZ", "limit": "U", "industry": "热点", "amount": 100000000 + i * 1000000} for i in range(1, 90)]
        return []

    monkeypatch.setattr(mod, "post_tushare", fake_post_tushare)

    score = mod.calculate_macro_factors(code, history[current_date][code], history, current_date, "fake-token")

    assert score["sector_strength"] >= 8
    assert score["market_sentiment"] == 5
    assert score["hot_tracking"] >= 8
    assert score["total"] != 8


def test_strategy_score_v36_exposes_125_point_components(monkeypatch):
    mod = load_v36_module()
    code, history, current_date = sample_history()
    monkeypatch.setattr(mod, "calculate_macro_factors", lambda *args, **kwargs: {"sector_strength": 8, "market_sentiment": 4, "hot_tracking": 9, "total": 21})

    detail = mod.calculate_strategy_score_v36(code, history[current_date][code], history, current_date, "fake-token")

    assert {"sector_strength", "market_sentiment", "hot_tracking"}.issubset(detail)
    assert detail["sector_strength"] == 8
    assert detail["market_sentiment"] == 4
    assert detail["hot_tracking"] == 9
    assert detail["total"] == sum(v for k, v in detail.items() if k not in {"total", "max_consecutive"})
    assert detail["max_consecutive"] >= 4


def test_entry_position_advice_uses_each_stock_history_independently():
    mod = load_v36_module()
    history = {}
    dates = [f"202604{i:02d}" for i in range(1, 22)]
    for i, d in enumerate(dates, 1):
        history[d] = {
            "000001.SZ": {"close": 10 + i, "low": 9 + i, "high": 11 + i, "limit": "U" if 5 <= i <= 8 else None},
            "000002.SZ": {"close": 40 + i, "low": 39 + i, "high": 41 + i, "limit": "U" if 7 <= i <= 10 else None},
        }
    a = mod.generate_entry_position_advice(history["20260421"]["000001.SZ"], history, "000001.SZ", "20260421")
    b = mod.generate_entry_position_advice(history["20260421"]["000002.SZ"], history, "000002.SZ", "20260421")

    assert a["support_levels"]["today_low"]["price"] != b["support_levels"]["today_low"]["price"]
    assert a["support_levels"]["ma20"]["price"] != b["support_levels"]["ma20"]["price"]
    assert a["strategies"]["A"]["entry_price"] != b["strategies"]["A"]["entry_price"]
