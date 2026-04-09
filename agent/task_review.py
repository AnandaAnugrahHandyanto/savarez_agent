"""Structured review engine for completed tasks.

Analyzes a task-completion payload and produces a typed review result
indicating what follow-up actions (memory save, skill save) are warranted.
The actual writeback is handled separately — this module only decides *what*
to review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskReviewResult:
    """Typed, immutable result from reviewing a completed task.

    Attributes:
        should_review_memory: Whether the task warrants a memory review pass.
        should_review_skills: Whether the task warrants a skill review pass.
        review_reasons: Human-readable reasons explaining why review is needed.
        payload: The original task-completion payload (kept for downstream use).
    """

    should_review_memory: bool
    should_review_skills: bool
    review_reasons: List[str]
    payload: Dict[str, Any]


def review_completed_task(task_payload: Dict[str, Any]) -> TaskReviewResult:
    """Analyze a completed-task payload and return a structured review result.

    This is a pure function — it reads the payload and produces a decision
    without side effects.  The caller decides what to do with the result.

    Args:
        task_payload: Dict produced by ``AIAgent._build_task_completion_payload``.

    Returns:
        A :class:`TaskReviewResult` with review recommendations.

    Raises:
        ValueError: If ``task_payload`` is ``None`` or missing required keys.
    """
    if not task_payload:
        raise ValueError("task_payload must be a non-empty dict")

    trigger_reasons: List[str] = task_payload.get("trigger_reasons") or []
    tools_used: List[str] = task_payload.get("tools_used") or []

    reasons: List[str] = []
    should_memory = False
    should_skills = False

    # Explicit memory request from user always triggers memory review.
    if "explicit_memory_request" in trigger_reasons:
        should_memory = True
        reasons.append("user explicitly asked to remember/save")

    # Tool use indicates a non-trivial task — worth checking for skill patterns
    # and also for memory-worthy context (user preferences revealed during work).
    if "tool_used" in trigger_reasons:
        should_skills = True
        reasons.append("tools were used during the task")

        # Memory-specific tools hint that the user interacted with their
        # knowledge store — review for additional memory-worthy content.
        _memory_tools = {"memory", "memory_manage", "user_profile"}
        if _memory_tools & set(tools_used):
            should_memory = True
            reasons.append("memory/profile tools were invoked")

    # If we have no reasons at all, nothing to review.
    if not reasons:
        return TaskReviewResult(
            should_review_memory=False,
            should_review_skills=False,
            review_reasons=[],
            payload=task_payload,
        )

    return TaskReviewResult(
        should_review_memory=should_memory,
        should_review_skills=should_skills,
        review_reasons=reasons,
        payload=task_payload,
    )
