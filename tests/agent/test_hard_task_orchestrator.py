"""Tests for hard-task orchestration prompt generation."""

from agent.hard_task_orchestrator import build_orchestration_prompt, slugify_task


def test_slugify_task_produces_stable_plan_slug():
    assert slugify_task("Fix OAuth refresh + webhook retries!!!") == "fix-oauth-refresh-webhook-retries"


def test_build_orchestration_prompt_contains_required_plan_first_contract():
    prompt = build_orchestration_prompt("Refactor gateway routing for WhatsApp and Discord")

    assert "Refactor gateway routing for WhatsApp and Discord" in prompt
    assert ".hermes/plans/refactor-gateway-routing-for-whatsapp-and-discord.md" in prompt
    assert "Do not implement before the plan document exists" in prompt
    assert "acceptance criteria" in prompt.lower()
    assert "rollback plan" in prompt.lower()


def test_build_orchestration_prompt_documents_model_and_worker_policy():
    prompt = build_orchestration_prompt("Implement a multi-file cache migration")

    assert "claude-opus-4-7[1m]" in prompt
    assert "claude-sonnet-4-6" in prompt
    assert "claude-sonnet-4-6[1m]" in prompt
    assert "gpt-5.5" in prompt
    assert "checkpoint" in prompt.lower()
    assert "monitor" in prompt.lower()
