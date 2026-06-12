"""Deterministic /goal standard-mode policy helpers.

The helpers in this module are intentionally side-effect free so CLI, gateway,
TUI, prompt-building, and tests can share one compact contract without calling a
model or touching the filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

GoalBand = Literal["chat", "verified", "operational", "workpack"]


@dataclass(frozen=True)
class GoalPolicyDecision:
    band: GoalBand
    requires_direct_evidence: bool = False
    requires_trust_sweep: bool = False
    requires_workpack: bool = False
    reason: str = ""


_WORKPACK_TERMS = {
    "supergoal",
    "workpack",
    "roadmap",
    "hintergrund",
    "background",
    "autonom",
    "autonomous",
    "multi-phase",
    "mehrphas",
    "alle slices",
    "product slices",
}

_OPERATIONAL_TERMS = {
    "cleanup",
    "clean up",
    "bereinige",
    "aufräumen",
    "prüfe",
    "check",
    "audit",
    "verifiziere",
    "verify",
    "restarte",
    "restart",
    "rate limit",
    "ratelimit",
    "blocked",
    "blocker",
    "kanban",
    "cron",
    "cronjob",
    "gateway",
    "dispatcher",
    "global",
    "alle",
    "alles",
    "stale",
    "altlast",
    "superseded",
}

_VERIFIED_ACTION_TERMS = {
    "baue",
    "build",
    "implement",
    "implementiere",
    "fix",
    "repariere",
    "teste",
    "test",
    "run",
    "deploy",
    "install",
    "configure",
    "konfiguriere",
    "erstelle",
    "create",
    "write",
}

_SIMPLE_QUESTION_STARTS = (
    "was ist ",
    "what is ",
    "erkläre ",
    "explain ",
    "wie findest ",
    "what do you think",
)


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def classify_request(text: str) -> GoalPolicyDecision:
    """Classify user text into the standard Supergoal execution band."""

    lowered = (text or "").strip().lower()
    if not lowered:
        return GoalPolicyDecision("chat", reason="empty request")

    simple_question = lowered.startswith(_SIMPLE_QUESTION_STARTS) or lowered.endswith("?")

    if _contains_any(lowered, _WORKPACK_TERMS):
        return GoalPolicyDecision(
            "workpack",
            requires_direct_evidence=True,
            requires_trust_sweep=True,
            requires_workpack=True,
            reason="broad/background/supergoal wording",
        )

    if simple_question and not _contains_any(
        lowered,
        _VERIFIED_ACTION_TERMS | {"cleanup", "prüfe", "check", "audit", "restarte", "restart"},
    ):
        return GoalPolicyDecision("chat", reason="simple question")

    if _contains_any(lowered, _OPERATIONAL_TERMS):
        return GoalPolicyDecision(
            "operational",
            requires_direct_evidence=True,
            requires_trust_sweep=True,
            reason="operational cleanup or system-state wording",
        )

    if _contains_any(lowered, _VERIFIED_ACTION_TERMS):
        return GoalPolicyDecision(
            "verified",
            requires_direct_evidence=True,
            reason="action or implementation wording",
        )

    if simple_question:
        return GoalPolicyDecision("chat", reason="simple question")
    return GoalPolicyDecision("chat", reason="default chat")


def render_standard_contract(decision: GoalPolicyDecision) -> str:
    """Return the compact completion contract for non-chat goal work."""

    if decision.band == "chat":
        return ""
    lines = [
        "Supergoal standard: before reporting DONE, verify the direct target scope with concrete evidence/readback.",
    ]
    if decision.requires_trust_sweep:
        lines.append(
            "For operational cleanup/system-state work, also verify adjacent/global visible state, search for stale/conflicting/superseded leftovers, and report conditional/BLOCKED instead of DONE if visible leftovers remain."
        )
    if decision.requires_workpack:
        lines.append(
            "For broad or multi-phase work, create or update a workpack/STATE handoff unless the user explicitly asks for plan-only chat."
        )
    return "\n".join(lines)


def render_standard_notice(decision: GoalPolicyDecision) -> str:
    """Return the one-line user-visible notice for standard-mode goals."""

    if decision.band == "chat":
        return ""
    base = "Supergoal gates: direct evidence + adjacent/global trust sweep before DONE."
    if decision.requires_workpack:
        return f"{base} Workpack recommended for this broad goal."
    if decision.requires_trust_sweep:
        return base
    return ""


def should_enable_standard_mode(config: dict[str, Any] | None) -> bool:
    goals_cfg = ((config or {}).get("goals") or {}) if isinstance(config, dict) else {}
    standard = goals_cfg.get("standard_mode") or {}
    if isinstance(standard, dict) and "enabled" in standard:
        return bool(standard.get("enabled"))
    return True


def render_notice_for_goal(goal: str, config: dict[str, Any] | None = None) -> str:
    """Return the standard-mode notice for a goal, honoring config when supplied."""

    if config is not None and not should_enable_standard_mode(config):
        return ""
    return render_standard_notice(classify_request(goal))


def standard_subgoals_for(goal: str) -> list[str]:
    """Seed explicit criteria for non-chat goal work."""

    decision = classify_request(goal)
    if decision.band == "chat":
        return []
    subgoals = ["Direct evidence/readback exists for the target scope before DONE."]
    if decision.requires_trust_sweep:
        subgoals.extend(
            [
                "The adjacent/global visible state was checked for stale, conflicting, or superseded leftovers before DONE.",
                "If visible leftovers remain, report conditional/BLOCKED or clean them first instead of claiming DONE.",
            ]
        )
    if decision.requires_workpack:
        subgoals.append(
            "Workpack/STATE handoff exists for broad or multi-phase work, or the response explicitly says why it is unnecessary."
        )
    return subgoals


def augment_goal_with_standard_contract(goal: str) -> str:
    """Append the standard contract to goal text when policy says it applies."""

    contract = render_standard_contract(classify_request(goal))
    if not contract:
        return goal
    return f"{goal}\n\nStandard completion contract:\n{contract}"
