from datetime import datetime
import json
import sys

import pytest

from hermes_olin.profile import RuntimeProfile
from hermes_olin.runtime import (
    arbitrate_candidate,
    build_execution_suggestion,
    confirm_dispatch_sent,
    deliver_pending_signal,
    recover_signal_runtime,
    run_runtime_cycle,
    stage_pending_signal,
)
from hermes_olin.store import OlinStateStore, TradingStateStore

def test_default_runtime_profile_keeps_olin_compatible_values():
    from hermes_olin.profile import DEFAULT_RUNTIME_PROFILE

    assert DEFAULT_RUNTIME_PROFILE.profile_id == "olin-688319"
    assert DEFAULT_RUNTIME_PROFILE.symbol == "688319"
    assert DEFAULT_RUNTIME_PROFILE.trade_unit == 10000
    assert DEFAULT_RUNTIME_PROFILE.max_trades == 4

def test_olin_state_store_remains_backward_compatible(tmp_path):
    store = OlinStateStore(tmp_path)

    assert store.profile.profile_id == "olin-688319"
    assert store.profile.symbol == "688319"

def test_build_execution_suggestion_uses_execution_state_sequence(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 2,
            "buy_count": 1,
            "actions": [{"signal_id": "older"}],
            "active_signal": None,
            "last_signal_id": "older",
            "last_signal_action": "sell",
            "last_signal_status": "sent",
            "last_signal_at": "2026-04-22 09:20:00",
        }
    )

    suggestion = build_execution_suggestion(
        store,
        {"summary_signal": "sell", "score": {"total": 20}},
        "20260422",
    )

    assert suggestion["next_action"] == "sell"
    assert suggestion["sequence"] == 3
    assert suggestion["execution_state"]["sell_count"] == 2
    assert suggestion["state_snapshot"]["actions"][0]["signal_id"] == "older"


def test_build_execution_suggestion_holds_when_active_signal_exists(tmp_path):
    from hermes_olin.signal_policy import DEFAULT_SIGNAL_POLICY

    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 0,
            "buy_count": 0,
            "actions": [],
            "active_signal": {
                "signal_id": "sell_1_20260422_093000",
                "signal_key": "sell_1",
                "action": "sell",
                "sequence": 1,
                "status": "pending",
                "created_at": "2026-04-22 09:30:00",
            },
            "last_signal_id": None,
            "last_signal_action": None,
            "last_signal_status": None,
            "last_signal_at": None,
        }
    )

    suggestion = build_execution_suggestion(
        store,
        {"summary_signal": "sell", "score": {"total": 20}},
        "20260422",
    )

    assert suggestion["next_action"] == "hold"
    assert suggestion["sequence"] == 0
    assert suggestion["reason"] == "active_signal_exists"
    assert suggestion["text"] == DEFAULT_SIGNAL_POLICY.active_signal_hold_text


def test_build_execution_suggestion_uses_policy_no_action_text(tmp_path):
    from hermes_olin.signal_policy import DEFAULT_SIGNAL_POLICY

    store = OlinStateStore(tmp_path)

    suggestion = build_execution_suggestion(
        store,
        {"summary_signal": "hold", "score": {"total": 50}},
        "20260422",
    )

    assert suggestion["next_action"] == "hold"
    assert suggestion["sequence"] == 0
    assert suggestion["text"] == DEFAULT_SIGNAL_POLICY.no_action_text


def test_stage_pending_signal_sets_active_signal_in_execution_state(tmp_path):
    store = OlinStateStore(tmp_path)
    suggestion = {
        "next_action": "sell",
        "sequence": 3,
        "signal": "sell",
        "text": "第3次卖出 10000 股",
        "trade_unit": 10000,
        "execution_state": {
            "trade_date": "20260422",
            "sell_count": 2,
            "buy_count": 1,
            "actions": [{"signal_id": "older"}],
            "active_signal": None,
            "last_signal_id": "older",
            "last_signal_action": "sell",
            "last_signal_status": "sent",
            "last_signal_at": "2026-04-22 09:20:00",
        },
    }

    pending = stage_pending_signal(
        store,
        suggestion,
        suggestion["execution_state"],
        "20260422",
        datetime(2026, 4, 22, 9, 30, 0),
    )

    execution_state = store.load_execution_state()
    assert pending["signal_id"] == "sell_3_20260422_093000"
    assert store.load_pending_signal()["signal_id"] == "sell_3_20260422_093000"
    assert execution_state["trade_date"] == "20260422"
    assert execution_state["sell_count"] == 2
    assert execution_state["active_signal"]["signal_id"] == "sell_3_20260422_093000"
    assert execution_state["active_signal"]["sequence"] == 3
    assert execution_state["actions"][0]["signal_id"] == "older"


def test_stage_pending_signal_skips_hold_candidate(tmp_path):
    store = OlinStateStore(tmp_path)
    suggestion = {
        "next_action": "hold",
        "sequence": 0,
        "signal": "hold",
        "text": "暂无新增执行建议",
        "trade_unit": 10000,
        "execution_state": {
            "trade_date": "20260422",
            "sell_count": 0,
            "buy_count": 0,
            "actions": [],
            "active_signal": None,
            "last_signal_id": None,
            "last_signal_action": None,
            "last_signal_status": None,
            "last_signal_at": None,
        },
    }

    pending = stage_pending_signal(
        store,
        suggestion,
        suggestion["execution_state"],
        "20260422",
        datetime(2026, 4, 22, 9, 30, 0),
    )

    assert pending == {}
    assert store.load_pending_signal() == {}
    assert store.load_execution_state()["active_signal"] is None


def test_stage_pending_signal_clears_stale_previous_trade_date_pending(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_pending_signal(
        {
            "signal_id": "sell_1_20260421_145000",
            "signal_key": "sell_1",
            "trade_date": "20260421",
            "status": "failed",
            "action": "sell",
            "sequence": 1,
            "text": "old",
        }
    )
    suggestion = {
        "next_action": "buy",
        "sequence": 1,
        "signal": "buy",
        "text": "第1次买入 10000 股",
        "trade_unit": 10000,
        "execution_state": {
            "trade_date": "20260422",
            "sell_count": 0,
            "buy_count": 0,
            "actions": [],
            "active_signal": None,
            "last_signal_id": None,
            "last_signal_action": None,
            "last_signal_status": None,
            "last_signal_at": None,
        },
    }

    pending = stage_pending_signal(
        store,
        suggestion,
        suggestion["execution_state"],
        "20260422",
        datetime(2026, 4, 22, 9, 31, 0),
    )

    assert pending["signal_id"] == "buy_1_20260422_093100"
    assert store.load_pending_signal()["trade_date"] == "20260422"


def test_stage_pending_signal_clears_stale_missing_trade_date_pending(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_pending_signal(
        {
            "signal_id": "sell_1_legacy",
            "signal_key": "sell_1",
            "status": "pending",
            "action": "sell",
            "sequence": 1,
            "text": "legacy",
        }
    )
    suggestion = {
        "next_action": "buy",
        "sequence": 1,
        "signal": "buy",
        "text": "第1次买入 10000 股",
        "trade_unit": 10000,
        "execution_state": {
            "trade_date": "20260422",
            "sell_count": 0,
            "buy_count": 0,
            "actions": [],
            "active_signal": None,
            "last_signal_id": None,
            "last_signal_action": None,
            "last_signal_status": None,
            "last_signal_at": None,
        },
    }

    pending = stage_pending_signal(
        store,
        suggestion,
        suggestion["execution_state"],
        "20260422",
        datetime(2026, 4, 22, 9, 32, 0),
    )

    assert pending["signal_id"] == "buy_1_20260422_093200"
    assert store.load_pending_signal()["trade_date"] == "20260422"


def test_confirm_dispatch_sent_updates_pending_push_state_and_history(tmp_path):
    store = OlinStateStore(tmp_path)
    pending = {
        "signal_id": "sell_1_20260422_093000",
        "signal_key": "sell_1",
        "trade_date": "20260422",
        "action": "sell",
        "sequence": 1,
        "status": "pending",
        "text": "第1次卖出 10000 股",
        "attempts": 1,
    }
    store.save_pending_signal(pending)
    store.save_push_state({"existing": "value"})

    result = confirm_dispatch_sent(
        store,
        pending,
        channel="feishu_webhook",
        delivery_result={"channel": "feishu_webhook", "dry_run": True},
    )

    saved_push_state = store.load_push_state()
    history = store.read_jsonl("signal_send_history.jsonl")
    ledger = store.read_jsonl("dispatch_ledger.jsonl")
    assert result["status"] == "sent"
    assert store.load_pending_signal() == {}
    assert saved_push_state["existing"] == "value"
    assert saved_push_state["last_pushed_signal"] == "sell_1"
    assert saved_push_state["last_pushed_signal_id"] == "sell_1_20260422_093000"
    assert saved_push_state["last_dispatch_channel"] == "feishu_webhook"
    assert history[-1]["event"] == "sent"
    assert history[-1]["signal_id"] == "sell_1_20260422_093000"
    assert ledger[-1]["event"] == "dry_run_sent"
    assert ledger[-1]["signal_id"] == "sell_1_20260422_093000"


def test_confirm_dispatch_sent_commits_execution_state_and_clears_active_signal(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 0,
            "buy_count": 0,
            "actions": [],
            "active_signal": {
                "signal_id": "sell_1_20260422_093000",
                "signal_key": "sell_1",
                "action": "sell",
                "sequence": 1,
                "status": "pending",
                "created_at": "2026-04-22 09:30:00",
            },
            "last_signal_id": None,
            "last_signal_action": None,
            "last_signal_status": None,
            "last_signal_at": None,
        }
    )
    pending = {
        "signal_id": "sell_1_20260422_093000",
        "signal_key": "sell_1",
        "trade_date": "20260422",
        "action": "sell",
        "sequence": 1,
        "status": "pending",
        "text": "第1次卖出 10000 股",
        "attempts": 1,
    }

    confirm_dispatch_sent(
        store,
        pending,
        channel="feishu_session",
        delivery_result={"channel": "feishu_session", "dry_run": False},
    )

    execution_state = store.load_execution_state()
    assert execution_state["active_signal"] is None
    assert execution_state["last_signal_id"] == "sell_1_20260422_093000"
    assert execution_state["last_signal_action"] == "sell"
    assert execution_state["last_signal_status"] == "sent"
    assert execution_state["sell_count"] == 1
    assert execution_state["actions"][-1]["signal_id"] == "sell_1_20260422_093000"
    assert execution_state["actions"][-1]["status"] == "sent"


def test_confirm_dispatch_sent_rejects_missing_trade_date(tmp_path):
    store = OlinStateStore(tmp_path)

    try:
        confirm_dispatch_sent(
            store,
            {
                "signal_id": "sell_1_legacy",
                "signal_key": "sell_1",
                "action": "sell",
                "sequence": 1,
                "status": "pending",
                "text": "legacy",
                "attempts": 1,
            },
            channel="feishu_session",
            delivery_result={"channel": "feishu_session", "dry_run": False},
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "trade_date" in str(exc)

def test_deliver_pending_signal_confirms_state_after_successful_dispatch(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 0,
            "buy_count": 0,
            "actions": [],
            "active_signal": {
                "signal_id": "sell_1_20260422_093000",
                "signal_key": "sell_1",
                "action": "sell",
                "sequence": 1,
                "status": "pending",
                "created_at": "2026-04-22 09:30:00",
            },
            "last_signal_id": None,
            "last_signal_action": None,
            "last_signal_status": None,
            "last_signal_at": None,
        }
    )
    pending = {
        "signal_id": "sell_1_20260422_093000",
        "signal_key": "sell_1",
        "trade_date": "20260422",
        "action": "sell",
        "sequence": 1,
        "status": "pending",
        "text": "第1次卖出 10000 股",
        "attempts": 0,
    }
    store.save_pending_signal(pending)

    calls = []

    def fake_dispatch(payload: dict) -> dict:
        calls.append(payload)
        return {
            "success": True,
            "platform": "feishu",
            "chat_id": "oc_8bdfeacaaffbbb9b8a74a3e6450ea49f",
            "message_id": "om_xxx",
        }

    result = deliver_pending_signal(
        store,
        pending,
        dispatch_fn=fake_dispatch,
    )

    assert calls[0]["channel"] == "feishu"
    assert calls[0]["message"] == "第1次卖出 10000 股"
    assert calls[0]["signal_id"] == "sell_1_20260422_093000"
    assert result["status"] == "sent"
    assert store.load_pending_signal() == {}
    assert store.load_execution_state()["sell_count"] == 1
    assert store.load_push_state()["last_dispatch_channel"] == "feishu"


def test_deliver_pending_signal_marks_failed_attempt_when_dispatch_fails(tmp_path):
    store = OlinStateStore(tmp_path)
    pending = {
        "signal_id": "sell_1_20260422_093000",
        "signal_key": "sell_1",
        "trade_date": "20260422",
        "action": "sell",
        "sequence": 1,
        "status": "pending",
        "text": "第1次卖出 10000 股",
        "attempts": 0,
    }
    store.save_pending_signal(pending)

    def fake_dispatch(_: dict) -> dict:
        return {"success": False, "error": "boom"}

    result = deliver_pending_signal(
        store,
        pending,
        dispatch_fn=fake_dispatch,
    )

    saved = store.load_pending_signal()
    assert result["status"] == "failed"
    assert saved["status"] == "failed"
    assert saved["attempts"] == 1
    assert saved["last_attempt_status"] == "failed"
    assert saved["last_error"] == "boom"


def test_deliver_pending_signal_is_noop_for_stale_non_matching_store_pending(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_pending_signal(
        {
            "signal_id": "buy_2_20260422_094000",
            "signal_key": "buy_2",
            "trade_date": "20260422",
            "action": "buy",
            "sequence": 2,
            "status": "pending",
            "text": "第2次买入 10000 股",
            "attempts": 0,
        }
    )
    stale_pending = {
        "signal_id": "sell_1_20260422_093000",
        "signal_key": "sell_1",
        "trade_date": "20260422",
        "action": "sell",
        "sequence": 1,
        "status": "pending",
        "text": "第1次卖出 10000 股",
        "attempts": 0,
    }
    called = {"count": 0}

    def fake_dispatch(_payload):
        called["count"] += 1
        return {"success": True}

    result = deliver_pending_signal(store, stale_pending, dispatch_fn=fake_dispatch)

    assert called["count"] == 0
    assert result["signal_id"] == "sell_1_20260422_093000"
    assert store.load_pending_signal()["signal_id"] == "buy_2_20260422_094000"


def test_deliver_pending_signal_is_noop_for_already_sent_pending(tmp_path):
    store = OlinStateStore(tmp_path)
    pending = {
        "signal_id": "sell_1_20260422_093000",
        "signal_key": "sell_1",
        "trade_date": "20260422",
        "action": "sell",
        "sequence": 1,
        "status": "sent",
        "text": "第1次卖出 10000 股",
        "attempts": 1,
    }
    called = {"count": 0}

    def fake_dispatch(_payload):
        called["count"] += 1
        return {"success": True}

    result = deliver_pending_signal(store, pending, dispatch_fn=fake_dispatch)

    assert called["count"] == 0
    assert result["status"] == "sent"


def test_deliver_pending_signal_is_idempotent_when_push_state_already_sent(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 0,
            "buy_count": 0,
            "actions": [],
            "active_signal": {
                "signal_id": "sell_1_20260422_093000",
                "signal_key": "sell_1",
                "action": "sell",
                "sequence": 1,
                "status": "pending",
                "created_at": "2026-04-22 09:30:00",
            },
            "last_signal_id": None,
            "last_signal_action": None,
            "last_signal_status": None,
            "last_signal_at": None,
        }
    )
    store.save_pending_signal(
        {
            "signal_id": "sell_1_20260422_093000",
            "signal_key": "sell_1",
            "trade_date": "20260422",
            "action": "sell",
            "sequence": 1,
            "status": "pending",
            "text": "第1次卖出 10000 股",
            "attempts": 0,
        }
    )
    store.save_push_state(
        {
            "last_pushed_signal_id": "sell_1_20260422_093000",
            "last_pushed_trade_date": "20260422",
            "last_pushed_at": "2026-04-22 09:30:05",
            "last_dispatch_channel": "feishu",
            "last_delivery_result": {"message_id": "om_xxx"},
        }
    )
    pending = {
        "signal_id": "sell_1_20260422_093000",
        "signal_key": "sell_1",
        "trade_date": "20260422",
        "action": "sell",
        "sequence": 1,
        "status": "pending",
        "text": "第1次卖出 10000 股",
        "attempts": 0,
    }
    called = {"count": 0}

    def fake_dispatch(_payload):
        called["count"] += 1
        return {"success": True}

    result = deliver_pending_signal(store, pending, dispatch_fn=fake_dispatch)

    execution_state = store.load_execution_state()
    assert called["count"] == 0
    assert result["status"] == "sent"
    assert result["dispatch_channel"] == "feishu"
    assert store.load_pending_signal() == {}
    assert execution_state["active_signal"] is None
    assert execution_state["sell_count"] == 1


def test_deliver_pending_signal_marks_failed_for_missing_trade_date_without_resetting_execution_state(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 1,
            "buy_count": 0,
            "actions": [{"signal_id": "older", "status": "sent"}],
            "active_signal": None,
            "last_signal_id": "older",
            "last_signal_action": "sell",
            "last_signal_status": "sent",
            "last_signal_at": "2026-04-22 09:20:00",
        }
    )
    pending = {
        "signal_id": "sell_2_legacy",
        "signal_key": "sell_2",
        "action": "sell",
        "sequence": 2,
        "status": "pending",
        "text": "legacy missing trade_date",
        "attempts": 0,
    }

    result = deliver_pending_signal(store, pending, dispatch_fn=lambda _payload: {"success": True})

    execution_state = store.load_execution_state()
    assert result["status"] == "failed"
    assert result["last_error"] == "invalid pending signal payload"
    assert execution_state["trade_date"] == "20260422"
    assert execution_state["sell_count"] == 1
    assert execution_state["actions"][0]["signal_id"] == "older"


def test_deliver_pending_signal_reconciles_actions_only_sent_signal_and_clears_stale_pending(tmp_path):
    store = OlinStateStore(tmp_path)
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
                    "text": "第1次卖出 10000 股",
                }
            ],
            "active_signal": {
                "signal_id": "sell_1_20260422_093000",
                "signal_key": "sell_1",
                "action": "sell",
                "sequence": 1,
                "status": "pending",
                "created_at": "2026-04-22 09:30:00",
            },
            "last_signal_id": None,
            "last_signal_action": None,
            "last_signal_status": None,
            "last_signal_at": None,
        }
    )
    store.save_pending_signal(
        {
            "signal_id": "sell_1_20260422_093000",
            "signal_key": "sell_1",
            "trade_date": "20260422",
            "action": "sell",
            "sequence": 1,
            "status": "pending",
            "text": "第1次卖出 10000 股",
            "attempts": 0,
        }
    )
    pending = {
        "signal_id": "sell_1_20260422_093000",
        "signal_key": "sell_1",
        "trade_date": "20260422",
        "action": "sell",
        "sequence": 1,
        "status": "pending",
        "text": "第1次卖出 10000 股",
        "attempts": 0,
    }
    called = {"count": 0}

    def fake_dispatch(_payload):
        called["count"] += 1
        return {"success": True}

    result = deliver_pending_signal(store, pending, dispatch_fn=fake_dispatch)

    execution_state = store.load_execution_state()
    assert called["count"] == 0
    assert result["status"] == "sent"
    assert store.load_pending_signal() == {}
    assert execution_state["active_signal"] is None
    assert execution_state["last_signal_id"] == "sell_1_20260422_093000"


def test_deliver_pending_signal_reconciles_missing_trade_date_when_push_state_matches(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 0,
            "buy_count": 0,
            "actions": [],
            "active_signal": {
                "signal_id": "sell_1_20260422_093000",
                "signal_key": "sell_1",
                "action": "sell",
                "sequence": 1,
                "status": "pending",
                "created_at": "2026-04-22 09:30:00",
            },
            "last_signal_id": None,
            "last_signal_action": None,
            "last_signal_status": None,
            "last_signal_at": None,
        }
    )
    store.save_pending_signal(
        {
            "signal_id": "sell_1_20260422_093000",
            "signal_key": "sell_1",
            "action": "sell",
            "sequence": 1,
            "status": "pending",
            "text": "第1次卖出 10000 股",
            "attempts": 0,
        }
    )
    store.save_push_state(
        {
            "last_pushed_signal_id": "sell_1_20260422_093000",
            "last_pushed_trade_date": "20260422",
            "last_pushed_at": "2026-04-22 09:30:05",
            "last_dispatch_channel": "feishu",
            "last_delivery_result": {"message_id": "om_xxx"},
        }
    )
    pending = {
        "signal_id": "sell_1_20260422_093000",
        "signal_key": "sell_1",
        "action": "sell",
        "sequence": 1,
        "status": "pending",
        "text": "第1次卖出 10000 股",
        "attempts": 0,
    }
    called = {"count": 0}

    def fake_dispatch(_payload):
        called["count"] += 1
        return {"success": True}

    result = deliver_pending_signal(store, pending, dispatch_fn=fake_dispatch)

    execution_state = store.load_execution_state()
    assert called["count"] == 0
    assert result["status"] == "sent"
    assert result["trade_date"] == "20260422"
    assert store.load_pending_signal() == {}
    assert execution_state["active_signal"] is None
    assert execution_state["sell_count"] == 1
    assert execution_state["last_signal_id"] == "sell_1_20260422_093000"


def test_run_runtime_cycle_stages_pending_signal_without_dispatch(tmp_path):
    store = OlinStateStore(tmp_path)

    result = run_runtime_cycle(
        store,
        tech_data={"summary_signal": "sell", "score": {"total": 20}},
        effective_trade_date="20260422",
        now=datetime(2026, 4, 22, 9, 30, 0),
        dispatch=False,
    )

    assert result["trade_date"] == "20260422"
    assert result["pending"]["signal_id"] == "sell_1_20260422_093000"
    assert result["result"]["status"] == "pending"
    assert store.load_pending_signal()["signal_id"] == "sell_1_20260422_093000"
    assert store.load_execution_state()["active_signal"]["signal_id"] == "sell_1_20260422_093000"

def test_run_runtime_cycle_dispatches_and_confirms_sent(tmp_path):
    store = OlinStateStore(tmp_path)
    calls = []

    def fake_dispatch(payload: dict) -> dict:
        calls.append(payload)
        return {"success": True, "platform": "feishu", "message_id": "om_test"}

    result = run_runtime_cycle(
        store,
        tech_data={"summary_signal": "sell", "score": {"total": 20}},
        effective_trade_date="20260422",
        now=datetime(2026, 4, 22, 9, 30, 0),
        dispatch=True,
        dispatch_fn=fake_dispatch,
    )

    assert len(calls) == 1
    assert calls[0]["signal_id"] == "sell_1_20260422_093000"
    assert result["pending"] == {}
    assert result["result"]["status"] == "sent"
    assert store.load_pending_signal() == {}
    assert store.load_execution_state()["sell_count"] == 1
    assert store.load_push_state()["last_pushed_signal_id"] == "sell_1_20260422_093000"


def test_cli_main_passes_explicit_dispatch_target(monkeypatch, tmp_path, capsys):
    from hermes_olin import __main__ as main_mod

    captured = {}

    def fake_run_runtime_cycle(store, **kwargs):
        captured["base_dir"] = str(store.base_dir)
        captured.update(kwargs)
        return {"ok": True, "chat_id": kwargs.get("chat_id"), "thread_id": kwargs.get("thread_id")}

    monkeypatch.setattr(main_mod, "run_runtime_cycle", fake_run_runtime_cycle)
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes_olin",
            "--base-dir",
            str(tmp_path),
            "--trade-date",
            "20260422",
            "--signal",
            "sell",
            "--score",
            "20",
            "--dispatch",
            "--channel",
            "feishu",
            "--chat-id",
            "oc_test",
            "--thread-id",
            "omt_test",
        ],
    )

    main_mod.main()
    out = json.loads(capsys.readouterr().out)

    assert captured["base_dir"] == str(tmp_path)
    assert captured["effective_trade_date"] == "20260422"
    assert captured["dispatch"] is True
    assert captured["channel"] == "feishu"
    assert captured["chat_id"] == "oc_test"
    assert captured["thread_id"] == "omt_test"
    assert out["chat_id"] == "oc_test"
    assert out["thread_id"] == "omt_test"


def test_cli_main_uses_env_dispatch_target(monkeypatch, tmp_path, capsys):
    from hermes_olin import __main__ as main_mod

    captured = {}

    def fake_run_runtime_cycle(store, **kwargs):
        captured["base_dir"] = str(store.base_dir)
        captured.update(kwargs)
        return {"ok": True, "chat_id": kwargs.get("chat_id"), "thread_id": kwargs.get("thread_id")}

    monkeypatch.setattr(main_mod, "run_runtime_cycle", fake_run_runtime_cycle)
    monkeypatch.setenv("HERMES_OLIN_CHANNEL", "feishu")
    monkeypatch.setenv("HERMES_OLIN_CHAT_ID", "oc_env")
    monkeypatch.setenv("HERMES_OLIN_THREAD_ID", "omt_env")
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes_olin",
            "--base-dir",
            str(tmp_path),
            "--trade-date",
            "20260422",
            "--signal",
            "sell",
            "--score",
            "20",
            "--dispatch",
        ],
    )

    main_mod.main()
    out = json.loads(capsys.readouterr().out)

    assert captured["base_dir"] == str(tmp_path)
    assert captured["dispatch"] is True
    assert captured["channel"] == "feishu"
    assert captured["chat_id"] == "oc_env"
    assert captured["thread_id"] == "omt_env"
    assert out["chat_id"] == "oc_env"
    assert out["thread_id"] == "omt_env"



def test_cli_main_supports_profile_override(monkeypatch, tmp_path, capsys):
    from hermes_olin import __main__ as main_mod

    captured = {}

    def fake_run_runtime_cycle(store, **kwargs):
        captured["base_dir"] = str(store.base_dir)
        captured["profile_id"] = store.profile.profile_id
        captured["symbol"] = store.profile.symbol
        captured["trade_unit"] = store.profile.trade_unit
        captured["max_trades"] = store.profile.max_trades
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(main_mod, "run_runtime_cycle", fake_run_runtime_cycle)
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes_olin",
            "--base-dir",
            str(tmp_path),
            "--trade-date",
            "20260501",
            "--profile-id",
            "demo-600519",
            "--symbol",
            "600519",
            "--trade-unit",
            "200",
            "--max-trades",
            "6",
        ],
    )

    main_mod.main()
    json.loads(capsys.readouterr().out)

    assert captured["base_dir"] == str(tmp_path)
    assert captured["profile_id"] == "demo-600519"
    assert captured["symbol"] == "600519"
    assert captured["trade_unit"] == 200
    assert captured["max_trades"] == 6


def test_cli_shared_build_runtime_store_keeps_olin_compatibility_for_legacy_mode(tmp_path):
    from hermes_t.cli_shared import build_runtime_store
    from hermes_olin.profile import DEFAULT_RUNTIME_PROFILE
    from hermes_olin.store import OlinStateStore, TradingStateStore

    default_store = build_runtime_store(
        base_dir=tmp_path,
        profile=DEFAULT_RUNTIME_PROFILE,
        prefer_legacy_olin_store=True,
    )
    generic_store = build_runtime_store(
        base_dir=tmp_path,
        profile=DEFAULT_RUNTIME_PROFILE,
        prefer_legacy_olin_store=False,
    )

    assert isinstance(default_store, OlinStateStore)
    assert isinstance(generic_store, TradingStateStore)
    assert type(generic_store).__name__ == "TradingStateStore"



def test_load_runtime_profiles_from_json_rejects_profile_missing_required_fields(tmp_path):
    from hermes_t.orchestrator import load_runtime_profiles_from_json

    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps([
            {
                "profile_id": "demo-1",
                "trade_unit": 200,
                "max_trades": 6,
            }
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="profile item 0 missing required fields: symbol"):
        load_runtime_profiles_from_json(config_path)



def test_load_runtime_profiles_from_json_rejects_non_list_payload(tmp_path):
    from hermes_t.orchestrator import load_runtime_profiles_from_json

    config_path = tmp_path / "profiles.json"
    config_path.write_text(
        json.dumps({"profile_id": "demo-1", "symbol": "600519"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="runtime profiles config must be a JSON list"):
        load_runtime_profiles_from_json(config_path)



def test_cli_main_defaults_base_dir_under_home_even_after_chdir(monkeypatch, tmp_path, capsys):
    from hermes_olin import __main__ as main_mod

    captured = {}
    home_dir = tmp_path / "home"
    cwd_dir = tmp_path / "workspace"
    home_dir.mkdir()
    cwd_dir.mkdir()

    def fake_run_runtime_cycle(store, **kwargs):
        captured["base_dir"] = str(store.base_dir)
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(main_mod, "run_runtime_cycle", fake_run_runtime_cycle)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(cwd_dir)
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes_olin",
            "--trade-date",
            "20260422",
            "--signal",
            "hold",
        ],
    )

    main_mod.main()
    json.loads(capsys.readouterr().out)

    assert captured["base_dir"] == str(home_dir / ".hermes_olin_runtime")

def test_cli_main_rejects_invalid_trade_date(monkeypatch, tmp_path, capsys):
    from hermes_olin import __main__ as main_mod

    called = {"ran": False}

    def fake_run_runtime_cycle(*args, **kwargs):
        called["ran"] = True
        return {}

    monkeypatch.setattr(main_mod, "run_runtime_cycle", fake_run_runtime_cycle)
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes_olin",
            "--base-dir",
            str(tmp_path),
            "--trade-date",
            "2026-04-22",
            "--signal",
            "sell",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main_mod.main()

    err = capsys.readouterr().err
    assert exc.value.code == 2
    assert "trade-date" in err
    assert "YYYYMMDD" in err
    assert called["ran"] is False


def test_recover_signal_runtime_clears_orphan_active_signal_without_pending(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 1,
            "buy_count": 0,
            "actions": [],
            "active_signal": {
                "signal_id": "sell_1_20260422_093000",
                "signal_key": "sell_1",
                "action": "sell",
                "sequence": 1,
                "status": "pending",
                "created_at": "2026-04-22 09:30:00",
            },
        }
    )

    result = recover_signal_runtime(
        store,
        trade_date="20260422",
        now=datetime(2026, 4, 22, 10, 0, 0),
    )

    assert result["pending_status"] is None
    assert "cleared_orphan_active_signal" in result["repairs"]
    assert store.load_execution_state()["active_signal"] is None


def test_recover_signal_runtime_expires_cross_day_pending_and_clears_active_signal(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 1,
            "buy_count": 0,
            "actions": [],
            "active_signal": {
                "signal_id": "sell_1_20260422_093000",
                "signal_key": "sell_1",
                "action": "sell",
                "sequence": 1,
                "status": "pending",
                "created_at": "2026-04-22 09:30:00",
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
            "status": "pending",
            "created_at": "2026-04-22 09:30:00",
            "text": "第1次卖出 10000 股",
            "attempts": 0,
        }
    )

    result = recover_signal_runtime(
        store,
        trade_date="20260423",
        now=datetime(2026, 4, 23, 9, 31, 0),
    )

    pending = store.load_pending_signal()
    assert result["pending_status"] == "expired_cross_day"
    assert "expired_cross_day_pending_signal" in result["repairs"]
    assert pending["status"] == "expired_cross_day"
    assert pending["escalation_reason"] == "cross_day_cleanup"
    assert store.load_execution_state()["active_signal"] is None
    assert store.read_jsonl("signal_send_history.jsonl")[-1]["event"] == "expired_cross_day"


def test_recover_signal_runtime_marks_timeout_pending(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 1,
            "buy_count": 0,
            "actions": [],
            "active_signal": {
                "signal_id": "sell_1_20260422_093000",
                "signal_key": "sell_1",
                "action": "sell",
                "sequence": 1,
                "status": "pending",
                "created_at": "2026-04-22 09:30:00",
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
            "status": "pending",
            "created_at": "2026-04-22 09:20:00",
            "text": "第1次卖出 10000 股",
            "attempts": 1,
        }
    )

    result = recover_signal_runtime(
        store,
        trade_date="20260422",
        now=datetime(2026, 4, 22, 9, 31, 0),
    )

    pending = store.load_pending_signal()
    assert result["pending_status"] == "timed_out"
    assert result["pending_age_seconds"] == 660
    assert "timed_out_pending_signal" in result["repairs"]
    assert pending["status"] == "timed_out"
    assert pending["timed_out"] is True
    assert pending["timeout_sec"] == 300
    assert store.load_execution_state()["active_signal"] is None


def test_recover_signal_runtime_marks_failed_exhausted_for_non_retryable_failed_signal(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 1,
            "buy_count": 0,
            "actions": [],
            "active_signal": {
                "signal_id": "sell_1_20260422_093000",
                "signal_key": "sell_1",
                "action": "sell",
                "sequence": 1,
                "status": "failed",
                "created_at": "2026-04-22 09:30:00",
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
            "text": "第1次卖出 10000 股",
            "attempts": 1,
            "last_error_retryable": False,
            "last_error_class": "AuthError",
        }
    )

    result = recover_signal_runtime(
        store,
        trade_date="20260422",
        now=datetime(2026, 4, 22, 9, 32, 0),
    )

    pending = store.load_pending_signal()
    assert result["pending_status"] == "failed_exhausted"
    assert "non_retryable_failed_pending_signal" in result["repairs"]
    assert pending["status"] == "failed_exhausted"
    assert pending["escalation_reason"] == "non_retryable_dispatch_error"
    assert pending["max_attempts"] == 3
    assert store.load_execution_state()["active_signal"] is None


def test_run_runtime_cycle_clears_cross_day_stale_pending_before_new_suggestion(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 1,
            "buy_count": 0,
            "actions": [],
            "active_signal": {
                "signal_id": "sell_1_20260422_093000",
                "signal_key": "sell_1",
                "trade_date": "20260422",
                "action": "sell",
                "sequence": 1,
                "status": "pending",
                "created_at": "2026-04-22 09:30:00",
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
            "status": "pending",
            "created_at": "2026-04-22 09:30:00",
            "text": "第1次卖出 10000 股",
            "attempts": 0,
        }
    )

    result = run_runtime_cycle(
        store,
        tech_data={"summary_signal": "sell", "score": {"total": 20}},
        effective_trade_date="20260423",
        dispatch=False,
        now=datetime(2026, 4, 23, 9, 31, 0),
    )

    assert result["recovery"]["pending_status"] == "expired_cross_day"
    assert result["suggestion"]["next_action"] == "sell"
    assert result["suggestion"]["sequence"] == 1
    assert result["pending"]["signal_id"] == "sell_1_20260423_093100"
    assert store.load_execution_state()["trade_date"] == "20260423"


def test_run_runtime_cycle_returns_timeout_recovery_without_restaging_same_cycle(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 1,
            "buy_count": 0,
            "actions": [],
            "active_signal": {
                "signal_id": "sell_1_20260422_092000",
                "signal_key": "sell_1",
                "trade_date": "20260422",
                "action": "sell",
                "sequence": 1,
                "status": "pending",
                "created_at": "2026-04-22 09:20:00",
            },
        }
    )
    store.save_pending_signal(
        {
            "signal_id": "sell_1_20260422_092000",
            "signal_key": "sell_1",
            "trade_date": "20260422",
            "action": "sell",
            "sequence": 1,
            "status": "pending",
            "created_at": "2026-04-22 09:20:00",
            "text": "第1次卖出 10000 股",
            "attempts": 1,
        }
    )

    result = run_runtime_cycle(
        store,
        tech_data={"summary_signal": "sell", "score": {"total": 20}},
        effective_trade_date="20260422",
        dispatch=False,
        now=datetime(2026, 4, 22, 9, 31, 0),
    )

    assert result["recovery"]["pending_status"] == "timed_out"
    assert result["suggestion"]["next_action"] == "hold"
    assert result["suggestion"]["reason"] == "recovery_blocked"
    assert result["pending"]["status"] == "timed_out"



def test_run_runtime_cycle_allows_new_candidate_after_terminal_pending_recovery(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_execution_state(
        {
            "trade_date": "20260422",
            "sell_count": 0,
            "buy_count": 0,
            "actions": [],
            "active_signal": {
                "signal_id": "buy_1_20260422_093100",
                "signal_key": "buy_1",
                "trade_date": "20260422",
                "action": "buy",
                "sequence": 1,
                "status": "failed",
                "created_at": "2026-04-22 09:31:00",
            },
        }
    )
    store.save_pending_signal(
        {
            "signal_id": "buy_1_20260422_093100",
            "signal_key": "buy_1",
            "trade_date": "20260422",
            "action": "buy",
            "sequence": 1,
            "status": "failed",
            "created_at": "2026-04-22 09:31:00",
            "text": "第1次买入 10000 股",
            "attempts": 1,
            "last_error_retryable": False,
            "last_error_class": "AuthError",
        }
    )

    first = run_runtime_cycle(
        store,
        tech_data={"summary_signal": "sell", "score": {"total": 20}},
        effective_trade_date="20260422",
        dispatch=False,
        now=datetime(2026, 4, 22, 9, 32, 0),
    )

    assert first["recovery"]["pending_status"] == "failed_exhausted"
    assert first["suggestion"]["reason"] == "recovery_blocked"
    assert first["pending"]["status"] == "failed_exhausted"

    second = run_runtime_cycle(
        store,
        tech_data={"summary_signal": "sell", "score": {"total": 20}},
        effective_trade_date="20260422",
        dispatch=False,
        now=datetime(2026, 4, 22, 9, 33, 0),
    )

    assert second["recovery"]["pending_status"] is None
    assert second["suggestion"]["next_action"] == "sell"
    assert second["suggestion"]["sequence"] == 1
    assert second["pending"]["signal_id"] == "sell_1_20260422_093300"
    assert second["pending"]["status"] == "pending"
    assert store.load_execution_state()["active_signal"]["signal_id"] == "sell_1_20260422_093300"



def test_run_runtime_cycle_retries_retryable_failed_pending_with_dispatch(tmp_path):
    store = OlinStateStore(tmp_path)
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
                "last_attempt_at": "2026-04-22 09:30:30",
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
            "text": "第1次卖出 10000 股",
            "attempts": 1,
            "last_attempt_at": "2026-04-22 09:30:30",
            "last_attempt_status": "failed",
            "last_error": "temporary gateway error",
            "last_error_retryable": True,
            "last_error_class": "RuntimeError",
        }
    )

    calls = []

    def fake_dispatch(payload):
        calls.append(payload)
        return {"success": True, "message_id": "msg_retry_1", "channel": "feishu"}

    result = run_runtime_cycle(
        store,
        tech_data={"summary_signal": "sell", "score": {"total": 20}},
        effective_trade_date="20260422",
        dispatch=True,
        dispatch_fn=fake_dispatch,
        now=datetime(2026, 4, 22, 9, 32, 0),
    )

    assert result["recovery"]["pending_status"] == "pending"
    assert len(calls) == 1
    assert calls[0]["signal_id"] == "sell_1_20260422_093000"
    assert result["result"]["status"] == "sent"
    assert result["pending"] == {}
    execution_state = store.load_execution_state()
    assert execution_state["active_signal"] is None
    assert execution_state["sell_count"] == 1


def test_arbitrate_candidate_blocks_duplicate_pending(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_pending_signal(
        {
            "signal_id": "sell_1_20260422_093000",
            "signal_key": "sell_1",
            "trade_date": "20260422",
            "action": "sell",
            "sequence": 1,
            "status": "pending",
            "created_at": "2026-04-22 09:30:00",
            "text": "第1次卖出 10000 股",
            "attempts": 0,
        }
    )
    result = arbitrate_candidate(
        store,
        {
            "next_action": "sell",
            "action": "sell",
            "sequence": 1,
            "signal": "sell",
            "text": "第1次卖出 10000 股",
            "trade_date": "20260422",
        },
        effective_trade_date="20260422",
        now=datetime(2026, 4, 22, 9, 31, 0),
    )

    assert result["decision"] == "blocked"
    assert result["reason"] == "duplicate_pending_signal"


def test_arbitrate_candidate_blocks_pending_active_for_different_signal(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_pending_signal(
        {
            "signal_id": "buy_1_20260422_093000",
            "signal_key": "buy_1",
            "trade_date": "20260422",
            "action": "buy",
            "sequence": 1,
            "status": "pending",
            "created_at": "2026-04-22 09:30:00",
            "text": "第1次买入 10000 股",
            "attempts": 0,
        }
    )
    result = arbitrate_candidate(
        store,
        {
            "next_action": "sell",
            "action": "sell",
            "sequence": 1,
            "signal": "sell",
            "text": "第1次卖出 10000 股",
            "trade_date": "20260422",
        },
        effective_trade_date="20260422",
        now=datetime(2026, 4, 22, 9, 31, 0),
    )

    assert result["decision"] == "blocked"
    assert result["reason"] == "another_pending_signal_active"


def test_arbitrate_candidate_blocks_duplicate_sent_summary(tmp_path):
    store = OlinStateStore(tmp_path)
    store.save_push_state(
        {
            "last_pushed_signal": "sell_1",
            "last_pushed_signal_id": "sell_1_20260422_093000",
            "last_pushed_trade_date": "20260422",
            "last_pushed_at": "2026-04-22 09:30:05",
        }
    )
    result = arbitrate_candidate(
        store,
        {
            "next_action": "sell",
            "action": "sell",
            "sequence": 1,
            "signal": "sell",
            "text": "第1次卖出 10000 股",
            "trade_date": "20260422",
        },
        effective_trade_date="20260422",
        now=datetime(2026, 4, 22, 9, 31, 0),
    )

    assert result["decision"] == "blocked"
    assert result["reason"] == "duplicate_sent_signal"


def test_arbitrate_candidate_blocks_duplicate_execution(tmp_path):
    store = OlinStateStore(tmp_path)
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
                    "text": "第1次卖出 10000 股",
                }
            ],
            "active_signal": None,
            "last_signal_id": "sell_1_20260422_093000",
            "last_signal_action": "sell",
            "last_signal_status": "sent",
            "last_signal_at": "2026-04-22 09:30:05",
        }
    )
    result = arbitrate_candidate(
        store,
        {
            "next_action": "sell",
            "action": "sell",
            "sequence": 1,
            "signal": "sell",
            "text": "第1次卖出 10000 股",
            "trade_date": "20260422",
        },
        effective_trade_date="20260422",
        now=datetime(2026, 4, 22, 9, 31, 0),
    )

    assert result["decision"] == "blocked"
    assert result["reason"] == "duplicate_execution_signal"


def test_arbitrate_candidate_blocks_retry_cooldown_active(tmp_path, monkeypatch):
    store = OlinStateStore(tmp_path)
    store.save_pending_signal(
        {
            "signal_id": "sell_1_20260422_093000",
            "signal_key": "sell_1",
            "trade_date": "20260422",
            "action": "sell",
            "sequence": 1,
            "status": "failed",
            "created_at": "2026-04-22 09:30:00",
            "text": "第1次卖出 10000 股",
            "attempts": 1,
            "last_attempt_at": "2026-04-22 09:30:40",
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
            "pending_retry_cooldown_sec": 120,
        },
    )
    result = arbitrate_candidate(
        store,
        {
            "next_action": "sell",
            "action": "sell",
            "sequence": 1,
            "signal": "sell",
            "text": "第1次卖出 10000 股",
            "trade_date": "20260422",
        },
        effective_trade_date="20260422",
        now=datetime(2026, 4, 22, 9, 31, 0),
    )

    assert result["decision"] == "blocked"
    assert result["reason"] == "retry_cooldown_active"
    assert result["cooldown_remaining_sec"] == 100


def test_arbitrate_candidate_allows_retry_ready_and_reuses_failed_pending(tmp_path, monkeypatch):
    store = OlinStateStore(tmp_path)
    store.save_pending_signal(
        {
            "signal_id": "sell_1_20260422_093000",
            "signal_key": "sell_1",
            "trade_date": "20260422",
            "action": "sell",
            "sequence": 1,
            "status": "failed",
            "created_at": "2026-04-22 09:30:00",
            "text": "第1次卖出 10000 股",
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
        },
    )
    result = arbitrate_candidate(
        store,
        {
            "next_action": "sell",
            "action": "sell",
            "sequence": 1,
            "signal": "sell",
            "text": "第1次卖出 10000 股",
            "trade_date": "20260422",
        },
        effective_trade_date="20260422",
        now=datetime(2026, 4, 22, 9, 31, 0),
    )

    assert result["decision"] == "reuse_failed_pending"
    assert result["reason"] == "retry_ready_reuse_failed_pending"
    assert result["pending"]["signal_id"] == "sell_1_20260422_093000"


def test_arbitrate_candidate_blocks_freshness_failure(tmp_path, monkeypatch):
    store = OlinStateStore(tmp_path)
    import hermes_olin.runtime as runtime_mod

    monkeypatch.setattr(
        runtime_mod,
        "load_runtime_policy",
        lambda: {
            "pending_signal_timeout_sec": 300,
            "pending_signal_max_attempts": 3,
            "pending_retry_cooldown_sec": 30,
            "candidate_freshness_limit_sec": 60,
        },
    )
    result = arbitrate_candidate(
        store,
        {
            "next_action": "sell",
            "action": "sell",
            "sequence": 1,
            "signal": "sell",
            "text": "第1次卖出 10000 股",
            "trade_date": "20260422",
            "signal_time": "2026-04-22 09:28:00",
        },
        effective_trade_date="20260422",
        now=datetime(2026, 4, 22, 9, 31, 0),
    )

    assert result["decision"] == "blocked"
    assert result["reason"] == "candidate_stale"

def test_run_runtime_cycle_blocks_duplicate_sent_candidate_without_restaging(tmp_path):
    store = OlinStateStore(tmp_path)
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
                    "text": "第1次卖出 10000 股",
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
    assert result["pending"] == {}
    assert store.load_pending_signal() == {}
    assert store.load_execution_state()["active_signal"] is None


def test_run_runtime_cycle_reuses_failed_pending_after_cooldown_instead_of_restaging(tmp_path, monkeypatch):
    store = OlinStateStore(tmp_path)
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
            "text": "第1次卖出 10000 股",
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
    assert result["result"]["signal_id"] == "sell_1_20260422_093000"
    assert result["result"]["status"] == "failed"
    assert result["pending"]["signal_id"] == "sell_1_20260422_093000"
    assert store.load_pending_signal()["signal_id"] == "sell_1_20260422_093000"
