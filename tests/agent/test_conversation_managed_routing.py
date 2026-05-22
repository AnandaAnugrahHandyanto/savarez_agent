from __future__ import annotations

from types import SimpleNamespace

from agent import conversation_loop
from agent.task_card import TaskCard


def _write_managed_agents_yaml(tmp_path):
    path = tmp_path / "configs" / "managed_agents"
    path.mkdir(parents=True)
    (path / "agents.yaml").write_text(
        """
version: "2026-05-21"
agents:
  - agent_id: claude
    name: Claude Code
    role: lead_implementer
    tools: [file, terminal, git]
    permission: ask
    can_delegate: false
    capabilities: [code_edit]
    risk_allowed: [R1, R2, R3]
  - agent_id: codex
    name: Codex
    role: principal_engineer
    tools: [file]
    permission: read_only
    can_delegate: false
    capabilities: [code_review]
    risk_allowed: [R0, R1, R2, R3, R4]
routing:
  default_route:
    mode: review_only
    agents: [codex]
    reason: unresolved_route_requires_review
  fallback_route:
    mode: review_only
    agents: [codex]
    reason: unresolved_route_requires_review
  rules:
    - id: standard_feature
      when:
        task_category: feature
        risk_level: R2
      mode: single_agent
      agents: [claude]
      reason: default_feature_implementation
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_route_task_prefers_managed_agents_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_managed_agents_yaml(tmp_path)
    card = TaskCard.create("implement feature", task_category="feature")

    decision = conversation_loop._route_task(SimpleNamespace(), card, "implement feature")

    assert decision.mode == "single_agent"
    assert decision.agents == ["claude"]
    assert decision.routing_basis == ["rule:standard_feature", "risk:R2"]
    assert card.risk_level == "R2"


def test_route_task_falls_back_to_legacy_router_without_managed_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(conversation_loop, "_managed_agents_config_path", lambda: None)
    card = TaskCard.create("hello", task_category="other")
    legacy_decision = SimpleNamespace(
        mode="self_execute",
        agents=[],
        reason="legacy",
        routing_basis=["legacy"],
    )
    agent = SimpleNamespace(
        _agent_router=SimpleNamespace(route=lambda **_kwargs: legacy_decision)
    )

    decision = conversation_loop._route_task(agent, card, "hello")

    assert decision is legacy_decision
