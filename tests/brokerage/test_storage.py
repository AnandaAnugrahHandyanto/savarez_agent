"""Tests for brokerage SQLite storage."""

from datetime import datetime, timedelta, timezone

from brokerage.models import TradeEvent, TradeIntent
from brokerage.storage import SQLiteBrokerageStore


def _make_intent() -> TradeIntent:
    return TradeIntent(
        request_id="req-1",
        account_mode="paper",
        symbol="AAPL",
        side="BUY",
        quantity=10,
        order_type="MARKET",
        asset_class="stock",
    )


def test_store_initializes_schema_and_round_trips_intent(tmp_path):
    store = SQLiteBrokerageStore(tmp_path / "brokerage.db")
    intent = _make_intent()

    store.create_intent(
        intent,
        confirmation_code="T-82K4",
        confirmation_expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
        raw_request_text="buy 10 aapl market paper",
        session_id="session-1",
    )

    loaded = store.get_intent(intent.request_id)
    assert loaded is not None
    assert loaded["intent_id"] == "req-1"
    assert loaded["symbol"] == "AAPL"
    assert loaded["confirmation_code"] == "T-82K4"
    assert loaded["status"] == "pending_confirmation"


def test_store_updates_status_and_order_id(tmp_path):
    store = SQLiteBrokerageStore(tmp_path / "brokerage.db")
    intent = _make_intent()
    store.create_intent(intent, confirmation_code="T-82K4")

    # Must follow legal transition graph: pending_confirmation -> confirmed -> submitted
    store.update_status("req-1", "confirmed")
    store.update_status("req-1", "submitted", ibkr_order_id="ib-123")

    loaded = store.get_intent("req-1")
    assert loaded is not None
    assert loaded["status"] == "submitted"
    assert loaded["ibkr_order_id"] == "ib-123"


def test_store_rejects_illegal_transition(tmp_path):
    store = SQLiteBrokerageStore(tmp_path / "brokerage.db")
    intent = _make_intent()
    store.create_intent(intent, confirmation_code="T-82K4")

    import pytest
    with pytest.raises(ValueError, match="Illegal state transition"):
        store.update_status("req-1", "submitted")  # can't skip confirmed


def test_store_consume_confirmation_code(tmp_path):
    store = SQLiteBrokerageStore(tmp_path / "brokerage.db")
    intent = _make_intent()
    store.create_intent(intent, confirmation_code="T-82K4")

    assert store.get_intent("req-1")["confirmation_code"] == "T-82K4"
    assert store.consume_confirmation_code("req-1") is True
    assert store.get_intent("req-1")["confirmation_code"] is None
    # Second consume is a no-op
    assert store.consume_confirmation_code("req-1") is False


def test_store_appends_audit_events(tmp_path):
    store = SQLiteBrokerageStore(tmp_path / "brokerage.db")
    store.append_event(TradeEvent(intent_id="req-1", event_type="created", detail="created by test"))

    events = store.list_events("req-1")
    assert len(events) == 1
    assert events[0]["event_type"] == "created"
    assert events[0]["detail"] == "created by test"


def test_store_expires_stale_pending_confirmations(tmp_path):
    store = SQLiteBrokerageStore(tmp_path / "brokerage.db")
    intent = _make_intent()
    store.create_intent(
        intent,
        confirmation_code="T-82K4",
        confirmation_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    expired = store.expire_pending_confirmations(datetime.now(timezone.utc))

    assert expired == 1
    loaded = store.get_intent("req-1")
    assert loaded is not None
    assert loaded["status"] == "expired"
