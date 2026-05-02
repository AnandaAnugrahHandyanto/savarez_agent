from datetime import datetime
import json
from pathlib import Path

import pytest

from hermes_olin.profile import RuntimeProfile
from hermes_olin.runtime import (
    build_execution_suggestion,
    dispatch_ledger_sent_event,
    run_runtime_cycle,
    stage_pending_signal,
)
from hermes_olin.store import TradingStateStore


def test_fixed_tech_data_provider_returns_same_payload_for_any_symbol():
    from hermes_t.tech_data import FixedTechDataProvider

    provider = FixedTechDataProvider({"summary_signal": "sell", "score": {"total": 20}})

    assert provider.get("600519") == {"summary_signal": "sell", "score": {"total": 20}}
    assert provider.get("300750") == {"summary_signal": "sell", "score": {"total": 20}}


def test_json_symbol_tech_data_provider_reads_symbol_specific_payload_and_falls_back():
    from hermes_t.tech_data import JsonSymbolTechDataProvider

    provider = JsonSymbolTechDataProvider(
        tech_data_by_symbol={"600519": {"summary_signal": "buy", "score": {"total": 88}}},
        default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
    )

    assert provider.get("600519") == {"summary_signal": "buy", "score": {"total": 88}}
    assert provider.get("300750") == {"summary_signal": "hold", "score": {"total": 50}}


def test_json_quote_data_provider_returns_raw_quote_payload():
    from hermes_t.tech_data import JsonQuoteDataProvider

    provider = JsonQuoteDataProvider(
        quote_data_by_symbol={
            "600519": {"last_price": 1688.0, "tech_data": {"summary_signal": "sell", "score": {"total": 12}}}
        }
    )

    assert provider.get("600519") == {"last_price": 1688.0, "tech_data": {"summary_signal": "sell", "score": {"total": 12}}}
    assert provider.get("300750") == {}


def test_in_memory_quote_snapshot_provider_normalizes_snapshot_and_returns_default_for_missing_symbol():
    from hermes_t.tech_data import InMemoryQuoteSnapshotProvider

    provider = InMemoryQuoteSnapshotProvider(
        snapshots_by_symbol={
            "600519": {
                "symbol": 600519,
                "last_price": 1688.0,
                "source": "mock",
                "as_of": "2026-05-02T10:00:00+08:00",
                "tech_data": {"summary_signal": "sell", "score": {"total": 18}},
            }
        }
    )

    snapshot = provider.get("600519")
    assert snapshot["symbol"] == "600519"
    assert snapshot["last_price"] == 1688.0
    assert snapshot["source"] == "mock"
    assert snapshot["as_of"] == "2026-05-02T10:00:00+08:00"
    assert snapshot["tech_data"] == {"summary_signal": "sell", "score": {"total": 18}}
    assert provider.get("300750") == {}


def test_file_quote_snapshot_provider_reads_json_file_and_normalizes_symbol(tmp_path):
    from hermes_t.tech_data import FileQuoteSnapshotProvider

    snapshot_path = tmp_path / "quote_snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "600519": {
                    "symbol": 600519,
                    "last_price": 1688.0,
                    "source": "file",
                    "as_of": "2026-05-02T10:01:00+08:00",
                    "tech_data": {"summary_signal": "buy", "score": {"total": 88}},
                }
            }
        ),
        encoding="utf-8",
    )

    provider = FileQuoteSnapshotProvider(snapshot_path=snapshot_path)

    assert provider.get("600519") == {
        "symbol": "600519",
        "last_price": 1688.0,
        "source": "file",
        "as_of": "2026-05-02T10:01:00+08:00",
        "tech_data": {"summary_signal": "buy", "score": {"total": 88}},
    }
    assert provider.get("300750") == {}


def test_quote_snapshot_tech_data_adapter_extracts_tech_data_and_uses_default_fallback():
    from hermes_t.tech_data import InMemoryQuoteSnapshotProvider, QuoteSnapshotTechDataAdapter

    provider = InMemoryQuoteSnapshotProvider(
        snapshots_by_symbol={
            "600519": {
                "symbol": "600519",
                "last_price": 1688.0,
                "source": "mock",
                "as_of": "2026-05-02T10:00:00+08:00",
                "tech_data": {"summary_signal": "sell", "score": {"total": 18}},
            }
        }
    )
    adapter = QuoteSnapshotTechDataAdapter(
        quote_source=provider,
        default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
    )

    assert adapter.get("600519") == {"summary_signal": "sell", "score": {"total": 18}}
    assert adapter.get("300750") == {"summary_signal": "hold", "score": {"total": 50}}


def test_quote_snapshot_tech_data_adapter_returns_deep_copied_payloads():
    from hermes_t.tech_data import InMemoryQuoteSnapshotProvider, QuoteSnapshotTechDataAdapter

    adapter = QuoteSnapshotTechDataAdapter(
        quote_source=InMemoryQuoteSnapshotProvider(
            snapshots_by_symbol={
                "600519": {
                    "symbol": "600519",
                    "last_price": 1688.0,
                    "source": "mock",
                    "as_of": "2026-05-02T10:00:00+08:00",
                    "tech_data": {"summary_signal": "sell", "score": {"total": 18}},
                }
            }
        ),
        default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
    )

    first = adapter.get("600519")
    first["score"]["total"] = 999
    second = adapter.get("600519")

    assert second == {"summary_signal": "sell", "score": {"total": 18}}

    fallback_first = adapter.get("300750")
    fallback_first["score"]["total"] = 1
    fallback_second = adapter.get("300750")

    assert fallback_second == {"summary_signal": "hold", "score": {"total": 50}}



def test_build_quote_snapshot_provider_uses_file_source(tmp_path):
    from hermes_t.tech_data import FileQuoteSnapshotProvider, build_quote_snapshot_provider

    snapshot_path = tmp_path / "quote_snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "600519": {
                    "symbol": 600519,
                    "last_price": 1688.0,
                    "source": "file",
                    "as_of": "2026-05-02T10:01:00+08:00",
                    "tech_data": {"summary_signal": "buy", "score": {"total": 88}},
                }
            }
        ),
        encoding="utf-8",
    )

    provider = build_quote_snapshot_provider(source="file", snapshot_path=snapshot_path)

    assert isinstance(provider, FileQuoteSnapshotProvider)
    assert provider.get("600519")["tech_data"] == {"summary_signal": "buy", "score": {"total": 88}}



def test_build_quote_snapshot_provider_uses_mock_source():
    from hermes_t.tech_data import InMemoryQuoteSnapshotProvider, build_quote_snapshot_provider

    provider = build_quote_snapshot_provider(
        source="mock",
        snapshots_by_symbol={
            "600519": {
                "symbol": 600519,
                "last_price": 1688.0,
                "source": "mock",
                "as_of": "2026-05-02T10:00:00+08:00",
                "tech_data": {"summary_signal": "sell", "score": {"total": 18}},
            }
        },
    )

    assert isinstance(provider, InMemoryQuoteSnapshotProvider)
    assert provider.get("600519")["tech_data"] == {"summary_signal": "sell", "score": {"total": 18}}



def test_build_quote_snapshot_provider_file_source_requires_snapshot_path():
    from hermes_t.tech_data import build_quote_snapshot_provider

    with pytest.raises(ValueError, match="snapshot_path is required"):
        build_quote_snapshot_provider(source="file")



def test_build_quote_snapshot_provider_supports_tdx_placeholder_source():
    from hermes_t.tech_data import TdxQuoteSnapshotSource, build_quote_snapshot_provider

    provider = build_quote_snapshot_provider(source="tdx")

    assert isinstance(provider, TdxQuoteSnapshotSource)



def test_tdx_quote_snapshot_source_fetches_first_valid_server_and_normalizes_snapshot():
    from hermes_t.tech_data import TdxQuoteSnapshotSource

    class FakeTdxApi:
        instances = []

        def __init__(self, *, heartbeat, auto_retry, raise_exception):
            self.heartbeat = heartbeat
            self.auto_retry = auto_retry
            self.raise_exception = raise_exception
            self.connected_to = None
            self.disconnected = False
            FakeTdxApi.instances.append(self)

        def connect(self, host, port, time_out):
            self.connected_to = (host, port, time_out)
            return host == "good-host"

        def get_security_quotes(self, symbols):
            assert symbols == [(1, "600519")]
            return [
                {
                    "price": 14.23,
                    "servertime": "10:15:30",
                }
            ]

        def disconnect(self):
            self.disconnected = True

    provider = TdxQuoteSnapshotSource(
        api_cls=FakeTdxApi,
        servers=[("bad", "bad-host", 7709), ("good", "good-host", 7709)],
    )

    snapshot = provider.get("600519")

    assert snapshot["symbol"] == "600519"
    assert snapshot["last_price"] == 14.23
    assert snapshot["source"] == "tdx_tcp"
    assert snapshot["as_of"] == "10:15:30"
    assert len(FakeTdxApi.instances) == 2
    assert FakeTdxApi.instances[0].connected_to == ("bad-host", 7709, 3)
    assert FakeTdxApi.instances[1].connected_to == ("good-host", 7709, 3)
    assert all(instance.disconnected for instance in FakeTdxApi.instances)



def test_tdx_quote_snapshot_source_raises_when_pytdx_unavailable(monkeypatch):
    from hermes_t import tech_data as tech_data_module

    original_api_cls = tech_data_module.TdxHq_API
    monkeypatch.setattr(tech_data_module, "TdxHq_API", None)
    try:
        provider = tech_data_module.TdxQuoteSnapshotSource()
        with pytest.raises(RuntimeError, match="pytdx unavailable"):
            provider.get("600519")
    finally:
        monkeypatch.setattr(tech_data_module, "TdxHq_API", original_api_cls)



def test_tdx_quote_snapshot_source_raises_after_all_servers_return_invalid_quotes():
    from hermes_t.tech_data import TdxQuoteSnapshotSource

    class FakeTdxApi:
        instances = []

        def __init__(self, *, heartbeat, auto_retry, raise_exception):
            self.disconnected = False
            self.connected_to = None
            FakeTdxApi.instances.append(self)

        def connect(self, host, port, time_out):
            self.connected_to = (host, port, time_out)
            return True

        def get_security_quotes(self, symbols):
            return [{"price": 0, "servertime": "10:01:00"}]

        def disconnect(self):
            self.disconnected = True

    provider = TdxQuoteSnapshotSource(
        api_cls=FakeTdxApi,
        servers=[("s1", "host-1", 7709), ("s2", "host-2", 7709)],
    )

    with pytest.raises(RuntimeError, match="all tdx servers failed or returned invalid quotes"):
        provider.get("600519")

    assert len(FakeTdxApi.instances) == 2
    assert all(instance.disconnected for instance in FakeTdxApi.instances)



def test_quote_snapshot_tech_data_adapter_falls_back_to_default_when_source_raises_and_logs_warning(caplog):
    import logging

    from hermes_t.tech_data import QuoteSnapshotTechDataAdapter

    class FailingSnapshotSource:
        def get(self, symbol):
            raise RuntimeError(f"boom for {symbol}")

    adapter = QuoteSnapshotTechDataAdapter(
        quote_source=FailingSnapshotSource(),
        default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
    )

    with caplog.at_level(logging.WARNING):
        assert adapter.get("600519") == {"summary_signal": "hold", "score": {"total": 50}}

    assert any(
        record.levelno == logging.WARNING
        and "quote snapshot source failed; falling back to default tech_data" in record.message
        and record.__dict__.get("symbol") == "600519"
        for record in caplog.records
    )



def test_build_tech_data_provider_from_quote_snapshot_config_tdx_source_falls_back_to_default_on_runtime_error(tmp_path):
    from hermes_t import tech_data as tech_data_module
    from hermes_t.tech_data import QuoteSnapshotTechDataAdapter, build_tech_data_provider

    class StubFailingTdxQuoteSnapshotSource:
        def __init__(self, *args, **kwargs):
            self.calls = []

        def get(self, symbol):
            self.calls.append(symbol)
            raise RuntimeError("tdx temporarily unavailable")

    stub_source = StubFailingTdxQuoteSnapshotSource()
    original_cls = tech_data_module.TdxQuoteSnapshotSource
    tech_data_module.TdxQuoteSnapshotSource = lambda *args, **kwargs: stub_source
    try:
        config_path = tmp_path / "quote_snapshot_config_tdx.json"
        config_path.write_text(json.dumps({"source": "tdx"}), encoding="utf-8")

        provider = build_tech_data_provider(
            tech_data_config_path=None,
            quote_data_config_path=None,
            quote_snapshot_config_path=config_path,
            default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
        )

        assert isinstance(provider, QuoteSnapshotTechDataAdapter)
        assert provider.get("600519") == {"summary_signal": "hold", "score": {"total": 50}}
        assert stub_source.calls == ["600519"]
    finally:
        tech_data_module.TdxQuoteSnapshotSource = original_cls



def test_build_tech_data_provider_from_quote_snapshot_config_tdx_source_uses_runtime_quote_snapshot(tmp_path):
    from hermes_t import tech_data as tech_data_module
    from hermes_t.tech_data import QuoteSnapshotTechDataAdapter, build_tech_data_provider

    class StubTdxQuoteSnapshotSource:
        def __init__(self, *args, **kwargs):
            self.calls = []

        def get(self, symbol):
            self.calls.append(symbol)
            return {
                "symbol": symbol,
                "last_price": 14.23,
                "source": "tdx_tcp",
                "as_of": "10:15:30",
                "tech_data": {"summary_signal": "buy", "score": {"total": 88}},
            }

    stub_source = StubTdxQuoteSnapshotSource()
    original_cls = tech_data_module.TdxQuoteSnapshotSource
    tech_data_module.TdxQuoteSnapshotSource = lambda *args, **kwargs: stub_source
    try:
        config_path = tmp_path / "quote_snapshot_config_tdx.json"
        config_path.write_text(json.dumps({"source": "tdx"}), encoding="utf-8")

        provider = build_tech_data_provider(
            tech_data_config_path=None,
            quote_data_config_path=None,
            quote_snapshot_config_path=config_path,
            default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
        )

        assert isinstance(provider, QuoteSnapshotTechDataAdapter)
        assert provider.get("600519") == {"summary_signal": "buy", "score": {"total": 88}}
        assert stub_source.calls == ["600519"]
    finally:
        tech_data_module.TdxQuoteSnapshotSource = original_cls



def test_build_quote_snapshot_provider_supports_eastmoney_placeholder_source():
    from hermes_t.tech_data import EastmoneyQuoteSnapshotSource, build_quote_snapshot_provider

    provider = build_quote_snapshot_provider(source="eastmoney")

    assert isinstance(provider, EastmoneyQuoteSnapshotSource)
    with pytest.raises(NotImplementedError, match="eastmoney quote snapshot source is not implemented"):
        provider.get("600519")



def test_build_quote_snapshot_provider_rejects_unknown_source():
    from hermes_t.tech_data import build_quote_snapshot_provider

    with pytest.raises(ValueError, match="Unsupported quote snapshot source"):
        build_quote_snapshot_provider(source="not-a-real-source")



def test_build_tech_data_provider_quote_snapshot_factory_config_resolves_relative_snapshot_path_from_config_dir(tmp_path, monkeypatch):
    from hermes_t.tech_data import build_tech_data_provider

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    snapshot_path = config_dir / "quote_snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "600519": {
                    "symbol": 600519,
                    "last_price": 1688.0,
                    "source": "file",
                    "as_of": "2026-05-02T10:02:00+08:00",
                    "tech_data": {"summary_signal": "buy", "score": {"total": 91}},
                }
            }
        ),
        encoding="utf-8",
    )
    config_path = config_dir / "quote_snapshot_config.json"
    config_path.write_text(
        json.dumps(
            {
                "source": "file",
                "snapshot_path": "quote_snapshot.json",
            }
        ),
        encoding="utf-8",
    )

    other_cwd = tmp_path / "elsewhere"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)

    provider = build_tech_data_provider(
        tech_data_config_path=None,
        quote_data_config_path=None,
        quote_snapshot_config_path=config_path,
        default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
    )

    assert provider.get("600519") == {"summary_signal": "buy", "score": {"total": 91}}



def test_build_tech_data_provider_from_quote_snapshot_config_uses_snapshot_adapter(tmp_path):
    from hermes_t.tech_data import QuoteSnapshotTechDataAdapter, build_tech_data_provider

    snapshot_path = tmp_path / "quote_snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "600519": {
                    "symbol": "600519",
                    "last_price": 1688.0,
                    "source": "file",
                    "tech_data": {"summary_signal": "buy", "score": {"total": 88}},
                }
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "quote_snapshot_config.json"
    config_path.write_text(
        json.dumps(
            {
                "source": "file",
                "snapshot_path": str(snapshot_path),
            }
        ),
        encoding="utf-8",
    )

    provider = build_tech_data_provider(
        tech_data_config_path=None,
        quote_data_config_path=None,
        quote_snapshot_config_path=config_path,
        default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
    )

    assert isinstance(provider, QuoteSnapshotTechDataAdapter)
    assert provider.get("600519") == {"summary_signal": "buy", "score": {"total": 88}}



def test_build_tech_data_provider_from_quote_snapshot_config_eastmoney_placeholder_falls_back_to_default_on_get(tmp_path):
    from hermes_t.tech_data import QuoteSnapshotTechDataAdapter, build_tech_data_provider

    config_path = tmp_path / "quote_snapshot_config_eastmoney.json"
    config_path.write_text(json.dumps({"source": "eastmoney"}), encoding="utf-8")

    provider = build_tech_data_provider(
        tech_data_config_path=None,
        quote_data_config_path=None,
        quote_snapshot_config_path=config_path,
        default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
    )

    assert isinstance(provider, QuoteSnapshotTechDataAdapter)
    assert provider.get("600519") == {"summary_signal": "hold", "score": {"total": 50}}



def test_build_tech_data_provider_prefers_explicit_quote_data_config_over_quote_snapshot_config(tmp_path):
    from hermes_t.tech_data import QuoteTechDataAdapter, build_tech_data_provider

    quote_data_path = tmp_path / "quote_data.json"
    snapshot_path = tmp_path / "quote_snapshot.json"
    quote_data_path.write_text(
        json.dumps({"600519": {"last_price": 1688.0, "tech_data": {"summary_signal": "sell", "score": {"total": 12}}}}),
        encoding="utf-8",
    )
    snapshot_path.write_text(
        json.dumps({"600519": {"symbol": "600519", "last_price": 1688.0, "source": "file", "as_of": "2026-05-02T10:01:00+08:00", "tech_data": {"summary_signal": "buy", "score": {"total": 88}}}}),
        encoding="utf-8",
    )

    provider = build_tech_data_provider(
        tech_data_config_path=None,
        quote_data_config_path=quote_data_path,
        quote_snapshot_config_path=snapshot_path,
        default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
    )

    assert isinstance(provider, QuoteTechDataAdapter)
    assert provider.get("600519") == {"summary_signal": "sell", "score": {"total": 12}}


def test_build_tech_data_provider_from_paths_uses_json_provider(tmp_path):
    from hermes_t.tech_data import JsonSymbolTechDataProvider, build_tech_data_provider

    tech_data_path = tmp_path / "tech_data.json"
    tech_data_path.write_text(
        json.dumps({"600519": {"summary_signal": "buy", "score": {"total": 88}}}),
        encoding="utf-8",
    )

    provider = build_tech_data_provider(
        tech_data_config_path=tech_data_path,
        default_tech_data={"summary_signal": "sell", "score": {"total": 20}},
    )

    assert isinstance(provider, JsonSymbolTechDataProvider)
    assert provider.get("600519") == {"summary_signal": "buy", "score": {"total": 88}}
    assert provider.get("300750") == {"summary_signal": "sell", "score": {"total": 20}}


def test_build_tech_data_provider_from_quote_config_extracts_nested_tech_data(tmp_path):
    from hermes_t.tech_data import QuoteTechDataAdapter, build_tech_data_provider

    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text(
        json.dumps(
            {
                "600519": {
                    "last_price": 1688.0,
                    "bid_price": 1687.5,
                    "ask_price": 1688.5,
                    "tech_data": {"summary_signal": "sell", "score": {"total": 18}},
                }
            }
        ),
        encoding="utf-8",
    )

    provider = build_tech_data_provider(
        tech_data_config_path=None,
        quote_data_config_path=quote_data_path,
        default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
    )

    assert isinstance(provider, QuoteTechDataAdapter)
    assert provider.get("600519") == {"summary_signal": "sell", "score": {"total": 18}}
    assert provider.get("300750") == {"summary_signal": "hold", "score": {"total": 50}}


def test_json_quote_data_provider_returns_raw_quote_payload_and_falls_back_to_empty_dict():
    from hermes_t.tech_data import JsonQuoteDataProvider

    provider = JsonQuoteDataProvider(
        quote_data_by_symbol={
            "600519": {
                "last_price": 1688.0,
                "tech_data": {"summary_signal": "sell", "score": {"total": 18}},
            }
        }
    )

    assert provider.get("600519") == {
        "last_price": 1688.0,
        "tech_data": {"summary_signal": "sell", "score": {"total": 18}},
    }
    assert provider.get("300750") == {}


def test_quote_tech_data_adapter_extracts_nested_tech_data_and_uses_default_fallback():
    from hermes_t.tech_data import JsonQuoteDataProvider, QuoteTechDataAdapter

    quote_provider = JsonQuoteDataProvider(
        quote_data_by_symbol={
            "600519": {
                "last_price": 1688.0,
                "tech_data": {"summary_signal": "sell", "score": {"total": 18}},
            }
        }
    )
    adapter = QuoteTechDataAdapter(
        quote_provider=quote_provider,
        default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
    )

    assert adapter.get("600519") == {"summary_signal": "sell", "score": {"total": 18}}
    assert adapter.get("300750") == {"summary_signal": "hold", "score": {"total": 50}}


def test_signal_policy_defaults_and_templates_are_available():
    from hermes_olin.signal_policy import DEFAULT_SIGNAL_POLICY, render_signal_text

    assert DEFAULT_SIGNAL_POLICY.buy_score_threshold == 70
    assert DEFAULT_SIGNAL_POLICY.sell_score_threshold == 30
    assert DEFAULT_SIGNAL_POLICY.active_signal_hold_text == "当前已有待处理信号，暂停生成下一笔执行建议"
    assert DEFAULT_SIGNAL_POLICY.no_action_text == "暂无新增执行建议"
    assert render_signal_text(action="sell", sequence=2, trade_unit=500, policy=DEFAULT_SIGNAL_POLICY) == "第2次卖出 500 股"
    assert render_signal_text(action="buy", sequence=3, trade_unit=200, policy=DEFAULT_SIGNAL_POLICY) == "第3次买入 200 股"
    assert render_signal_text(action="hold", sequence=0, trade_unit=0, policy=DEFAULT_SIGNAL_POLICY) == DEFAULT_SIGNAL_POLICY.no_action_text


def test_runtime_profile_supports_non_olin_symbol():
    from hermes_olin.profile import RuntimeProfile

    profile = RuntimeProfile(
        profile_id="test-600519",
        symbol="600519",
        trade_unit=200,
        max_trades=6,
    )

    assert profile.profile_id == "test-600519"
    assert profile.symbol == "600519"
    assert profile.trade_unit == 200
    assert profile.max_trades == 6


def test_hermes_t_exports_generic_runtime_api():
    import hermes_t

    assert hermes_t.RuntimeProfile is RuntimeProfile
    assert hermes_t.TradingStateStore is TradingStateStore
    assert callable(hermes_t.run_runtime_cycle)


def test_hermes_t_does_not_expose_olin_named_store_in_generic_all():
    import hermes_t

    assert "TradingStateStore" in hermes_t.__all__
    assert "OlinStateStore" not in hermes_t.__all__


def test_trading_state_store_uses_profile_scoped_state_directory(tmp_path):
    from hermes_olin.profile import RuntimeProfile
    from hermes_olin.store import TradingStateStore

    profile = RuntimeProfile(profile_id="demo-600519", symbol="600519")
    store = TradingStateStore(tmp_path, profile=profile)

    assert store.base_dir == tmp_path
    assert store.profile.profile_id == "demo-600519"
    assert store.state_dir == tmp_path / "profiles" / "demo-600519" / "state" / "realtime"


def test_build_execution_suggestion_uses_profile_trade_unit_and_max_trades(tmp_path):
    from hermes_olin.profile import RuntimeProfile
    from hermes_olin.store import TradingStateStore

    profile = RuntimeProfile(
        profile_id="demo-600519",
        symbol="600519",
        trade_unit=200,
        max_trades=6,
    )
    store = TradingStateStore(tmp_path, profile=profile)

    suggestion = build_execution_suggestion(
        store,
        {"summary_signal": "sell", "score": {"total": 20}},
        "20260501",
    )

    assert suggestion["trade_unit"] == 200
    assert suggestion["max_trades"] == 6
    assert suggestion["text"] == "第1次卖出 200 股"


def test_build_execution_suggestion_respects_profile_max_trades_limit(tmp_path):
    from hermes_olin.profile import RuntimeProfile
    from hermes_olin.store import TradingStateStore

    profile = RuntimeProfile(
        profile_id="demo-600519",
        symbol="600519",
        trade_unit=200,
        max_trades=1,
    )
    store = TradingStateStore(tmp_path, profile=profile)
    store.save_execution_state({"trade_date": "20260501", "sell_count": 1})

    suggestion = build_execution_suggestion(
        store,
        {"summary_signal": "sell", "score": {"total": 20}},
        "20260501",
    )

    assert suggestion["next_action"] == "hold"


def test_stage_pending_signal_falls_back_to_profile_trade_unit_for_generic_store(tmp_path):
    profile = RuntimeProfile(
        profile_id="demo-600519",
        symbol="600519",
        trade_unit=200,
        max_trades=6,
    )
    store = TradingStateStore(tmp_path, profile=profile)
    suggestion = {
        "next_action": "sell",
        "action": "sell",
        "sequence": 1,
        "text": "第1次卖出 200 股",
        "signal": "sell",
    }

    pending = stage_pending_signal(
        store,
        suggestion,
        store.load_execution_state(),
        "20260501",
        datetime(2026, 5, 1, 9, 30, 0),
    )

    assert pending["trade_unit"] == 200
    assert store.load_pending_signal()["trade_unit"] == 200


def test_dispatch_ledger_sent_event_uses_dry_run_variant():
    assert dispatch_ledger_sent_event({"dry_run": True}) == "dry_run_sent"
    assert dispatch_ledger_sent_event({"dry_run": False}) == "sent"
    assert dispatch_ledger_sent_event(None) == "sent"


def test_run_runtime_cycle_uses_profile_trade_unit_for_generic_store(tmp_path):
    profile = RuntimeProfile(
        profile_id="demo-600519",
        symbol="600519",
        trade_unit=200,
        max_trades=6,
    )
    store = TradingStateStore(tmp_path, profile=profile)

    result = run_runtime_cycle(
        store,
        tech_data={"summary_signal": "sell", "score": {"total": 20}},
        effective_trade_date="20260501",
        now=datetime(2026, 5, 1, 9, 30, 0),
        dispatch=False,
    )

    assert result["pending"]["trade_unit"] == 200
    assert result["suggestion"]["trade_unit"] == 200
    assert result["suggestion"]["text"] == "第1次卖出 200 股"
    assert store.load_pending_signal()["trade_unit"] == 200


def test_cli_shared_builds_parser_with_custom_runtime_defaults(monkeypatch, tmp_path):
    from hermes_t.cli_shared import build_runtime_parser

    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("HERMES_T_CHANNEL", "feishu-test")

    parser = build_runtime_parser(
        description="generic runtime",
        default_base_dir_name=".custom_runtime",
        channel_env_vars=("HERMES_T_CHANNEL",),
    )
    args = parser.parse_args(["--trade-date", "20260502"])

    assert args.base_dir == str(home_dir / ".custom_runtime")
    assert args.channel == "feishu-test"
    assert args.trade_date == "20260502"


def test_build_runtime_profile_from_args_rejects_blank_required_strings():
    import argparse

    from hermes_t.cli_shared import build_runtime_profile_from_args

    args = argparse.Namespace(profile_id="   ", symbol="", trade_unit=10000, max_trades=4)

    with pytest.raises(ValueError, match="profile item 0 missing required fields: profile_id, symbol"):
        build_runtime_profile_from_args(args)


def test_build_runtime_profile_from_args_rejects_non_positive_ints():
    import argparse

    from hermes_t.cli_shared import build_runtime_profile_from_args

    args = argparse.Namespace(profile_id="demo-600519", symbol="600519", trade_unit=0, max_trades=4)
    with pytest.raises(ValueError, match="profile item 0 field trade_unit must be a positive integer"):
        build_runtime_profile_from_args(args)

    args = argparse.Namespace(profile_id="demo-600519", symbol="600519", trade_unit=10000, max_trades=True)
    with pytest.raises(ValueError, match="profile item 0 field max_trades must be a positive integer"):
        build_runtime_profile_from_args(args)


def test_hermes_t_cli_uses_generic_home_based_default_dir(monkeypatch, tmp_path, capsys):
    import hermes_t.__main__ as main_mod

    captured = {}
    home_dir = tmp_path / "home"
    home_dir.mkdir()

    def fake_run_runtime_cycle(store, **kwargs):
        captured["base_dir"] = str(store.base_dir)
        captured["profile_id"] = store.profile.profile_id
        return {"ok": True}

    monkeypatch.setattr(main_mod, "run_runtime_cycle", fake_run_runtime_cycle)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setattr(
        "sys.argv",
        ["hermes_t", "--trade-date", "20260501", "--signal", "hold"],
    )

    main_mod.main()
    json.loads(capsys.readouterr().out)

    assert captured["base_dir"] == str(home_dir / ".hermes_t_runtime")
    assert captured["profile_id"] == "olin-688319"


def test_hermes_t_cli_uses_trading_state_store_even_for_default_profile(monkeypatch, tmp_path, capsys):
    import hermes_t.__main__ as main_mod

    captured = {}

    def fake_run_runtime_cycle(store, **kwargs):
        captured["store_class"] = type(store).__name__
        return {"ok": True}

    monkeypatch.setattr(main_mod, "run_runtime_cycle", fake_run_runtime_cycle)
    monkeypatch.setattr(
        "sys.argv",
        ["hermes_t", "--base-dir", str(tmp_path), "--trade-date", "20260501"],
    )

    main_mod.main()
    json.loads(capsys.readouterr().out)

    assert captured["store_class"] == "TradingStateStore"


def test_hermes_t_cli_passes_runtime_delivery_kwargs_to_single_profile_runner(monkeypatch, tmp_path, capsys):
    import hermes_t.__main__ as main_mod

    captured = {}

    def fake_run_runtime_cycle(store, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(main_mod, "run_runtime_cycle", fake_run_runtime_cycle)
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes_t",
            "--base-dir",
            str(tmp_path),
            "--trade-date",
            "20260501",
            "--dispatch",
            "--channel",
            "feishu",
            "--chat-id",
            "oc_demo",
            "--thread-id",
            "omt_demo",
        ],
    )

    main_mod.main()
    json.loads(capsys.readouterr().out)

    assert captured["effective_trade_date"] == "20260501"
    assert captured["dispatch"] is True
    assert captured["channel"] == "feishu"
    assert captured["chat_id"] == "oc_demo"
    assert captured["thread_id"] == "omt_demo"


def test_load_runtime_profiles_from_json_reads_multiple_profiles(tmp_path):
    from hermes_t.orchestrator import load_runtime_profiles_from_json

    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps(
            [
                {"profile_id": "demo-600519", "symbol": "600519", "trade_unit": 200, "max_trades": 6},
                {"profile_id": "demo-300750", "symbol": "300750", "trade_unit": 100, "max_trades": 3},
            ]
        ),
        encoding="utf-8",
    )

    profiles = load_runtime_profiles_from_json(config_path)

    assert [profile.profile_id for profile in profiles] == ["demo-600519", "demo-300750"]
    assert profiles[0].trade_unit == 200
    assert profiles[1].max_trades == 3


def test_load_runtime_profiles_from_json_rejects_non_positive_trade_unit(tmp_path):
    from hermes_t.orchestrator import load_runtime_profiles_from_json

    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps([
            {"profile_id": "demo-600519", "symbol": "600519", "trade_unit": 0, "max_trades": 6}
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="profile item 0 field trade_unit must be a positive integer"):
        load_runtime_profiles_from_json(config_path)


def test_load_runtime_profiles_from_json_rejects_non_positive_max_trades(tmp_path):
    from hermes_t.orchestrator import load_runtime_profiles_from_json

    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps([
            {"profile_id": "demo-600519", "symbol": "600519", "trade_unit": 200, "max_trades": -1}
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="profile item 0 field max_trades must be a positive integer"):
        load_runtime_profiles_from_json(config_path)


def test_load_runtime_profiles_from_json_rejects_non_int_trade_unit(tmp_path):
    from hermes_t.orchestrator import load_runtime_profiles_from_json

    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps([
            {"profile_id": "demo-600519", "symbol": "600519", "trade_unit": "100", "max_trades": 6}
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="profile item 0 field trade_unit must be a positive integer"):
        load_runtime_profiles_from_json(config_path)


def test_load_runtime_profiles_from_json_rejects_non_int_max_trades(tmp_path):
    from hermes_t.orchestrator import load_runtime_profiles_from_json

    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps([
            {"profile_id": "demo-600519", "symbol": "600519", "trade_unit": 200, "max_trades": 3.5}
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="profile item 0 field max_trades must be a positive integer"):
        load_runtime_profiles_from_json(config_path)


def test_load_runtime_profiles_from_json_rejects_bool_trade_unit(tmp_path):
    from hermes_t.orchestrator import load_runtime_profiles_from_json

    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps([
            {"profile_id": "demo-600519", "symbol": "600519", "trade_unit": True, "max_trades": 6}
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="profile item 0 field trade_unit must be a positive integer"):
        load_runtime_profiles_from_json(config_path)


def test_load_runtime_profiles_from_json_rejects_bool_max_trades(tmp_path):
    from hermes_t.orchestrator import load_runtime_profiles_from_json

    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps([
            {"profile_id": "demo-600519", "symbol": "600519", "trade_unit": 200, "max_trades": True}
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="profile item 0 field max_trades must be a positive integer"):
        load_runtime_profiles_from_json(config_path)


def test_build_runtime_profile_from_item_builds_profile_with_defaults():
    from hermes_t.orchestrator import _build_runtime_profile_from_item

    profile = _build_runtime_profile_from_item(
        item={"profile_id": "demo-600519", "symbol": "600519"},
        idx=0,
    )

    assert profile.profile_id == "demo-600519"
    assert profile.symbol == "600519"
    assert profile.trade_unit == 10000
    assert profile.max_trades == 4


def test_build_runtime_profile_from_item_rejects_missing_required_fields():
    from hermes_t.orchestrator import _build_runtime_profile_from_item

    with pytest.raises(ValueError, match="profile item 0 missing required fields: symbol"):
        _build_runtime_profile_from_item(item={"profile_id": "demo-600519"}, idx=0)


def test_validated_positive_int_accepts_positive_int():
    from hermes_t.orchestrator import _validated_positive_int

    assert _validated_positive_int(value=200, field_name="trade_unit", idx=0) == 200


def test_validated_positive_int_rejects_bool():
    from hermes_t.orchestrator import _validated_positive_int

    with pytest.raises(ValueError, match="profile item 0 field max_trades must be a positive integer"):
        _validated_positive_int(value=True, field_name="max_trades", idx=0)


def test_missing_required_fields_returns_missing_field_names_in_order():
    from hermes_t.orchestrator import _missing_required_fields

    assert _missing_required_fields(
        {"profile_id": "", "symbol": None, "trade_unit": "   "},
        ("profile_id", "symbol", "trade_unit"),
    ) == ["profile_id", "symbol", "trade_unit"]


def test_build_runtime_profile_from_item_rejects_blank_required_string_fields():
    from hermes_t.orchestrator import _build_runtime_profile_from_item

    with pytest.raises(ValueError, match="profile item 0 missing required fields: profile_id, symbol"):
        _build_runtime_profile_from_item(item={"profile_id": "   ", "symbol": ""}, idx=0)


def test_build_runtime_profile_from_item_rejects_non_string_required_fields():
    from hermes_t.orchestrator import _build_runtime_profile_from_item

    with pytest.raises(ValueError, match="profile item 0 field profile_id must be a non-empty string"):
        _build_runtime_profile_from_item(item={"profile_id": 123, "symbol": "600519"}, idx=0)

    with pytest.raises(ValueError, match="profile item 0 field symbol must be a non-empty string"):
        _build_runtime_profile_from_item(item={"profile_id": "demo-600519", "symbol": True}, idx=0)


def test_missing_required_fields_returns_empty_list_when_all_required_fields_present():
    from hermes_t.orchestrator import _missing_required_fields

    assert _missing_required_fields(
        {"profile_id": "demo-600519", "symbol": "600519", "trade_unit": 10000},
        ("profile_id", "symbol", "trade_unit"),
    ) == []


def test_load_runtime_profiles_from_json_rejects_duplicate_profile_ids(tmp_path):
    from hermes_t.orchestrator import load_runtime_profiles_from_json

    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps([
            {"profile_id": "demo-600519", "symbol": "600519"},
            {"profile_id": "demo-600519", "symbol": "300750"},
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate profile_id 'demo-600519' at item 1"):
        load_runtime_profiles_from_json(config_path)


def test_run_profiles_from_config_returns_empty_summary_for_empty_profiles_config(tmp_path):
    from hermes_t.orchestrator import run_profiles_from_config
    from hermes_t.tech_data import FixedTechDataProvider

    config_path = tmp_path / "profiles.json"
    config_path.write_text("[]", encoding="utf-8")

    result = run_profiles_from_config(
        config_path=config_path,
        base_dir=tmp_path / "runtime",
        tech_data_provider=FixedTechDataProvider({"summary_signal": "hold", "score": {"total": 50}}),
        effective_trade_date="20260502",
        dispatch=False,
    )

    assert result == {
        "config_path": str(config_path),
        "total_profiles": 0,
        "results": [],
    }


def test_run_profiles_from_config_propagates_runner_exception(tmp_path):
    from hermes_t.orchestrator import run_profiles_from_config
    from hermes_t.tech_data import FixedTechDataProvider

    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps([
            {"profile_id": "demo-600519", "symbol": "600519", "trade_unit": 200, "max_trades": 6}
        ]),
        encoding="utf-8",
    )

    def fake_runner(store, **kwargs):
        raise RuntimeError("runner boom")

    with pytest.raises(RuntimeError, match="runner boom"):
        run_profiles_from_config(
            config_path=config_path,
            base_dir=tmp_path / "runtime",
            tech_data_provider=FixedTechDataProvider({"summary_signal": "hold", "score": {"total": 50}}),
            effective_trade_date="20260502",
            dispatch=False,
            runner=fake_runner,
        )


def test_run_profiles_from_config_executes_each_profile_and_returns_summary(tmp_path):
    from hermes_t.orchestrator import run_profiles_from_config
    from hermes_t.tech_data import JsonSymbolTechDataProvider

    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps(
            [
                {"profile_id": "demo-600519", "symbol": "600519", "trade_unit": 200, "max_trades": 6},
                {"profile_id": "demo-300750", "symbol": "300750", "trade_unit": 100, "max_trades": 3},
            ]
        ),
        encoding="utf-8",
    )

    calls = []

    def fake_runner(store, **kwargs):
        calls.append(
            {
                "profile_id": store.profile.profile_id,
                "symbol": store.profile.symbol,
                "base_dir": str(store.base_dir),
                "trade_date": kwargs["effective_trade_date"],
                "tech_data": kwargs["tech_data"],
            }
        )
        return {"next_action": "hold", "symbol": store.profile.symbol}

    result = run_profiles_from_config(
        config_path=config_path,
        base_dir=tmp_path / "runtime",
        tech_data_provider=JsonSymbolTechDataProvider(
            tech_data_by_symbol={
                "600519": {"summary_signal": "sell", "score": {"total": 20}},
                "300750": {"summary_signal": "buy", "score": {"total": 80}},
            },
            default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
        ),
        effective_trade_date="20260502",
        dispatch=False,
        runner=fake_runner,
    )

    assert [call["profile_id"] for call in calls] == ["demo-600519", "demo-300750"]
    assert calls[0]["trade_date"] == "20260502"
    assert calls[0]["tech_data"] == {"summary_signal": "sell", "score": {"total": 20}}
    assert calls[1]["tech_data"] == {"summary_signal": "buy", "score": {"total": 80}}
    assert result["total_profiles"] == 2
    assert [item["profile_id"] for item in result["results"]] == ["demo-600519", "demo-300750"]
    assert result["results"][1]["payload"]["symbol"] == "300750"


def test_run_profiles_from_config_uses_default_tech_data_when_symbol_missing(tmp_path):
    from hermes_t.orchestrator import run_profiles_from_config
    from hermes_t.tech_data import FixedTechDataProvider

    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps([
            {"profile_id": "demo-600519", "symbol": "600519", "trade_unit": 200, "max_trades": 6}
        ]),
        encoding="utf-8",
    )

    captured = {}

    def fake_runner(store, **kwargs):
        captured["tech_data"] = kwargs["tech_data"]
        return {"ok": True}

    run_profiles_from_config(
        config_path=config_path,
        base_dir=tmp_path / "runtime",
        tech_data_provider=FixedTechDataProvider({"summary_signal": "sell", "score": {"total": 20}}),
        effective_trade_date="20260502",
        dispatch=False,
        runner=fake_runner,
    )

    assert captured["tech_data"] == {"summary_signal": "sell", "score": {"total": 20}}


def test_hermes_t_cli_routes_profiles_config_to_orchestrator(monkeypatch, tmp_path, capsys):
    import hermes_t.__main__ as main_mod

    captured = {}
    config_path = tmp_path / "profiles.json"
    tech_data_path = tmp_path / "tech_data.json"
    config_path.write_text(
        json.dumps([
            {"profile_id": "demo-600519", "symbol": "600519", "trade_unit": 200, "max_trades": 6}
        ]),
        encoding="utf-8",
    )
    tech_data_path.write_text(
        json.dumps({"600519": {"summary_signal": "buy", "score": {"total": 88}}}),
        encoding="utf-8",
    )

    def fake_run_profiles_from_config(**kwargs):
        captured.update(kwargs)
        return {"mode": "multi", "total_profiles": 1}

    monkeypatch.setattr(main_mod, "run_profiles_from_config", fake_run_profiles_from_config)
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes_t",
            "--base-dir",
            str(tmp_path / "runtime"),
            "--trade-date",
            "20260502",
            "--profiles-config",
            str(config_path),
            "--tech-data-config",
            str(tech_data_path),
            "--signal",
            "sell",
            "--score",
            "20",
            "--dispatch",
            "--channel",
            "feishu",
            "--chat-id",
            "oc_demo",
            "--thread-id",
            "omt_demo",
        ],
    )

    main_mod.main()
    out = json.loads(capsys.readouterr().out)

    assert out["mode"] == "multi"
    assert captured["config_path"] == str(config_path)
    assert captured["effective_trade_date"] == "20260502"
    assert captured["dispatch"] is True
    assert captured["channel"] == "feishu"
    assert captured["chat_id"] == "oc_demo"
    assert captured["thread_id"] == "omt_demo"
    assert captured["tech_data_provider"].get("600519") == {"summary_signal": "buy", "score": {"total": 88}}
    assert captured["tech_data_provider"].get("300750") == {"summary_signal": "sell", "score": {"total": 20}}


def test_hermes_t_cli_routes_profiles_config_with_quote_data_to_orchestrator(monkeypatch, tmp_path, capsys):
    import hermes_t.__main__ as main_mod

    captured = {}
    config_path = tmp_path / "profiles.json"
    quote_data_path = tmp_path / "quote_data.json"
    config_path.write_text(
        json.dumps([
            {"profile_id": "demo-600519", "symbol": "600519", "trade_unit": 200, "max_trades": 6},
            {"profile_id": "demo-300750", "symbol": "300750", "trade_unit": 100, "max_trades": 3},
        ]),
        encoding="utf-8",
    )
    quote_data_path.write_text(
        json.dumps(
            {
                "600519": {
                    "last_price": 1688.0,
                    "tech_data": {"summary_signal": "sell", "score": {"total": 18}},
                }
            }
        ),
        encoding="utf-8",
    )

    def fake_run_profiles_from_config(**kwargs):
        captured.update(kwargs)
        return {"mode": "multi", "total_profiles": 2}

    monkeypatch.setattr(main_mod, "run_profiles_from_config", fake_run_profiles_from_config)
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes_t",
            "--base-dir",
            str(tmp_path / "runtime"),
            "--trade-date",
            "20260502",
            "--profiles-config",
            str(config_path),
            "--quote-data-config",
            str(quote_data_path),
            "--signal",
            "hold",
            "--score",
            "50",
        ],
    )

    main_mod.main()
    out = json.loads(capsys.readouterr().out)

    assert out["mode"] == "multi"
    assert captured["config_path"] == str(config_path)
    assert captured["tech_data_provider"].get("600519") == {"summary_signal": "sell", "score": {"total": 18}}
    assert captured["tech_data_provider"].get("300750") == {"summary_signal": "hold", "score": {"total": 50}}


def test_hermes_t_cli_multi_profile_passes_quote_snapshot_config_to_provider(monkeypatch, tmp_path, capsys):
    import hermes_t.__main__ as main_mod

    captured = {}
    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps(
            [
                {
                    "profile_id": "demo-600519",
                    "symbol": "600519",
                    "label": "贵州茅台",
                    "trade_unit": 100,
                    "max_trades": 4,
                }
            ]
        ),
        encoding="utf-8",
    )
    snapshot_path = tmp_path / "quote_snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "600519": {
                    "symbol": 600519,
                    "last_price": 1688.0,
                    "source": "file",
                    "as_of": "2026-05-02T10:01:00+08:00",
                    "tech_data": {"summary_signal": "buy", "score": {"total": 88}},
                }
            }
        ),
        encoding="utf-8",
    )

    def fake_run_profiles_from_config(**kwargs):
        captured.update(kwargs)
        return {"mode": "multi", "total_profiles": 1}

    monkeypatch.setattr(main_mod, "run_profiles_from_config", fake_run_profiles_from_config)
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes_t",
            "--base-dir",
            str(tmp_path / "runtime"),
            "--trade-date",
            "20260502",
            "--profiles-config",
            str(config_path),
            "--quote-snapshot-config",
            str(snapshot_path),
            "--signal",
            "hold",
            "--score",
            "50",
        ],
    )

    main_mod.main()
    json.loads(capsys.readouterr().out)

    assert captured["tech_data_provider"].get("600519") == {"summary_signal": "buy", "score": {"total": 88}}
    assert captured["tech_data_provider"].get("300750") == {"summary_signal": "hold", "score": {"total": 50}}



def test_hermes_t_cli_single_profile_uses_quote_snapshot_config(monkeypatch, tmp_path, capsys):
    import hermes_t.__main__ as main_mod

    captured = {}
    snapshot_path = tmp_path / "quote_snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "600519": {
                    "symbol": 600519,
                    "last_price": 1688.0,
                    "source": "file",
                    "as_of": "2026-05-02T10:01:00+08:00",
                    "tech_data": {"summary_signal": "sell", "score": {"total": 18}},
                }
            }
        ),
        encoding="utf-8",
    )

    def fake_run_runtime_cycle(store, **kwargs):
        captured["symbol"] = store.profile.symbol
        captured["tech_data"] = kwargs["tech_data"]
        return {"ok": True}

    monkeypatch.setattr(main_mod, "run_runtime_cycle", fake_run_runtime_cycle)
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes_t",
            "--base-dir",
            str(tmp_path / "runtime"),
            "--trade-date",
            "20260502",
            "--symbol",
            "600519",
            "--quote-snapshot-config",
            str(snapshot_path),
            "--signal",
            "hold",
            "--score",
            "50",
        ],
    )

    main_mod.main()
    json.loads(capsys.readouterr().out)

    assert captured["symbol"] == "600519"
    assert captured["tech_data"] == {"summary_signal": "sell", "score": {"total": 18}}


def test_build_tech_data_provider_prefers_explicit_tech_data_config_over_quote_snapshot_config(tmp_path):
    from hermes_t.tech_data import JsonSymbolTechDataProvider, build_tech_data_provider

    tech_data_path = tmp_path / "tech_data.json"
    snapshot_path = tmp_path / "quote_snapshot.json"
    tech_data_path.write_text(
        json.dumps({"600519": {"summary_signal": "sell", "score": {"total": 12}}}),
        encoding="utf-8",
    )
    snapshot_path.write_text(
        json.dumps({"600519": {"symbol": "600519", "last_price": 1688.0, "source": "file", "as_of": "2026-05-02T10:01:00+08:00", "tech_data": {"summary_signal": "buy", "score": {"total": 88}}}}),
        encoding="utf-8",
    )

    provider = build_tech_data_provider(
        tech_data_config_path=tech_data_path,
        quote_data_config_path=None,
        quote_snapshot_config_path=snapshot_path,
        default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
    )

    assert isinstance(provider, JsonSymbolTechDataProvider)
    assert provider.get("600519") == {"summary_signal": "sell", "score": {"total": 12}}



def test_build_tech_data_provider_prefers_explicit_tech_data_config_over_quote_data_config(tmp_path):
    from hermes_t.tech_data import JsonSymbolTechDataProvider, build_tech_data_provider

    tech_data_path = tmp_path / "tech_data.json"
    quote_data_path = tmp_path / "quote_data.json"
    tech_data_path.write_text(
        json.dumps({"600519": {"summary_signal": "buy", "score": {"total": 88}}}),
        encoding="utf-8",
    )
    quote_data_path.write_text(
        json.dumps(
            {
                "600519": {
                    "last_price": 1688.0,
                    "tech_data": {"summary_signal": "sell", "score": {"total": 18}},
                }
            }
        ),
        encoding="utf-8",
    )

    provider = build_tech_data_provider(
        tech_data_config_path=tech_data_path,
        quote_data_config_path=quote_data_path,
        default_tech_data={"summary_signal": "hold", "score": {"total": 50}},
    )

    assert isinstance(provider, JsonSymbolTechDataProvider)
    assert provider.get("600519") == {"summary_signal": "buy", "score": {"total": 88}}


def test_hermes_t_cli_routes_quote_data_config_through_provider(monkeypatch, tmp_path, capsys):
    import hermes_t.__main__ as main_mod

    captured = {}
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text(
        json.dumps(
            {
                "600519": {
                    "last_price": 1688.0,
                    "tech_data": {"summary_signal": "sell", "score": {"total": 12}},
                }
            }
        ),
        encoding="utf-8",
    )

    def fake_run_runtime_cycle(store, **kwargs):
        captured["tech_data"] = kwargs["tech_data"]
        captured["base_dir"] = str(store.base_dir)
        return {"ok": True, "tech_data": kwargs["tech_data"]}

    monkeypatch.setattr(main_mod, "run_runtime_cycle", fake_run_runtime_cycle)
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes_t",
            "--base-dir",
            str(tmp_path / "runtime"),
            "--trade-date",
            "20260502",
            "--symbol",
            "600519",
            "--quote-data-config",
            str(quote_data_path),
            "--signal",
            "hold",
            "--score",
            "50",
        ],
    )

    main_mod.main()
    out = json.loads(capsys.readouterr().out)

    assert captured["base_dir"] == str(tmp_path / "runtime")
    assert captured["tech_data"] == {"summary_signal": "sell", "score": {"total": 12}}
    assert out["tech_data"] == {"summary_signal": "sell", "score": {"total": 12}}


def test_run_runtime_cycle_blocks_duplicate_sent_candidate_without_restaging_for_custom_profile(tmp_path):
    profile = RuntimeProfile(
        profile_id="demo-600519",
        symbol="600519",
        trade_unit=200,
        max_trades=6,
    )
    store = TradingStateStore(tmp_path, profile=profile)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 1,
            "buy_count": 0,
            "actions": [
                {
                    "signal_id": "sell_1_20260422_093000",
                    "signal_key": "sell_1",
                    "trade_date": "20260422",
                    "action": "sell",
                    "sequence": 1,
                    "status": "sent",
                    "sent_at": "2026-04-22 09:30:05",
                    "channel": "feishu",
                    "text": "第1次卖出 200 股",
                }
            ],
            "active_signal": None,
            "last_signal_id": "sell_1_20260422_093000",
            "last_signal_action": "sell",
            "last_signal_status": "sent",
            "last_signal_at": "2026-04-22 09:30:05",
        }
    )
    store.save_push_state(
        {
            "last_pushed_signal": "sell_1",
            "last_pushed_signal_id": "sell_1_20260422_093000",
            "last_pushed_trade_date": "20260422",
            "last_pushed_at": "2026-04-22 09:30:05",
        }
    )

    result = run_runtime_cycle(
        store,
        tech_data={"summary_signal": "sell", "score": {"total": 20}},
        effective_trade_date="20260422",
        now=datetime(2026, 4, 22, 9, 31, 0),
        dispatch=False,
    )

    assert result["suggestion"]["next_action"] == "hold"
    assert result["suggestion"]["reason"] == "duplicate_sent_signal"
    assert result["suggestion"]["trade_unit"] == 200
    assert result["suggestion"]["max_trades"] == 6
    assert result["pending"] == {}
    assert store.load_pending_signal() == {}
    assert store.load_execution_state()["active_signal"] is None


def test_run_runtime_cycle_reuses_failed_pending_after_cooldown_with_custom_profile(tmp_path, monkeypatch):
    profile = RuntimeProfile(
        profile_id="demo-600519",
        symbol="600519",
        trade_unit=200,
        max_trades=6,
    )
    store = TradingStateStore(tmp_path, profile=profile)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 0,
            "buy_count": 0,
            "actions": [],
            "active_signal": {
                "signal_id": "sell_1_20260422_093000",
                "signal_key": "sell_1",
                "trade_date": "20260422",
                "action": "sell",
                "sequence": 1,
                "status": "failed",
                "created_at": "2026-04-22 09:30:00",
                "last_attempt_at": "2026-04-22 09:30:00",
                "last_error": "temporary gateway error",
            },
        }
    )
    store.save_pending_signal(
        {
            "signal_id": "sell_1_20260422_093000",
            "signal_key": "sell_1",
            "trade_date": "20260422",
            "action": "sell",
            "sequence": 1,
            "status": "failed",
            "created_at": "2026-04-22 09:30:00",
            "text": "第1次卖出 200 股",
            "trade_unit": 200,
            "attempts": 1,
            "last_attempt_at": "2026-04-22 09:30:00",
            "last_attempt_status": "failed",
            "last_error": "temporary gateway error",
            "last_error_retryable": True,
        }
    )
    import hermes_olin.runtime as runtime_mod

    monkeypatch.setattr(
        runtime_mod,
        "load_runtime_policy",
        lambda: {
            "pending_signal_timeout_sec": 300,
            "pending_signal_max_attempts": 3,
            "pending_retry_cooldown_sec": 30,
            "candidate_freshness_limit_sec": 0,
        },
    )

    result = run_runtime_cycle(
        store,
        tech_data={"summary_signal": "sell", "score": {"total": 20}},
        effective_trade_date="20260422",
        now=datetime(2026, 4, 22, 9, 31, 0),
        dispatch=False,
    )

    assert result["suggestion"]["next_action"] == "sell"
    assert result["suggestion"]["reason"] == "retry_ready_reuse_failed_pending"
    assert result["suggestion"]["trade_unit"] == 200
    assert result["suggestion"]["max_trades"] == 6
    assert result["result"]["signal_id"] == "sell_1_20260422_093000"
    assert result["result"]["status"] == "failed"
    assert result["pending"]["signal_id"] == "sell_1_20260422_093000"
    assert store.load_pending_signal()["signal_id"] == "sell_1_20260422_093000"
