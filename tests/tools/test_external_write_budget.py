"""Tests for the external-write budget ledger prototype."""

import pytest

from tools.external_write_budget import (
    EXTERNAL_WRITE_CATEGORIES,
    SURFACE_TAXONOMY,
    ExternalWriteBudgetError,
    ExternalWriteBudgetLedger,
    category_for_surface,
)


def test_taxonomy_covers_initial_required_policy_categories():
    assert set(SURFACE_TAXONOMY.values()).issubset(set(EXTERNAL_WRITE_CATEGORIES))

    assert {
        "public_send",
        "cron_mutation",
        "notion_write",
        "profile_skill_mutation",
        "profile_memory_mutation",
        "filesystem_durable_write",
        "paid_api",
        "deploy_push_merge",
    }.issubset(set(EXTERNAL_WRITE_CATEGORIES))

    assert SURFACE_TAXONOMY["send_message:send"] == "public_send"
    assert SURFACE_TAXONOMY["cronjob:create"] == "cron_mutation"
    assert SURFACE_TAXONOMY["notion:page_write"] == "notion_write"
    assert SURFACE_TAXONOMY["skill_manage:patch"] == "profile_skill_mutation"
    assert SURFACE_TAXONOMY["memory:add"] == "profile_memory_mutation"
    assert SURFACE_TAXONOMY["write_file"] == "filesystem_durable_write"
    assert SURFACE_TAXONOMY["paid_api:call"] == "paid_api"
    assert SURFACE_TAXONOMY["git:push"] == "deploy_push_merge"


def test_zero_budget_blocks_send_message_public_send_surface():
    ledger = ExternalWriteBudgetLedger(limits={"public_send": 0})

    decision = ledger.check_surface_write("send_message:send", target="telegram:-100123:9")
    assert decision.allowed is False
    assert decision.category == "public_send"
    assert decision.used == 0
    assert decision.limit == 0
    assert decision.target_digest is not None
    assert "telegram:-100123:9" not in repr(decision)

    with pytest.raises(ExternalWriteBudgetError, match="public_send"):
        ledger.record_surface_write("send_message:send", target="telegram:-100123:9")
    assert ledger.counts.get("public_send", 0) == 0


def test_n_budget_caps_send_message_after_exact_limit():
    ledger = ExternalWriteBudgetLedger(limits={"public_send": 2})

    first = ledger.record_surface_write("send_message:send", target="discord:#ops")
    second = ledger.record_surface_write("send_message:send", target="discord:#ops")

    assert first.allowed is True
    assert first.used == 1
    assert second.allowed is True
    assert second.used == 2
    assert ledger.snapshot["public_send"] == {"used": 2, "limit": 2}

    with pytest.raises(ExternalWriteBudgetError, match="used 2/2"):
        ledger.record_surface_write("send_message:send", target="discord:#ops")
    assert ledger.counts["public_send"] == 2


def test_zero_budget_blocks_cron_mutation_surface():
    ledger = ExternalWriteBudgetLedger(limits={"cron_mutation": 0})

    decision = ledger.check_surface_write("cronjob:create", target="daily briefing")
    assert decision.allowed is False
    assert decision.category == "cron_mutation"
    assert decision.surface == "cronjob:create"

    with pytest.raises(ExternalWriteBudgetError, match="cron_mutation"):
        ledger.record_surface_write("cronjob:create", target="daily briefing")


def test_n_budget_caps_cron_mutation_after_exact_limit():
    ledger = ExternalWriteBudgetLedger(limits={"cron_mutation": 1})

    allowed = ledger.record_surface_write("cronjob:update", target="job-123")
    assert allowed.used == 1

    blocked = ledger.check_surface_write("cronjob:remove", target="job-123")
    assert blocked.allowed is False
    assert blocked.used == 1
    assert blocked.limit == 1


def test_unknown_surface_and_category_fail_closed():
    with pytest.raises(ValueError, match="Unknown external-write surface"):
        category_for_surface("unknown:write")

    with pytest.raises(ValueError, match="Unknown external-write budget categories"):
        ExternalWriteBudgetLedger(limits={"unknown_category": 1})
