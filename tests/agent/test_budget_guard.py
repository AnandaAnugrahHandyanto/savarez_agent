import pytest

from agent.budget_guard import (
    BudgetCaps,
    BudgetExceededError,
    check_budget_caps,
    load_budget_caps,
)


def test_load_budget_caps_noop_without_config():
    caps = load_budget_caps({})
    assert caps.enabled is False
    check_budget_caps(current_spend_usd=999.0, caps=caps)


def test_load_budget_caps_ignores_invalid_or_nonpositive_values():
    caps = load_budget_caps({"budget": {"daily_usd_cap": "nope", "monthly_usd_cap": 0}})
    assert caps.enabled is False


def test_daily_cap_blocks_when_estimated_spend_reaches_cap():
    with pytest.raises(BudgetExceededError, match="daily cap"):
        check_budget_caps(current_spend_usd=5.0, caps=BudgetCaps(daily_usd_cap=5.0))


def test_monthly_cap_blocks_when_estimated_spend_reaches_cap():
    with pytest.raises(BudgetExceededError, match="monthly cap"):
        check_budget_caps(current_spend_usd=50.25, caps=BudgetCaps(monthly_usd_cap=50.0))


def test_spend_below_cap_allows_next_call():
    check_budget_caps(current_spend_usd=4.99, caps=BudgetCaps(daily_usd_cap=5.0, monthly_usd_cap=50.0))
