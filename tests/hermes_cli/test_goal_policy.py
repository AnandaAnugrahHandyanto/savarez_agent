from __future__ import annotations

from hermes_cli.goal_policy import (
    augment_goal_with_standard_contract,
    classify_request,
    render_notice_for_goal,
    render_standard_contract,
    render_standard_notice,
    should_enable_standard_mode,
    standard_subgoals_for,
)


def test_simple_question_is_chat_without_contract():
    decision = classify_request("was ist kanban?")
    assert decision.band == "chat"
    assert render_standard_contract(decision) == ""
    assert standard_subgoals_for("was ist kanban?") == []


def test_operational_cleanup_requires_trust_sweep():
    decision = classify_request("prüfe und restarte alle cronjobs die ins rate limit gelaufen sind")
    assert decision.band == "operational"
    assert decision.requires_direct_evidence is True
    assert decision.requires_trust_sweep is True
    contract = render_standard_contract(decision)
    assert "adjacent/global visible state" in contract
    assert "conditional/BLOCKED" in contract


def test_workpack_goal_recommends_workpack():
    decision = classify_request("supergoal das bis zum ende")
    assert decision.band == "workpack"
    assert decision.requires_workpack is True
    notice = render_standard_notice(decision)
    assert "Workpack recommended" in notice


def test_verified_build_requires_direct_evidence_but_not_trust_sweep():
    decision = classify_request("implement the parser")
    assert decision.band == "verified"
    assert decision.requires_direct_evidence is True
    assert decision.requires_trust_sweep is False
    assert standard_subgoals_for("implement the parser") == [
        "Direct evidence/readback exists for the target scope before DONE."
    ]


def test_standard_subgoals_spell_out_visible_leftovers():
    subgoals = standard_subgoals_for("cleanup stale kanban blockers")
    assert any("Direct evidence" in item for item in subgoals)
    assert any("adjacent/global visible state" in item for item in subgoals)
    assert any("visible leftovers remain" in item for item in subgoals)


def test_config_gate_disables_notice():
    config = {"goals": {"standard_mode": {"enabled": False}}}
    assert should_enable_standard_mode(config) is False
    assert render_notice_for_goal("cleanup stale kanban blockers", config) == ""
    assert should_enable_standard_mode({}) is True


def test_augment_goal_appends_contract_only_when_needed():
    assert augment_goal_with_standard_contract("was ist kanban?") == "was ist kanban?"
    augmented = augment_goal_with_standard_contract("restart rate limit cronjobs")
    assert "Standard completion contract" in augmented
    assert "adjacent/global visible state" in augmented
