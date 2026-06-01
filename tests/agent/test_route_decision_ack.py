"""Regression tests for route-decision continuations."""

from __future__ import annotations

from agent.agent_runtime_helpers import looks_like_codex_intermediate_ack


class _Agent:
    @staticmethod
    def _strip_think_blocks(text: str) -> str:
        return text


def test_route_decision_delegate_line_continues_without_tools():
    assert looks_like_codex_intermediate_ack(
        _Agent(),
        "Use GPT-5.5 xhigh for this legal drafting task.",
        (
            "Routing Decision: Vitatide legal/policy drafting -> "
            "hermes-orchestrator + vitatide-aldnoah-operations -> "
            "delegate(xhigh legal drafting/review lane) -> "
            "architecture_design/gpt-5.5-xhigh"
        ),
        [],
    )


def test_front_door_route_decision_alone_can_end_inline():
    assert not looks_like_codex_intermediate_ack(
        _Agent(),
        "What model are you using?",
        (
            "Routing Decision: model status -> orchestrator -> "
            "inline(read-only) -> front_door/gpt-5.5-high"
        ),
        [],
    )

